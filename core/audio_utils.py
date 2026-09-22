import time
import numpy as np
def rms_int16(data_bytes: bytes) -> float:
    if not data_bytes:
        return 0.0
    s = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(s * s)))
def _load_audio_settings() -> dict:
    try:
        import json, os
        # Same file the rest of the app reads/writes (%APPDATA%\Jarvis\...) —
        # a project-relative path here would never see the mic device chosen
        # in settings (and gets wiped by a rebuild).
        try:
            from config_pack.config import get_settings_path
            p = get_settings_path()
        except Exception:
            p = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}
def open_input_stream(pa, rate: int, chunk_frames: int, device_index: int | None = None):
    if device_index is None:
        s = _load_audio_settings()
        di = s.get('audio_input_device_index')
        if isinstance(di, int):
            device_index = di
    kw = dict(format=8, channels=1, rate=rate, input=True, frames_per_buffer=chunk_frames)
    if isinstance(device_index, int):
        kw['input_device_index'] = device_index
    return pa.open(**kw)
def now() -> float:
    return time.perf_counter()

_last_hp_check = 0.0
_last_hp_res = False

def is_current_output_headphones() -> bool:
    global _last_hp_check, _last_hp_res
    t = time.time()
    if t - _last_hp_check < 2.5:
        return _last_hp_res
    
    _last_hp_check = t
    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities
        pythoncom.CoInitialize()
        dev = AudioUtilities.GetSpeakers()
        if not dev:
            _last_hp_res = False
            return False
        
        name = str(dev.GetFriendlyName() or "").lower()
        keywords = ['headphone', 'headset', 'phone', 'наушники', 'гарнитура', 'kopfhörer', 'ear', 'pod', 'bt', 'blue', 'hands-free', 'wireless']
        _last_hp_res = any(k in name for k in keywords)
    except Exception:
        _last_hp_res = False
    return _last_hp_res


_last_jarvis_hp_check = 0.0
_last_jarvis_hp_res = False

def is_jarvis_output_headphones() -> bool:
    """Check if Jarvis's *configured* output device is headphones.
    Checks manual headphone_mode flag first, then detects by device name.
    """
    global _last_jarvis_hp_check, _last_jarvis_hp_res
    t = time.time()
    if t - _last_jarvis_hp_check < 2.5:
        return _last_jarvis_hp_res

    _last_jarvis_hp_check = t
    try:
        d = _load_audio_settings()
        # Manual override: if the user explicitly set headphone mode — trust them
        if d.get('headphone_mode', False):
            _last_jarvis_hp_res = True
            return True
        dev_name = str(d.get('audio_output_device_name') or '').lower()
        if dev_name:
            keywords = ['headphone', 'headset', 'kopfhörer', 'наушники', 'гарнитура', 'phone', 'ear', 'pod', 'bt', 'blue', 'hands-free', 'wireless']
            _last_jarvis_hp_res = any(k in dev_name for k in keywords)
            return _last_jarvis_hp_res
    except Exception:
        pass
    # No configured device → fall back to checking system default
    _last_jarvis_hp_res = is_current_output_headphones()
    return _last_jarvis_hp_res

