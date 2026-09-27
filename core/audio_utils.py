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
def open_input_stream(pa, rate: int, chunk_frames: int, device_index: int | None = None,
                       force_default: bool = False):
    """force_default=True skips the saved-device lookup entirely, even if
    device_index is None — used by open_input_stream_resilient below to fall
    back to whatever PortAudio considers the current system default once a
    saved index has already failed to open."""
    if device_index is None and not force_default:
        s = _load_audio_settings()
        di = s.get('audio_input_device_index')
        if isinstance(di, int):
            device_index = di
    kw = dict(format=8, channels=1, rate=rate, input=True, frames_per_buffer=chunk_frames)
    if isinstance(device_index, int):
        kw['input_device_index'] = device_index
    return pa.open(**kw)

def open_input_stream_resilient(pa, rate: int, chunk_frames: int, attempts: int = 5):
    """Same as open_input_stream, but recovers from the two most common
    real-world causes of PortAudio's generic 'Unanticipated host error'
    (-9999) on open: a saved mic device index that's gone stale (unplugged,
    replaced, or renumbered by Windows — the first attempt still honors it,
    every attempt after forces the live system default instead of retrying
    the same bad index), and a transient failure right at startup (audio
    subsystem/driver still coming up, e.g. Jarvis set to autostart at login).

    Without this, a single failed open here used to silently abort the whole
    background init — see main.py's _background_init: no engine, no ASR, no
    retry, and no indication to the user that anything went wrong at all.
    Raises the last error if every attempt fails, so the caller can still
    notify/log — this only makes transient/stale-device failures recoverable,
    it doesn't hide a genuinely broken audio setup.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return open_input_stream(pa, rate, chunk_frames, force_default=(attempt > 0))
        except Exception as e:
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(1.0 + attempt * 0.5)
    raise last_exc
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
    """Check if audio is actually going out over headphones right now.
    Checks manual headphone_mode flag first, then the LIVE current Windows
    default output device — not the device name saved in settings from
    whenever the user last touched that dropdown, which can silently go
    stale (Bluetooth headphones disconnect, Windows falls back to the
    laptop's built-in speaker, but the saved 'audio_output_device_name'
    still says "Kopfhörer ..."). This function's whole reason to exist is
    deciding whether to suppress the mic during TTS playback to avoid
    self-echo (see core/engine/jarvis.py) — trusting stale config there
    meant Jarvis kept assuming headphones and never suppressed anything,
    letting it hear its own voice through the actual live speaker.
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
    except Exception:
        pass
    _last_jarvis_hp_res = is_current_output_headphones()
    return _last_jarvis_hp_res

