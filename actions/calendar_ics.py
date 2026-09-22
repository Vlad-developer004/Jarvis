from __future__ import annotations
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
_SETTINGS_PATH = Path('data') / 'jarvis_settings.json'
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
def parse_ics_events(raw: str, limit: int = 64) -> list[tuple[datetime, str]]:
    text = _unfold(raw)
    events: list[tuple[datetime, str]] = []
    for block in text.split('BEGIN:VEVENT'):
        if 'END:VEVENT' not in block:
            continue
        chunk = block.split('END:VEVENT', 1)[0]
        dt_start: datetime | None = None
        summary = ''
        for ln in chunk.splitlines():
            ul = ln.upper()
            if ul.startswith('DTSTART'):
                d = _event_dt(ln)
                if d:
                    dt_start = d
                    break
        for ln in chunk.splitlines():
            ul = ln.upper()
            if ul.startswith('SUMMARY'):
                summary = _summary(ln) or summary
        if dt_start:
            events.append((dt_start, summary or '(без названия)'))
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
