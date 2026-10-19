"""ui_next/bridge/backup.py: settings backup and restore (no secrets, no machine-bound values, confirmation by token)."""
import json

import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import backup


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    settings = {'theme': 'dark', 'ai_provider': 'groq', 'meetings': [{'name': 'x', 'phrase': 'p', 'url': 'https://a.b'}], 'mail_account': {'email': 'me@x.y', 'password': 'hunter2', 'imap_port': 993},
                'telegram_token': '123:abc', 'audio_input_device_index': 3, 'zoom_factor': 2.0, 'last_location': {'city': 'Kyiv'}, 'GROQ_API_KEY': 'gsk_secret', 'bad key': 1}
    path.write_text(json.dumps(settings), encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    from actions import calendar_hub as hub
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    return {'path': path, 'dir': tmp_path, 'hub': hub}


def test_the_file_has_no_secrets_and_no_machine_values(env):
    out = env['dir'] / 'b.json'
    r = backup.export({'jarvisTheme': 'space', 'evil': 'x'}, str(out))
    text = out.read_text(encoding='utf-8')
    d = json.loads(text)
    assert r['ok'] and d['format'] == 'jarvis-backup' and d['ui'] == {'jarvisTheme': 'space'}
    assert d['settings']['theme'] == 'dark' and d['settings']['mail_account'] == {'email': 'me@x.y', 'imap_port': 993}
    for gone in ('hunter2', '123:abc', 'gsk_secret', 'audio_input_device_index', 'zoom_factor', 'Kyiv', 'bad key'):
        assert gone not in text


def test_export_dialog_cancel(env, monkeypatch):
    monkeypatch.setattr('ui_next.bridge.filepick.save_file', lambda *a, **k: '')
    assert bridge.run_command('backup', {'op': 'export'})['error'] == 'cancelled'


def test_calendar_events_travel_and_are_not_duplicated(env):
    hub = env['hub']
    hub.add_local({'title': 'Встреча', 'date': '2030-01-02', 'time': '10:00'})
    out = env['dir'] / 'b.json'
    assert backup.export(None, str(out))['events'] == 1
    p = backup.preview(str(out))
    assert p['events'] == 1
    r = backup.apply(p['token'])
    assert r['ok'] and r['events_added'] == 0 and len(hub.load_local()) == 1


def test_restore_is_two_steps_and_keeps_a_copy(env):
    out = env['dir'] / 'b.json'
    backup.export(None, str(out))
    env['path'].write_text(json.dumps({'theme': 'light', 'ai_provider': 'openai', 'mail_account': {'password': 'keep-me'}}), encoding='utf-8')
    p = backup.preview(str(out))
    assert p['ok'] and p['settings'] >= 3 and json.loads(env['path'].read_text(encoding='utf-8'))['theme'] == 'light'      # nothing changed yet
    r = backup.apply(p['token'])
    now = json.loads(env['path'].read_text(encoding='utf-8'))
    assert r['ok'] and now['theme'] == 'dark' and now['ai_provider'] == 'groq'
    assert now['mail_account'] == {'email': 'me@x.y', 'imap_port': 993, 'password': 'keep-me'}
    before = json.loads((env['dir'] / 'jarvis_settings.before_restore.json').read_text(encoding='utf-8'))
    assert before['theme'] == 'light'
    assert backup.apply(p['token'])['error'] == 'expired'


def test_secrets_in_a_hand_edited_file_are_ignored_on_restore(env):
    f = env['dir'] / 'evil.json'
    f.write_text(json.dumps({'format': 'jarvis-backup', 'version': 1, 'settings': {'theme': 'x', 'GROQ_API_KEY': 'stolen', 'a/b': 1, 'audio_input_device_index': 9, 'nested': {'token': 't', 'ok': 1}}}), encoding='utf-8')
    p = backup.preview(str(f))
    backup.apply(p['token'])
    now = json.loads(env['path'].read_text(encoding='utf-8'))
    assert now['theme'] == 'x' and now['audio_input_device_index'] == 3 and now['GROQ_API_KEY'] == 'gsk_secret' and now['nested'] == {'ok': 1} and 'a/b' not in now


@pytest.mark.parametrize('content', ['not json', '[]', '{"format": "other", "version": 1, "settings": {}}', '{"format": "jarvis-backup", "version": 99, "settings": {}}', '{"format": "jarvis-backup", "version": 1}'])
def test_bad_files_are_refused(env, content):
    f = env['dir'] / 'x.json'
    f.write_text(content, encoding='utf-8')
    assert backup.preview(str(f))['error'] == 'bad_file'
    assert backup.preview(str(env['dir'] / 'missing.json'))['error'] == 'bad_file'


def test_the_screen_cannot_name_a_path(env, monkeypatch):
    seen = []
    monkeypatch.setattr('ui_next.bridge.filepick.pick_files', lambda *a, **k: seen.append(1) or [])
    assert bridge.run_command('backup', {'op': 'preview', 'path': 'C:/Windows/win.ini'})['error'] == 'cancelled' and seen == [1]
    assert bridge.run_command('backup', {'op': 'nope'})['error'] == 'bad_op' and bridge.run_command('backup', {'op': 'apply', 'token': 'zz'})['error'] == 'expired'
