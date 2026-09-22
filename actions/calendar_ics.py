from __future__ import annotations
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from config_pack.config import get_settings_path
# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\jarvis_settings.json)
# — this used to be a project-relative 'data/jarvis_settings.json' instead, a
# different file that other settings readers never saw and that a rebuild/
# reinstall silently wipes (the bundled data/ folder gets overwritten).
_SETTINGS_PATH = Path(get_settings_path())
def _load_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}
def _unfold(raw: str) -> str:
    lines = raw.replace('\r\n', '\n').split('\n')
    out: list[str] = []
    for line in lines:
        if line and line[0] in ' \t' and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return '\n'.join(out)
def _parse_dt_value(val: str) -> datetime | None:
    val = val.strip()
    if not val:
        return None
    if val.endswith('Z'):
        val = val[:-1]
        try:
            if len(val) >= 15:
                dt = datetime.strptime(val[:15], '%Y%m%dT%H%M%S')
            else:
                dt = datetime.strptime(val, '%Y%m%dT%H%M')
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                dt = datetime.strptime(val[:13], '%Y%m%dT%H%M')
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
    if re.fullmatch(r'\d{8}', val):
        try:
            return datetime.strptime(val, '%Y%m%d')
        except ValueError:
            return None
    if 'T' in val:
        for fmt in ('%Y%m%dT%H%M%S', '%Y%m%dT%H%M'):
            try:
                return datetime.strptime(val[:15], fmt)
            except ValueError:
                continue
    return None
def _event_dt(line: str) -> datetime | None:
    if ':' not in line:
        return None
    _, rest = line.split(':', 1)
    return _parse_dt_value(rest)
def _summary(line: str) -> str:
    if not line.upper().startswith('SUMMARY'):
        return ''
    parts = line.split(':', 1)
    if len(parts) < 2:
        return ''
    return parts[1].strip().replace('\\n', ' ').replace('\\,', ',')
def _fetch_text(ref: str) -> tuple[bool, str]:
    ref = ref.strip()
    if not ref:
        return False, ''
    low = ref.lower()
    if low.startswith(('http://', 'https://', 'webcal://')):
        u = ref.replace('webcal://', 'https://', 1)
        req = Request(u, headers={'User-Agent': 'JARVIS-Calendar/1.0'})
        with urlopen(req, timeout=15) as r:
            return True, r.read().decode('utf-8', errors='ignore')
    p = Path(ref)
    if p.exists():
        return True, p.read_text(encoding='utf-8', errors='ignore')
    return False, ''
_RRULE_WEEKDAYS = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}

def _parse_rrule(rrule_line: str) -> dict:
    """Parses an RRULE line ('RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=10') into
    an upper-cased key->value dict of its components."""
    if ':' not in rrule_line:
        return {}
    _, val = rrule_line.split(':', 1)
    rule: dict[str, str] = {}
    for part in val.split(';'):
        if '=' not in part:
            continue
        k, v = part.split('=', 1)
        rule[k.strip().upper()] = v.strip()
    return rule

def _align_tzinfo(ref: datetime, other: datetime) -> datetime:
    """Makes `other`'s tz-awareness match `ref`'s, so they can be compared."""
    if ref.tzinfo and not other.tzinfo:
        return other.replace(tzinfo=timezone.utc)
    if not ref.tzinfo and other.tzinfo:
        return other.replace(tzinfo=None)
    return other

def _add_months(dt: datetime, months: int) -> datetime:
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = dt.day
    while day > 28:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return dt.replace(year=year, month=month, day=day)

