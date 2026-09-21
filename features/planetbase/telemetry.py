"""Reads Planetbase telemetry JSON written by the C# mod."""

import json
import logging
import os
import threading
import time
from pathlib import Path

_log = logging.getLogger(__name__)

_TELEMETRY_FILE = Path(os.path.expandvars("%USERPROFILE%")) / "OneDrive" / "Документи" / "Planetbase" / "jarvis_telemetry.json"
# Fallback to standard Documents if not found
if not _TELEMETRY_FILE.parent.exists():
    import ctypes.wintypes
    _buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(0, 5, 0, 0, _buf)
    _TELEMETRY_FILE = Path(_buf.value) / "Planetbase" / "jarvis_telemetry.json"
_STALE_THRESHOLD = 10  # seconds before data is considered stale

_lock = threading.Lock()
_data: dict = {}
_last_mtime: float = 0.0
_poll_thread: threading.Thread | None = None
_running = False


def _default() -> dict:
    return {
        "colonists": 0,
        "humans": 0,
        "low_food": False,
        "game_time": 0,
        "power_balance": 0,
        "power_storage": 0,
        "power_capacity": 0,
        "power_pct": 0,
        "water_balance": 0,
        "water_storage": 0,
        "water_capacity": 0,
        "water_pct": 0,
        "oxygen_gen": 0,
        "module_count": 0,
        "paused": False,
        "time_scale": 1.0,
        "any_disaster": False,
        "sandstorm": False,
        "solar_flare": False,
        "blizzard": False,
        "res_vegetables": 0,
        "res_meat": 0,
        "res_meals": 0,
        "res_starch": 0,
        "res_metal": 0,
        "res_ore": 0,
        "res_bioplastic": 0,
        "res_medical": 0,
        "ts": 0,
        "_valid": False,
    }


def _poll_loop():
    global _data, _last_mtime, _running
    while _running:
        try:
            if _TELEMETRY_FILE.exists():
                mtime = _TELEMETRY_FILE.stat().st_mtime
                if mtime != _last_mtime:
                    raw = _TELEMETRY_FILE.read_text(encoding="utf-8")
                    parsed = json.loads(raw)
                    age = time.time() - parsed.get("ts", 0)
                    parsed["_valid"] = bool(parsed.get("valid", False)) and age < _STALE_THRESHOLD
                    with _lock:
                        _data = parsed
                        _last_mtime = mtime
            else:
                with _lock:
                    _data = _default()
        except Exception:
            pass
        time.sleep(1.0)


def start():
    global _poll_thread, _running
    if _poll_thread and _poll_thread.is_alive():
        return
    _running = True
    _poll_thread = threading.Thread(target=_poll_loop, daemon=True, name="PBTelemetry")
    _poll_thread.start()
    _log.info("Planetbase telemetry reader started")


def stop():
    global _running
    _running = False


def get() -> dict:
    """Return latest telemetry snapshot (thread-safe)."""
    with _lock:
        return dict(_data) if _data else _default()


def is_valid() -> bool:
    return get().get("_valid", False)
