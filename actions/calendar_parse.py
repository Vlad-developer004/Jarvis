"""ICS (iCalendar) parsing for the calendar: events with end time, all-day flag, place and notes, time zones (TZID), recurrence rules expanded
inside a time window (so a daily series that started years ago still reaches today), EXDATE, moved or cancelled instances (RECURRENCE-ID),
and the same recurrence engine for the user's own events (actions/calendar_hub.py).

`start` and `end` keep the form they have in the file: aware (UTC or a named zone) or naive ("floating", meaning local time). Use `local()` to
get naive local time for comparing and showing. For all-day events `start` is midnight and `end` is the exclusive end (midnight of the next day).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

MAX_STEPS = 20000                                   # safety stop for one series
_WEEKDAYS = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}


@dataclass
class CalEvent:
    start: datetime
    end: datetime
    title: str
    all_day: bool = False
    location: str = ''
    notes: str = ''
    uid: str = ''
    orig: str = ''                                     # own events: the date this occurrence has in its series (differs from the start when it was moved)

    def local_start(self) -> datetime:
        return local(self.start)

    def local_end(self) -> datetime:
        return local(self.end)


def local(dt: datetime) -> datetime:
    """Naive local time of a datetime (aware ones are converted)."""
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


# ---- low level ----

def unfold(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if line and line[0] in ' \t' and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _unescape(v: str) -> str:
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m.group(1) in 'nN' else m.group(1), v)


def _prop(line: str):
    """'NAME;P=V;P2=V2:value' -> (NAME, {P: V}, value) or None."""
    head, sep, value = line.partition(':')
    if not sep:
        return None
    parts = head.split(';')
    params = {}
    for p in parts[1:]:
        k, _, v = p.partition('=')
        params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def _zone(name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return None


def parse_value(value: str, params: dict | None = None) -> tuple[datetime | None, bool]:
    """A DATE / DATE-TIME value -> (datetime, is_date_only)."""
    v = (value or '').strip()
    params = params or {}
    if not v:
        return None, False
    try:
        if params.get('VALUE', '').upper() == 'DATE' or re.fullmatch(r'\d{8}', v):
            return datetime.strptime(v[:8], '%Y%m%d'), True
        utc = v.endswith('Z')
        core = v.rstrip('Z')
        fmt = '%Y%m%dT%H%M%S' if len(core) >= 15 else '%Y%m%dT%H%M'
        dt = datetime.strptime(core[:15] if len(core) >= 15 else core[:13], fmt)
        if utc:
            return dt.replace(tzinfo=timezone.utc), False
        tz = _zone(params.get('TZID', '')) if params.get('TZID') else None
        return (dt.replace(tzinfo=tz) if tz else dt), False
    except ValueError:
        return None, False


def parse_duration(v: str) -> timedelta | None:
    m = re.fullmatch(r'([+-]?)P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', (v or '').strip().upper())
    if not m or not any(m.groups()[1:]):
        return None
    sign = -1 if m.group(1) == '-' else 1
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    return sign * timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def parse_rrule(value: str) -> dict:
    rule = {}
    for part in (value or '').split(';'):
        k, sep, v = part.partition('=')
        if sep:
            rule[k.strip().upper()] = v.strip()
    return rule


# ---- recurrence ----

def add_months(dt: datetime, months: int) -> datetime:
    total = dt.month - 1 + months
    year, month = dt.year + total // 12, total % 12 + 1
    day = dt.day
    while True:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1


def _nth_weekday(year: int, month: int, wd: int, n: int) -> date | None:
    """The n-th (1..5) or last (-1) weekday `wd` of a month."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(wd - d.weekday()) % 7 + 7 * (n - 1))
        return d if d.month == month else None
    nxt = date(year + month // 12, month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    d -= timedelta(days=(d.weekday() - wd) % 7)
    return d


def _same_kind(ref: datetime, other: datetime) -> datetime:
    if ref.tzinfo and not other.tzinfo:
        return other.replace(tzinfo=timezone.utc)
    if not ref.tzinfo and other.tzinfo:
        return local(other)
    return other


def expand(start: datetime, rule: dict, win_start: datetime | None, win_end: datetime | None, exdates: set | None = None, limit: int = 5000) -> list[datetime]:
    """Occurrence start times of a series, inside [win_start, win_end] (both naive local, or None for open). Counting (COUNT) always starts at
    the first occurrence, so the series is walked from DTSTART, but only the occurrences inside the window are kept."""
    freq = rule.get('FREQ', '').upper()
    if freq not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'):
        return [start]
    try:
        interval = max(1, int(rule.get('INTERVAL', '1')))
    except ValueError:
        interval = 1
    try:
        count = max(1, int(rule['COUNT'])) if 'COUNT' in rule else None
    except ValueError:
        count = None
    until = None
    if 'UNTIL' in rule:
        u, date_only = parse_value(rule['UNTIL'])
        until = local(_same_kind(start, u)) if u and not date_only else (u + timedelta(days=1) - timedelta(seconds=1) if u else None)
    ex = {local(e) for e in (exdates or set())}
    out: list[datetime] = []
    total = 0                                       # occurrences generated so far (for COUNT)

    def emit(occ: datetime) -> bool:
        """Adds one occurrence; returns False when the series is over."""
        nonlocal total
        lo = local(occ)
        if (until and lo > until) or (win_end and lo > win_end):
            return False
        total += 1
        if count and total > count:
            return False
        if (win_start and lo < win_start) or lo in ex:
            return True
        out.append(occ)
        return len(out) < limit

    steps = 0
    if freq == 'WEEKLY':
        days = sorted({_WEEKDAYS[d[-2:]] for d in rule.get('BYDAY', '').upper().split(',') if d[-2:] in _WEEKDAYS}) or [start.weekday()]
        week = start - timedelta(days=start.weekday())
        while steps < MAX_STEPS:
            steps += 1
            for wd in days:
                occ = week + timedelta(days=wd)
                if occ < start:
                    continue
                if not emit(occ):
                    return out
            week += timedelta(weeks=interval)
            if win_end and local(week) > win_end + timedelta(days=7) and not count:
                break
        return out
    if freq == 'MONTHLY' and (rule.get('BYDAY') or rule.get('BYMONTHDAY')):
        month_off = 0
        while steps < MAX_STEPS:
            steps += 1
            base = add_months(start.replace(day=1), month_off)
            cands: list[date] = []
            if rule.get('BYDAY'):
                for tok in rule['BYDAY'].upper().split(','):
                    m = re.fullmatch(r'([+-]?\d)?(MO|TU|WE|TH|FR|SA|SU)', tok.strip())
                    if m and m.group(1):
                        d = _nth_weekday(base.year, base.month, _WEEKDAYS[m.group(2)], int(m.group(1)))
                        if d:
                            cands.append(d)
            else:
                for tok in rule['BYMONTHDAY'].split(','):
                    try:
                        n = int(tok)
                    except ValueError:
                        continue
                    nxt = date(base.year + base.month // 12, base.month % 12 + 1, 1)
                    last = (nxt - timedelta(days=1)).day
                    day = n if n > 0 else last + 1 + n
                    if 1 <= day <= last:
                        cands.append(date(base.year, base.month, day))
            for d in sorted(set(cands)):
                occ = datetime.combine(d, start.timetz())
                if occ < start:
                    continue
                if not emit(occ):
                    return out
            month_off += interval
            if win_end and local(base) > win_end and not count:
                break
        return out
    cur = start
    while steps < MAX_STEPS:
        steps += 1
        if not emit(cur):
            break
        if freq == 'DAILY':
            cur = cur + timedelta(days=interval)
        elif freq == 'WEEKLY':
            cur = cur + timedelta(weeks=interval)
        elif freq == 'MONTHLY':
            cur = add_months(start, interval * steps)
        else:
            cur = add_months(start, 12 * interval * steps)
    return out


# ---- events ----

def _end_of(start: datetime, all_day: bool, dtend, dur: timedelta | None) -> datetime:
    if dtend is not None:
        end = dtend
        if all_day and local(end) <= local(start):
            end = start + timedelta(days=1)
        return end
    if dur is not None:
        return start + dur
    return start + timedelta(days=1) if all_day else start


def parse_events(raw: str, win_start: datetime | None = None, win_end: datetime | None = None, limit: int = 5000) -> list[CalEvent]:
    """All events of an ICS text that overlap [win_start, win_end] (naive local; None = open), recurring ones expanded, sorted by start."""
    blocks: list[list[tuple]] = []
    cur: list[tuple] | None = None
    for line in unfold(raw):
        up = line.strip().upper()
        if up == 'BEGIN:VEVENT':
            cur = []
        elif up == 'END:VEVENT':
            if cur is not None:
                blocks.append(cur)
            cur = None
        elif cur is not None:
            p = _prop(line)
            if p:
                cur.append(p)
    masters: list[dict] = []
    overrides: dict[tuple, dict] = {}
    for props in blocks:
        d: dict = {'exdates': set(), 'rrule': None, 'title': '', 'location': '', 'notes': '', 'uid': '', 'status': '', 'rid': None, 'dur': None, 'dtend': None}
        for name, params, value in props:
            if name == 'DTSTART' and 'start' not in d:
                dt, date_only = parse_value(value, params)
                if dt:
                    d['start'], d['all_day'] = dt, date_only
            elif name == 'DTEND':
                d['dtend'] = parse_value(value, params)[0]
            elif name == 'DURATION':
                d['dur'] = parse_duration(value)
            elif name == 'SUMMARY':
                d['title'] = _unescape(value).strip()
            elif name == 'LOCATION':
                d['location'] = _unescape(value).strip()
            elif name == 'DESCRIPTION':
                d['notes'] = _unescape(value).strip()
            elif name == 'UID':
                d['uid'] = value.strip()
            elif name == 'STATUS':
                d['status'] = value.strip().upper()
            elif name == 'RRULE':
                d['rrule'] = parse_rrule(value)
            elif name == 'EXDATE':
                for part in value.split(','):
                    e = parse_value(part, params)[0]
                    if e:
                        d['exdates'].add(e)
            elif name == 'RECURRENCE-ID':
                d['rid'] = parse_value(value, params)[0]
        if 'start' not in d:
            continue
        if d['rid'] is not None and d['uid']:
            overrides[(d['uid'], local(d['rid']))] = d
        else:
            masters.append(d)

    def overlaps(s: datetime, e: datetime) -> bool:
        ls, le = local(s), local(e)
        if win_end and ls > win_end:
            return False
        if win_start and (le < win_start or (le == win_start and le != ls)):
            return False
        return True

    def make(d: dict, s: datetime) -> CalEvent:
        all_day = d['all_day']
        end = s + (_end_of(d['start'], all_day, d['dtend'], d['dur']) - d['start'])
        return CalEvent(s, end, d['title'] or '(без названия)', all_day, d['location'], d['notes'], d['uid'])

    out: list[CalEvent] = []
    used: set[tuple] = set()
    for d in masters:
        if d['status'] == 'CANCELLED':
            continue
        if d['rrule']:
            wide_start = (win_start - (local(_end_of(d['start'], d['all_day'], d['dtend'], d['dur'])) - local(d['start'])) - timedelta(days=1)) if win_start else None
            starts = expand(d['start'], d['rrule'], wide_start, win_end, d['exdates'], limit)
        else:
            starts = [d['start']]
        for s in starts:
            ov = overrides.get((d['uid'], local(s))) if d['uid'] else None
            if ov is not None:
                used.add((d['uid'], local(s)))
                if ov['status'] == 'CANCELLED':
                    continue
                ev = make(ov, ov['start'])
            else:
                ev = make(d, s)
            if overlaps(ev.start, ev.end):
                out.append(ev)
    master_uids = {d['uid'] for d in masters if d['uid'] and d['status'] != 'CANCELLED'}
    for key, ov in overrides.items():                       # an instance moved into the window from outside it
        if key not in used and key[0] in master_uids and ov['status'] != 'CANCELLED':
            ev = make(ov, ov['start'])
            if overlaps(ev.start, ev.end):
                out.append(ev)
    out.sort(key=lambda e: local(e.start))
    return out[:limit]