def _expand_rrule(dt_start: datetime, rule: dict, horizon: datetime, max_occurrences: int = 200) -> list[datetime]:
    """Expands a recurring VEVENT's RRULE into concrete occurrence datetimes,
    from dt_start up to `horizon` (or COUNT/UNTIL, whichever limits first).
    Supports FREQ=DAILY/WEEKLY/MONTHLY/YEARLY with INTERVAL, COUNT, UNTIL,
    and BYDAY (weekly only). Unsupported/malformed FREQ falls back to a
    single occurrence (the plain DTSTART) rather than erroring."""
    freq = rule.get('FREQ', '').upper()
    if freq not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'):
        return [dt_start]
    try:
        interval = max(1, int(rule.get('INTERVAL', '1')))
    except ValueError:
        interval = 1
    count = None
    if 'COUNT' in rule:
        try:
            count = max(1, int(rule['COUNT']))
        except ValueError:
            count = None
    until = _parse_dt_value(rule['UNTIL']) if 'UNTIL' in rule else None
    if until:
        until = _align_tzinfo(dt_start, until)

    occurrences: list[datetime] = []

    if freq == 'WEEKLY' and 'BYDAY' in rule:
        byday_idx = sorted({_RRULE_WEEKDAYS[d.strip().upper()[-2:]]
                             for d in rule['BYDAY'].split(',')
                             if d.strip().upper()[-2:] in _RRULE_WEEKDAYS})
        if not byday_idx:
            byday_idx = [dt_start.weekday()]
        week_start = dt_start - timedelta(days=dt_start.weekday())
        while len(occurrences) < max_occurrences:
            stop = False
            for wd in byday_idx:
                occ = (week_start + timedelta(days=wd)).replace(
                    hour=dt_start.hour, minute=dt_start.minute, second=dt_start.second)
                if occ < dt_start:
                    continue
                if occ > horizon or (until and occ > until):
                    stop = True
                    break
                occurrences.append(occ)
                if count and len(occurrences) >= count:
                    stop = True
                    break
            if stop or len(occurrences) >= max_occurrences:
                break
            week_start += timedelta(weeks=interval)
        return occurrences[:max_occurrences]

    cur = dt_start
    while len(occurrences) < max_occurrences:
        if cur > horizon or (until and cur > until):
            break
        occurrences.append(cur)
        if count and len(occurrences) >= count:
            break
        if freq == 'DAILY':
            cur = cur + timedelta(days=interval)
        elif freq == 'WEEKLY':
            cur = cur + timedelta(weeks=interval)
        elif freq == 'MONTHLY':
            cur = _add_months(cur, interval)
        elif freq == 'YEARLY':
            cur = _add_months(cur, interval * 12)
    return occurrences

def parse_ics_events(raw: str, limit: int = 64, horizon_days: int = 60) -> list[tuple[datetime, str]]:
    text = _unfold(raw)
    events: list[tuple[datetime, str]] = []
    horizon_utc = datetime.now(timezone.utc) + timedelta(days=horizon_days)
    for block in text.split('BEGIN:VEVENT'):
        if 'END:VEVENT' not in block:
            continue
        chunk = block.split('END:VEVENT', 1)[0]
        dt_start: datetime | None = None
        summary = ''
        rrule: dict | None = None
        exdates: set[datetime] = set()
        for ln in chunk.splitlines():
            ul = ln.upper()
            if ul.startswith('DTSTART') and dt_start is None:
                d = _event_dt(ln)
                if d:
                    dt_start = d
            elif ul.startswith('SUMMARY'):
                summary = _summary(ln) or summary
            elif ul.startswith('RRULE'):
                rrule = _parse_rrule(ln)
            elif ul.startswith('EXDATE'):
                ed = _event_dt(ln)
                if ed:
                    exdates.add(ed)
        if not dt_start:
            continue
        title = summary or '(без названия)'
        if rrule:
            horizon = _align_tzinfo(dt_start, horizon_utc)
            for occ in _expand_rrule(dt_start, rrule, horizon):
                if occ in exdates:
                    continue
                events.append((occ, title))
        else:
            events.append((dt_start, title))
    events.sort(key=lambda x: x[0])
    return events[:limit]
def _collect_upcoming(settings: dict | None) -> list[tuple[datetime, str, str]]:
    s = settings if isinstance(settings, dict) else _load_settings()
    sources = s.get('calendar_sources')
    if not isinstance(sources, list) or not sources:
        return []
    def _is_upcoming(dt: datetime) -> bool:
        margin = timedelta(hours=1)
        if dt.tzinfo:
            return dt >= datetime.now(timezone.utc) - margin
        return dt >= datetime.now() - margin
    collected: list[tuple[datetime, str, str]] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        ref = (src.get('url') or src.get('path') or '').strip()
        if not ref:
            continue
        ok, raw = _fetch_text(ref)
        if not ok or not raw:
            continue
        label = ref
        if len(label) > 48:
            label = label[:45] + '...'
        for dt, title in parse_ics_events(raw, limit=80):
            if not _is_upcoming(dt):
                continue
            collected.append((dt, title, label))
    collected.sort(key=lambda x: x[0])
    return collected
def next_event_dt(settings: dict | None = None) -> tuple[datetime, str] | None:
    """Soonest upcoming event as (start, title), for cross-checking against weather."""
    collected = _collect_upcoming(settings)
    if not collected:
        return None
    dt, title, _label = collected[0]
    return (dt, title)
def next_events_summary(settings: dict | None, max_events: int = 3) -> str:
    s = settings if isinstance(settings, dict) else _load_settings()
    sources = s.get('calendar_sources')
    if not isinstance(sources, list) or not sources:
        return 'Календарь не настроен. Добавьте файл или ссылку на календарь в настройках.'
    collected = _collect_upcoming(s)
    if not collected:
        return 'Нет ближайших событий в указанных ICS или источники недоступны.'
    out: list[str] = []
    for dt, title, label in collected[:max_events]:
        if dt.tzinfo:
            local = dt.astimezone()
        else:
            local = dt
        out.append(f'{local.strftime("%d.%m %H:%M")} — {title} (источник: {label})')
    return 'Ближайшие события: ' + '; '.join(out)
