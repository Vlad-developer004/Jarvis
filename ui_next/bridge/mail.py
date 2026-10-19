"""Mail for the Mail screen: folders, the message list, reading with formatting, flags, moving and deleting, replying, composing, on top of
one long-lived IMAP connection (imapsession.py) and the same SMTP code the voice commands and the old mail window use (actions/mail_client.py).

Attachments to send never come from the UI as paths: the user picks files in a native dialog opened here, the files are registered under short
ids and a message refers to those ids. Received attachments are saved by index into the Downloads folder. Links in letters open only through
`open_url`, which accepts http(s) only.
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading
import uuid
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

from . import mail_render
from .imapsession import SESSION, MailError, addresses, _ts

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_attach: dict[str, Path] = {}         # id -> file chosen in the dialog, until the message is sent
_saved: set[str] = set()              # files written by save_attachment, the only ones `reveal` accepts
MAX_ATTACH_BYTES = 25 * 1024 * 1024
MAX_SAVE_BYTES = 60 * 1024 * 1024
_MAX_BODY = 200_000
FOLDERS = ('inbox', 'sent', 'drafts', 'junk', 'trash', 'archive')
FILTERS = ('all', 'unread', 'flagged')


def _client():
    from actions import mail_client
    return mail_client


def configured() -> dict:
    cfg = _client().get_resolved_mail_config()
    return {'configured': bool(cfg), 'email': str((cfg or {}).get('email') or '')}


def _guard(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except MailError as ex:
            return {'ok': False, 'error': ex.code, 'message': ex.message if ex.code == 'failed' else ''}
    wrapper.__name__ = fn.__name__
    return wrapper


def _folder(value) -> str:
    v = str(value or 'inbox')
    if v not in FOLDERS and not re.fullmatch(r'f\d{1,2}', v):
        raise MailError('bad_folder')
    return v


def _uid(value) -> str:
    v = str(value or '')
    if not v.isdigit():
        raise MailError('bad_uid')
    return v


def _uids(value) -> list[str]:
    items = value if isinstance(value, list) else [value]
    out = [_uid(v) for v in items[:200]]
    if not out:
        raise MailError('bad_uid')
    return out


@_guard
def folders() -> dict:
    if not configured()['configured']:
        return {'ok': False, 'error': 'not_configured'}
    info = SESSION.folder_list()
    return {'ok': True, 'folders': info['roles'], 'unread': info['unread'], 'custom': info['custom']}


@_guard
def list_messages(folder='inbox', flt='all', q='', offset=0, limit=40, refresh=False) -> dict:
    c = configured()
    if not c['configured']:
        return {'ok': False, 'error': 'not_configured'}
    role = _folder(folder)
    flt = flt if flt in FILTERS else 'all'
    q = ' '.join(str(q or '').split())[:100]
    res = SESSION.page(role, flt, q, max(0, int(offset or 0)), max(1, min(int(limit or 40), 100)), bool(refresh))
    return {'ok': True, 'email': c['email'], 'folder': role, 'rows': res['rows'], 'total': res['total'], 'more': res['more'], 'cached': res['cached']}


@_guard
def read_message(folder='inbox', uid='', images=False, mark=True) -> dict:
    role, uid = _folder(folder), _uid(uid)
    cl = _client()
    msg, was_unread = SESSION.message(role, uid, bool(mark))
    text = cl._extract_plain_body(msg).strip()
    shown = mail_render.render(msg, text, bool(images))
    name, addr = parseaddr(cl._decode_hdr(msg.get('From')))
    reply = parseaddr(cl._decode_hdr(msg.get('Reply-To')))[1] or addr
    date = (msg.get('Date') or '').strip()
    return {'ok': True, 'uid': uid, 'subject': cl._decode_hdr(msg.get('Subject')), 'name': name or addr, 'addr': addr, 'to': addresses(msg.get('To')),
            'cc': addresses(msg.get('Cc')), 'ts': _ts(date), 'date': date, 'body': text[:_MAX_BODY], 'html': shown['html'], 'blocked': shown['blocked'],
            'files': shown['files'], 'reply_to': reply, 'message_id': (msg.get('Message-ID') or '').strip(),
            'references': (msg.get('References') or '').strip(), 'was_unread': was_unread, 'unsub': _unsub_public(_unsub_info(msg))}


def _unsub_info(msg) -> dict | None:
    """How a newsletter can be left: RFC 8058 one-click POST, a web page, or a mailto: address (List-Unsubscribe headers)."""
    raw = _client()._decode_hdr(msg.get('List-Unsubscribe'))
    urls = re.findall(r'<([^<>\s]+)>', raw or '')
    one_click = 'one-click' in str(msg.get('List-Unsubscribe-Post') or '').lower()
    https = next((u for u in urls if u.lower().startswith('https://')), '')
    plain = next((u for u in urls if u.lower().startswith('http://')), '')
    mailto = next((u for u in urls if u.lower().startswith('mailto:')), '')
    if https and one_click:
        return {'kind': 'oneclick', 'url': https}
    if https or plain:
        return {'kind': 'web', 'url': https or plain}
    if mailto:
        return {'kind': 'mail', 'url': mailto}
    return None


def _unsub_public(info) -> dict | None:
    """What the UI may see: the kind and where the request goes, never the raw link."""
    if not info:
        return None
    from urllib.parse import urlsplit, unquote
    u = urlsplit(info['url'])
    target = unquote(u.path) if info['kind'] == 'mail' else (u.hostname or '')
    return {'kind': info['kind'], 'target': target[:80]}


def _http_post(url: str) -> int:
    """One-click unsubscribe POST. Public https hosts only, no redirects, short timeout."""
    import ipaddress
    import socket
    import urllib.error
    import urllib.request
    from urllib.parse import urlsplit
    u = urlsplit(url)
    if u.scheme != 'https' or not u.hostname or u.username:
        raise MailError('bad_url')
    try:
        for ai in socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP):
            if not ipaddress.ip_address(ai[4][0]).is_global:
                raise MailError('blocked_host')
    except OSError:
        raise MailError('failed', 'Не удалось найти сервер рассылки')

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    req = urllib.request.Request(url, data=b'List-Unsubscribe=One-Click', method='POST',
                                 headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Jarvis'})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as ex:
        return ex.code
    except OSError:
        raise MailError('failed', 'Сервер рассылки не ответил')


@_guard
def unsubscribe(folder, uid) -> dict:
    """Leaves the mailing list the letter came from. The link always comes from the letter's own headers, never from the UI."""
    msg, _ = SESSION.message(_folder(folder), _uid(uid), False)
    info = _unsub_info(msg)
    if not info:
        return {'ok': False, 'error': 'no_unsubscribe'}
    if info['kind'] == 'oneclick':
        code = _http_post(info['url'])
        return {'ok': 200 <= code < 400, 'how': 'oneclick', 'code': code}
    if info['kind'] == 'web':
        return {**open_url(info['url']), 'how': 'web'}
    from urllib.parse import urlsplit, unquote, parse_qs
    u = urlsplit(info['url'])
    to = unquote(u.path).strip()
    if not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+', to):
        return {'ok': False, 'error': 'bad_address'}
    q = parse_qs(u.query)
    subject = (q.get('subject') or ['unsubscribe'])[0][:120] or 'unsubscribe'
    body = (q.get('body') or ['unsubscribe'])[0][:300] or 'unsubscribe'
    ok, text = _client().send_message(to, subject, body)
    return {'ok': bool(ok), 'how': 'mail', 'message': text}


