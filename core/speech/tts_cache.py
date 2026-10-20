"""Speed and night-volume settings and wav-cache housekeeping for core.speech.tts (moved out of tts.py unchanged)."""

import json
import os
import tempfile
import threading
import wave

CACHE_DIR = os.path.join(tempfile.gettempdir(), 'jarvis_tts_cache')

os.makedirs(CACHE_DIR, exist_ok=True)

# --- TTS speed cache ---------------------------------------------------
_tts_speed_cache: float | None = None

_tts_speed_lock = threading.Lock()

def invalidate_tts_speed_cache() -> None:
    global _tts_speed_cache
    with _tts_speed_lock:
        _tts_speed_cache = None

# --- Night volume cache ------------------------------------------------
_night_vol_cache: tuple[bool, int, int, int, int, float] | None = None

_night_vol_lock = threading.Lock()

def _invalidate_night_vol_cache() -> None:
    global _night_vol_cache
    with _night_vol_lock:
        _night_vol_cache = None

def _get_night_vol_settings() -> tuple[bool, int, int, int, int, float]:
    global _night_vol_cache
    with _night_vol_lock:
        if _night_vol_cache is not None:
            return _night_vol_cache
        try:
            from config_pack.config import get_settings_path as _gsp
            _s = json.load(open(_gsp(), encoding='utf-8'))
            result: tuple[bool, int, int, int, int, float] = (
                bool(_s.get('tts_night_enabled', True)),
                int(_s.get('tts_night_start', 22)),
                int(_s.get('tts_night_start_min', 0)),
                int(_s.get('tts_night_end', 7)),
                int(_s.get('tts_night_end_min', 0)),
                float(_s.get('tts_night_volume', 0.7)),
            )
        except Exception:
            result = (True, 22, 0, 7, 0, 0.7)
        _night_vol_cache = result
        return result

# --- WAV cache eviction ------------------------------------------------
_CACHE_MAX_FILES = 300  # Keep newest N files; extras are deleted.

_CACHE_EVICT_INTERVAL = 1800  # Seconds between automatic eviction runs.

def _evict_wav_cache() -> None:
    try:
        files = sorted(
            (f for f in os.scandir(CACHE_DIR) if f.name.endswith('.wav')),
            key=lambda e: e.stat().st_mtime,
            reverse=True,
        )
        for entry in files[_CACHE_MAX_FILES:]:
            try:
                os.remove(entry.path)
            except OSError:
                pass
    except Exception:
        pass

def _schedule_cache_eviction() -> None:
    _evict_wav_cache()
    t = threading.Timer(_CACHE_EVICT_INTERVAL, _schedule_cache_eviction)
    t.daemon = True
    t.start()

# Run once at import time and then on a recurring timer.
threading.Thread(target=_schedule_cache_eviction, daemon=True).start()

def _get_tts_speed() -> float:
    global _tts_speed_cache
    with _tts_speed_lock:
        if _tts_speed_cache is not None:
            return _tts_speed_cache
        try:
            from config_pack.config import get_settings_path
            with open(get_settings_path(), 'r', encoding='utf-8') as _f:
                val = max(0.6, min(1.4, float(json.load(_f).get('tts_speed', 1.0))))
        except Exception:
            val = 1.0
        _tts_speed_cache = val
        return val

def _apply_wav_speed(src: str, speed: float) -> str:
    """Return path to WAV with modified framerate for playback speed control.
    speed < 1.0 → slower (lower pitch); speed > 1.0 → faster (higher pitch)."""
    if abs(speed - 1.0) < 0.02:
        return src
    spct = int(round(speed * 100))
    dst = src.replace('.wav', f'_sp{spct}.wav')
    if os.path.exists(dst):
        return dst
    try:
        with wave.open(src, 'rb') as r:
            p = r.getparams()
            data = r.readframes(p.nframes)
        with wave.open(dst, 'wb') as w:
            w.setnchannels(p.nchannels)
            w.setsampwidth(p.sampwidth)
            w.setframerate(max(1, int(p.framerate * speed)))
            w.writeframes(data)
        return dst
    except Exception:
        return src
