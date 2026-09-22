"""Persists the previous Planetbase session's totals so get_session_report()
can compare against it, mirroring features/ets2/session_history.py."""
from __future__ import annotations
from features.gaming_common.session_history import load_json, save_json

_FILENAME = 'planetbase_session_history.json'


def load_last_session() -> dict | None:
    return load_json(_FILENAME)


def save_session(peak_colonists: int, disasters_survived: int, session_minutes: float) -> None:
    save_json(_FILENAME, {
        'peak_colonists': peak_colonists,
        'disasters_survived': disasters_survived,
        'session_minutes': session_minutes,
    })
