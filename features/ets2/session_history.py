"""Persists the previous ETS2 session's totals so get_session_report() can
compare against it ("today you've already out-earned last session") instead
of only ever showing today's numbers in isolation."""
from __future__ import annotations
from features.gaming_common.session_history import load_json, save_json

_FILENAME = 'ets2_session_history.json'


def load_last_session() -> dict | None:
    return load_json(_FILENAME)


def save_session(jobs: int, revenue: int, dist_km: float) -> None:
    save_json(_FILENAME, {'jobs': jobs, 'revenue': revenue, 'dist_km': dist_km})
