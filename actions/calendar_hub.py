"""One place for calendar data: the user's own events (stored in %APPDATA%\\Jarvis\\local_events.json), the ICS sources from the settings with a
download cache (so the reminder loop does not hit the network every minute), a single query "events between two dates" used by the calendar
screen, search, and the "which reminders are due now" logic used by features/calendar_reminders.py.

Own events and external ones go through the same parser and recurrence engine (actions/calendar_parse.py). `local_events.ics` is still written
as an export for other programs; it is no longer registered as a source, and an older registration of it is ignored here to avoid duplicates.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from actions import calendar_parse as cp
from actions.calendar_parse import CalEvent, local

_log = logging.getLogger(__name__)
_lock = threading.RLock()
CACHE_TTL = 300
REPEATS = ('none', 'daily', 'weekly', 'monthly', 'yearly')
_FREQ = {'daily': 'DAILY', 'weekly': 'WEEKLY', 'monthly': 'MONTHLY', 'yearly': 'YEARLY'}
_DAYS = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
COLORS = ['#3df5ac', '#22d3ee', '#4c8dff', '#b197fc', '#f783ac', '#ff6b6b', '#ffa94d', '#ffd43b']
OWN_NAME = 'Мои события'
MAX_LOCAL = 1000


class CalendarError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _dir() -> str:
    from config_pack.config import get_app_data_root
    return get_app_data_root()


def json_path() -> str:
    return os.path.join(_dir(), 'local_events.json')


def ics_path() -> str:
    return os.path.join(_dir(), 'local_events.ics')


def _settings() -> dict:
    from core import settings_io
    return settings_io.read()


# ---- own events: validation ----

def _d(v, code='bad_date') -> date:
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise CalendarError(code)


def _t(v) -> str:
    v = str(v or '').strip()
    if not v:
        return ''
    try:
        return datetime.strptime(v, '%H:%M').strftime('%H:%M')
    except ValueError:
        raise CalendarError('bad_time')


OV_KEYS = ('title', 'date', 'time', 'end_date', 'end_time', 'all_day', 'location', 'notes', 'color')


def _override(v) -> dict:
    """One changed occurrence of a series: its own title, time, place... (validated like a single event)."""
    if not isinstance(v, dict):
        raise CalendarError('bad_override')
    one = normalize({**{k: v[k] for k in OV_KEYS if k in v}, 'repeat': 'none'})
    return {k: one[k] for k in OV_KEYS}


def normalize(data: dict, eid: str = '', keep: dict | None = None) -> dict:
    """Validated own event (all fields, defaults filled). `keep` supplies the fields an update does not mention."""
    src = {**(keep or {}), **data}
    title = ' '.join(str(src.get('title') or '').split())[:120]
    if not title:
        raise CalendarError('no_title')
    start = _d(src.get('date'))
    time_s = _t(src.get('time'))
    all_day = bool(src['all_day']) if 'all_day' in src and src['all_day'] is not None else not time_s
    if all_day:
        time_s = ''
    elif not time_s:
        raise CalendarError('bad_time')
    end_d = _d(src.get('end_date') or start.isoformat())
    end_t = _t(src.get('end_time')) if not all_day else ''
    if not all_day and not end_t:
        if src.get('end_date') and end_d != start:
            end_t = time_s
        else:                                            # no end given: one hour, rolling into the next day after 23:00
            later = datetime.combine(start, datetime.strptime(time_s, '%H:%M').time()) + timedelta(hours=1)
            end_d, end_t = later.date(), later.strftime('%H:%M')
    s_dt = datetime.combine(start, datetime.strptime(time_s or '00:00', '%H:%M').time())
    e_dt = datetime.combine(end_d, datetime.strptime(end_t or '00:00', '%H:%M').time())
    if e_dt < s_dt:
        raise CalendarError('bad_range')
    repeat = str(src.get('repeat') or 'none')
    if repeat not in REPEATS:
        raise CalendarError('bad_repeat')
    try:
        interval = max(1, min(99, int(src.get('interval') or 1)))
    except (TypeError, ValueError):
        raise CalendarError('bad_repeat')
    weekdays = sorted({int(x) for x in (src.get('weekdays') or []) if str(x).isdigit() and 0 <= int(x) <= 6})
    until = ''
    if src.get('until'):
        u = _d(src['until'], 'bad_until')
        if u < start:
            raise CalendarError('bad_until')
        until = u.isoformat()
    color = str(src.get('color') or '')
    if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise CalendarError('bad_color')
    remind = src.get('remind')
    if remind is not None:
        try:
            remind = sorted({int(x) for x in remind})[:3]
        except (TypeError, ValueError):
            raise CalendarError('bad_remind')
        if any(not 1 <= x <= 10080 for x in remind):
            raise CalendarError('bad_remind')
    exceptions = sorted({_d(x).isoformat() for x in (src.get('exceptions') or [])})
    overrides = {_d(k).isoformat(): _override(v) for k, v in (src.get('overrides') or {}).items()} if isinstance(src.get('overrides'), dict) else {}
    return {'id': eid or uuid.uuid4().hex[:12], 'title': title, 'date': start.isoformat(), 'time': time_s, 'end_date': end_d.isoformat(), 'end_time': end_t,
            'all_day': all_day, 'repeat': repeat, 'interval': interval, 'weekdays': weekdays if repeat == 'weekly' else [], 'until': until,
            'location': ' '.join(str(src.get('location') or '').split())[:200], 'notes': str(src.get('notes') or '').strip()[:2000], 'color': color,
            'remind': remind, 'exceptions': exceptions, 'overrides': overrides}


def load_local() -> list[dict]:
    """Own events; the first version of the file (title, date, time, repeat only) is read as is and gets the new fields from defaults."""
    try:
        with open(json_path(), 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return []
    out = []
    for e in raw if isinstance(raw, list) else []:
        try:
            if isinstance(e, dict) and e.get('id'):
                out.append(normalize(e, str(e['id'])))
        except CalendarError:
            _log.debug('skipping a bad own event %r', e.get('id') if isinstance(e, dict) else e)
    return out


def _esc(text: str) -> str:
    return str(text).replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')


def _rule(e: dict) -> dict:
    if e['repeat'] == 'none':
        return {}
    r = {'FREQ': _FREQ[e['repeat']], 'INTERVAL': str(e['interval'])}
    if e['repeat'] == 'weekly' and e['weekdays']:
        r['BYDAY'] = ','.join(_DAYS[i] for i in e['weekdays'])
    if e['until']:
        r['UNTIL'] = e['until'].replace('-', '')
    return r


def _bounds(e: dict) -> tuple[datetime, datetime]:
    s = datetime.combine(date.fromisoformat(e['date']), datetime.strptime(e['time'] or '00:00', '%H:%M').time())
    if e['all_day']:
        return s, datetime.combine(date.fromisoformat(e['end_date']), datetime.min.time()) + timedelta(days=1)
    return s, datetime.combine(date.fromisoformat(e['end_date']), datetime.strptime(e['end_time'], '%H:%M').time())


def _write_ics(events: list[dict]) -> None:
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Jarvis//Own events//RU']
    for e in events:
        s, en = _bounds(e)
        lines += ['BEGIN:VEVENT', f"UID:{e['id']}@jarvis"]
        if e['all_day']:
            lines += [f'DTSTART;VALUE=DATE:{s:%Y%m%d}', f'DTEND;VALUE=DATE:{en:%Y%m%d}']
        else:
            lines += [f'DTSTART:{s:%Y%m%dT%H%M%S}', f'DTEND:{en:%Y%m%dT%H%M%S}']
        lines.append(f"SUMMARY:{_esc(e['title'])}")
        if e['location']:
            lines.append(f"LOCATION:{_esc(e['location'])}")
        if e['notes']:
            lines.append(f"DESCRIPTION:{_esc(e['notes'])}")
        r = _rule(e)
        if r:
            lines.append('RRULE:' + ';'.join(f'{k}={v}' for k, v in r.items()))
        for x in e['exceptions']:
            lines.append((f'EXDATE;VALUE=DATE:{x.replace("-", "")}' if e['all_day'] else f'EXDATE:{x.replace("-", "")}T{e["time"].replace(":", "")}00'))
        lines.append('END:VEVENT')
        for orig, ov in e['overrides'].items():
            o = {**e, **ov}
            os_, oe = _bounds(o)
            stamp = '' if o['all_day'] else f'T{orig and e["time"].replace(":", "")}00'
            lines += ['BEGIN:VEVENT', f"UID:{e['id']}@jarvis", f'RECURRENCE-ID{";VALUE=DATE" if e["all_day"] else ""}:{orig.replace("-", "")}{stamp}']
            lines += ([f'DTSTART;VALUE=DATE:{os_:%Y%m%d}', f'DTEND;VALUE=DATE:{oe:%Y%m%d}'] if o['all_day'] else [f'DTSTART:{os_:%Y%m%dT%H%M%S}', f'DTEND:{oe:%Y%m%dT%H%M%S}'])
            lines.append(f"SUMMARY:{_esc(o['title'])}")
            if o['location']:
                lines.append(f"LOCATION:{_esc(o['location'])}")
            if o['notes']:
                lines.append(f"DESCRIPTION:{_esc(o['notes'])}")
            lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    with open(ics_path(), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def _save_local(events: list[dict]) -> None:
    os.makedirs(_dir(), exist_ok=True)
    tmp = json_path() + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    os.replace(tmp, json_path())
    try:
        _write_ics(events)
    except Exception:
        _log.debug('own events export failed', exc_info=True)


def add_local(data: dict) -> dict:
    with _lock:
        events = load_local()
        if len(events) >= MAX_LOCAL:
            raise CalendarError('too_many')
        e = normalize(data)
        events.append(e)
        _save_local(events)
    return e


def update_local(eid: str, data: dict) -> dict:
    with _lock:
        events = load_local()
        for i, old in enumerate(events):
            if old['id'] == str(eid):
                new = normalize(data, old['id'], keep=old)
                if any(new[k] != old[k] for k in ('date', 'time', 'repeat', 'interval', 'weekdays')) and 'overrides' not in data:
                    new['overrides'] = {}                                  # the old dates are no longer occurrences
                events[i] = new
                _save_local(events)
                return events[i]
    raise CalendarError('unknown_event')


def update_occurrence(eid: str, occ: str, data: dict) -> dict:
    """Changes one occurrence of a repeating own event (`occ` is its date in the series): the fields in `data` replace the series' values for that day."""
    occ = _d(occ).isoformat()
    with _lock:
        events = load_local()
        for i, old in enumerate(events):
            if old['id'] != str(eid):
                continue
            if old['repeat'] == 'none':
                raise CalendarError('not_repeating')
            day = datetime.combine(date.fromisoformat(occ), datetime.min.time())
            if not any(ce.orig == occ for ce in _occurrences(old, day, day + timedelta(days=1), raw=True)):
                raise CalendarError('not_an_occurrence')
            base = _base_occurrence(old, occ)
            events[i]['overrides'] = {**old['overrides'], occ: _override({**base, **{k: data[k] for k in OV_KEYS if k in data}})}
            events[i]['exceptions'] = [x for x in old['exceptions'] if x != occ]
            _save_local(events)
            return events[i]
    raise CalendarError('unknown_event')


