"""One long-lived IMAP connection for the Mail screen.

The old helpers in actions/mail_client.py open a new SSL connection and log in for every single action, which is what made the list and
every letter slow. Here one connection is kept (and re-opened when the server drops it), folders are discovered once, and the first page of
a folder and the last opened letters are cached in memory. All access goes through one lock, so the UI can never interleave two commands.
"""
from __future__ import annotations

import base64
import imaplib
import logging
import re
import ssl
import threading
import time
from collections import OrderedDict
from datetime import date
from email.parser import BytesParser
from email.policy import default as email_policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)

ROLES = ('inbox', 'sent', 'drafts', 'junk', 'trash', 'archive')
_ATTR_ROLE = {'\\sent': 'sent', '\\drafts': 'drafts', '\\junk': 'junk', '\\spam': 'junk', '\\trash': 'trash', '\\archive': 'archive', '\\all': 'archive'}
_NAME_ROLE = (('sent', ('sent', 'отправлен', 'надіслан')), ('drafts', ('draft', 'черновик', 'чернетк')), ('junk', ('junk', 'spam', 'спам')),
              ('trash', ('trash', 'deleted', 'корзин', 'удален', 'видален', 'кошик')), ('archive', ('archive', 'архив', 'all mail')))
_LIST_RE = re.compile(r'\((?P<attrs>[^)]*)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)$')
HEADERS = '(UID FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID CONTENT-TYPE)])'
PAGE = 40
IDLE_PING = 20.0        # seconds of silence after which the connection is checked with a NOOP (a round trip on every command made each one slower)
UNREAD_TTL = 10.0       # the unread counter is a slow STATUS on a big mailbox; it is reused this long unless a letter changed
PAGE_FRESH = 30.0        # a cached first page younger than this is reported fresh: the window does not refetch it in the background
SNIP_BATCH = 10         # previews are fetched in small batches so a letter the user opens in between does not wait for all of them
_BODY_CACHE_MAX = 10
_BODY_CACHE_BYTES = 8_000_000


class MailError(Exception):
    def __init__(self, code: str, message: str = ''):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def _q(name: str) -> str:
    return '"' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _ts(date_s: str) -> int:
    try:
        return int(parsedate_to_datetime(date_s).timestamp())
    except Exception:
        return 0


def _hdr(value) -> str:
    from actions.mail_client import _decode_hdr
    return _decode_hdr(str(value)) if value else ''


def _iter_list(lines):
    for line in lines or []:
        if not line:
            continue
        text = line.decode('utf-8', errors='replace') if isinstance(line, (bytes, bytearray)) else str(line)
        m = _LIST_RE.match(text.strip())
        if not m:
            continue
        name = m.group('name').strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        yield m.group('attrs').lower().split(), name


def parse_folders(lines: list, inbox_raw: str = 'INBOX') -> dict[str, str]:
    """role -> raw IMAP name, from the LIST response."""
    found: dict[str, str] = {'inbox': inbox_raw}
    guessed: dict[str, str] = {}
    for attrs, name in _iter_list(lines):
        if '\\noselect' in attrs:
            continue
        role = next((_ATTR_ROLE[a] for a in attrs if a in _ATTR_ROLE), '')
        if role:
            found.setdefault(role, name)
            continue
        low = name.lower().rsplit('/', 1)[-1]
        for r, keys in _NAME_ROLE:
            if any(k in low for k in keys):
                guessed.setdefault(r, name)
    for r, name in guessed.items():
        found.setdefault(r, name)
    return found


_PLAIN_ATTRS = {'\\haschildren', '\\hasnochildren', '\\unmarked', '\\marked', '\\noinferiors'}


def parse_custom(lines: list, taken: set[str]) -> list[str]:
    """User folders / labels: everything selectable that is not a special-use folder and not already one of the roles."""
    out = []
    for attrs, name in _iter_list(lines):
        if '\\noselect' in attrs or name.upper() == 'INBOX' or name in taken or any(a not in _PLAIN_ATTRS for a in attrs):
            continue
        if name.startswith('[Gmail]') or name.startswith('[Google Mail]'):
            continue
        low = name.lower().rsplit('/', 1)[-1]
        if any(k in low for _, keys in _NAME_ROLE for k in keys):
            continue
        out.append(name)
    return out[:40]


