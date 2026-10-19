"""ui_next/bridge/tools.py: the Tools settings of the new UI (videos, quick links, game-mode list, launch rules, Telegram, updates)."""
import json

import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import tools as tl


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    monkeypatch.setattr(tl, '_GAME_PREFS', str(tmp_path / 'data' / 'game_mode_prefs.json'))
    vids = tmp_path / 'videos.txt'
    monkeypatch.setattr(tl, '_videos_path', lambda: str(vids))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
        monkeypatch.setenv(k, 'x')     # so that teardown removes whatever remote_save puts into os.environ
        monkeypatch.delenv(k)
    return {'path': path, 'vids': vids, 'tmp': tmp_path}


def run(**kw):
    return bridge.run_command('tools', kw)


def settings(env):
    return json.loads(env['path'].read_text(encoding='utf-8'))


def test_state_defaults(env):
    r = run(op='state')
    assert r['ok'] and r['max_videos'] == 10 and r['videos'] == [] and r['meetings'] == [] and r['keep'] == [] and r['launch'] == {}
    assert r['remote']['token_set'] is False and r['update']['auto'] is True


def test_max_videos_is_validated_and_saved(env):
    assert run(op='max_videos', n=25)['max_videos'] == 25 and settings(env)['max_saved_videos'] == 25 and settings(env)['keep'] == 1
    assert run(op='max_videos', n=0)['error'] == 'bad_value'
    assert run(op='max_videos', n=51)['error'] == 'bad_value'
    assert run(op='max_videos', n='x')['error'] == 'bad_value'


def test_saved_videos_newest_first_and_delete(env):
    env['vids'].write_text('2026-01-01 10:00 - https://youtu.be/aaaaaaaaaaa\nbroken line\n2026-01-02 11:00 - https://youtu.be/bbbbbbbbbbb\n', encoding='utf-8')
    r = run(op='state')
    assert [v['url'] for v in r['videos']] == ['https://youtu.be/bbbbbbbbbbb', 'https://youtu.be/aaaaaaaaaaa'] and r['videos_total'] == 2
    r = run(op='video_del', ts='2026-01-02 11:00', url='https://youtu.be/bbbbbbbbbbb')
    assert r['ok'] and [v['url'] for v in r['videos']] == ['https://youtu.be/aaaaaaaaaaa']
    assert run(op='video_del', ts='x', url='y')['error'] == 'not_found'


def test_quick_links(env):
    r = run(op='meeting_add', phrase='  Стендап ', url='https://zoom.us/j/123', name='')
    assert r['ok'] and r['meetings'] == [{'name': 'стендап', 'phrase': 'стендап', 'url': 'https://zoom.us/j/123'}]
    assert settings(env)['meetings'][0]['phrase'] == 'стендап'
    assert run(op='meeting_add', phrase='стендап', url='https://a.b')['error'] == 'exists'
    assert run(op='meeting_add', phrase='x', url='javascript:alert(1)')['error'] == 'bad_url'
    assert run(op='meeting_add', phrase='x', url='file:///c:/x')['error'] == 'bad_url'
    assert run(op='meeting_add', phrase='', url='https://a.b')['error'] == 'required'
    assert run(op='meeting_del', phrase='стендап')['meetings'] == [] and run(op='meeting_del', phrase='стендап')['error'] == 'not_found'


def test_game_mode_keep_list_keeps_other_keys(env):
    f = env['tmp'] / 'data'
    f.mkdir()
    (f / 'game_mode_prefs.json').write_text('{"other": 7}', encoding='utf-8')
    assert run(op='keep_add', title=' Spotify ')['keep'] == ['spotify']
    assert run(op='keep_add', title='spotify')['error'] == 'exists'
    assert json.loads((f / 'game_mode_prefs.json').read_text(encoding='utf-8')) == {'other': 7, 'keep_titles': ['spotify']}
    assert run(op='keep_del', title='Spotify')['keep'] == [] and run(op='keep_del', title='nope')['error'] == 'not_found'


def test_launch_rules(env):
    r = run(op='launch_set', app='C:\\Apps\\Discord.EXE', mode='new')
    assert r['launch'] == {'discord': 'new'} and settings(env)['app_launch_rules'] == {'discord': 'new'}
    assert run(op='launch_set', app='discord', mode='switch')['launch'] == {'discord': 'switch'}
    assert run(op='launch_set', app='discord', mode='weird')['error'] == 'bad_value'
    assert run(op='launch_del', app='DISCORD')['launch'] == {} and run(op='launch_del', app='x')['error'] == 'not_found'


