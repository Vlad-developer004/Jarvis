"""Calendar sources (ICS links and files) for the voice command "что в календаре", the morning briefing and the weather cross-check.

Parsing lives in actions/calendar_parse.py (end times, time zones, recurrence inside a window, moved and cancelled instances). Everything the
calendar screen and the reminder loop need (own events, cached downloads, search) is in actions/calendar_hub.py. This module keeps the
settings-driven entry points the rest of the app already imports.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from actions.calendar_parse import parse_events, local
from config_pack.config import get_settings_path
from core.safe import swallow as _swallow

# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\jarvis_settings.json)
# — this used to be a project-relative 'data/jarvis_settings.json' instead, a
# different file that other settings readers never saw and that a rebuild/
# reinstall silently wipes (the bundled data/ folder gets overwritten).
_SETTINGS_PATH = Path(get_settings_path())
MAX_DOWNLOAD = 8 * 1024 * 1024


def _load_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        _swallow()
    return {}


def _fetch_text(ref: str) -> tuple[bool, str]:
    ref = ref.strip()
    if not ref:
        return False, ''
    low = ref.lower()
    if low.startswith(('http://', 'https://', 'webcal://')):
        u = ref.replace('webcal://', 'https://', 1)
        req = Request(u, headers={'User-Agent': 'JARVIS-Calendar/1.0'})
        with urlopen(req, timeout=15) as r:
            return True, r.read(MAX_DOWNLOAD).decode('utf-8', errors='ignore')
    p = Path(ref)
    if p.exists():
        return True, p.read_text(encoding='utf-8', errors='ignore')
    return False, ''


def parse_ics_events(raw: str, limit: int = 64, horizon_days: int = 60) -> list[tuple[datetime, str]]:
    """(start, title) of the first `limit` events of the text, from the beginning up to `horizon_days` ahead. For "what is coming up" use
    parse_events with a window instead: this one counts from the oldest event, so on a calendar with a long history it never reaches today."""
    events = parse_events(raw, None, datetime.now() + timedelta(days=horizon_days), limit=limit)
    return [(e.start, e.title) for e in events][:limit]


def _collect_upcoming(settings: dict | None, include_all_day: bool = True) -> list[tuple[datetime, str, str]]:
    """Events from one hour ago to 60 days ahead as (start, title, source label), soonest first. All-day events count while their day lasts.
    With settings=None (the real app) the user's own events from the calendar screen are included too."""
    s = settings if isinstance(settings, dict) else _load_settings()
    now = datetime.now()
    lo, hi = now - timedelta(hours=1), now + timedelta(days=60)
    collected: list[tuple[datetime, str, str]] = []
    for src in s.get('calendar_sources') or []:
        if not isinstance(src, dict) or src.get('hidden'):
            continue
        ref = (src.get('url') or src.get('path') or '').strip()
        if not ref:
            continue
        try:
            ok, raw = _fetch_text(ref)
        except Exception:
            continue
        if not ok or not raw:
            continue
        label = str(src.get('name') or ref)
        if len(label) > 48:
            label = label[:45] + '...'
        for e in parse_events(raw, lo, hi, limit=500):
            if e.all_day:
                if include_all_day and local(e.end) > now:
                    collected.append((e.start, e.title, label))
            elif local(e.start) >= lo:
                collected.append((e.start, e.title, label))
    if settings is None:
        try:
            from actions import calendar_hub
            collected += calendar_hub.upcoming_local(lo, hi, include_all_day)
            collected += calendar_hub.upcoming_remote(lo, hi, include_all_day)
        except Exception:
            _swallow()
    collected.sort(key=lambda x: local(x[0]))
    return collected


def _has_sources(s: dict, include_local: bool) -> bool:
    if isinstance(s.get('calendar_sources'), list) and s['calendar_sources']:
        return True
    if not include_local:
        return False
    try:
        from actions import calendar_hub
        return calendar_hub.has_local_events()
    except Exception:
        return False


def next_event_dt(settings: dict | None = None) -> tuple[datetime, str] | None:
    """Soonest upcoming timed event as (start, title), for cross-checking against weather."""
    collected = _collect_upcoming(settings, include_all_day=False)
    if not collected:
        return None
    dt, title, _label = collected[0]
    return (dt, title)


def next_events_summary(settings: dict | None, max_events: int = 3) -> str:
    s = settings if isinstance(settings, dict) else _load_settings()
    if not _has_sources(s, settings is None):
        return 'Календарь не настроен. Добавьте файл или ссылку на календарь в настройках.'
    collected = _collect_upcoming(settings)
    if not collected:
        return 'Нет ближайших событий в указанных ICS или источники недоступны.'
    out: list[str] = []
    for dt, title, label in collected[:max_events]:
        lo = local(dt)
        when = f'{lo.strftime("%d.%m")} весь день' if (lo.hour, lo.minute) == (0, 0) else lo.strftime('%d.%m %H:%M')
        out.append(f'{when} — {title} (источник: {label})')
    return 'Ближайшие события: ' + '; '.join(out)