def reset_occurrence(eid: str, occ: str) -> bool:
    with _lock:
        events = load_local()
        for e in events:
            if e['id'] == str(eid) and occ in e['overrides']:
                del e['overrides'][occ]
                _save_local(events)
                return True
    return False


def _base_occurrence(e: dict, occ: str) -> dict:
    """The fields an occurrence has when it follows the series (the day shifted to `occ`)."""
    s, en = _bounds(e)
    delta = date.fromisoformat(occ) - s.date()
    return {'title': e['title'], 'date': occ, 'time': e['time'], 'end_date': (en.date() + delta).isoformat(), 'end_time': e['end_time'], 'all_day': e['all_day'],
            'location': e['location'], 'notes': e['notes'], 'color': e['color']}


def delete_local(eid: str, only_date: str = '') -> bool:
    """Deletes an own event, or only one day of a repeating one (that day becomes an exception)."""
    with _lock:
        events = load_local()
        for i, old in enumerate(events):
            if old['id'] != str(eid):
                continue
            if only_date and old['repeat'] != 'none':
                day = _d(only_date).isoformat()
                events[i]['exceptions'] = sorted(set(old['exceptions']) | {day})
                events[i]['overrides'] = {k: v for k, v in old['overrides'].items() if k != day}
            else:
                del events[i]
            _save_local(events)
            return True
    return False


