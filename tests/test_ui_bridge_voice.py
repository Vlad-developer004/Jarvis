import json

import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import voice as vc


class FakeEngine:
    """The audio loop: records the live parameters the screen sets."""

    def __init__(self):
        self.calls = []

    def update_params(self, t, g, v):
        self.calls.append((t, g, v))


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    hud = FakeEngine()
    import core.engine.jarvis as eng_mod
    monkeypatch.setattr(eng_mod, 'get_engine', lambda: hud)
    monkeypatch.setattr(vc, '_invalidate_tts', lambda: hud.calls.append('tts-cache'))
    profile = {'threshold': 200, 'gain': 2.5}
    saved = []
    import core.mic_calibration as mc
    monkeypatch.setattr(mc, 'save_profile', lambda t, g, nf=0.0, sr=16000: saved.append((t, g)))
    monkeypatch.setattr(vc, '_profile', lambda: profile)
    return {'path': path, 'hud': hud, 'saved': saved}


def _file(env):
    return json.loads(env['path'].read_text(encoding='utf-8'))


def test_defaults_when_nothing_is_stored(env):
    v = vc.get_all()
    assert v['stt_engine'] == 'gigaam' and v['tts_speed'] == 1.0 and v['night_start'] == [22, 0] and v['night_end'] == [7, 0]
    assert v['wake_word_mode'] == 'continuous' and v['address_mode'] == 'male' and v['volume'] == 1.0


def test_threshold_gain_volume_apply_live_and_persist(env):
    assert vc.set_value('threshold', 350)['ok']
    assert env['hud'].calls[-1] == (350, 2.5, 1.0) and env['saved'][-1] == (350, 2.5)
    assert vc.set_value('gain', 3.46)['ok'] and env['hud'].calls[-1][1] == 3.5
    assert vc.set_value('volume', 0.5)['ok'] and _file(env)['volume'] == 0.5
    assert _file(env)['keep'] == 1                                   # unrelated keys survive
    for key, bad in (('threshold', 5), ('threshold', 5000), ('gain', 9), ('volume', 1.5), ('threshold', 'x')):
        assert vc.set_value(key, bad) == {'ok': False, 'error': 'bad_value'}


def test_speech_settings_validate_and_clear_the_cache(env):
    assert vc.set_value('tts_speed', 1.23)['ok'] and _file(env)['tts_speed'] == 1.25 and 'tts-cache' in env['hud'].calls
    assert vc.set_value('tts_speed', 3)['error'] == 'bad_value'
    assert vc.set_value('tts_unload_timeout', 600)['ok'] and vc.set_value('tts_unload_timeout', 601)['error'] == 'bad_value'
    assert vc.set_value('night_start', [23, 30])['ok'] and _file(env)['tts_night_start'] == 23 and _file(env)['tts_night_start_min'] == 30
    assert vc.set_value('night_end', [25, 0])['error'] == 'bad_value'
    assert vc.set_value('tts_night_enabled', False)['ok'] and _file(env)['tts_night_enabled'] is False
    assert vc.set_value('tts_night_volume', 0.05)['error'] == 'bad_value'


def test_enumerated_and_text_settings(env):
    assert vc.set_value('stt_engine', 'vosk')['ok'] and vc.set_value('stt_engine', 'whisper')['error'] == 'bad_value'
    assert vc.set_value('wake_word_mode', 'single')['ok'] and vc.set_value('wake_word_mode', 'x')['error'] == 'bad_value'
    assert vc.set_value('wake_active_timeout_sec', 47)['ok'] and _file(env)['wake_active_timeout_sec'] == 45
    assert vc.set_value('address_mode', 'female')['ok']
    assert vc.set_value('custom_address', '  мастер  ')['ok']
    f = _file(env)
    assert f['address_mode'] == 'custom' and f['custom_address'] == 'мастер'
    assert vc.set_value('custom_address', 'я' * 80)['ok'] and len(_file(env)['custom_address']) == 30
    assert vc.set_value('nope', 1) == {'ok': False, 'error': 'unknown_key'}


def test_llm_switch_goes_to_feature_modules(env, monkeypatch):
    refreshed = []
    import core.system as system
    monkeypatch.setattr(system, 'refresh_module_flags', lambda: refreshed.append(1), raising=False)
    assert vc.set_value('llm_chat_fallback', True)['ok']
    assert _file(env)['feature_modules']['llm_chat_fallback'] is True and refreshed
    assert vc.get_all()['llm_chat_fallback'] is True


def test_devices_selection_can_be_cleared(env, monkeypatch):
    applied = []
    import core.speech.tts as tts
    monkeypatch.setattr(tts, 'apply_audio_devices', lambda output_device_name=None, input_device_index=None: (applied.append((output_device_name, input_device_index)) or (True, 'ok')))
    assert vc.set_devices(2, 'Speakers')['applied'] is True and applied[-1] == ('Speakers', 2)
    assert _file(env)['audio_input_device_index'] == 2
    assert vc.set_devices(None, '')['ok'] and 'audio_input_device_index' not in _file(env) and 'audio_output_device_name' not in _file(env)
    assert applied[-1] == (None, None)


