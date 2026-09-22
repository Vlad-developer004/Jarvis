from __future__ import annotations
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import ssl
from email.header import decode_header
from html import unescape
from email.message import EmailMessage
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('mail')
from email.parser import BytesParser
from email.policy import default as email_policy
from pathlib import Path
from config_pack.config import get_settings_path, get_secrets_path

# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\jarvis_settings.json)
# — this used to be a project-relative 'data/jarvis_settings.json' instead, a
# different file that other settings readers never saw and that a rebuild/
# reinstall silently wipes (the bundled data/ folder gets overwritten).
_SETTINGS_PATH = Path(get_settings_path())

def _update_env_var(key: str, value: str):
    """Safely update or add a variable in the secrets file. Uses
    get_secrets_path() — the same file llm_processor._load_api_key() and the
    startup loader read from (see config_pack.config.get_secrets_path's
    docstring) — instead of an ad-hoc '.env' path, so a saved mail password
    is actually found again on the next run."""
    try:
        env_path = Path(get_secrets_path())
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding='utf-8').splitlines()
        
        found = False
        new_line = f'{key}="{value}"'
        for i, line in enumerate(lines):
            if line.strip().startswith(f'{key}='):
                lines[i] = new_line
                found = True
                break
        
        if not found:
            if lines and lines[-1].strip():
                lines.append('')
            lines.append(new_line)
            
        env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        # Also update os.environ for the current session
        os.environ[key] = value
    except Exception as e:
        _log.error('Error updating .env: %s', e, exc_info=True)
def _load_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}
def _is_gmail_address(email: str) -> bool:
    e = email.lower().strip()
    return e.endswith('@gmail.com') or e.endswith('@googlemail.com')
def _apply_gmail_defaults(cfg: dict) -> dict:
    if not _is_gmail_address(cfg.get('email', '')):
        return cfg
    out = dict(cfg)
    if not (out.get('imap_host') or '').strip():
        out['imap_host'] = 'imap.gmail.com'
    if not (out.get('smtp_host') or '').strip():
        out['smtp_host'] = 'smtp.gmail.com'
    out['imap_port'] = int(out.get('imap_port') or 993)
    out['smtp_port'] = int(out.get('smtp_port') or 587)
    return out

# Where each major provider lets a user generate an app-specific password
# (needed once 2FA/two-step verification is on — a normal account password
# won't authenticate over IMAP/SMTP for any of them). Matched by domain
# suffix against the typed email address so the UI can point at the right
# page instead of only ever linking to Google's.
APP_PASSWORD_PAGES: dict[str, str] = {
    'gmail.com': 'https://myaccount.google.com/apppasswords',
    'googlemail.com': 'https://myaccount.google.com/apppasswords',
    'yandex.ru': 'https://id.yandex.ru/security/app-passwords',
    'yandex.com': 'https://id.yandex.ru/security/app-passwords',
    'ya.ru': 'https://id.yandex.ru/security/app-passwords',
    'mail.ru': 'https://account.mail.ru/user/2-step-auth/passwords/',
    'bk.ru': 'https://account.mail.ru/user/2-step-auth/passwords/',
    'inbox.ru': 'https://account.mail.ru/user/2-step-auth/passwords/',
    'list.ru': 'https://account.mail.ru/user/2-step-auth/passwords/',
    'outlook.com': 'https://account.live.com/proofs/AppPassword',
    'hotmail.com': 'https://account.live.com/proofs/AppPassword',
    'live.com': 'https://account.live.com/proofs/AppPassword',
    'icloud.com': 'https://appleid.apple.com/account/manage',
}
_DEFAULT_APP_PASSWORD_PAGE = 'https://support.google.com/accounts/answer/185833'

def app_password_url_for_email(email: str) -> str:
    """The app-password creation page for `email`'s provider, or a generic
    explainer link if the domain isn't recognized."""
    e = (email or '').strip().lower()
    domain = e.rsplit('@', 1)[-1] if '@' in e else ''
    return APP_PASSWORD_PAGES.get(domain, _DEFAULT_APP_PASSWORD_PAGE)