@_guard
def set_flag(folder, uids, flag, on) -> dict:
    if flag not in ('seen', 'flagged'):
        return {'ok': False, 'error': 'bad_flag'}
    SESSION.set_flag(_folder(folder), _uids(uids), flag, bool(on))
    return {'ok': True}


@_guard
def remove(folder, uids, to='') -> dict:
    if to not in ('', 'trash', 'archive', 'junk') and not re.fullmatch(r'f\d{1,2}', str(to)):
        return {'ok': False, 'error': 'bad_target'}
    where = SESSION.remove(_folder(folder), _uids(uids), to)
    return {'ok': True, 'where': where}


@_guard
def mark_all_read(folder) -> dict:
    SESSION.mark_all_read(_folder(folder))
    return {'ok': True}


@_guard
def empty_folder(folder) -> dict:
    role = _folder(folder)
    if role not in ('trash', 'junk'):
        return {'ok': False, 'error': 'bad_folder'}
    SESSION.empty(role)
    return {'ok': True}


# ---- preferences and drafts ----

MAX_SIGNATURE = 500


def get_prefs() -> dict:
    from core import settings_io
    return {'ok': True, 'signature': str(settings_io.read().get('mail_signature') or '')[:MAX_SIGNATURE]}


def set_prefs(signature) -> dict:
    from core import settings_io
    settings_io.update({'mail_signature': str(signature or '').strip()[:MAX_SIGNATURE]})
    return get_prefs()