def has_local_events() -> bool:
    return bool(load_local())


# ---- own events: occurrences ----

def _occurrences(e: dict, win_start: datetime, win_end: datetime, raw: bool = False) -> list[CalEvent]:
    """Occurrences of an own event touching the window. A changed occurrence (e['overrides']) is returned with its own time and fields;
    `raw=True` ignores the changes and the removed days (used to check that a date really is an occurrence)."""
    s, en = _bounds(e)
    length = en - s
    rule = _rule(e)
    ex = set() if raw else {datetime.combine(date.fromisoformat(x), s.time()) for x in e['exceptions']}
    starts = cp.expand(s, rule, win_start - length - timedelta(days=1), win_end, ex) if rule else [s]
    out = []

    def touches(ce):
        return local(ce.start) <= win_end and (local(ce.end) > win_start or local(ce.end) == local(ce.start) >= win_start)
    for st in starts:
        orig = st.date().isoformat()
        if not raw and orig in e['overrides']:
            continue
        ce = CalEvent(st, st + length, e['title'], e['all_day'], e['location'], e['notes'], e['id'], orig)
        if touches(ce) or raw:
            out.append(ce)
    if not raw:
        for orig, ov in e['overrides'].items():
            o = {**e, **ov}
            os_, oe = _bounds(o)
            ce = CalEvent(os_, oe, ov['title'], ov['all_day'], ov['location'], ov['notes'], e['id'], orig)
            if orig not in e['exceptions'] and touches(ce):
                out.append(ce)
    return out


