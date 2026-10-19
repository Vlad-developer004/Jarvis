"""Voice settings for the Voice screen: the same controls as the old settings dialog's voice tab, applied the same way.

    recognition   stt_engine (applied after a restart)
    microphone    threshold, gain (live), input/output devices, headphone mode, calibration
    speech        volume (live), speed, cache retention, night mode (switch, hours, volume)
    activation    wake_word_mode, wake_active_timeout_sec
    address       address_mode (male / female / custom) + custom_address
    local model   llm_chat_fallback switch, llm_chat_unload_timeout

`get_all` returns every value, `set_value` validates one and applies it (with the live side effects the old dialog had). Values live in
jarvis_settings.json through core.settings_io; the mic profile (threshold, gain) in its own file through core.mic_calibration.
"""
from __future__ import annotations

import logging
import threading

from core import settings_io

_log = logging.getLogger(__name__)
_cal_lock = threading.Lock()
_pub = None                       # bridge publish(topic, payload), bound at startup
_llm_busy = {'busy': '', 'pct': 0, 'text': ''}
_calibrating = False
UNLOAD_STEPS = (60, 180, 300, 600, 900, 1800, 3600, 7200, 18000, 0)       # seconds; 0 = keep loaded


def _invalidate_tts() -> None:
    try:
        from core.speech.tts import invalidate_tts_caches
        invalidate_tts_caches()
    except Exception:
        _log.debug('tts cache reset failed', exc_info=True)


def _profile() -> dict:
    try:
        from core.mic_calibration import load_profile
        return load_profile()
    except Exception:
        return {}


def _speech_language() -> str:
    try:
        from core.i18n import get_speech_language
        return get_speech_language()
    except Exception:
        return 'ru'


def _llm_enabled(s: dict) -> bool:
    fm = s.get('feature_modules')
    if isinstance(fm, dict) and 'llm_chat_fallback' in fm:
        return bool(fm['llm_chat_fallback'])
    try:
        from core.system.modules import _PROFILE_PRESETS
        return bool(_PROFILE_PRESETS.get(str(s.get('feature_profile', 'minimal')).strip().lower(), {}).get('llm_chat_fallback', True))
    except Exception:
        return True


def get_all() -> dict:
    s = settings_io.read()
    p = _profile()
    return {
        'stt_engine': s.get('stt_engine', 'gigaam'),
        'threshold': int(p.get('threshold', 200)), 'gain': float(p.get('gain', 2.5)), 'volume': float(s.get('volume', 1.0)),
        'headphone_mode': bool(s.get('headphone_mode', False)),
        'tts_speed': float(s.get('tts_speed', 1.0)), 'tts_unload_timeout': float(s.get('tts_unload_timeout', 300.0)),
        'tts_night_enabled': bool(s.get('tts_night_enabled', True)), 'tts_night_volume': float(s.get('tts_night_volume', 0.7)),
        'night_start': [int(s.get('tts_night_start', 22)), int(s.get('tts_night_start_min', 0))],
        'night_end': [int(s.get('tts_night_end', 7)), int(s.get('tts_night_end_min', 0))],
        'wake_word_mode': s.get('wake_word_mode', 'continuous'), 'wake_active_timeout_sec': float(s.get('wake_active_timeout_sec', 30.0)),
        'address_mode': s.get('address_mode', 'male'), 'custom_address': str(s.get('custom_address') or ''),
        'llm_chat_fallback': _llm_enabled(s), 'llm_chat_unload_timeout': float(s.get('llm_chat_unload_timeout', 600.0)),
        'language': s.get('language', 'ru'), 'speech_language': _speech_language(),
        'unload_steps': list(UNLOAD_STEPS),
    }


# ---- one setter per key: validate, store, apply ----

def _num(v, lo, hi, step=None, cast=float):
    x = float(v)
    if not lo <= x <= hi:
        raise ValueError('range')
    if step:
        x = round(x / step) * step
    return cast(round(x, 3)) if cast is float else cast(round(x))


