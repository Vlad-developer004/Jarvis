"""ui_next/bridge/mail_watch.py: the background new-mail check (baseline, announcements, switches)."""
import pytest

from ui_next import host
from ui_next.bridge import mail_watch as mw


@pytest.fixture
def env(monkeypatch):
    mw._last.update(uidnext=None, unread=None)
    ev = {'cmd': [], 'notice': [], 'alert': [], 'status': None, 'rows': [], 'notify': True, 'game': False}
    monkeypatch.setattr(mw, '_status', lambda: ev['status'])
    monkeypatch.setattr(mw.SESSION, 'page', lambda *a, **k: {'rows': ev['rows']})
    monkeypatch.setattr(mw, 'notify_enabled', lambda: ev['notify'])
    monkeypatch.setattr(host, 'command', lambda op, **a: ev['cmd'].append((op, a)) or True)
    monkeypatch.setattr(host, 'notify', lambda *a, **k: ev['notice'].append(a))
    monkeypatch.setattr(host, 'show_alert', lambda *a, **k: ev['alert'].append((a, k)) or True)
    from core.system import app_state
    monkeypatch.setattr(app_state, 'game_snapshot', lambda: (ev['game'], ''))
    return ev


def row(uid, unread=True, name='Anna', subject='Hi'):
    return {'uid': str(uid), 'name': name, 'addr': 'a@b.c', 'subject': subject, 'unread': unread}


def test_first_check_only_remembers_state(env):
    env['status'] = {'uidnext': 50, 'unread': 7}
    assert mw.check_once() == 0
    assert mw.last_unread() == 7 and not env['alert'] and not env['notice']
    assert env['cmd'] == [('mail', {'unread': 7, 'new': 0})]


def test_new_letter_updates_window_and_announces(env):
    env['status'] = {'uidnext': 50, 'unread': 7}
    mw.check_once()
    env['cmd'].clear()
    env['status'] = {'uidnext': 52, 'unread': 9}
    env['rows'] = [row(51, name='Bob', subject='Report'), row(50), row(49)]
    assert mw.check_once() == 2
    assert env['cmd'] == [('mail', {'unread': 9, 'new': 2})]
    assert 'Новых писем: 2' in env['notice'][0][1] and env['alert'][0][0][0] == 'Новых писем: 2'
    assert 'Bob' in env['alert'][0][0][1]


def test_single_letter_title_and_open_button(env):
    env['status'] = {'uidnext': 10, 'unread': 0}
    mw.check_once()
    env['status'] = {'uidnext': 11, 'unread': 1}
    env['rows'] = [row(10, name='Bob', subject='Report')]
    mw.check_once()
    args, kw = env['alert'][0]
    assert args == ('Новое письмо', 'Bob: Report') and kw['actions'][0]['id'] == 'open'


def test_read_elsewhere_refreshes_badge_without_announcing(env):
    env['status'] = {'uidnext': 50, 'unread': 7}
    mw.check_once()
    env['cmd'].clear()
    env['status'] = {'uidnext': 50, 'unread': 3}
    assert mw.check_once() == 0
    assert env['cmd'] == [('mail', {'unread': 3, 'new': 0})] and not env['alert']


def test_already_read_new_letter_is_not_announced(env):
    env['status'] = {'uidnext': 5, 'unread': 0}
    mw.check_once()
    env['status'] = {'uidnext': 6, 'unread': 0}
    env['rows'] = [row(5, unread=False)]
    assert mw.check_once() == 0 and not env['alert'] and not env['notice']


def test_switch_off_keeps_the_badge_but_stays_quiet(env):
    env['status'] = {'uidnext': 5, 'unread': 0}
    mw.check_once()
    env.update(notify=False, status={'uidnext': 6, 'unread': 1}, rows=[row(5)])
    mw.check_once()
    assert env['cmd'][-1] == ('mail', {'unread': 1, 'new': 1}) and not env['alert'] and not env['notice']


def test_game_mode_shows_only_the_notice(env):
    env['status'] = {'uidnext': 5, 'unread': 0}
    mw.check_once()
    env.update(game=True, status={'uidnext': 6, 'unread': 1}, rows=[row(5)])
    mw.check_once()
    assert env['notice'] and not env['alert']


def test_prefs_notify_flag_roundtrip(monkeypatch):
    from core import settings_io
    from ui_next.bridge import mail as ml
    store = {}
    monkeypatch.setattr(settings_io, 'read', lambda: dict(store))
    monkeypatch.setattr(settings_io, 'update', lambda d: store.update(d))
    assert ml.get_prefs()['notify'] is True
    assert ml.set_prefs(notify=False)['notify'] is False and store == {'mail_notify': False}
    assert ml.set_prefs('  Sig ')['signature'] == 'Sig' and store['mail_notify'] is False