def _with_signature(body: str) -> str:
    sig = get_prefs()['signature']
    return f'{body.rstrip()}\n\n-- \n{sig}' if sig else body


@_guard
def save_draft(data: dict) -> dict:
    """Stores the message being written in the Drafts folder (it is not sent). A draft that was being edited is replaced."""
    from email.message import EmailMessage
    paths = _take(data.get('attach'))
    if paths is None:
        return {'ok': False, 'error': 'bad_attachment'}
    cfg = _client().get_resolved_mail_config() or {}
    msg = EmailMessage()
    msg['Subject'] = str(data.get('subject') or '')[:300]
    msg['From'] = cfg.get('email', '')
    for key, field in (('to', 'To'), ('cc', 'Cc'), ('bcc', 'Bcc')):
        if str(data.get(key) or '').strip():
            msg[field] = str(data[key]).strip()
    msg.set_content(str(data.get('body') or '')[:_MAX_BODY] or ' ', charset='utf-8')
    rich = mail_render.fragment(str(data.get('html') or '')[:300_000])
    if rich:
        msg.add_alternative(f'<div>{rich}</div>', subtype='html', charset='utf-8')
    for p in paths:
        if p.is_file():
            import mimetypes
            kind = (mimetypes.guess_type(p.name)[0] or 'application/octet-stream').split('/', 1)
            msg.add_attachment(p.read_bytes(), maintype=kind[0], subtype=kind[-1], filename=p.name)
    SESSION.append('drafts', msg.as_bytes())
    old = str(data.get('replace') or '')
    if old.isdigit():
        try:
            SESSION.remove('drafts', [old], '')
        except MailError:
            _log.debug('old draft not removed', exc_info=True)
    return {'ok': True}


# ---- received attachments ----

def _safe_name(name: str) -> str:
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name or '')).strip(' .')[:120] or 'file'
    if n.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'LPT1', 'LPT2', 'LPT3'}:
        n = '_' + n
    return n


def _downloads() -> Path:
    d = Path.home() / 'Downloads'
    return d if d.is_dir() else Path.home()


def _unique(folder: Path, name: str) -> Path:
    p = folder / name
    stem, suffix, i = p.stem, p.suffix, 1
    while p.exists():
        i += 1
        p = folder / f'{stem} ({i}){suffix}'
    return p


@_guard
def save_attachment(folder, uid, idx) -> dict:
    role, uid = _folder(folder), _uid(uid)
    msg, _ = SESSION.message(role, uid, False)
    files = mail_render.attachments(msg, _referenced(msg))
    try:
        item = files[int(idx)]
    except (ValueError, IndexError, TypeError):
        return {'ok': False, 'error': 'bad_attachment'}
    data = item['part'].get_payload(decode=True) or b''
    if len(data) > MAX_SAVE_BYTES:
        return {'ok': False, 'error': 'too_big'}
    target = _unique(_downloads(), _safe_name(item['name']))
    target.write_bytes(data)
    _saved.add(str(target))
    return {'ok': True, 'path': str(target), 'name': target.name}


def _referenced(msg) -> set[str]:
    try:
        body = msg.get_body(preferencelist=('html',))
        raw = mail_render._decode_payload(body) if body is not None else ''
    except Exception:
        raw = ''
    return {m.strip('<>') for m in re.findall(r'(?i)cid:([^"\'\s)>]+)', raw)}


def reveal(path: str) -> dict:
    p = str(path or '')
    if p not in _saved or not Path(p).exists():
        return {'ok': False, 'error': 'unknown_file'}
    subprocess.Popen(['explorer', '/select,', p])
    return {'ok': True}


# ---- warm-up ----

def warm() -> None:
    """Opens the connection and loads the first page in the background, so the screen is instant when the user gets to it."""
    try:
        if not configured()['configured']:
            return
        SESSION.folder_list()
        rows = SESSION.page('inbox')['rows']
        for r in rows[:2]:
            SESSION.message('inbox', r['uid'], False)
    except Exception:
        _log.debug('mail warm-up failed', exc_info=True)


# ---- attachments to send ----

def _pick_paths() -> list[str]:
    from . import filepick
    return filepick.pick_files('Вложения', filepick.MAIL, multi=True)


