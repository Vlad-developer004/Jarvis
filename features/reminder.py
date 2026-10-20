from __future__ import annotations
import re
import threading
import time
from core.nlp.commands import normalize_numbers
from core.safe import swallow as _swallow

_TIME_PATTERNS = [
    r'\d+\s*час(?:а|ов)?',
    r'\d+\s*минут(?:у|ы|е)?',
    r'\d+\s*секунд(?:у|ы|е)?',
]


def extract_reminder_text(raw: str) -> str:
    text = normalize_numbers(raw.lower()).strip()
    for prefix in ('напомни мне', 'напомни', 'поставь напоминание', 'напоминание'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = re.sub(r'(?<=\sв\s)(\d{1,2})(\d{2})\b', r'\1:\2', normalize_numbers(raw.lower()).strip())     # the speech normalizer turns "18:00" into "1800"
    for word in ('что', 'о том что', 'про то что'):
        if text.startswith(word):
            text = text[len(word):].strip()
            break
    return text.strip(' ,.') or 'Напоминание'


_LEAD_VERB = re.compile(r'^(?:напомни(?:\s+мне)?|поставь\s+напоминание|напоминание)\s*(?:что\s+|о том что\s+)?', re.I)


def calendar_reminder(raw: str) -> dict | None:
    """"Напомни завтра в 10 купить хлеб": a reminder for a day and time becomes an event in the user's own calendar (it survives a restart and shows
    in the calendar screen; the spoken reminder comes one minute before). Returns {title, date, time}, {'past': True} for a moment already gone,
    or None when the phrase has no day and time."""
    from datetime import datetime
    from actions import calendar_hub, calendar_quick
    text = re.sub(r'(?<=\sв\s)(\d{1,2})(\d{2})\b', r'\1:\2', normalize_numbers(raw.lower()).strip())     # the speech normalizer turns "18:00" into "1800"
    q = calendar_quick.parse_phrase(_LEAD_VERB.sub('', text, count=1))
    if not (q['date'] and q['time'] and q['title']):
        return None
    if datetime.fromisoformat(f"{q['date']}T{q['time']}") <= datetime.now():
        return {'past': True}
    try:
        calendar_hub.add_local({'title': q['title'], 'date': q['date'], 'time': q['time'], 'end_time': '', 'all_day': False, 'repeat': 'none', 'remind': [1]})
    except calendar_hub.CalendarError:
        return None
    return {'title': q['title'], 'date': q['date'], 'time': q['time']}


# Registry of reminders that have not fired yet; read by the new-UI bridge (ui_next/bridge/observer.py).
_pending_lock = threading.Lock()
_pending: dict[int, tuple[float, str]] = {}   # id -> (deadline as epoch seconds, message)
_pending_seq = 0
_cancel_events: dict[int, threading.Event] = {}   # id -> set() when the user cancels the reminder


def pending_reminders() -> list[tuple[float, str]]:
    """Snapshot of (deadline epoch, message) for reminders still waiting, soonest first."""
    with _pending_lock:
        return sorted(_pending.values())


def pending_items() -> list[tuple[int, float, str]]:
    """Like pending_reminders() but with the id that cancel_reminder() takes."""
    with _pending_lock:
        return sorted(((rid, at, msg) for rid, (at, msg) in _pending.items()), key=lambda r: r[1])


def cancel_reminder(rid: int) -> bool:
    """Drops a reminder that has not fired yet. Returns False when it already fired or never existed."""
    with _pending_lock:
        found = _pending.pop(rid, None)
        ev = _cancel_events.pop(rid, None)
    if found is None:
        return False
    if ev is not None:
        ev.set()
    return True


def schedule_reminder(seconds: int, message: str, speak_fn) -> None:
    global _pending_seq
    cancelled = threading.Event()
    with _pending_lock:
        _pending_seq += 1
        rid = _pending_seq
        _pending[rid] = (time.time() + seconds, message)
        _cancel_events[rid] = cancelled

    def _run():
        if cancelled.wait(seconds):
            return
        with _pending_lock:
            _pending.pop(rid, None)
            _cancel_events.pop(rid, None)
        _fire_reminder(message, speak_fn)

    threading.Thread(target=_run, daemon=True, name='reminder').start()


_SNOOZE = (('snooze5', 'Отложить на 5 минут', 300), ('snooze10', 'Отложить на 10 минут', 600))
_CLOSE_WORDS = ('закрой', 'закрыть', 'ок', 'окей', 'okay', 'понял', 'ясно', 'хорошо', 'да')


def _fire_reminder(message: str, speak_fn):
    _play_alert_sound()
    _show_reminder_window(message, speak_fn)
    try:
        speak_fn(f'Сэр, напоминаю: {message}')
    except Exception:
        _swallow()


def _play_alert_sound():
    try:
        from core.speech import play_alert_sound
        play_alert_sound('reminder')
    except Exception:
        _swallow()


def _show_reminder_window(message: str, speak_fn) -> bool:
    """The pop-up in the window: the text, snooze buttons, and spoken "закрой" / "ок" close it. It closes itself after a minute."""
    from ui_next import host
    by_id = {i: sec for i, _label, sec in _SNOOZE}

    def done(status, value):
        if status == 'ok' and value in by_id:
            schedule_reminder(by_id[value], message, speak_fn)

    return host.show_alert('Напоминание', message, tone='info', actions=[{'id': i, 'label': label} for i, label, _sec in _SNOOZE],
                           voice=(_CLOSE_WORDS, ('закрой', 'закрыть', 'стоп')), done=done, timeout=60)