def utf7_decode(name: str) -> str:
    """IMAP modified UTF-7 (how servers spell non-ASCII folder names) to text."""
    def one(m):
        if not m.group(1):
            return '&'
        try:
            b = m.group(1).replace(',', '/')
            return base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-16-be')
        except Exception:
            return m.group(0)
    return re.sub(r'&([^-]*)-', one, name)


_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
_TOKEN = re.compile(r'(\w+):("[^"]*"|\S+)|(\S+)')


def parse_query(q: str) -> tuple[list[str], str]:
    """Gmail-style search text -> (IMAP criteria, free text for TEXT). Understands from: to: cc: subject: is:unread|read|starred
    has:attachment after: before: (YYYY-MM-DD); anything else is searched as text."""
    crit: list[str] = []
    text: list[str] = []
    for op, val, plain in _TOKEN.findall(q or ''):
        if plain:
            text.append(plain)
            continue
        op, val = op.lower(), val.strip('"')
        if op in ('from', 'to', 'cc', 'bcc', 'subject'):
            if val and val.isascii() and not re.search(r'["\\]', val):
                crit += [op.upper(), f'"{val}"']
            elif val:
                text.append(val)
        elif op == 'is' and val.lower() in ('unread', 'read', 'starred', 'flagged'):
            crit.append({'unread': 'UNSEEN', 'read': 'SEEN', 'starred': 'FLAGGED', 'flagged': 'FLAGGED'}[val.lower()])
        elif op == 'has' and val.lower() == 'attachment':
            crit += ['HEADER', 'CONTENT-TYPE', '"multipart/mixed"']
        elif op in ('after', 'before'):
            try:
                y, mo, d = (int(x) for x in val.split('-'))
                date(y, mo, d)
                crit += ['SINCE' if op == 'after' else 'BEFORE', f'{d:02d}-{_MONTHS[mo - 1]}-{y}']
            except Exception:
                text.append(f'{op}:{val}')
        else:
            text.append(f'{op}:{val}')
    return crit, ' '.join(text)


def parse_header_rows(msgdata: list, who: str = 'from') -> list[dict]:
    """Rows from a `UID FETCH ... (UID FLAGS BODY.PEEK[HEADER.FIELDS ...])` response, newest first."""
    rows = []
    items = list(msgdata or [])
    for i, item in enumerate(items):
        if not (isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray))):
            continue
        head = item[0].decode('ascii', errors='ignore') if isinstance(item[0], bytes) else str(item[0])
        if i + 1 < len(items) and isinstance(items[i + 1], bytes):
            head += ' ' + items[i + 1].decode('ascii', errors='ignore')
        m_uid = re.search(r'UID\s+(\d+)', head, re.I)
        if not m_uid:
            continue
        p = BytesParser(policy=email_policy).parsebytes(bytes(item[1]))
        name, addr = parseaddr(_hdr(p.get('To') if who == 'to' else p.get('From')))
        if who == 'to' and ',' in _hdr(p.get('To')):
            name, addr = parseaddr(_hdr(p.get('To')).split(',')[0])
        ctype = (p.get('Content-Type') or '').lower()
        rows.append({'uid': m_uid.group(1), 'subject': _hdr(p.get('Subject')), 'name': name or addr, 'addr': addr, 'ts': _ts((p.get('Date') or '').strip()),
                     'unread': not re.search(r'FLAGS\s*\([^)]*\\Seen', head, re.I), 'flagged': bool(re.search(r'FLAGS\s*\([^)]*\\Flagged', head, re.I)),
                     'att': 'multipart/mixed' in ctype or 'multipart/signed' in ctype})
    rows.sort(key=lambda r: int(r['uid']), reverse=True)
    return rows


def addresses(value) -> list[dict]:
    out = []
    for name, addr in getaddresses([_hdr(value)]):
        if addr and '@' in addr:
            out.append({'name': name or addr, 'addr': addr})
    return out


