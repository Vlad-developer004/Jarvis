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
        # v2 fields (mod collects them on the Unity main thread)
        "res_spares": 0,
        "res_coins": 0,
        "disaster_intensity": 0.0,
        "prestige": 0.0,
        "prestige_level": -1,
        "welfare": 0.0,
        "welfare_level": -1,
        "techs_acquired": 0,
        "alert_state": -1,  # 0 green, 1 yellow, 2 red
        "outside_allowed": True,
        "land_colonists": True,
        "land_visitors": True,
        "land_merchants": True,
        "planet": "",
        "difficulty": "",
        "risk_sandstorm": "",
        "risk_solar_flare": "",
        "risk_blizzard": "",
        "risk_meteor": "",
        "risk_thunderstorm": "",
        "n_anti_meteor": 0,
        "n_lightning_rod": 0,
        "n_workers": 0,
        "n_biologists": 0,
        "n_engineers": 0,
        "n_medics": 0,
        "n_guards": 0,
        "n_bots": 0,
        "n_intruders": 0,
        "n_visitors": 0,
        "n_sick": 0,
        "n_ko": 0,
        "n_low_status": 0,
        "n_fighting": 0,
        "mod_damaged": 0,
        "mod_unpowered": 0,
        "mod_unoperated": 0,
        "mod_vital_down": 0,
        "storage_modules": 0,
        "storage_space_avg": 0.0,
        "err": "",
        "ts": 0,
        "_valid": False,
        "_stale": False,
    }


def _apply_freshness(parsed: dict) -> None:
    """Sets _valid (mod is alive: recent heartbeat) and _stale (the snapshot is
    older than the heartbeat: the game isn't rendering, e.g. minimised)."""
    now = time.time()
    heartbeat_age = now - parsed.get("ts", 0)
    parsed["_valid"] = bool(parsed.get("valid", False)) and heartbeat_age < _STALE_THRESHOLD
    collected = parsed.get("collected_ts", parsed.get("ts", 0))
    parsed["_stale"] = parsed.get("ts", 0) - collected > _STALE_THRESHOLD


def _poll_loop():
    global _data, _last_mtime, _running
    while _running:
        try:
            if _TELEMETRY_FILE.exists():
                mtime = _TELEMETRY_FILE.stat().st_mtime
                if mtime != _last_mtime:
                    parsed = json.loads(_TELEMETRY_FILE.read_text(encoding="utf-8"))
                    with _lock:
                        _data = parsed
                        _last_mtime = mtime
                # Re-evaluate every poll: a closed game stops touching the file,
                # so freshness must not depend on the file changing.
                with _lock:
                    if _data:
                        _apply_freshness(_data)
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