def get_resolved_mail_config() -> dict | None:
    s = _load_settings()
    acct = s.get('mail_account')
    if not isinstance(acct, dict):
        acct = {}
        
    # Security: Check for password in JSON and migrate to .env if found
    json_pass = acct.get('password', '').strip()
    env_pass = os.environ.get('JARVIS_IMAP_PASS', '').strip()
    
    password = env_pass
    if json_pass and not env_pass:
        # Auto-migrate
        _update_env_var('JARVIS_IMAP_PASS', json_pass)
        password = json_pass
        # Scrub from JSON
        acct['password'] = ""
        s['mail_account'] = acct
        try:
            _SETTINGS_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            # Password stays in the JSON on disk in plaintext if this fails — must be visible.
            _log.error('failed to scrub migrated password from %s: %s', _SETTINGS_PATH, e, exc_info=True)
    elif json_pass and env_pass:
        # Already migrated, just scrub from JSON
        acct['password'] = ""
        s['mail_account'] = acct
        try:
            _SETTINGS_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            _log.error('failed to scrub leftover password from %s: %s', _SETTINGS_PATH, e, exc_info=True)

    email = (acct.get('email') or os.environ.get('JARVIS_IMAP_USER', '')).strip()
    imap_host = (acct.get('imap_host') or os.environ.get('JARVIS_IMAP_HOST', '')).strip()
    smtp_host = (acct.get('smtp_host') or os.environ.get('JARVIS_SMTP_HOST', '')).strip()
    
    try:
        imap_port = int(acct.get('imap_port') or os.environ.get('JARVIS_IMAP_PORT', '993') or 993)
    except ValueError:
        imap_port = 993
    try:
        smtp_port = int(acct.get('smtp_port') or os.environ.get('JARVIS_SMTP_PORT', '587') or 587)
    except ValueError:
        smtp_port = 587
        
    mailbox = (acct.get('mailbox') or os.environ.get('JARVIS_IMAP_MAILBOX', 'INBOX') or 'INBOX').strip() or 'INBOX'
    
    cfg = {
        'email': email,
        'password': password,
        'imap_host': imap_host,
        'imap_port': imap_port,
        'smtp_host': smtp_host,
        'smtp_port': smtp_port,
        'mailbox': mailbox,
    }
    cfg = _apply_gmail_defaults(cfg)
    if not email or not password:
        return None
    if not cfg['imap_host']:
        return None
    if not cfg['smtp_host']:
        cfg['smtp_host'] = cfg['imap_host'].replace('imap.', 'smtp.')
    return cfg
def save_mail_account(
    email: str,
    password: str,
    imap_host: str = '',
    smtp_host: str = '',
    imap_port: int = 993,
    smtp_port: int = 587,
) -> None:
    data = _load_settings()
    if not isinstance(data.get('mail_account'), dict):
        data['mail_account'] = {}
    acc = data['mail_account']
    acc['email'] = email.strip()
    acc['password'] = "" # NEVER save key to JSON
    
    # Save password to .env
    if password.strip():
        _update_env_var('JARVIS_IMAP_PASS', password.strip())
        _update_env_var('JARVIS_IMAP_USER', email.strip())

    ih = (imap_host or '').strip()
    sh = (smtp_host or '').strip()
    if _is_gmail_address(email):
        ih = ih or 'imap.gmail.com'
        sh = sh or 'smtp.gmail.com'
    acc['imap_host'] = ih
    acc['smtp_host'] = sh
    acc['imap_port'] = imap_port
    acc['smtp_port'] = smtp_port
    acc['mailbox'] = acc.get('mailbox') or 'INBOX'
    data['mail_account'] = acc
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def _raw_error_text(exc: BaseException) -> str:
    chunks: list[str] = []
    for a in getattr(exc, 'args', ()) or ():
        if isinstance(a, (bytes, bytearray)):
            chunks.append(bytes(a).decode('utf-8', errors='replace'))
        else:
            chunks.append(str(a))
    if chunks:
        return ' '.join(chunks)
    return str(exc)
def format_mail_error(exc: BaseException) -> str:
    t = _raw_error_text(exc)
    low = t.lower()
    if 'application-specific password' in low or '185833' in t:
        return (
            'Gmail отклонил вход: нужен пароль приложения (16 символов), а не обычный пароль от почты. '
            'Создайте его в Google Аккаунт → Безопасность → Двухэтапная проверка → Пароли приложений, '
            'затем в JARVIS: Центр расширений → модуль «Почта» → «Настройки почты» — вставьте новый пароль. '
            'Справка Google: https://support.google.com/accounts/answer/185833'
        )
    if 'authenticationfailed' in low or 'invalid credentials' in low or 'авторизац' in low:
        return (
            'Ошибка входа в почту. Проверьте адрес и пароль приложения в настройках модуля «Почта». '
            f'Технически: {t}'
        )
    if 'lookup failed' in low or 'getaddrinfo' in low:
        return f'Не удалось найти сервер почты (проверьте интернет и имя IMAP/SMTP). {t}'
    return t

def _decode_hdr(s: str | None) -> str:
    if not s:
        return ''
    parts = decode_header(s)
    out: list[str] = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(text)
    return ''.join(out)

def _connect_imap(cfg: dict, select_mailbox: bool = True) -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL(cfg['imap_host'], cfg['imap_port'], ssl_context=ctx, timeout=25.0)
    conn.login(cfg['email'], cfg['password'])
    if select_mailbox:
        conn.select(cfg['mailbox'])
    return conn

