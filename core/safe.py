"""Makes a deliberately ignored error visible in the log instead of gone.

Inside an ``except`` block, ``swallow()`` records which exception was ignored and where, at DEBUG level, and only the first few times for
each place so a failing loop cannot flood the log. It never raises and never changes what the caller does next.
"""
from __future__ import annotations

import logging
import sys
import threading

_MAX_PER_PLACE = 3
_MAX_PLACES = 5000
_lock = threading.Lock()
_seen: dict[tuple, int] = {}


def swallow(note: str = '') -> None:
    try:
        exc_type, exc, _tb = sys.exc_info()
        if exc_type is None:
            return
        frame = sys._getframe(1)
        key = (frame.f_code.co_filename, frame.f_lineno, exc_type)
        with _lock:
            n = _seen.get(key, 0) + 1
            if n == 1 and len(_seen) >= _MAX_PLACES:
                return
            _seen[key] = n
        if n > _MAX_PER_PLACE:
            return
        from core.redact import redact
        logging.getLogger(frame.f_globals.get('__name__', 'swallowed')).debug(
            'ignored %s at line %d%s: %s', exc_type.__name__, frame.f_lineno, f' ({note})' if note else '', redact(exc))
    except Exception:  # noqa: BLE001 - logging must never break the caller
        return


def stats() -> dict[str, int]:
    """How many times each ignored place fired ("file:line:ExceptionName" -> count), for diagnostics and tests."""
    with _lock:
        return {f'{k[0]}:{k[1]}:{k[2].__name__}': v for k, v in _seen.items()}