def _apply_mic(threshold=None, gain=None, volume=None) -> None:
    """Live parameters of the audio loop (what the old sliders did), then the mic profile / volume are stored."""
    p = _profile()
    t = int(threshold if threshold is not None else p.get('threshold', 200))
    g = float(gain if gain is not None else p.get('gain', 2.5))
    v = float(volume if volume is not None else settings_io.read().get('volume', 1.0))
    from core.engine.jarvis import get_engine
    eng = get_engine()
    if eng:
        eng.update_params(t, g, v)
    if threshold is not None or gain is not None:
        from core.mic_calibration import save_profile
        save_profile(t, g, float(p.get('noise_floor', 0)))
    if volume is not None:
        settings_io.update({'volume': v})


def _set_threshold(v):
    _apply_mic(threshold=_num(v, 30, 1200, cast=int))


def _set_gain(v):
    _apply_mic(gain=_num(v, 1.0, 6.0, 0.1))


def _set_volume(v):
    _apply_mic(volume=_num(v, 0.0, 1.0, 0.01))


def _set_stt(v):
    if v not in ('gigaam', 'vosk'):
        raise ValueError('value')
    settings_io.update({'stt_engine': v})


def _set_headphone(v):
    settings_io.update({'headphone_mode': bool(v)})
    try:
        import core.audio_utils as au
        au._last_jarvis_hp_check = 0.0
    except Exception:
        pass


def _set_speed(v):
    settings_io.update({'tts_speed': _num(v, 0.6, 1.4, 0.05)})
    _invalidate_tts()


def _set_unload(v):
    t = float(v)
    if int(t) not in UNLOAD_STEPS:
        raise ValueError('value')
    settings_io.update({'tts_unload_timeout': t})
    try:
        import config_pack.config as cfg
        cfg.TTS_UNLOAD_TIMEOUT = t
    except Exception:
        pass


def _set_night_enabled(v):
    settings_io.update({'tts_night_enabled': bool(v)})


def _hm(v):
    h, m = v
    h, m = int(h), int(m)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError('range')
    return h, m


def _set_night_start(v):
    h, m = _hm(v)
    settings_io.update({'tts_night_start': h, 'tts_night_start_min': m})


def _set_night_end(v):
    h, m = _hm(v)
    settings_io.update({'tts_night_end': h, 'tts_night_end_min': m})


def _set_night_volume(v):
    settings_io.update({'tts_night_volume': _num(v, 0.1, 1.0, 0.05)})
    _invalidate_tts()


def _set_wake_mode(v):
    if v not in ('single', 'continuous'):
        raise ValueError('value')
    s = settings_io.read()
    settings_io.update({'wake_word_mode': v})
    try:
        import config_pack.config as cfg
        cfg.WAKE_WORD_MODE = v
        from core.engine.jarvis import get_engine
        eng = get_engine()
        if eng:
            eng.active_timeout_sec = 0 if v == 'single' else float(s.get('wake_active_timeout_sec', 30.0))
    except Exception:
        _log.debug('wake mode apply failed', exc_info=True)


def _set_wake_timeout(v):
    secs = _num(v, 10, 120, 5)
    s = settings_io.read()
    settings_io.update({'wake_active_timeout_sec': secs})
    try:
        import config_pack.config as cfg
        cfg.WAKE_ACTIVE_TIMEOUT_SEC = secs
        from core.engine.jarvis import get_engine
        eng = get_engine()
        if eng and s.get('wake_word_mode', 'continuous') == 'continuous':
            eng.active_timeout_sec = secs
    except Exception:
        _log.debug('wake timeout apply failed', exc_info=True)


def _set_address_mode(v):
    if v not in ('male', 'female', 'custom'):
        raise ValueError('value')
    settings_io.update({'address_mode': v})
    _invalidate_tts()