def test_command_routing(env):
    assert bridge.run_command('voice', {'op': 'get'})['ok'] is True
    assert bridge.run_command('voice', {'op': 'set', 'key': 'tts_speed', 'value': 0.9})['ok'] is True
    assert bridge.run_command('voice', {'op': 'zzz'})['error'] == 'bad_op'
    assert bridge.run_command('voice', {'op': 'say'})['error'] == 'no_handler'


def test_language_setting_switches_the_ui_language(env, monkeypatch):
    from core import i18n
    seen = []
    monkeypatch.setattr(i18n, 'set_language', lambda lang: seen.append(lang))
    assert vc.set_value('language', 'uk')['ok'] and _file(env)['language'] == 'uk' and seen == ['uk']
    assert vc.set_value('language', 'de')['error'] == 'bad_value'
    values = vc.get_all()
    assert values['language'] == 'uk' and values['speech_language'] == 'ru'      # speech stays pinned to Russian


@pytest.fixture
def llm(env, monkeypatch):
    import threading
    import core.speech.llm_chat as chat
    import core.speech.llm_downloader as dl
    from ui_next.bridge import filepick
    events = []
    monkeypatch.setattr(vc, '_pub', lambda topic, payload: events.append((topic, dict(payload))))
    monkeypatch.setattr(chat, 'invalidate_model', lambda: events.append('invalidate'))
    monkeypatch.setattr(dl, 'is_default_model_present', lambda: False)
    monkeypatch.setattr(dl, 'is_downloading', lambda: False)
    vc._llm_busy.update(busy='', pct=0, text='')

    class Sync:                                   # run the picker's worker inline
        def __init__(self, target, **kw):
            self.target = target

        def start(self):
            self.target()
    monkeypatch.setattr(threading, 'Thread', Sync)
    return {'events': events, 'chat': chat, 'dl': dl, 'filepick': filepick, 'mp': monkeypatch}


def test_pick_valid_model_is_stored(env, llm):
    llm['mp'].setattr(llm['filepick'], 'pick_files', lambda title, flt=None, multi=False: [r'C:\models\tiny.gguf'])
    llm['mp'].setattr(llm['chat'], 'validate_gguf_model', lambda path: (True, 'Модель загружается'))
    assert vc.llm_pick() == {'ok': True}
    assert _file(env)['llm_chat_model_path'] == r'C:\models\tiny.gguf' and 'invalidate' in llm['events']
    last = [e for e in llm['events'] if isinstance(e, tuple)][-1][1]
    assert last['busy'] == '' and 'tiny.gguf' in last['text'] and last['custom'] == 'tiny.gguf'


def test_pick_rejected_model_is_not_stored(env, llm):
    llm['mp'].setattr(llm['filepick'], 'pick_files', lambda title, flt=None, multi=False: [r'C:\models\bad.gguf'])
    llm['mp'].setattr(llm['chat'], 'validate_gguf_model', lambda path: (False, 'формат не поддерживается'))
    vc.llm_pick()
    assert 'llm_chat_model_path' not in _file(env) and 'не подошла' in vc.llm_state()['text']


def test_pick_cancelled_changes_nothing(env, llm):
    llm['mp'].setattr(llm['filepick'], 'pick_files', lambda title, flt=None, multi=False: [])
    vc.llm_pick()
    assert 'llm_chat_model_path' not in _file(env) and vc.llm_state()['busy'] == ''


def test_reset_returns_to_default_model(env, llm):
    sio.update({'llm_chat_model_path': 'x.gguf'})
    assert vc.llm_reset() == {'ok': True} and 'llm_chat_model_path' not in _file(env) and 'invalidate' in llm['events']


def test_enabling_the_fallback_downloads_a_missing_default_model(env, llm, monkeypatch):
    started = []
    monkeypatch.setattr(llm['dl'], 'download_default_model', lambda on_progress=None, on_done=None: started.append(1) or True)
    import core.system as system
    monkeypatch.setattr(system, 'refresh_module_flags', lambda: None, raising=False)
    assert vc.set_value('llm_chat_fallback', True)['ok'] and started == [1]
    started.clear()
    sio.update({'llm_chat_model_path': 'mine.gguf'})                     # a custom model means nothing to download
    vc.set_value('llm_chat_fallback', True)
    assert started == []


def test_download_progress_and_cancel(env, llm, monkeypatch):
    captured = {}
    monkeypatch.setattr(llm['dl'], 'download_default_model', lambda on_progress=None, on_done=None: captured.update(p=on_progress, d=on_done) or True)
    cancelled = []
    monkeypatch.setattr(llm['dl'], 'cancel_download', lambda: cancelled.append(1))
    assert vc.llm_download()['ok']
    captured['p'](50, 200)
    assert vc.llm_state()['pct'] == 25
    vc.llm_cancel()
    captured['d'](False, 'cancelled')
    assert cancelled == [1] and vc.llm_state()['text'] == 'Загрузка отменена' and vc.llm_state()['busy'] == ''
    assert vc.llm_download()['ok'] and (captured['p'](1, 1), captured['d'](True, ''))
    assert 'загружена' in vc.llm_state()['text']
