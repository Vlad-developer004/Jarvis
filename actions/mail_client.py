from __future__ import annotations
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import ssl
from email.header import decode_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as email_policy
from pathlib import Path
_SETTINGS_PATH = Path('data') / 'jarvis_settings.json'
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
def get_resolved_mail_config() -> dict | None:
    s = _load_settings()
    acct = s.get('mail_account')
    if not isinstance(acct, dict):
        acct = {}
    email = (acct.get('email') or os.environ.get('JARVIS_IMAP_USER', '')).strip()
    password = (acct.get('password') or os.environ.get('JARVIS_IMAP_PASS', '')).strip()
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
    acc['password'] = password
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
def _connect_imap(cfg: dict) -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL(cfg['imap_host'], cfg['imap_port'], ssl_context=ctx)
    conn.login(cfg['email'], cfg['password'])
    conn.select(cfg['mailbox'])
    return conn
def unread_count() -> tuple[bool, str]:
    cfg = get_resolved_mail_config()
    if not cfg:
        return False, 'Почта не настроена. Откройте «Центр расширений» и настройте модуль «Почта».'
    try:
        conn = _connect_imap(cfg)
        typ, data = conn.search(None, 'UNSEEN')
        n = 0
        if typ == 'OK' and data and data[0]:
            n = len(data[0].split())
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
            conn.logout()
            return True, []
        uids = data[0].split()
        if len(uids) > limit:
            uids = uids[-limit:]
        rows: list[dict] = []
        for uid in reversed(uids):
            typ, msgdata = conn.uid(
                'fetch',
                uid,
                '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])',
            )
            if typ != 'OK' or not msgdata or not isinstance(msgdata[0], tuple):
                continue
            raw = msgdata[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            p = BytesParser(policy=email_policy).parsebytes(raw)
            subj = _decode_hdr(p.get('Subject'))
            from_ = _decode_hdr(p.get('From'))
            date_ = (p.get('Date') or '').strip()
            mid = (p.get('Message-ID') or '').strip()
            uid_s = uid.decode('ascii', errors='ignore') if isinstance(uid, bytes) else str(uid)
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
        try:
            conn.logout()
        except Exception:
            pass
        return True, rows
    except Exception as ex:
        return False, format_mail_error(ex)
def _extract_plain_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain':
                try:
                    return part.get_content()
                except Exception:
                    pl = part.get_payload(decode=True)
                    if isinstance(pl, bytes):
                        return pl.decode(part.get_content_charset() or 'utf-8', errors='replace')
    else:
        if msg.get_content_type() == 'text/plain':
            try:
                return msg.get_content()
            except Exception:
                pl = msg.get_payload(decode=True)
                if isinstance(pl, bytes):
                    return pl.decode(msg.get_content_charset() or 'utf-8', errors='replace')
        if msg.get_content_type() == 'text/html':
            pl = msg.get_payload(decode=True)
            if isinstance(pl, bytes):
                t = pl.decode(msg.get_content_charset() or 'utf-8', errors='replace')
                t = re.sub(r'<[^>]+>', ' ', t)
                return re.sub(r'\s+', ' ', t).strip()
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
