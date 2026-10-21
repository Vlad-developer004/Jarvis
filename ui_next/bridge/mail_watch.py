"""Background check for new mail, so the window learns about a letter without being open on the Mail screen.

Once a minute the shared IMAP connection (imapsession.SESSION) is asked for the Inbox UIDNEXT and unread count, which is one cheap STATUS call.
A higher UIDNEXT means new letters: the first page of the Inbox is refreshed (the Mail screen then shows it from the cache), the window gets a
`mail` command (sidebar badge, list refresh) and, when notifications are on, a notice in the header strip plus a pop-up with an "open" button.
The pop-up is skipped in game mode; the first check after start only remembers the state, so old unread mail is not announced again.
"""
from __future__ import annotations

import logging
import re
import threading

from .imapsession import SESSION, MailError, _q

_log = logging.getLogger(__name__)
INTERVAL = 60
FIRST_DELAY = 15
_stop = threading.Event()
_thread: threading.Thread | None = None
_last = {'uidnext': None, 'unread': None}


def last_unread() -> int | None:
    """Unread count from the latest check (None before the first one), for a window that connects later."""
    return _last['unread']


def notify_enabled() -> bool:
    from core import settings_io
    return settings_io.read().get('mail_notify', True) is not False


def _status() -> dict:
    def go(conn):
        raw = SESSION.folder_map(conn).get('inbox')
        if not raw:
            raise MailError('no_folder')
        typ, data = conn.status(_q(raw), '(UIDNEXT UNSEEN)')
        text = data[0].decode('utf-8', errors='replace') if typ == 'OK' and data and data[0] else ''
        nxt, unseen = re.search(r'UIDNEXT\s+(\d+)', text, re.I), re.search(r'UNSEEN\s+(\d+)', text, re.I)
        if not nxt:
            raise MailError('failed', 'STATUS gave no UIDNEXT')
        return {'uidnext': int(nxt.group(1)), 'unread': int(unseen.group(1)) if unseen else 0}
    return SESSION.run(go)


def _announce(fresh: list[dict]) -> None:
    from ui_next import host
    first = fresh[0]
    who, subj = first['name'] or first['addr'] or 'Без отправителя', first['subject'] or 'Без темы'
    if len(fresh) == 1:
        title, text = 'Новое письмо', f'{who}: {subj}'
    else:
        title, text = f'Новых писем: {len(fresh)}', f'Последнее от {who}: {subj}'
    host.toast('mail', title, text, actions=[{'id': 'open', 'label': 'Открыть почту', 'primary': True}],
               done=lambda status, value: host.open_view('mail') if status == 'ok' and value == 'open' else None)


def check_once() -> int:
    """One check. Returns how many new unread letters were found (0 on the first run, when nothing is announced)."""
    from ui_next import host
    st = _status()
    prev_next, prev_unread = _last['uidnext'], _last['unread']
    _last.update(st)
    if prev_next is None:
        host.command('mail', unread=st['unread'], new=0)
        return 0
    fresh: list[dict] = []
    if st['uidnext'] > prev_next:
        rows = SESSION.page('inbox', 'all', '', 0, 40, True)['rows']
        fresh = [r for r in rows if int(r['uid']) >= prev_next and r['unread']]
    if fresh or st['unread'] != prev_unread:
        host.command('mail', unread=st['unread'], new=len(fresh))
    if fresh and notify_enabled():
        _announce(fresh)
    return len(fresh)


def _loop() -> None:
    from . import mail as ml
    wait = FIRST_DELAY                      # the first check only takes a baseline; it waits until start-up is done
    while not _stop.wait(wait):
        wait = INTERVAL
        try:
            if ml.configured()['configured']:
                check_once()
            else:
                _last.update(uidnext=None, unread=None)
        except MailError as ex:
            _log.debug('mail check failed: %s', ex.code)
        except Exception:
            _log.warning('mail watcher tick failed', exc_info=True)


def start_mail_watch() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name='mail-watch')
    _thread.start()