def test_telegram_is_validated_and_the_token_never_comes_back(env, monkeypatch):
    saved = {}
    import actions.mail_client as mc
    monkeypatch.setattr(mc, '_update_env_var', lambda k, v: saved.__setitem__(k, v))
    monkeypatch.setattr(tl, '_set_module', lambda n, on: saved.__setitem__('mod', (n, on)))
    assert run(op='remote_save', token='abc', chat_id='123456')['error'] == 'bad_value'
    assert run(op='remote_save', token='', chat_id='123456')['error'] == 'required'
    tok = '123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw'
    r = run(op='remote_save', token=tok, chat_id='-1001234567')
    assert r['ok'] and saved['TELEGRAM_BOT_TOKEN'] == tok and saved['TELEGRAM_CHAT_ID'] == '-1001234567' and saved['mod'] == ('remote_control', True)
    assert r['remote']['token_set'] is True and r['remote']['chat_id'] == '-1001234567'
    assert tok not in json.dumps(r) and tok not in json.dumps(run(op='state'))
    # only the chat changes: the saved token is kept
    assert run(op='remote_save', token='', chat_id='42424242')['ok'] and saved['TELEGRAM_BOT_TOKEN'] == tok


def test_updates(env, monkeypatch):
    assert run(op='auto_update', on=False)['update']['auto'] is False and settings(env)['auto_update_enabled'] is False
    from core.system import app_updater
    monkeypatch.setattr(app_updater, 'is_update_staged', lambda: False)
    assert run(op='update_install')['error'] == 'not_ready'


def test_unknown_op(env):
    assert run(op='nope')['error'] == 'bad_op'


def test_a_quick_link_can_be_changed(env):
    run(op='meeting_add', phrase='пара', url='https://zoom.us/j/1', name='Математика')
    run(op='meeting_add', phrase='лекция', url='https://meet.google.com/x')
    r = run(op='meeting_edit', old='ПАРА', phrase=' Пара по матану ', url='https://teams.microsoft.com/l/1', name='')
    assert r['ok'] and r['meetings'][0] == {'name': 'пара по матану', 'phrase': 'пара по матану', 'url': 'https://teams.microsoft.com/l/1'}
    assert len(r['meetings']) == 2 and settings(env)['meetings'][1]['phrase'] == 'лекция'
    assert run(op='meeting_edit', old='пара по матану', phrase='лекция', url='https://a.b')['error'] == 'exists'     # another link already uses it
    assert run(op='meeting_edit', old='пара по матану', phrase='пара по матану', url='https://c.d')['ok']               # the same phrase is fine
    assert run(op='meeting_edit', old='нет такой', phrase='x', url='https://a.b')['error'] == 'not_found'
    assert run(op='meeting_edit', old='лекция', phrase='x', url='ftp://a.b')['error'] == 'bad_url'
    assert run(op='meeting_edit', old='лекция', phrase='', url='https://a.b')['error'] == 'required'


def test_video_details_are_fetched_in_the_background_and_only_for_youtube_ids(env, monkeypatch):
    from ui_next.bridge import video_meta as vmeta
    monkeypatch.setattr(vmeta, '_cache', {})
    monkeypatch.setattr(vmeta, '_pending', set())
    asked = []

    def fake(vid):
        asked.append(vid)
        with vmeta._lock:
            vmeta._cache[vid] = {'title': 'Песня', 'author': 'Автор', 'thumb': 'data:image/jpeg;base64,AAA', 'duration': '3:21', 'at': 0.0}
            vmeta._pending.discard(vid)
    monkeypatch.setattr(vmeta, '_fetch', fake)
    urls = ['https://youtu.be/dQw4w9WgXcQ', 'https://example.com/evil?v=zzzzzzzzzzz', 'not a url', 5]
    r = run(op='video_meta', urls=urls)
    assert r['ok'] and r['pending'] >= 0
    import time
    end = time.time() + 2
    while time.time() < end and not asked:
        time.sleep(0.01)
    assert asked == ['dQw4w9WgXcQ']                                         # the foreign address and the garbage were never requested
    r = run(op='video_meta', urls=urls)
    assert r['items'] == {'https://youtu.be/dQw4w9WgXcQ': {'title': 'Песня', 'author': 'Автор', 'thumb': 'data:image/jpeg;base64,AAA', 'duration': '3:21'}} and r['pending'] == 0
    assert 'videos' not in r                                                 # a lookup does not return the whole state
    assert run(op='video_meta', urls='x')['items'] == {}