def _set_custom_address(v):
    text = str(v).strip()[:30]
    settings_io.update({'address_mode': 'custom', 'custom_address': text})
    _invalidate_tts()


def _set_llm(v):
    s = settings_io.read()
    fm = s.get('feature_modules') if isinstance(s.get('feature_modules'), dict) else {}
    fm['llm_chat_fallback'] = bool(v)
    settings_io.update({'feature_modules': fm})
    try:
        from core.system import refresh_module_flags
        refresh_module_flags()
    except Exception:
        _log.debug('module flags refresh failed', exc_info=True)
    if v:
        _maybe_download_default()


def _set_llm_unload(v):
    t = float(v)
    if int(t) not in UNLOAD_STEPS:
        raise ValueError('value')
    settings_io.update({'llm_chat_unload_timeout': t})


def _set_language(v):
    if v not in ('ru', 'uk'):
        raise ValueError('value')
    settings_io.update({'language': v})
    from core import i18n
    i18n.set_language(v)


_SETTERS = {
    'language': _set_language,
    'stt_engine': _set_stt, 'threshold': _set_threshold, 'gain': _set_gain, 'volume': _set_volume, 'headphone_mode': _set_headphone,
    'tts_speed': _set_speed, 'tts_unload_timeout': _set_unload, 'tts_night_enabled': _set_night_enabled, 'night_start': _set_night_start,
    'night_end': _set_night_end, 'tts_night_volume': _set_night_volume, 'wake_word_mode': _set_wake_mode, 'wake_active_timeout_sec': _set_wake_timeout,
    'address_mode': _set_address_mode, 'custom_address': _set_custom_address, 'llm_chat_fallback': _set_llm, 'llm_chat_unload_timeout': _set_llm_unload,
}


def set_value(key: str, value) -> dict:
    fn = _SETTERS.get(key)
    if fn is None:
        return {'ok': False, 'error': 'unknown_key'}
    try:
        fn(value)
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'bad_value'}
    except Exception:
        _log.exception('voice setting %s failed', key)
        return {'ok': False, 'error': 'failed'}
    return {'ok': True, 'values': get_all()}


# ---- audio devices ----

_SKIP_IN = {'Microsoft Sound Mapper - Input', 'Primary Sound Capture Driver'}
_SKIP_OUT = {'Microsoft Sound Mapper - Output', 'Primary Sound Driver'}


def scan_devices() -> dict:
    """Input and output devices (MME list with the fuller WASAPI names), plus what is selected now. Takes a second or two."""
    ins, outs = [], []
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        try:
            mme, wasapi = [], []
            for i in range(pa.get_device_count()):
                try:
                    d = dict(pa.get_device_info_by_index(i))
                except Exception:
                    continue
                d['_idx'] = i
                api = int(d.get('hostApi', -1))
                (mme if api == 0 else wasapi if api == 2 else []).append(d)
        finally:
            pa.terminate()
        full_in, full_out = {}, {}
        for d in wasapi:
            n = str(d.get('name', '')).strip()
            if n and int(d.get('maxInputChannels', 0)) > 0:
                full_in.setdefault(n[:12].lower(), n)
            if n and int(d.get('maxOutputChannels', 0)) > 0:
                full_out.setdefault(n[:12].lower(), n)
        for d in mme:
            name = str(d.get('name', '')).strip()
            if int(d.get('maxInputChannels', 0)) > 0 and name not in _SKIP_IN:
                ins.append({'index': int(d['_idx']), 'name': full_in.get(name[:12].lower(), name).replace('\n', ' ').strip()})
            if int(d.get('maxOutputChannels', 0)) > 0 and name not in _SKIP_OUT:
                outs.append({'name': full_out.get(name[:12].lower(), name).replace('\n', ' ').strip()})
    except Exception:
        _log.debug('device scan failed', exc_info=True)
    s = settings_io.read()
    idx = s.get('audio_input_device_index')
    return {'inputs': ins, 'outputs': outs, 'input': idx if isinstance(idx, int) else None, 'output': str(s.get('audio_output_device_name') or '')}


