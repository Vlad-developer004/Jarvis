from __future__ import annotations
import json
from pathlib import Path
from config_pack.config import get_settings_path
_SETTINGS_PATH = Path(get_settings_path())
_PROFILE_PRESETS: dict[str, dict[str, bool]] = {
    "full": {
        "games": True,
        "qa": True,
        "llm_chat_fallback": False,
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
        "remote_control": False,
        "push_to_talk": True,
        "git_integration": True,
        "translator": True,
        "song_id": True,
    },
    "assistant": {
        "games": False,
        "qa": False,
        "llm_chat_fallback": False,
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
        "remote_control": False,
        "push_to_talk": True,
        "git_integration": True,
        "translator": True,
        "song_id": False,
    },
    "minimal": {
        "games": False,
        "qa": False,
        "llm_chat_fallback": False,
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
        "remote_control": False,
        "push_to_talk": True,
        "git_integration": True,
        "translator": True,
        "song_id": False,
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

# 'photoshop_voice'/'figma_voice' are hardcoded False in every profile above
# and have no settings-UI toggle of their own — the only real, user-facing
# switch for them is installing the matching extension (feature_photoshop_voice/
# feature_figma_voice in data/extensions_catalog.json). Routing them through
# ExtensionManager here — instead of leaving callers to duplicate this check,
# as core.nlp.commands's PS/Figma shortcut logic already did on its own —
# is what makes dispatch.py's _MODULE_GATES and semantic.py's _intent_allowed()
# (both call module_enabled()) agree with the extension system instead of
# always blocking these commands regardless of whether the extension is on.
_EXTENSION_BACKED_MODULES = frozenset({'photoshop_voice', 'figma_voice'})

def module_enabled(name: str) -> bool:
    global _cached_flags
    if name in _EXTENSION_BACKED_MODULES:
        from core.extensions import ExtensionManager
        return ExtensionManager().has_feature(name)
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