def pick_attachments() -> dict:
    out = []
    total = sum(p.stat().st_size for p in _attach.values() if p.is_file())
    for raw in _pick_paths():
        p = Path(raw)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if not p.is_file():
            continue
        if total + size > MAX_ATTACH_BYTES:
            return {'ok': False, 'error': 'too_big', 'added': out}
        total += size
        aid = uuid.uuid4().hex[:10]
        with _lock:
            _attach[aid] = p
        out.append({'id': aid, 'name': p.name, 'size': size})
    return {'ok': True, 'added': out}


def drop_attachment(aid: str) -> dict:
    with _lock:
        return {'ok': _attach.pop(str(aid), None) is not None}


def _take(ids) -> list[Path] | None:
    if not isinstance(ids, list):
        return []
    with _lock:
        paths = [_attach.get(str(i)) for i in ids]
    return None if any(p is None for p in paths) else paths


def _quote_parts(q: dict, body: str, mine_html: str = '') -> tuple[str, str]:
    """Plain text and HTML of an outgoing message that carries the original letter: quoted under a reply, appended under a forward."""
    from html import escape
    role, uid = _folder(q.get('folder')), _uid(q.get('uid'))
    fwd = q.get('mode') == 'fwd'
    msg, _ = SESSION.message(role, uid, False)
    cl = _client()
    text = cl._extract_plain_body(msg).strip()[:_MAX_BODY]
    name, addr = parseaddr(cl._decode_hdr(msg.get('From')))
    who = f'{name} <{addr}>' if name and name != addr else addr
    ts = _ts((msg.get('Date') or '').strip())
    when = datetime.fromtimestamp(ts).strftime('%d.%m.%Y, %H:%M') if ts else ''
    original = mail_render.quote_fragment(msg) or f'<div style="white-space:pre-wrap">{escape(text)}</div>'
    mine = f'<div>{mine_html}</div><br>' if mine_html else f'<div style="white-space:pre-wrap">{escape(body)}</div><br>'
    if fwd:
        return f'{body}\n\n{text}', f'{mine}<div>{original}</div>'
    head = f'{when}, {who} написал(а):'.lstrip(', ')
    lines = text.splitlines()[:200]
    plain = f'{body}\n\n{head}\n' + '\n'.join(f'> {line}' for line in lines)
    html = (f'{mine}<div>{escape(head)}</div><blockquote style="margin:.6em 0 0 .8ex;padding-left:1ex;border-left:2px solid #b8c6d4">{original}</blockquote>')
    return plain, html


@_guard
def send(data: dict) -> dict:
    to = str(data.get('to') or '').strip()
    if not to or '@' not in to:
        return {'ok': False, 'error': 'bad_to'}
    paths = _take(data.get('attach'))
    if paths is None:
        return {'ok': False, 'error': 'bad_attachment'}
    subject = str(data.get('subject') or '').strip()[:300]
    body = str(data.get('body') or '')[:_MAX_BODY]
    if not body.strip() and not paths:
        return {'ok': False, 'error': 'empty'}
    mine = mail_render.fragment(str(data.get('html') or '')[:300_000])
    if data.get('sign', True) and body.strip():
        sig = get_prefs()['signature']
        body = _with_signature(body)
        if sig and mine:
            from html import escape
            mine += f'<div>-- <br>{escape(sig).replace(chr(10), "<br>")}</div>'
    html = f'<div>{mine}</div>' if mine else ''
    q = data.get('quote')
    if isinstance(q, dict):
        body, html = _quote_parts(q, body, mine)
    ok, msg = _client().send_message(to, subject, body, cc=str(data.get('cc') or '').strip(), bcc=str(data.get('bcc') or '').strip(),
                                     in_reply_to=str(data.get('in_reply_to') or ''), references=str(data.get('references') or ''), attachments=paths, html=html)
    if ok:
        with _lock:
            for i in data.get('attach') or []:
                _attach.pop(str(i), None)
        SESSION.pages.pop('sent', None)
        old = str(data.get('replace') or '')
        if old.isdigit():
            try:
                SESSION.remove('drafts', [old], '')
            except MailError:
                _log.debug('old draft not removed', exc_info=True)
    return {'ok': bool(ok), 'message': msg}


def open_url(url: str) -> dict:
    import webbrowser
    u = str(url or '').strip()
    if not u.lower().startswith(('http://', 'https://')) or len(u) > 2000 or any(c in u for c in '\r\n\0 '):
        return {'ok': False, 'error': 'bad_url'}
    return {'ok': bool(webbrowser.open(u))}
