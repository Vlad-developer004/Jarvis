from __future__ import annotations
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from actions.briefing_config import load_briefing_prefs
from actions.calendar_ics import _load_settings, _fetch_text, parse_ics_events
from core.system import module_enabled
_ANNOUNCE_PATH = Path('logs') / 'calendar_reminders_announced.json'
_LOCK = threading.Lock()
_announced: set[str] = set()
def _to_local_naive(dt: datetime) -> datetime:
    if dt.tzinfo:
        return dt.astimezone().replace(tzinfo=None)
    return dt
def _load_announced() -> set[str]:
    try:
        if _ANNOUNCE_PATH.exists():
            data = json.loads(_ANNOUNCE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return {str(x) for x in data}
    except Exception:
        pass
    return set()
def _save_announced(s: set[str]) -> None:
    try:
        _ANNOUNCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lst = sorted(s)[-500:]
        _ANNOUNCE_PATH.write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding='utf-8')
    except Exception:
        pass
def _event_key(dt: datetime, title: str) -> str:
    ts = _to_local_naive(dt).strftime('%Y-%m-%d %H:%M')
    return f'{ts}|{title[:80]}'
def _collect_upcoming_events() -> list[tuple[datetime, str]]:
    s = _load_settings()
    sources = s.get('calendar_sources')
    if not isinstance(sources, list):
        return []
    seen: set[tuple[datetime, str]] = set()
    out: list[tuple[datetime, str]] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        ref = (src.get('url') or src.get('path') or '').strip()
        if not ref:
            continue
        ok, raw = _fetch_text(ref)
        if not ok or not raw:
            continue
        for dt, title in parse_ics_events(raw, limit=120):
            t = title or '(без названия)'
            key = (_to_local_naive(dt), t)
            if key in seen:
                continue
            seen.add(key)
            out.append((dt, t))
    return out
def _run_loop(handler):
    global _announced
    with _LOCK:
        _announced = _load_announced()
    while True:
        try:
            time.sleep(60)
            if not module_enabled('calendar_ics'):
                continue
            prefs = load_briefing_prefs()
            if not prefs.get('calendar_reminders_enabled', True):
                continue
            lead_min = int(prefs.get('calendar_reminder_minutes') or 15)
            lead_min = max(1, min(lead_min, 120))
            target_sec = lead_min * 60
            now_local = datetime.now()
            events = _collect_upcoming_events()
            for dt, title in events:
                ev_local = _to_local_naive(dt)
                if ev_local <= now_local:
                    continue
                delta_sec = (ev_local - now_local).total_seconds()
                if abs(delta_sec - target_sec) > 90:
                    continue
                key = _event_key(dt, title)
                with _LOCK:
                    if key in _announced:
                        continue
                    _announced.add(key)
                    _save_announced(_announced)
                try:
                    from features.reminder import schedule_reminder
                    from ui import hud as _hud
                    msg = f'Через {lead_min} минут: {title}.'
                    _h = getattr(_hud, '_hud', None)
                    schedule_reminder(1, msg, handler.speak, _h)
                except Exception:
                    try:
                        handler.speak(f'Напоминание: через {lead_min} минут — {title}.')
                    except Exception:
                        pass
        except Exception:
            time.sleep(30)
def start_calendar_reminders(handler) -> None:
    if not module_enabled('calendar_ics'):
        return
    t = threading.Thread(target=_run_loop, args=(handler,), daemon=True, name='calendar_reminders')
    t.start()