def upcoming_local(lo: datetime, hi: datetime, include_all_day: bool = True) -> list[tuple[datetime, str, str]]:
    out = []
    now = datetime.now()
    for e in load_local():
        for ce in _occurrences(e, lo, hi):
            if ce.all_day:
                if include_all_day and local(ce.end) > now:
                    out.append((ce.start, ce.title, OWN_NAME))
            elif local(ce.start) >= lo:
                out.append((ce.start, ce.title, OWN_NAME))
    return out


# ---- sources ----

def _ref(src: dict) -> str:
    return str(src.get('url') or src.get('path') or src.get('caldav') or '').strip()


def sources_info() -> list[dict]:
    """Calendar sources from the settings: ref, display name, colour, hidden flag. The old registration of the own-events export is left out."""
    out = []
    for i, src in enumerate(_settings().get('calendar_sources') or []):
        ref = _ref(src) if isinstance(src, dict) else ''
        if not ref or ref == ics_path():
            continue
        label = ref.rsplit('/', 1)[-1] if ref.lower().startswith(('http', 'webcal')) else os.path.basename(ref)
        out.append({'ref': ref, 'name': str(src.get('name') or (label or ref)[:40]), 'color': str(src.get('color') or COLORS[(i + 1) % len(COLORS)]), 'hidden': bool(src.get('hidden')),
                    'kind': 'caldav' if src.get('caldav') else 'ics', 'id': str(src.get('id') or ''), 'writable': bool(src.get('caldav'))})
    return out


@dataclass
class Fetched:
    text: str
    status: str                  # 'ok' | 'stale' (could not refresh, showing what was downloaded before) | 'error'


_cache: dict[str, tuple[float, str]] = {}
_errors: dict[str, str] = {}


def fetch(ref: str, ttl: int = CACHE_TTL, force: bool = False) -> Fetched:
    from actions import calendar_ics
    now = time.time()
    with _lock:
        hit = _cache.get(ref)
    if hit and not force and now - hit[0] < ttl:
        return Fetched(hit[1], 'ok')
    try:
        ok, raw = calendar_ics._fetch_text(ref)
        if not ok:
            raise OSError('unavailable')
    except Exception as ex:
        with _lock:
            _errors[ref] = str(ex)[:120]
        return Fetched(hit[1], 'stale') if hit else Fetched('', 'error')
    with _lock:
        _cache[ref] = (now, raw)
        _errors.pop(ref, None)
    return Fetched(raw, 'ok')


