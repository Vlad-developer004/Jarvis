"""Calendar for the Calendar screen. A thin layer over actions/calendar_hub.py (own events, cached ICS sources, one query for everything);
this module only validates what comes from the UI, keeps the calendar settings (sources with names, colours and visibility, reminder defaults)
and turns hub errors into {'ok': False, 'error': code}.

Voice ("что в календаре"), the morning briefing and the spoken reminders read the same data through the hub, so what you see here is what Jarvis
says and reminds about.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import date

from actions import calendar_hub as hub
from core import settings_io

_log = logging.getLogger(__name__)
MAX_RANGE_DAYS = 100
_OWN_KEYS = ('title', 'date', 'time', 'end_date', 'end_time', 'all_day', 'repeat', 'interval', 'weekdays', 'until', 'location', 'notes', 'color', 'remind')


def ics_path() -> str:
    return hub.ics_path()


def _guard(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except hub.CalendarError as ex:
            return {'ok': False, 'error': ex.code}
        except Exception as ex:
            if ex.__class__.__name__ == 'CalDavError':                            # the CalDAV client's own errors carry a code and a sentence to show
                return {'ok': False, 'error': ex.code, 'message': ex.message}
            raise
    wrapper.__name__ = fn.__name__
    return wrapper


# ---- settings ----

def _sources() -> list[dict]:
    s = settings_io.read().get('calendar_sources')
    return [x for x in s if isinstance(x, dict)] if isinstance(s, list) else []


def _ref(src: dict) -> str:
    return hub._ref(src)


def _enable_module() -> None:
    """The calendar module and its extension must be on for reminders and voice commands to see events."""
    s = settings_io.read()
    fm = s.get('feature_modules') if isinstance(s.get('feature_modules'), dict) else {}
    fm['calendar_ics'] = True
    settings_io.update({'feature_modules': fm})
    try:
        from core.system import refresh_module_flags
        refresh_module_flags()
    except Exception:
        _log.debug('module flags refresh failed', exc_info=True)
    try:
        from .extensions import set_installed
        set_installed('feature_calendar_ics', True)
    except Exception:
        _log.debug('calendar extension install failed', exc_info=True)


def get_state() -> dict:
    try:
        from core.extensions import ExtensionManager
        installed = ExtensionManager().is_installed('feature_calendar_ics')
    except Exception:
        installed = False
    s = settings_io.read()
    fm = s.get('feature_modules') if isinstance(s.get('feature_modules'), dict) else {}
    b = s.get('briefing') if isinstance(s.get('briefing'), dict) else {}
    minutes = b.get('calendar_reminder_minutes', 15)
    minutes = minutes if isinstance(minutes, int) and 1 <= minutes <= 120 else 15
    enabled = b.get('calendar_reminders_enabled', True)
    return {'installed': installed, 'enabled': bool(fm.get('calendar_ics')), 'colors': hub.COLORS, 'own_name': hub.OWN_NAME,
            'sources': [{**i, 'status': hub.status_of(i['ref'])} for i in hub.sources_info()],
            'remind': {'enabled': enabled if isinstance(enabled, bool) else True, 'minutes': minutes}}


def add_source(ref: str, name: str = '') -> dict:
    ref = str(ref or '').strip()
    if not ref or len(ref) > 500:
        return {'ok': False, 'error': 'bad_source'}
    srcs = _sources()
    if any(_ref(x) == ref for x in srcs):
        return {'ok': False, 'error': 'exists'}
    entry = {'url': ref} if ref.lower().startswith(('http://', 'https://', 'webcal://')) else {'path': ref}
    if name:
        entry['name'] = str(name).strip()[:40]
    settings_io.update({'calendar_sources': srcs + [entry]})
    _enable_module()
    return {'ok': True, 'state': get_state()}


def _pick_paths() -> list[str]:
    from . import filepick
    return filepick.pick_files('Календарь (.ics)', filepick.ICS, multi=False)


def import_file() -> dict:
    """The user picks an .ics file; it is copied next to the settings (so it keeps working when the original moves) and added as a source."""
    paths = _pick_paths()
    if not paths:
        return {'ok': False, 'error': 'cancelled'}
    src = paths[0]
    if not src.lower().endswith('.ics') or not os.path.isfile(src) or os.path.getsize(src) > 8 * 1024 * 1024:
        return {'ok': False, 'error': 'bad_file'}
    folder = os.path.join(hub._dir(), 'calendars')
    os.makedirs(folder, exist_ok=True)
    stem = re.sub(r'[^\w.\- ]', '_', os.path.splitext(os.path.basename(src))[0])[:40] or 'calendar'
    dest, n = os.path.join(folder, stem + '.ics'), 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(folder, f'{stem} ({n}).ics')
    shutil.copyfile(src, dest)
    return add_source(dest, stem)


def remove_source(ref: str) -> dict:
    ref = str(ref or '').strip()
    settings_io.update({'calendar_sources': [x for x in _sources() if _ref(x) != ref]})
    hub.forget(ref)
    return {'ok': True, 'state': get_state()}


def source_set(ref: str, name=None, color=None, hidden=None) -> dict:
    ref = str(ref or '').strip()
    srcs = _sources()
    for x in srcs:
        if _ref(x) != ref:
            continue
        if name is not None:
            x['name'] = str(name).strip()[:40]
            if not x['name']:
                x.pop('name')
        if color is not None:
            if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', str(color)):
                return {'ok': False, 'error': 'bad_color'}
            x['color'] = str(color)
        if hidden is not None:
            x['hidden'] = bool(hidden)
        settings_io.update({'calendar_sources': srcs})
        return {'ok': True, 'state': get_state()}
    return {'ok': False, 'error': 'unknown_source'}


def set_reminders(enabled, minutes) -> dict:
    try:
        n = int(minutes)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'bad_minutes'}
    if not 1 <= n <= 120:
        return {'ok': False, 'error': 'bad_minutes'}
    cur = settings_io.read().get('briefing')
    cur = dict(cur) if isinstance(cur, dict) else {}
    cur.update({'calendar_reminders_enabled': bool(enabled), 'calendar_reminder_minutes': n})
    settings_io.update({'briefing': cur})
    return {'ok': True, 'state': get_state()}


# ---- events ----

@_guard
def list_events(start: str, end: str) -> dict:
    try:
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return {'ok': False, 'error': 'bad_range'}
    if d1 < d0 or (d1 - d0).days > MAX_RANGE_DAYS:
        return {'ok': False, 'error': 'bad_range'}
    return {'ok': True, **hub.events_between(d0, d1)}


def search(q: str) -> dict:
    return {'ok': True, 'events': hub.search(q)}


def _fields(data: dict) -> dict:
    return {k: data[k] for k in _OWN_KEYS if k in data}


def quick(text: str, day: str = '') -> dict:
    """The phrase typed in "quick add" as an event (same parser as the voice command)."""
    from actions import calendar_quick
    try:
        default = date.fromisoformat(day) if day else None
    except ValueError:
        default = None
    return {'ok': True, **calendar_quick.parse_phrase(str(text or '')[:300], default_date=default)}


@_guard
def caldav_find(server, user, password) -> dict:
    return {'ok': True, 'calendars': hub.caldav_find(str(server or '').strip(), str(user or '').strip(), str(password or ''))}


@_guard
def caldav_add(server, user, password, picks) -> dict:
    hub.caldav_add(str(server or '').strip(), str(user or '').strip(), str(password or ''), [p for p in picks if isinstance(p, dict)] if isinstance(picks, list) else [])
    _enable_module()
    return {'ok': True, 'state': get_state()}


@_guard
def add_event(data: dict) -> dict:
    if data.get('calendar'):                                                         # a CalDAV calendar instead of the own events
        e = hub.caldav_create(str(data['calendar']), _fields(data))
        _enable_module()
        return {'ok': True, 'event': e}
    e = hub.add_local(_fields(data))
    _enable_module()
    return {'ok': True, 'event': e, 'state': get_state()}


@_guard
def update_event(eid: str, data: dict) -> dict:
    if data.get('src'):
        return {'ok': True, 'event': hub.caldav_update(str(data['src']), str(data.get('href', '')), _fields(data))}
    return {'ok': True, 'event': hub.update_local(str(eid), _fields(data))}


@_guard
def update_occurrence(eid: str, occ: str, data: dict) -> dict:
    return {'ok': True, 'event': hub.update_occurrence(str(eid), str(occ), _fields(data))}


@_guard
def reset_occurrence(eid: str, occ: str) -> dict:
    return {'ok': True} if hub.reset_occurrence(str(eid), str(occ)) else {'ok': False, 'error': 'unknown_event'}


@_guard
def delete_event(eid: str, only_date: str = '', src: str = '', href: str = '') -> dict:
    if src:
        hub.caldav_delete(str(src), str(href))
        return {'ok': True}
    return {'ok': True} if hub.delete_local(str(eid), str(only_date or '')) else {'ok': False, 'error': 'unknown_event'}


def refresh() -> None:
    hub.refresh()