def unread_count() -> tuple[bool, str]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена. Откройте «Центр расширений» и настройте модуль «Почта».'
    try:
        # Fast IMAP status query without selecting/parsing the entire mailbox
        conn = _connect_imap(cfg, select_mailbox=False)
        mb = cfg.get('mailbox') or 'INBOX'
        typ, data = conn.status(mb, '(UNSEEN)')
        n = 0
        if typ == 'OK' and data and data[0]:
            raw_res = data[0].decode('utf-8', errors='replace') if isinstance(data[0], bytes) else str(data[0])
            m = re.search(r'UNSEEN\s+(\d+)', raw_res, re.IGNORECASE)
            if m:
                n = int(m.group(1))
        try:
            conn.logout()
        except Exception:
            pass
        return True, f'Непрочитанных писем: {n}.'
    except Exception as ex:
        return False, f'Не удалось подключиться к почте. {format_mail_error(ex)}'

def list_recent_messages(limit: int = 40) -> tuple[bool, str | list[dict]]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена.'
    try:
        conn = _connect_imap(cfg)
        typ, data = conn.uid('search', None, 'ALL')
        if typ != 'OK' or not data or not data[0]:
            try:
                conn.logout()
            except Exception:
                pass
            return True, []
        uids = data[0].split()
        if len(uids) > limit:
            uids = uids[-limit:]
        
        # Batch fetch all headers in 1 single IMAP command instead of 50 individual roundtrips
        uid_set = b','.join(uids)
        typ_f, msgdata = conn.uid(
            'fetch',
            uid_set,
            '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])',
        )
        rows: list[dict] = []
        if typ_f == 'OK' and msgdata:
            for item in msgdata:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw = item[1]
                    if not isinstance(raw, (bytes, bytearray)):
                        continue
                    p = BytesParser(policy=email_policy).parsebytes(raw)
                    subj = _decode_hdr(p.get('Subject'))
                    from_ = _decode_hdr(p.get('From'))
                    date_ = (p.get('Date') or '').strip()
                    mid = (p.get('Message-ID') or '').strip()
                    hdr_str = item[0].decode('ascii', errors='ignore') if isinstance(item[0], bytes) else str(item[0])
                    m_uid = re.search(r'UID\s+(\d+)', hdr_str, re.IGNORECASE)
                    uid_s = m_uid.group(1) if m_uid else ''
                    line = f'{subj or "(без темы)"} — {from_[:60]}'
                    rows.append(
                        {
                            'uid': uid_s,
                            'subject': subj,
                            'from': from_,
                            'date': date_,
                            'message_id': mid,
                            'list_line': line,
                        }
                    )
        rows.reverse()
        try:
            conn.logout()
        except Exception:
            pass
        return True, rows
    except Exception as ex:
        return False, format_mail_error(ex)
def _part_text(part) -> str:
    try:
        return part.get_content()
    except Exception:
        pl = part.get_payload(decode=True)
        if isinstance(pl, bytes):
            return pl.decode(part.get_content_charset() or 'utf-8', errors='replace')
    return ''

_ZERO_WIDTH_RE = re.compile(r'[­​-‏⁠﻿ ]')
# Marketing emails often hide a preheader/spacer block via inline
# display:none|visibility:hidden|font-size:0 — never a <script>/<style> tag,
# so it survives naive tag-stripping and leaks its zero-width padding chars.
_HIDDEN_EL_RE = re.compile(
    r'(?is)<(span|div|td|p)\b[^>]*style="[^"]*(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)[^"]*"[^>]*>.*?</\1>'
)

def _html_to_text(html: str) -> str:
    html = re.sub(r'(?s)<!--.*?-->', '', html)
    html = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', html)
    for _ in range(3):
        html, n = _HIDDEN_EL_RE.subn(' ', html)
        if not n:
            break
    html = re.sub(r'(?i)<(br\s*/?|/p|/div|/tr|/li|/h[1-6])>', '\n', html)
    html = re.sub(r'<[^>]+>', '', html)
    html = unescape(html)
    html = _ZERO_WIDTH_RE.sub('', html)
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in html.splitlines()]
    text = '\n'.join(ln for ln in lines if ln)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def _is_boilerplate(text: str) -> bool:
    """True if a text/plain part is empty or mostly tracking-link noise to
    be the actual message — common in newsletters that only fill in the
    HTML alternative and leave a link-only text/plain fallback. Does not
    flag on length alone — a short reply like "Ok, спасибо" is a real,
    legitimate plain-text message, not boilerplate."""
    stripped = text.strip()
    if not stripped:
        return True
    url_chars = sum(len(u) for u in re.findall(r'https?://\S+', stripped))
    return url_chars > len(stripped) * 0.5

