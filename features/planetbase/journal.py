"""Colony event journal: what Jarvis announced or did, for "what did I miss?"."""

import threading
import time
from collections import deque

_lock = threading.Lock()
_events: deque = deque(maxlen=200)


def reset() -> None:
    with _lock:
        _events.clear()


def log(text: str, now: float | None = None) -> None:
    text = (text or "").strip()
    if not text:
        return
    with _lock:
        _events.append((time.time() if now is None else now, text))


def recent(minutes: float = 15.0, limit: int = 6, now: float | None = None) -> list[tuple[float, str]]:
    cutoff = (time.time() if now is None else now) - minutes * 60.0
    with _lock:
        items = [e for e in _events if e[0] >= cutoff]
    return items[-limit:]


def summary(minutes: float = 15.0, limit: int = 6, now: float | None = None) -> str:
    current = time.time() if now is None else now
    items = recent(minutes, limit, current)
    if not items:
        return f"За последние {int(minutes)} минут ничего заметного не произошло."
    lines = []
    for ts, text in items:
        ago = max(1, int(round((current - ts) / 60.0)))
        lines.append(f"{ago} мин назад: {text.rstrip('.!')}.")
    return " ".join(lines)
