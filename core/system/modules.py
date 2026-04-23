from __future__ import annotations
import json
from pathlib import Path
def _get_settings_path() -> Path:
    import sys
    import os
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # Path to root from core/system/modules.py is two levels up
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return Path(base) / "data" / "jarvis_settings.json"

_SETTINGS_PATH = _get_settings_path()
_PROFILE_PRESETS: dict[str, dict[str, bool]] = {
    "full": {
        "games": True,
        "qa": True,
        "cinema": True,
        "system_monitoring": True,
        "battery_monitor": True,
        "lag_hunter": True,
        "morning_briefing": True,
        "updater": True,
        "photoshop_voice": False,
        "figma_voice": False,
        "network_profiles": False,
        "system_health": False,
        "calendar_ics": False,
        "inbox_digest": False,
    },
    "assistant": {
        "games": False,
        "qa": False,
        "cinema": False,
        "system_monitoring": True,
        "battery_monitor": True,
        "lag_hunter": False,
        "morning_briefing": False,
        "updater": True,
        "photoshop_voice": False,
        "figma_voice": False,
        "network_profiles": False,
        "system_health": False,
        "calendar_ics": False,
        "inbox_digest": False,
    },
    "minimal": {
        "games": False,
        "qa": False,
        "cinema": False,
        "system_monitoring": True,
        "battery_monitor": True,
        "lag_hunter": False,
        "morning_briefing": False,
        "updater": False,
        "photoshop_voice": False,
        "figma_voice": False,
        "network_profiles": False,
        "system_health": False,
        "calendar_ics": False,
        "inbox_digest": False,
    },
}
_cached_flags: dict[str, bool] | None = None
_cached_profile = "minimal"
def _read_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}
def _load_flags() -> tuple[str, dict[str, bool]]:
    settings = _read_settings()
    profile = str(settings.get("feature_profile", "minimal")).strip().lower() or "minimal"
    base = dict(_PROFILE_PRESETS.get(profile, _PROFILE_PRESETS["minimal"]))
    overrides = settings.get("feature_modules", {})
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key in base and isinstance(value, bool):
                base[key] = value
    return (profile, base)
def refresh_module_flags() -> None:
    global _cached_flags, _cached_profile
    _cached_profile, _cached_flags = _load_flags()
def module_enabled(name: str) -> bool:
    global _cached_flags
    if _cached_flags is None:
        refresh_module_flags()
    if _cached_flags is None:
        return True
    return _cached_flags.get(name, True)
def active_module_profile() -> str:
    global _cached_profile
    if _cached_flags is None:
        refresh_module_flags()
    return _cached_profile