def _extract_plain_body(msg) -> str:
    plain_text = ''
    html_text = ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain' and not plain_text:
                plain_text = _part_text(part)
            elif ctype == 'text/html' and not html_text:
                html_text = _part_text(part)
    elif msg.get_content_type() == 'text/plain':
        plain_text = _part_text(msg)
    elif msg.get_content_type() == 'text/html':
        html_text = _part_text(msg)
    if html_text and (not plain_text or _is_boilerplate(plain_text)):
        converted = _html_to_text(html_text)
        if converted:
            return converted
    if plain_text:
        return plain_text
    if html_text:
        return _html_to_text(html_text)
    return '(текст письма в неподдерживаемом формате)'
def fetch_message_body(uid: str) -> tuple[bool, str | dict]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена.'
    try:
        conn = _connect_imap(cfg)
        uid_b = uid.encode('ascii') if isinstance(uid, str) else uid
        typ, data = conn.uid('fetch', uid_b, '(RFC822)')
        if typ != 'OK' or not data or not isinstance(data[0], tuple):
            conn.logout()
            return False, 'Не удалось загрузить письмо.'
        raw = data[0][1]
        if not isinstance(raw, (bytes, bytearray)):
            conn.logout()
            return False, 'Пустое тело.'
        msg = BytesParser(policy=email_policy).parsebytes(raw)
        body = _extract_plain_body(msg)
        subj = _decode_hdr(msg.get('Subject'))
        from_ = _decode_hdr(msg.get('From'))
        to_ = _decode_hdr(msg.get('To'))
        mid = (msg.get('Message-ID') or '').strip()
        refs = (msg.get('References') or '').strip()
        reply_to = from_
        m = re.search(r'<([^>]+)>', from_)
        if m:
            reply_to = m.group(1).strip()
        elif '<' not in from_:
            reply_to = from_.strip()
        try:
            conn.logout()
        except Exception:
            pass
        return True, {
            'subject': subj,
            'from': from_,
            'to': to_,
            'body': body,
            'message_id': mid,
            'references': refs,
            'reply_to': reply_to,
        }
    except Exception as ex:
        return False, format_mail_error(ex)
def delete_message_by_uid(uid: str) -> tuple[bool, str]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена.'
    uid_s = (uid or '').strip()
    if not uid_s:
        return False, 'Не выбрано письмо.'
    try:
        conn = _connect_imap(cfg)
        uid_b = uid_s.encode('ascii') if isinstance(uid_s, str) else uid_s
        typ, _ = conn.uid('STORE', uid_b, '+FLAGS', r'(\Deleted)')
        if typ != 'OK':
            try:
                conn.logout()
            except Exception:
                pass
            return False, 'Сервер не принял удаление (IMAP STORE).'
        try:
            conn.expunge()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass
        return True, 'Письмо удалено.'
    except Exception as ex:
        return False, format_mail_error(ex)
def send_reply(
    to_addr: str,
    subject: str,
    body: str,
    in_reply_to: str = '',
    references: str = '',
    attachments: list[Path] | None = None,
) -> tuple[bool, str]:
    return send_message(
        to_addr=to_addr,
        subject=subject,
        body=body,
        in_reply_to=in_reply_to,
        references=references,
        attachments=attachments,
    )
def send_message(
    to_addr: str,
    subject: str,
    body: str,
    cc: str = '',
    bcc: str = '',
    in_reply_to: str = '',
    references: str = '',
    attachments: list[Path] | None = None,
) -> tuple[bool, str]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена.'
    if not (cfg.get('smtp_host') or '').strip():
        return False, 'Не указан SMTP-сервер.'
    if not (to_addr or '').strip():
        return False, 'Не указан адрес получателя.'
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = cfg['email']
        msg['To'] = to_addr
        if cc:
            msg['Cc'] = cc
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
        if references:
            msg['References'] = references
        elif in_reply_to:
            msg['References'] = in_reply_to
        plain = (body or '').strip()
        if not plain and attachments:
            plain = 'Во вложении.'
        msg.set_content(plain, charset='utf-8')
        for p in attachments or []:
            path = Path(p)
            if not path.is_file():
                continue
            data = path.read_bytes()
            ctype = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            if '/' in ctype:
                maintype, subtype = ctype.split('/', 1)
            else:
                maintype, subtype = 'application', 'octet-stream'
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        all_recipients = [to_addr]
        if cc:
            all_recipients.extend(a.strip() for a in cc.split(',') if a.strip())
        if bcc:
            all_recipients.extend(a.strip() for a in bcc.split(',') if a.strip())
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=120) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(cfg['email'], cfg['password'])
            s.send_message(msg, to_addrs=all_recipients)
        return True, 'Отправлено.'
    except Exception as ex:
        return False, format_mail_error(ex)
