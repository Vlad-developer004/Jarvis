import pytest

from ui_next import bridge
from ui_next.bridge import ext_setup


@pytest.fixture
def store(monkeypatch):
    """In-memory settings / secrets / installed flags instead of the user's real files."""
    c = ext_setup._common()
    st = {'settings': {}, 'env': {}, 'installed': set(), 'flags': {}}
    monkeypatch.setattr(c, '_load_settings', lambda: dict(st['settings']))
    monkeypatch.setattr(c, '_save_settings', lambda s: st['settings'].update(s))
    monkeypatch.setattr(c, '_save_env_key', lambda k, v: st['env'].__setitem__(k, v))
    monkeypatch.setattr(c, '_set_feature_module_flag', lambda k, on: st['flags'].__setitem__(k, on))
    monkeypatch.setattr(ext_setup, 'set_installed', lambda i, on: st['installed'].add(i) if on else st['installed'].discard(i))
    monkeypatch.delenv('TELEGRAM_CHAT_ID', raising=False)
    return st


def test_telegram_chat_id_validation_and_install(store):
    assert ext_setup.save('feature_guard_cam', {'chat_id': 'abc'}) == {'ok': False, 'error': 'bad_chat_id'}
    assert ext_setup.save('feature_guard_cam', {'chat_id': ''}) == {'ok': False, 'error': 'bad_chat_id'}
    assert ext_setup.save('feature_guard_cam', {'chat_id': '-100123'}) == {'ok': True}
    assert store['env'] == {'TELEGRAM_CHAT_ID': '-100123'} and 'feature_guard_cam' in store['installed']


def test_telegram_keeps_saved_id_on_empty(store, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '42')
    assert ext_setup.save('feature_guard_cam', {'chat_id': ''}) == {'ok': True}
    assert store['env'] == {}


def test_calendar_sources_split_into_urls_and_paths(store):
    res = ext_setup.save('feature_calendar_ics', {'sources': ['https://x/cal.ics', r'C:\a\b.ics', '  ', 'webcal://y/z']})
    assert res == {'ok': True}
    assert store['settings']['calendar_sources'] == [{'url': 'https://x/cal.ics'}, {'path': r'C:\a\b.ics'}, {'url': 'webcal://y/z'}]
    assert store['flags'] == {'calendar_ics': True}
    assert ext_setup.save('feature_calendar_ics', {'sources': 'nope'})['error'] == 'bad_sources'


def test_mail_validation(store, monkeypatch):
    import actions.mail_client as mc
    saved = []
    monkeypatch.setattr(mc, 'save_mail_account', lambda *a: saved.append(a))
    monkeypatch.setattr(mc, 'get_resolved_mail_config', lambda: None)
    assert ext_setup.save('feature_mail_client', {'email': 'nope', 'password': 'x'})['error'] == 'bad_email'
    assert ext_setup.save('feature_mail_client', {'email': 'a@b.c', 'password': ''})['error'] == 'no_password'
    assert ext_setup.save('feature_mail_client', {'email': 'a@b.c', 'password': ' secret ', 'imap': 'i', 'smtp': 's'}) == {'ok': True}
    assert saved == [('a@b.c', 'secret', 'i', 's', 993, 587)] and store['flags'] == {'inbox_digest': True}


def test_mail_state_never_contains_the_password(store, monkeypatch):
    import actions.mail_client as mc
    monkeypatch.setattr(mc, 'get_resolved_mail_config', lambda: {'password': 'topsecret'})
    store['settings']['mail_account'] = {'email': 'a@b.c', 'imap_host': 'i', 'smtp_host': 's'}
    state = ext_setup.get_state('feature_mail_client')
    assert state['has_password'] is True and 'topsecret' not in repr(state)


def test_command_routing_and_unknown_ids(store):
    assert bridge.run_command('ext_setup', {'id': 'game_hogwarts', 'op': 'get'}) == {'ok': False, 'error': 'unknown_extension'}
    assert bridge.run_command('ext_setup', {'id': 'feature_guard_cam', 'op': 'weird'})['ok'] is False
    assert ext_setup.act('feature_guard_cam', {'action': 'bogus'}) == {'ok': False, 'error': 'bad_action'}
