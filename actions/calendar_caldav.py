"""CalDAV calendar discovery and event writes (create, update, delete), split out of calendar_hub; reads stay in calendar_hub."""

from actions import calendar_parse as cp
from datetime import date, datetime, timedelta, timezone
import re
import uuid
from actions.calendar_hub import (CalendarError, _bounds, _dav_cache, _dav_client, _dav_entry, _esc, _lock, _pass_key, _settings, normalize)

def caldav_find(server: str, user: str, password: str) -> list[dict]:
    """The calendars a server offers for this login (nothing is stored)."""
    from actions.caldav_client import Client
    from actions.caldav_client import PRESETS
    server = PRESETS.get(server, server)
    return Client(server, user, password).calendars()

def caldav_add(server: str, user: str, password: str, picks: list[dict]) -> list[dict]:
    """Connects the chosen calendars. The password goes to the secrets file (JARVIS_CALDAV_PASS_<id>), never into the settings."""
    from actions.mail_client import _update_env_var
    from core import settings_io
    from actions.caldav_client import PRESETS
    server = PRESETS.get(server, server)
    srcs = [x for x in (_settings().get('calendar_sources') or []) if isinstance(x, dict)]
    have = {str(x.get('caldav')) for x in srcs}
    sid = uuid.uuid4().hex[:8]
    added = []
    for p in picks[:20]:
        href = str(p.get('href') or '').strip()
        if not href.startswith(('https://', 'http://')) or href in have:
            continue
        added.append({'caldav': href, 'server': server, 'user': str(user)[:200], 'id': sid, 'name': str(p.get('name') or 'Календарь')[:40]})
        if re.fullmatch(r'#[0-9a-fA-F]{6}', str(p.get('color') or '')):
            added[-1]['color'] = p['color']
    if not added:
        raise CalendarError('exists')
    _update_env_var(_pass_key(sid), password)
    settings_io.update({'calendar_sources': srcs + added})
    return added

def _vevent_text(uid: str, e: dict) -> list[str]:
    s, en = _bounds(e)
    lines = [f'UID:{uid}', f'DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}']
    if e['all_day']:
        lines += [f'DTSTART;VALUE=DATE:{s:%Y%m%d}', f'DTEND;VALUE=DATE:{en:%Y%m%d}']
    else:
        lines += [f'DTSTART:{s.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}', f'DTEND:{en.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}']
    lines.append(f"SUMMARY:{_esc(e['title'])}")
    if e['location']:
        lines.append(f"LOCATION:{_esc(e['location'])}")
    if e['notes']:
        lines.append(f"DESCRIPTION:{_esc(e['notes'])}")
    return lines

def _patch_ics(text: str, lines: list[str]) -> str:
    """Replaces the time, title, place and notes inside the first VEVENT of an existing object, keeping everything else (guests, alarms...)."""
    drop = ('DTSTART', 'DTEND', 'DURATION', 'SUMMARY', 'LOCATION', 'DESCRIPTION', 'DTSTAMP', 'LAST-MODIFIED', 'UID')
    out, inside, done = [], False, False
    keep_uid = ''
    for ln in cp.unfold(text):
        up = ln.upper()
        if up.startswith('BEGIN:VEVENT') and not done:
            inside = True
            out.append(ln)
            continue
        if inside and up.startswith('END:VEVENT'):
            out += [x for x in lines if not x.startswith('UID:')] + [f'UID:{keep_uid}'] if keep_uid else lines
            out.append(ln)
            inside, done = False, True
            continue
        if inside:
            name = up.split(':', 1)[0].split(';', 1)[0]
            if name == 'UID':
                keep_uid = ln.split(':', 1)[1]
            if name in drop:
                continue
        out.append(ln)
    return '\r\n'.join(out) + '\r\n'

def _dav_fields(data: dict) -> dict:
    keys = ('title', 'date', 'time', 'end_date', 'end_time', 'all_day', 'location', 'notes')
    return normalize({**{k: data[k] for k in keys if k in data}, 'repeat': 'none'})

def _check_href(entry: dict, href: str) -> str:
    href = str(href or '')
    if not href.startswith(str(entry['caldav']).rstrip('/') + '/'):
        raise CalendarError('bad_href')
    return href

def caldav_create(sid: str, data: dict) -> dict:
    from actions.caldav_client import Client
    entry = _dav_entry(sid)
    e = _dav_fields(data)
    href, uid = Client.new_href(entry['caldav'])
    ics = '\r\n'.join(['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Jarvis//CalDAV//RU', 'BEGIN:VEVENT'] + _vevent_text(uid, e) + ['END:VEVENT', 'END:VCALENDAR']) + '\r\n'
    _dav_client(entry).put(href, ics, create=True)
    with _lock:
        _dav_cache.clear()
    return e

def caldav_update(sid: str, href: str, data: dict) -> dict:
    entry = _dav_entry(sid)
    href = _check_href(entry, href)
    e = _dav_fields(data)
    c = _dav_client(entry)
    etag, text = c.get(href)
    up = text.upper()
    if 'RRULE' in up or 'RECURRENCE-ID' in up:
        raise CalendarError('recurring_readonly')
    uid = next((ln.split(':', 1)[1] for ln in cp.unfold(text) if ln.upper().startswith('UID:')), uuid.uuid4().hex)
    c.put(href, _patch_ics(text, _vevent_text(uid, e)), etag)
    with _lock:
        _dav_cache.clear()
    return e

def caldav_delete(sid: str, href: str) -> None:
    entry = _dav_entry(sid)
    href = _check_href(entry, href)
    c = _dav_client(entry)
    etag, text = c.get(href)
    if 'RRULE' in text.upper() or 'RECURRENCE-ID' in text.upper():
        raise CalendarError('recurring_readonly')
    c.delete(href, etag)
    with _lock:
        _dav_cache.clear()