class Session:
    def __init__(self):
        self.lock = threading.RLock()
        self.conn = None
        self.key = None
        self.cfg: dict = {}
        self.sel = None
        self.folders: dict[str, str] | None = None
        self.customs: list[str] = []
        self.pages: dict[str, dict] = {}
        self.bodies: OrderedDict = OrderedDict()
        self.snips: dict[tuple[str, str], str] = {}
        self.last_io = 0.0
        self.page_at: dict[str, float] = {}
        self.seen_todo: OrderedDict = OrderedDict()   # (role, uid) of letters opened but not yet flagged Seen on the server
        self.unread: tuple[float, int] | None = None

    # -- connection --
    def close(self):
        conn, self.conn, self.sel, self.folders = self.conn, None, None, None
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                _swallow()

    def reset(self):
        with self.lock:
            self.close()
            self.pages.clear()
            self.bodies.clear()
            self.snips.clear()
            self.seen_todo.clear()
            self.unread = None

    def _open(self):
        from actions import mail_client
        cfg = mail_client.get_resolved_mail_config()
        if not cfg:
            raise MailError('not_configured')
        key = (cfg['email'], cfg['imap_host'], cfg['imap_port'], cfg['mailbox'])
        if self.conn is not None and key != self.key:
            self.close()
            self.pages.clear()
            self.bodies.clear()
            self.snips.clear()
        if self.conn is not None and time.monotonic() - self.last_io > IDLE_PING:
            try:
                self.conn.noop()
            except Exception:
                self.close()
        if self.conn is None:
            try:
                self.conn = mail_client._connect_imap(cfg, select_mailbox=False)
            except Exception as ex:
                raise MailError('failed', mail_client.format_mail_error(ex))
            self.key, self.sel, self.cfg = key, None, cfg
            self.last_io = time.monotonic()
        return self.conn

    def run(self, fn):
        """Runs fn(conn) on the shared connection, reconnecting once when the server dropped it."""
        with self.lock:
            for attempt in (0, 1):
                conn = self._open()
                try:
                    res = fn(conn)
                    self.last_io = time.monotonic()
                    return res
                except (imaplib.IMAP4.abort, OSError, ssl.SSLError) as ex:
                    self.close()
                    if attempt:
                        from actions import mail_client
                        raise MailError('failed', mail_client.format_mail_error(ex))
                except imaplib.IMAP4.error as ex:
                    from actions import mail_client
                    raise MailError('failed', mail_client.format_mail_error(ex))

    # -- folders --
    def folder_map(self, conn) -> dict[str, str]:
        if self.folders is None:
            typ, lines = conn.list()
            lines = lines if typ == 'OK' else []
            self.folders = parse_folders(lines, self.cfg.get('mailbox') or 'INBOX')
            self.customs = parse_custom(lines, set(self.folders.values()))
            for i, raw in enumerate(self.customs):
                self.folders[f'f{i + 1}'] = raw
        return self.folders

    def _select(self, conn, role: str) -> str:
        raw = self.folder_map(conn).get(role)
        if not raw:
            raise MailError('no_folder')
        if self.sel != raw:
            typ, _ = conn.select(_q(raw))
            if typ != 'OK':
                self.sel = None
                raise MailError('failed', 'Не удалось открыть папку')
            self.sel = raw
        return raw

    def folder_list(self, unread: bool = True) -> dict:
        """Roles and custom folders; `unread=False` skips the (slow) unread counter and reports the last known one."""
        def go(conn):
            self._flush_seen(conn)       # the counter must not race the flags still waiting to be stored
            fm = self.folder_map(conn)
            n = self.unread[1] if self.unread else 0
            if unread and not (self.unread and time.monotonic() - self.unread[0] < UNREAD_TTL):
                try:
                    typ, data = conn.status(_q(fm['inbox']), '(UNSEEN)')
                    m = re.search(r'UNSEEN\s+(\d+)', data[0].decode('utf-8', errors='replace') if typ == 'OK' and data and data[0] else '', re.I)
                    n = int(m.group(1)) if m else 0
                    self.unread = (time.monotonic(), n)
                except Exception:
                    _swallow()
            return {'roles': [r for r in ROLES if r in fm], 'unread': n,
                    'custom': [{'id': f'f{i + 1}', 'name': utf7_decode(raw).replace('/', ' / ')} for i, raw in enumerate(self.customs)]}
        return self.run(go)

    # -- list --
    def page(self, role: str, flt: str = 'all', q: str = '', offset: int = 0, limit: int = PAGE, refresh: bool = False) -> dict:
        plain = flt == 'all' and not q and offset == 0
        if plain and not refresh and role in self.pages:
            return {**self.pages[role], 'cached': True, 'fresh': time.monotonic() - self.page_at.get(role, 0.0) < PAGE_FRESH}

        def go(conn):
            raw = self._select(conn, role)
            if plain or (flt == 'all' and not q):
                # The plain list needs only the count and the newest letters: a STATUS and a fetch by sequence number, not a SEARCH that
                # returns every UID of a mailbox of ten thousand letters.
                total = self._message_count(conn, raw)
                if total is not None:
                    end = max(0, total - offset)
                    lo = max(1, end - limit + 1)
                    rows = []
                    if end >= 1:
                        typ_f, msgdata = conn.fetch(f'{lo}:{end}', HEADERS)
                        if typ_f != 'OK':
                            raise MailError('failed', 'Не удалось получить список писем')
                        rows = parse_header_rows(msgdata, 'to' if role in ('sent', 'drafts') else 'from')
                    return {'rows': rows, 'total': total, 'more': lo > 1}
            crit = {'all': [], 'unread': ['UNSEEN'], 'flagged': ['FLAGGED']}.get(flt, [])
            more, text = parse_query(q)
            crit = (crit + more) or ['ALL']
            if text:
                conn.literal = text.encode('utf-8')
                typ, data = conn.uid('SEARCH', 'CHARSET', 'UTF-8', *crit, 'TEXT')
            else:
                typ, data = conn.uid('SEARCH', None, *crit)
            if typ != 'OK':
                raise MailError('failed', 'Поиск не удался')
            uids = (data[0] or b'').split()
            total = len(uids)
            end = max(0, total - offset)
            chunk = uids[max(0, end - limit):end]
            rows = []
            if chunk:
                typ_f, msgdata = conn.uid('fetch', b','.join(chunk), HEADERS)
                if typ_f != 'OK':
                    raise MailError('failed', 'Не удалось получить список писем')
                rows = parse_header_rows(msgdata, 'to' if role in ('sent', 'drafts') else 'from')
            return {'rows': rows, 'total': total, 'more': end - len(chunk) > 0}
        res = self.run(go)
        if plain:
            self.pages[role] = res
            self.page_at[role] = time.monotonic()
        return {**res, 'cached': False, 'fresh': True}

    @staticmethod
    def _message_count(conn, raw: str) -> int | None:
        try:
            typ, data = conn.status(_q(raw), '(MESSAGES)')
            m = re.search(r'MESSAGES\s+(\d+)', data[0].decode('utf-8', errors='replace') if typ == 'OK' and data and data[0] else '', re.I)
            return int(m.group(1)) if m else None
        except Exception:
            return None

    def snippets(self, role: str, uids: list[str]) -> dict[str, str]:
        """One-line previews for the given letters, fetched in one request and remembered (the text of a letter does not change)."""
        from . import mail_snippet
        with self.lock:
            have = {u: self.snips[(role, u)] for u in uids if (role, u) in self.snips}
        need = [u for u in uids if u not in have]
        for i in range(0, len(need), SNIP_BATCH):
            batch = need[i:i + SNIP_BATCH]

            def go(conn, batch=batch):
                self._select(conn, role)
                typ, data = conn.uid('fetch', ','.join(batch).encode('ascii'),
                                     f'(UID BODY.PEEK[HEADER.FIELDS (CONTENT-TYPE CONTENT-TRANSFER-ENCODING)] BODY.PEEK[TEXT]<0.{mail_snippet.PREVIEW_BYTES}>)')
                return mail_snippet.parse_fetch(data) if typ == 'OK' else {}
            got = self.run(go)       # the lock is free between batches, so opening a letter does not wait for the whole page of previews
            with self.lock:
                if len(self.snips) > 3000:
                    self.snips.clear()
                for u in batch:
                    head, body = got.get(u, (b'', b''))
                    have[u] = self.snips[(role, u)] = mail_snippet.snippet(head, body)
        return have

    def patch_page(self, role: str, uid: str, **changes):
        page = self.pages.get(role)
        if not page:
            return
        if changes.get('gone'):
            page['rows'] = [r for r in page['rows'] if r['uid'] != uid]
            page['total'] = max(0, page['total'] - 1)
            return
        for r in page['rows']:
            if r['uid'] == uid:
                r.update(changes)

    def _mark_seen(self, role: str, uid: str) -> bool:
        """Sets the Seen flag on the server if it is missing; returns whether the letter was unread."""
        def go(conn):
            self._select(conn, role)
            typ, data = conn.uid('fetch', uid.encode('ascii'), '(FLAGS)')
            head = ' '.join((d[0] if isinstance(d, tuple) else d).decode('ascii', errors='ignore') for d in (data or []) if isinstance(d, (bytes, tuple)))
            if typ != 'OK' or re.search(r'FLAGS\s*\([^)]*\\Seen', head, re.I):
                return False
            try:
                conn.uid('STORE', uid.encode('ascii'), '+FLAGS', r'(\Seen)')
            except Exception:
                _log.debug('mark seen failed', exc_info=True)
                return False
            return True
        done = self.run(go)
        if done:
            self.unread = None
        return done

    # -- the Seen flag of an opened letter is stored after the letter is shown (it used to cost the reader one more round trip) --
    def _mark_later(self, role: str, uid: str):
        with self.lock:
            self.seen_todo[(role, uid)] = None
        threading.Thread(target=self._seen_worker, daemon=True, name='imap-seen').start()

    def _seen_worker(self):
        try:
            with self.lock:
                self.run(self._flush_seen)
        except Exception:
            _log.debug('storing the Seen flags failed', exc_info=True)

    def _flush_seen(self, conn):
        while self.seen_todo:
            (role, uid), _ = self.seen_todo.popitem(last=False)
            try:
                self._select(conn, role)
                conn.uid('STORE', uid.encode('ascii'), '+FLAGS', r'(\Seen)')
                self.unread = None
            except (imaplib.IMAP4.abort, OSError, ssl.SSLError):
                self.pages.pop(role, None)      # the list showed it as read; let the next listing ask the server
                raise
            except Exception:
                _log.debug('mark seen failed', exc_info=True)
                self.pages.pop(role, None)

    def _forget_seen(self, role: str, uids=None):
        """A later change to these letters (unread again, moved, deleted) replaces the pending Seen flag."""
        with self.lock:
            for key in [k for k in self.seen_todo if k[0] == role and (uids is None or k[1] in uids)]:
                del self.seen_todo[key]

    def settle(self, timeout: float = 2.0):
        """Waits until the pending Seen flags are stored (the tests and a clean shutdown use it)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                if not self.seen_todo:
                    return
            time.sleep(0.005)

    # -- one letter --
    def message(self, role: str, uid: str, mark: bool = True):
        """Returns (parsed email message, was unread). Cached for a few letters, so toggling images or reopening is instant."""
        key = (role, uid)
        with self.lock:
            hit = self.bodies.get(key)
            if hit is not None:
                self.bodies.move_to_end(key)
        if hit is not None:
            # A body cached by a no-mark read (snippet prefetch, attachment, preview) must still mark the letter when it is opened.
            if not mark:
                return hit, False
            row = next((r for r in (self.pages.get(role) or {}).get('rows', []) if r['uid'] == uid), None)
            if row is None:
                unread = self._mark_seen(role, uid)      # a letter outside the cached listing: ask the server, which flags it at once
            else:
                unread = bool(row.get('unread'))         # the listing knows; the flag is stored in the background
                if unread:
                    self._mark_later(role, uid)
            if unread:
                self.patch_page(role, uid, unread=False)
            return hit, unread

        def go(conn):
            self._select(conn, role)
            typ, data = conn.uid('fetch', uid.encode('ascii'), '(FLAGS BODY.PEEK[])')
            if typ != 'OK' or not data or not isinstance(data[0], tuple) or not isinstance(data[0][1], (bytes, bytearray)):
                raise MailError('failed', 'Не удалось загрузить письмо')
            head = data[0][0].decode('ascii', errors='ignore') + ' ' + ''.join(d.decode('ascii', errors='ignore') for d in data[1:] if isinstance(d, bytes))
            unread = not re.search(r'FLAGS\s*\([^)]*\\Seen', head, re.I)
            raw = bytes(data[0][1])
            return raw, unread
        raw, unread = self.run(go)
        msg = BytesParser(policy=email_policy).parsebytes(raw)
        if len(raw) <= _BODY_CACHE_BYTES:
            with self.lock:
                self.bodies[key] = msg
                while len(self.bodies) > _BODY_CACHE_MAX:
                    self.bodies.popitem(last=False)
        if unread and mark:
            self._mark_later(role, uid)
            self.patch_page(role, uid, unread=False)
        return msg, unread

    # -- changes --
    def set_flag(self, role: str, uids: list[str], flag: str, on: bool):
        self._forget_seen(role, set(uids))
        imap_flag = {'seen': r'\Seen', 'flagged': r'\Flagged'}[flag]

        def go(conn):
            self._select(conn, role)
            typ, _ = conn.uid('STORE', ','.join(uids).encode('ascii'), '+FLAGS' if on else '-FLAGS', f'({imap_flag})')
            if typ != 'OK':
                raise MailError('failed', 'Сервер не принял изменение')
        self.run(go)
        self.unread = None
        for uid in uids:
            self.patch_page(role, uid, **({'unread': not on} if flag == 'seen' else {'flagged': on}))

    def remove(self, role: str, uids: list[str], to: str = '') -> str:
        """Moves letters to `to` (trash, archive, junk or a folder id) or deletes them for good. Returns where they ended up."""
        self._forget_seen(role, set(uids))
        def go(conn):
            self._select(conn, role)
            dest = self.folder_map(conn).get(to) if to and to != role else None
            if to and not dest and to != 'trash':
                raise MailError('no_folder')
            uid_set = ','.join(uids).encode('ascii')
            if dest:
                typ, _ = conn.uid('COPY', uid_set, _q(dest))
                if typ != 'OK':
                    raise MailError('failed', 'Сервер не принял перенос письма')
            typ, _ = conn.uid('STORE', uid_set, '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                raise MailError('failed', 'Сервер не принял удаление')
            try:
                conn.expunge()
            except Exception:
                _swallow()
            return to if dest else 'gone'
        where = self.run(go)
        self.unread = None
        for uid in uids:
            self.patch_page(role, uid, gone=True)
            self.bodies.pop((role, uid), None)
        self.pages.pop(where, None)
        return where

    def mark_all_read(self, role: str):
        self._forget_seen(role)
        def go(conn):
            self._select(conn, role)
            typ, _ = conn.uid('STORE', '1:*', '+FLAGS', r'(\Seen)')
            if typ != 'OK':
                raise MailError('failed', 'Сервер не принял изменение')
        self.run(go)
        self.unread = None
        for r in (self.pages.get(role) or {}).get('rows', []):
            r['unread'] = False

    def empty(self, role: str):
        """Deletes everything in a folder for good (the caller only allows trash and junk)."""
        self._forget_seen(role)
        def go(conn):
            self._select(conn, role)
            typ, _ = conn.uid('STORE', '1:*', '+FLAGS', r'(\Deleted)')
            if typ != 'OK':
                raise MailError('failed', 'Сервер не принял удаление')
            conn.expunge()
        self.run(go)
        self.unread = None
        self.pages.pop(role, None)
        self.bodies.clear()

    def append(self, role: str, raw: bytes, flags: str = r'(\Draft \Seen)'):
        def go(conn):
            dest = self.folder_map(conn).get(role)
            if not dest:
                raise MailError('no_folder')
            typ, _ = conn.append(_q(dest), flags, imaplib.Time2Internaldate(time.time()), raw)
            if typ != 'OK':
                raise MailError('failed', 'Сервер не принял черновик')
        self.run(go)
        self.pages.pop(role, None)


SESSION = Session()
