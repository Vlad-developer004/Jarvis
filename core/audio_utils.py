import time
import numpy as np
from core.safe import swallow
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
def open_input(rate: int, chunk_frames: int, device_name: str | None = None, force_default: bool = False):
    """Start the native microphone capture. With no name given the one saved in settings (`audio_input_device_name`) is used;
    force_default=True ignores it and takes the Windows default input, for when the saved one cannot be opened any more."""
    from core import audio_migrate, native_audio, settings_io
    try:
        audio_migrate.migrate_input_device(settings_io.read, settings_io.update)   # the pre-native microphone index, once
    except Exception:
        swallow()
    if device_name is None and not force_default:
        name = _load_audio_settings().get('audio_input_device_name')
        device_name = name if isinstance(name, str) and name.strip() else None
    return native_audio.open_mic(rate, chunk_frames, None if force_default else device_name)

def open_input_resilient(rate: int, chunk_frames: int, attempts: int = 5):
    """Same as open_input, but recovers from the two usual causes of a failed open: a saved microphone that is gone (the first attempt
    honours it, every later one takes the live system default) and a transient failure right at startup (the audio subsystem still
    coming up, e.g. Jarvis autostarting at login). Raises the last error if every attempt fails, so the caller can still tell the user."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return open_input(rate, chunk_frames, force_default=(attempt > 0))
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
    """Whether the default playback device is headphones or a headset, from its Windows endpoint form factor (native sidecar)."""
    global _last_hp_check, _last_hp_res
    t = time.time()
    if t - _last_hp_check < 2.5:
        return _last_hp_res
    _last_hp_check = t
    from core import native_audio
    info = native_audio.query_output()
    _last_hp_res = bool(info and info['is_headphones'])
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