def set_devices(input_index, output_name) -> dict:
    """Stores the chosen devices (None / '' = system default) and switches to them now."""
    changes, drop = {}, []
    in_idx = None
    if isinstance(input_index, int) and not isinstance(input_index, bool) and 0 <= input_index < 512:
        in_idx = input_index
        changes['audio_input_device_index'] = in_idx
    else:
        drop.append('audio_input_device_index')
    out = str(output_name or '').strip()[:200] or None
    if out:
        changes['audio_output_device_name'] = out
    else:
        drop.append('audio_output_device_name')
    if not settings_io.update(changes, remove=tuple(drop)):
        return {'ok': False, 'error': 'failed'}
    try:
        from core.speech.tts import apply_audio_devices
        ok, msg = apply_audio_devices(output_device_name=out, input_device_index=in_idx)
        return {'ok': True, 'applied': bool(ok), 'message': str(msg)}
    except Exception as e:
        _log.exception('apply devices failed')
        return {'ok': False, 'error': type(e).__name__}


# ---- calibration ----

def calibrate(publish) -> dict:
    """Starts the microphone calibration in a thread; progress and result go out on the `voice_cal` topic."""
    global _calibrating
    with _cal_lock:
        if _calibrating:
            return {'ok': False, 'error': 'busy'}
        _calibrating = True

    def work():
        global _calibrating
        publish('voice_cal', {'state': 'running', 'text': 'Подбираю частоту и уровень шума: помолчите несколько секунд'})
        result = {'state': 'error', 'text': 'Не получилось откалибровать микрофон'}
        try:
            from core.engine.jarvis import get_engine
            eng = get_engine()
            if eng:
                eng._calibrating = True
            try:
                import pyaudio
                from config_pack.config import CHUNK_MS
                from core.audio_utils import open_input_stream
                from core.mic_calibration import find_best_rate, run_calibration
                pa = pyaudio.PyAudio()
                try:
                    di = settings_io.read().get('audio_input_device_index')
                    di = int(di) if isinstance(di, int) else None
                    rate = find_best_rate(pa, CHUNK_MS, di)
                    publish('voice_cal', {'state': 'running', 'text': f'Частота {rate} Гц, замеряю фон…'})
                    chunk = max(128, int(rate * CHUNK_MS / 1000))
                    stream = open_input_stream(pa, rate, chunk, device_index=di)
                    try:
                        t, g = run_calibration(stream, chunk, rate, CHUNK_MS)
                    finally:
                        try:
                            stream.close()
                        except Exception:
                            pass
                finally:
                    try:
                        pa.terminate()
                    except Exception:
                        pass
                settings_io.update({'best_sample_rate': rate})
                _apply_mic(threshold=int(t), gain=float(g))
                result = {'state': 'done', 'text': f'Готово: порог {int(t)}, усиление ×{float(g):.1f}', 'threshold': int(t), 'gain': float(g)}
            finally:
                if eng:
                    eng._calibrating = False
        except Exception as e:
            _log.exception('calibration failed')
            result = {'state': 'error', 'text': f'Ошибка калибровки: {e}'}
        finally:
            with _cal_lock:
                _calibrating = False
            publish('voice_cal', result)

    threading.Thread(target=work, name='ui-bridge-calibration', daemon=True).start()
    return {'ok': True}


# ---- local model: custom GGUF file or the default download ----

def bind(publish) -> None:
    global _pub
    _pub = publish


