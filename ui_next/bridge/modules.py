"""Modules settings of the new UI (the old settings window, tab "Modules"): feature profile, per-module switches, briefing and calendar reminders, restart.

Storage is the one the core reads (core/system/modules.py, actions/briefing_config.py), through core.settings_io so the old window sees the same values:
  feature_profile  : "full" | "assistant" | "minimal"
  feature_modules  : {module: bool}, only the switches that differ from the profile (a switch equal to its profile is dropped, so it follows the profile later)
  briefing         : include_* flags, calendar_reminders_enabled, calendar_reminder_minutes (keys of other writers are kept; the old window used to drop them)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading

from core import settings_io

_log = logging.getLogger(__name__)

# the switches the settings screen shows, in display order ('remote_control' lives in the Tools tab, 'photoshop_voice'/'figma_voice' follow their extensions)
MODULES = ('qa', 'llm_chat_fallback', 'games', 'cinema', 'system_monitoring', 'battery_monitor', 'lag_hunter', 'morning_briefing', 'updater', 'network_profiles',
           'system_health', 'calendar_ics', 'inbox_digest', 'git_integration', 'translator', 'song_id')
_BRIEF_FLAGS = ('include_greeting', 'include_time', 'include_weather', 'include_battery', 'include_system_load', 'include_calendar', 'include_mail_unread', 'calendar_reminders_enabled')


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def _presets() -> dict:
    from core.system.modules import _PROFILE_PRESETS
    return _PROFILE_PRESETS


def _profile(s: dict) -> str:
    p = str(s.get('feature_profile', 'minimal')).strip().lower()
    return p if p in _presets() else 'minimal'


def _refresh() -> None:
    try:
        from core.system import refresh_module_flags
        refresh_module_flags()
    except Exception:
        _log.debug('refresh_module_flags failed', exc_info=True)


def get_state() -> dict:
    from actions.briefing_config import load_briefing_prefs
    s = settings_io.read()
    profile = _profile(s)
    base = _presets()[profile]
    ov = s.get('feature_modules', {})
    ov = ov if isinstance(ov, dict) else {}
    modules = []
    for k in MODULES:
        preset = bool(base.get(k, False))
        v = ov.get(k)
        on = v if isinstance(v, bool) else preset
        modules.append({'key': k, 'on': on, 'preset': preset, 'manual': on != preset})
    return {'ok': True, 'profile': profile, 'profiles': list(_presets()), 'modules': modules, 'briefing': load_briefing_prefs()}


def set_profile(profile) -> dict:
    p = str(profile or '').strip().lower()
    if p not in _presets():
        return _bad('bad_value')
    if not settings_io.update({'feature_profile': p}):
        return _bad('write_failed')
    _refresh()
    return {'ok': True}


def set_module(key, on) -> dict:
    if key not in MODULES or not isinstance(on, bool):
        return _bad('bad_value')
    s = settings_io.read()
    ov = s.get('feature_modules', {})
    ov = dict(ov) if isinstance(ov, dict) else {}
    if on == bool(_presets()[_profile(s)].get(key, False)):
        ov.pop(key, None)
    else:
        ov[key] = on
    if not settings_io.update({'feature_modules': ov}):
        return _bad('write_failed')
    _refresh()
    return {'ok': True}


def reset_modules() -> dict:
    s = settings_io.read()
    ov = s.get('feature_modules', {})
    ov = {k: v for k, v in ov.items() if k not in MODULES} if isinstance(ov, dict) else {}
    if not settings_io.update({'feature_modules': ov}):
        return _bad('write_failed')
    _refresh()
    return {'ok': True}


def set_briefing(key, value) -> dict:
    if key in _BRIEF_FLAGS:
        if not isinstance(value, bool):
            return _bad('bad_value')
    elif key == 'calendar_reminder_minutes':
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            return _bad('bad_value')
        if not 1 <= value <= 120:
            return _bad('bad_value')
    else:
        return _bad('bad_value')
    b = settings_io.read().get('briefing', {})
    b = dict(b) if isinstance(b, dict) else {}
    b[key] = value
    return {'ok': True} if settings_io.update({'briefing': b}) else _bad('write_failed')


def _exit_core() -> None:
    from ui_next import host
    host.exit_now(0)


def restart() -> dict:
    """Starts a fresh copy of Jarvis and exits this one after the reply went out (same as the old window's restart button)."""
    try:
        subprocess.Popen([sys.executable] + sys.argv)
    except OSError:
        return _bad('failed')
    threading.Timer(0.6, _exit_core).start()
    return {'ok': True}


def run(data: dict) -> dict:
    """Entry of the `modules` bridge command: op `state` | `profile` {profile} | `module` {key, on} | `reset` | `briefing` {key, value} | `restart`."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return get_state()
    if op == 'restart':
        return restart()
    fn = {'profile': lambda: set_profile(data.get('profile')), 'module': lambda: set_module(data.get('key'), data.get('on')), 'reset': reset_modules,
          'briefing': lambda: set_briefing(data.get('key'), data.get('value'))}.get(op)
    if fn is None:
        return _bad('bad_op')
    res = fn()
    return {**get_state(), 'ok': True} if res.get('ok') else res
