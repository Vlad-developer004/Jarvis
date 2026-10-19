"""ui_next/bridge/cinema.py and the `media` command: the Cinema screen backend."""
import pytest

import core.settings_io as sio
from actions import now_playing as np
from ui_next import bridge
from ui_next.bridge import cinema as bc


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    opened = []
    monkeypatch.setattr(bc.webbrowser, 'open', lambda u: opened.append(u) or True)
    return opened


def run(**kw):
    return bridge.run_command('cinema', kw)


def test_state_lists_services_and_the_presets_still_to_add(env):
    r = run(op='state')
    assert r['ok'] and [s['id'] for s in r['services']] == ['youtube'] and r['default'] == 'youtube' and r['services'][0]['own_search'] is True
    assert 'youtube' not in [p['id'] for p in r['presets']] and '1plus1' in [p['id'] for p in r['presets']] and 'teleportal' in [p['id'] for p in r['presets']]


def test_add_default_remove_round_trip(env):
    r = run(op='add', name='1+1 video', domain='1plus1.video')
    assert [s['id'] for s in r['services']] == ['youtube', '1plus1'] and '1plus1' not in [p['id'] for p in r['presets']]
    assert run(op='default', id='1plus1')['default'] == '1plus1'
    assert run(op='remove', id='1plus1')['default'] == 'youtube'
    assert run(op='add', name='', domain='x.com')['error'] == 'required' and run(op='add', name='X', domain='???')['error'] == 'bad_domain'
    assert run(op='nope')['error'] == 'bad_op'


def test_watch_opens_the_chosen_services_search(env):
    run(op='add', name='1+1 video', domain='1plus1.video')
    r = run(op='watch', title='Дюна', id='1plus1', kind='movie')
    assert r['ok'] and r['service'] == '1+1 video' and env == [r['url']] and 'site%3A1plus1.video' in r['url']
    r = run(op='watch', title='Шерлок', kind='series', season=2, episode='3')
    assert r['service'] == 'YouTube' and '%D1%81%D0%B5%D0%B7%D0%BE%D0%BD+2+%D1%81%D0%B5%D1%80%D0%B8%D1%8F+3' in r['url']
    assert run(op='watch', title=' ')['error'] == 'required'


def test_media_state_and_control_validate_their_input(env, monkeypatch):
    monkeypatch.setattr(np, 'snapshot', lambda: [{'id': 'a#0'}])
    sent = []
    monkeypatch.setattr(np, 'control', lambda a, i='', s=0.0: sent.append((a, i, s)) or {'ok': True})
    assert bridge.run_command('media', {'op': 'state'}) == {'ok': True, 'sessions': [{'id': 'a#0'}]}
    assert bridge.run_command('media', {'op': 'control', 'action': 'seek_by', 'id': 'a#0', 'seconds': '-10'})['ok'] and sent == [('seek_by', 'a#0', -10.0)]
    assert bridge.run_command('media', {'op': 'control', 'action': 'seek_by', 'seconds': 'x'})['error'] == 'bad_value'
    assert bridge.run_command('media', {'op': 'zzz'})['error'] == 'bad_op'