def status_of(ref: str) -> str:
    """'ok' when the source was downloaded, 'error' when the last try failed, 'unknown' before the first try."""
    with _lock:
        return 'error' if ref in _errors and ref not in _cache else 'ok' if ref in _cache else 'unknown'


def refresh() -> None:
    with _lock:
        _cache.clear()


def forget(ref: str) -> None:
    with _lock:
        _cache.pop(ref, None)
        _errors.pop(ref, None)


# ---- query ----

def _fmt(ev: CalEvent, source: str, color: str, ref: str, own: dict | None = None) -> dict:
    s, e = ev.local_start(), ev.local_end()
    if ev.all_day:
        last = (e - timedelta(days=1)).date()
        end_date, end_time = max(last, s.date()).isoformat(), ''
        time_s = ''
    else:
        end_date, end_time, time_s = e.date().isoformat(), (e.strftime('%H:%M') if e > s else ''), s.strftime('%H:%M')
    raw_id = f'{ref}|{ev.uid}|{s.isoformat()}|{ev.title}'
    d = {'id': hashlib.md5(raw_id.encode('utf-8', 'ignore'), usedforsecurity=False).hexdigest()[:12], 'title': ev.title, 'date': s.date().isoformat(), 'time': time_s, 'end_date': end_date,
         'end_time': end_time, 'all_day': ev.all_day, 'location': ev.location, 'notes': ev.notes[:2000], 'source': source, 'ref': ref, 'color': color, 'local': own is not None}
    if own is not None:
        occ = ev.orig or s.date().isoformat()
        d.update({'id': f"{own['id']}:{occ}", 'eid': own['id'], 'occ': occ, 'changed': occ in own['overrides'], 'repeat': own['repeat'], 'interval': own['interval'], 'weekdays': own['weekdays'], 'until': own['until'],
                  'remind': own['remind'], 'series': {k: own[k] for k in ('date', 'time', 'end_date', 'end_time', 'all_day')}})
    return d


def _sort_key(e: dict):
    return (e['date'], 0 if e['all_day'] else 1, e['time'], e['title'].lower())


def events_between(d0: date, d1: date) -> dict:
    """Events of all visible sources and the own events that touch [d0, d1], as dicts for the screen, plus the state of every source."""
    win_start, win_end = datetime.combine(d0, datetime.min.time()), datetime.combine(d1, datetime.max.time()).replace(microsecond=0)
    out, status, seen = [], [], set()
    for e in load_local():
        for ce in _occurrences(e, win_start, win_end):
            out.append(_fmt(ce, OWN_NAME, e['color'] or COLORS[0], 'own', e))
    for src in sources_info():
        if src['hidden']:
            continue
        if src['kind'] == 'caldav':
            _dav_events(src, win_start, win_end, out, status)
            continue
        f = fetch(src['ref'])
        status.append({'ref': src['ref'], 'ok': f.status == 'ok', 'stale': f.status == 'stale'})
        if f.status == 'error':
            continue
        for ce in cp.parse_events(f.text, win_start, win_end):
            key = (ce.local_start(), ce.title)
            if key in seen:
                continue
            seen.add(key)
            out.append(_fmt(ce, src['name'], src['color'], src['ref']))
    out.sort(key=_sort_key)
    return {'events': out, 'status': status}


def search(q: str, back_days: int = 365, ahead_days: int = 365, limit: int = 100) -> list[dict]:
    q = ' '.join(str(q or '').lower().split())
    if len(q) < 2:
        return []
    today = date.today()
    res = events_between(today - timedelta(days=back_days), today + timedelta(days=ahead_days))
    hits = [e for e in res['events'] if q in f"{e['title']} {e['location']} {e['notes']}".lower()]
    hits.sort(key=lambda e: (abs((date.fromisoformat(e['date']) - today).days), e['date']))
    return hits[:limit]


# ---- reminders ----

