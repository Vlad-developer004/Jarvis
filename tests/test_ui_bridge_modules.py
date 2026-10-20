"""ui_next/bridge/modules.py: the Modules settings of the new UI (profile, switches, briefing, restart)."""
import json

import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import modules as md


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    refreshed = []
    monkeypatch.setattr(md, '_refresh', lambda: refreshed.append(1))
    import actions.briefing_config as bc
    monkeypatch.setattr(bc, '_SETTINGS_PATH', path)
    return {'path': path, 'refreshed': refreshed}


def run(**kw):
    return bridge.run_command('modules', kw)


def settings(env):
    return json.loads(env['path'].read_text(encoding='utf-8'))


def mod(r, key):
    return next(m for m in r['modules'] if m['key'] == key)


def test_state_follows_the_profile(env):
    r = run(op='state')
    assert r['profile'] == 'minimal' and r['profiles'] == ['full', 'assistant', 'minimal'] and len(r['modules']) == 16
    assert mod(r, 'games')['on'] is False and mod(r, 'system_monitoring')['on'] is True and not any(m['manual'] for m in r['modules'])
    r = run(op='profile', profile='FULL')
    assert r['profile'] == 'full' and mod(r, 'games')['on'] is True and settings(env)['feature_profile'] == 'full' and settings(env)['keep'] == 1
    assert run(op='profile', profile='turbo')['error'] == 'bad_value'


def test_a_switch_equal_to_its_profile_is_not_stored(env):
    r = run(op='module', key='games', on=True)
    assert mod(r, 'games') == {'key': 'games', 'on': True, 'preset': False, 'manual': True} and settings(env)['feature_modules'] == {'games': True}
    r = run(op='module', key='games', on=False)
    assert mod(r, 'games')['manual'] is False and settings(env)['feature_modules'] == {}
    assert run(op='module', key='nope', on=True)['error'] == 'bad_value' and run(op='module', key='games', on='yes')['error'] == 'bad_value'
    assert len(env['refreshed']) == 2


def test_manual_switches_survive_a_profile_change_and_can_be_reset(env):
    run(op='module', key='games', on=True)
    run(op='module', key='updater', on=True)
    r = run(op='profile', profile='assistant')
    assert mod(r, 'games')['on'] is True and mod(r, 'games')['manual'] is True and mod(r, 'updater')['manual'] is False       # updater equals the assistant preset
    r = run(op='reset')
    assert mod(r, 'games')['on'] is False and not any(m['manual'] for m in r['modules'])


def test_reset_keeps_switches_that_belong_to_other_screens(env):
    env['path'].write_text('{"feature_modules": {"games": true, "remote_control": true}}', encoding='utf-8')
    run(op='reset')
    assert settings(env)['feature_modules'] == {'remote_control': True}


def test_briefing_keeps_foreign_keys_and_validates(env):
    env['path'].write_text('{"briefing": {"calendar_reminder_minutes": 20, "other": 5}}', encoding='utf-8')
    r = run(op='briefing', key='include_weather', value=False)
    assert r['briefing']['include_weather'] is False and r['briefing']['calendar_reminder_minutes'] == 20 and settings(env)['briefing']['other'] == 5
    assert run(op='briefing', key='calendar_reminder_minutes', value=45)['briefing']['calendar_reminder_minutes'] == 45
    assert run(op='briefing', key='calendar_reminder_minutes', value=0)['error'] == 'bad_value'
    assert run(op='briefing', key='calendar_reminder_minutes', value=121)['error'] == 'bad_value'
    assert run(op='briefing', key='include_time', value='no')['error'] == 'bad_value'
    assert run(op='briefing', key='sql', value=True)['error'] == 'bad_value'


def test_unknown_op(env):
    assert run(op='x')['error'] == 'bad_op'


def test_no_ai_in_the_wizard_is_the_qa_switch_and_survives_a_profile_change(env):
    # The wizard's "Без ИИ" tile: AI answers off on a profile that has them, back on when a provider is picked again.
    r = run(op='profile', profile='full')
    assert mod(r, 'qa')['on'] is True
    r = run(op='module', key='qa', on=False)
    assert mod(r, 'qa') == {'key': 'qa', 'on': False, 'preset': True, 'manual': True} and settings(env)['feature_modules'] == {'qa': False}
    assert mod(run(op='profile', profile='full'), 'qa')['on'] is False
    r = run(op='module', key='qa', on=True)
    assert mod(r, 'qa')['on'] is True and settings(env)['feature_modules'] == {}