def llm_state() -> dict:
    import os
    path = str(settings_io.read().get('llm_chat_model_path') or '')
    present, downloading = False, False
    try:
        from core.speech.llm_downloader import is_default_model_present, is_downloading
        present, downloading = is_default_model_present(), is_downloading()
    except Exception:
        _log.debug('llm state failed', exc_info=True)
    busy = _llm_busy['busy'] or ('downloading' if downloading else '')
    return {'custom': os.path.basename(path) if path else '', 'default_present': present, 'busy': busy, 'pct': _llm_busy['pct'], 'text': _llm_busy['text']}


def _emit() -> None:
    if _pub is not None:
        _pub('voice_llm', llm_state())


def _set_busy(busy: str = '', text: str = '', pct: int = 0) -> None:
    _llm_busy.update(busy=busy, text=text, pct=pct)
    _emit()


def llm_pick() -> dict:
    """File dialog for a .gguf model, then a test load in a throwaway process (can take a minute); progress on `voice_llm`."""
    if _llm_busy['busy']:
        return {'ok': False, 'error': 'busy'}
    _llm_busy['busy'] = 'picking'

    def work():
        import os
        try:
            from . import filepick
            picked = filepick.pick_files('Модель GGUF', filepick.GGUF)
            if not picked:
                _set_busy()
                return
            path = picked[0]
            _set_busy('validating', 'Проверяю модель…')
            from core.speech.llm_chat import invalidate_model, validate_gguf_model
            ok, msg = validate_gguf_model(path)
            if ok:
                settings_io.update({'llm_chat_model_path': path})
                invalidate_model()
                _set_busy('', f'Готово: {msg}  ·  {os.path.basename(path)}')
            else:
                _set_busy('', f'Модель не подошла: {msg}')
        except Exception as e:
            _log.exception('model pick failed')
            _set_busy('', f'Ошибка: {e}')

    threading.Thread(target=work, name='ui-bridge-llm-pick', daemon=True).start()
    return {'ok': True}


def llm_reset() -> dict:
    """Back to the default model (and its download, when the fallback is on and the file is missing)."""
    if _llm_busy['busy'] in ('validating', 'downloading'):
        return {'ok': False, 'error': 'busy'}
    settings_io.update({}, remove=('llm_chat_model_path',))
    try:
        from core.speech.llm_chat import invalidate_model
        invalidate_model()
    except Exception:
        _log.debug('model invalidate failed', exc_info=True)
    _set_busy('', 'Стандартная модель')
    if get_all()['llm_chat_fallback']:
        _maybe_download_default()
    return {'ok': True}


def _maybe_download_default() -> None:
    try:
        from core.speech.llm_downloader import is_default_model_present, is_downloading
        if settings_io.read().get('llm_chat_model_path') or is_default_model_present() or is_downloading():
            return
    except Exception:
        return
    llm_download()


def llm_download() -> dict:
    """Downloads the default model (about 870 MB) in the background; progress on `voice_llm`."""
    try:
        from core.speech.llm_chat import invalidate_model
        from core.speech.llm_downloader import download_default_model
    except Exception:
        return {'ok': False, 'error': 'failed'}
    cancelled = {'v': False}
    _llm_busy['cancelled'] = cancelled

    def progress(done, total):
        pct = int(done * 100 / total) if total else 0
        _set_busy('downloading', f'Скачиваю модель: {pct}%' if total else f'Скачиваю модель: {done // (1 << 20)} МБ', pct)

    def finished(ok, msg):
        if ok:
            invalidate_model()
            _set_busy('', 'Стандартная модель загружена')
        else:
            _set_busy('', 'Загрузка отменена' if cancelled['v'] else f'Не удалось скачать модель: {msg}')

    started = download_default_model(on_progress=progress, on_done=finished)
    if started:
        _set_busy('downloading', 'Скачиваю модель…', 0)
    return {'ok': bool(started), 'error': '' if started else 'busy'}


def llm_cancel() -> dict:
    from core.speech.llm_downloader import cancel_download
    flag = _llm_busy.get('cancelled')
    if isinstance(flag, dict):
        flag['v'] = True
    cancel_download()
    return {'ok': True}