def due_reminders(now: datetime, default_lead: int, enabled: bool = True) -> list[tuple[str, int, str]]:
    """(key, minutes left, title) of every reminder that should have been announced by now and whose event has not started. `key` identifies one
    reminder of one occurrence so the caller can announce it once. Own events may carry their own lead times (a list, or [] for none); every
    other timed event uses `default_lead` while `enabled`. All-day events get a reminder only when the own event asks for one."""
    res = events_between(now.date(), (now + timedelta(days=8)).date())
    out = []
    for ev in res['events']:
        own = ev['remind'] if ev['local'] and ev.get('remind') is not None else None
        if own is None and (not enabled or ev['all_day']):
            continue
        leads = own if own is not None else [default_lead]
        start = datetime.fromisoformat(f"{ev['date']}T{ev['time'] or '00:00'}")
        left = (start - now).total_seconds()
        if left <= 0:
            continue
        for lead in leads:
            if left <= lead * 60:
                out.append((f"{ev.get('eid') or ev['title']}|{start:%Y-%m-%dT%H:%M}|{lead}", max(1, math.ceil(left / 60)), ev['title']))
    return out


# ---- CalDAV calendars (read and write) ----
_dav_cache: dict[tuple, tuple[float, list]] = {}
DAV_TTL = 120


def _pass_key(sid: str) -> str:
    return f'JARVIS_CALDAV_PASS_{sid.upper()}'


def _dav_entry(sid: str) -> dict:
    for x in _settings().get('calendar_sources') or []:
        if isinstance(x, dict) and x.get('caldav') and str(x.get('id')) == str(sid):
            return x
    raise CalendarError('unknown_source')


def _dav_client(entry: dict):
    from actions.caldav_client import Client
    return Client(entry['server'], entry.get('user', ''), os.environ.get(_pass_key(str(entry['id'])), ''))


def _dav_objects(entry: dict, win_start: datetime, win_end: datetime, force: bool = False) -> list[dict]:
    key = (entry['id'], win_start.date().isoformat(), win_end.date().isoformat())
    now = time.time()
    with _lock:
        hit = _dav_cache.get(key)
    if hit and not force and now - hit[0] < DAV_TTL:
        return hit[1]
    objs = _dav_client(entry).objects(entry['caldav'], win_start - timedelta(days=1), win_end + timedelta(days=1))
    with _lock:
        _dav_cache[key] = (now, objs)
    return objs


def _dav_events(src: dict, win_start: datetime, win_end: datetime, out: list, status: list) -> None:
    from actions.caldav_client import CalDavError
    entry = _dav_entry(src['id'])
    try:
        objs = _dav_objects(entry, win_start, win_end)
        status.append({'ref': src['ref'], 'ok': True, 'stale': False})
    except CalDavError as ex:
        with _lock:
            stale = next((v[1] for k, v in _dav_cache.items() if k[0] == entry['id']), None)
            _errors[src['ref']] = ex.message
        status.append({'ref': src['ref'], 'ok': False, 'stale': stale is not None, 'error': ex.code})
        objs = stale or []
    for o in objs:
        up = o['ics'].upper()
        simple = 'RRULE' not in up and 'RECURRENCE-ID' not in up and up.count('BEGIN:VEVENT') == 1
        for ce in cp.parse_events(o['ics'], win_start, win_end):
            d = _fmt(ce, src['name'], src['color'], src['ref'])
            d.update({'src': src['id'], 'href': o['href'], 'etag': o['etag'], 'rw': simple, 'id': hashlib.md5(f"{o['href']}|{ce.local_start().isoformat()}".encode(), usedforsecurity=False).hexdigest()[:12]})
            out.append(d)


def upcoming_remote(lo: datetime, hi: datetime, include_all_day: bool = True) -> list[tuple[datetime, str, str]]:
    """Events of the CalDAV calendars for the voice summary: (start, title, calendar name)."""
    out, now = [], datetime.now()
    for src in sources_info():
        if src['kind'] != 'caldav' or src['hidden']:
            continue
        try:
            evs, st = [], []
            _dav_events(src, lo, hi, evs, st)
        except Exception:
            continue
        for d in evs:
            start = datetime.fromisoformat(f"{d['date']}T{d['time'] or '00:00'}")
            if d['all_day']:
                if include_all_day and datetime.fromisoformat(f"{d['end_date']}T00:00") + timedelta(days=1) > now:
                    out.append((start, d['title'], src['name']))
            elif start >= lo:
                out.append((start, d['title'], src['name']))
    return out


















