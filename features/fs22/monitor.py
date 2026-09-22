"""Background monitor for Farming Simulator 22.

Unlike ETS2 (reads the SCS SDK telemetry plugin's shared-memory segment via
actions/ets2_telemetry.py) or Planetbase (reads a custom Unity mod's data via
features/planetbase/telemetry.py), FS22 has no existing telemetry channel
this repo can read from. Getting one would mean authoring and shipping a new
FS22 Lua mod from scratch — out of scope here. So this monitor only tracks
real wall-clock foreground-focus time (via get_foreground_process_name()),
which is enough to offer the same "you've been playing without a real break
for N minutes" nudge as ETS2/Planetbase (features/gaming_common/real_break.py),
plus a session-length voice report — but no fuel/damage/field-progress
narration, since there's no data source for any of that.
"""
import logging
import threading
import time

from core.system import get_foreground_process_name
from features.gaming_common.real_break import RealBreakTracker
from features.fs22.config import REAL_BREAK_THRESHOLDS_MIN, POLL_INTERVAL
from features.fs22.phrases_fs22 import event_real_break_reminder, session_report_text

_log = logging.getLogger(__name__)

_FS22_EXE_NAMES = {'farmingsimulator22.exe', 'farmingsimulator25.exe', 'fs22.exe', 'fs25.exe'}

_thread: threading.Thread | None = None
_running = False
_break_tracker = RealBreakTracker(REAL_BREAK_THRESHOLDS_MIN)
_session_start: float = 0.0
_prev_fs22_session: dict | None = None


def _speak(text: str) -> None:
    try:
        from core.speech.tts import speak
        speak(text)
    except Exception as e:
        _log.debug('TTS error: %s', e)


def _is_foreground() -> bool:
    try:
        return (get_foreground_process_name() or '').lower() in _FS22_EXE_NAMES
    except Exception:
        return False


def _check_real_break(active: bool) -> None:
    threshold = _break_tracker.check(active)
    if threshold is not None:
        _speak(event_real_break_reminder(threshold))


def _monitor_loop():
    while _running:
        try:
            _check_real_break(_is_foreground())
        except Exception as e:
            _log.debug('Monitor error: %s', e)
        time.sleep(POLL_INTERVAL)


def get_session_report() -> str:
    elapsed_min = (time.time() - _session_start) / 60.0 if _session_start > 0 else 0.0
    prev_min = _prev_fs22_session.get('minutes', 0) if _prev_fs22_session else 0
    return session_report_text(elapsed_min, prev_min)


def _save_fs22_session_snapshot() -> None:
    try:
        from .session_history import save_session
        elapsed_min = (time.time() - _session_start) / 60.0 if _session_start > 0 else 0.0
        save_session(elapsed_min)
    except Exception:
        pass


def start():
    global _thread, _running, _session_start, _break_tracker, _prev_fs22_session

    if _thread and _thread.is_alive():
        return

    _session_start = time.time()
    _break_tracker = RealBreakTracker(REAL_BREAK_THRESHOLDS_MIN)
    try:
        from .session_history import load_last_session
        _prev_fs22_session = load_last_session()
    except Exception:
        _prev_fs22_session = None

    _running = True
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name='FS22Monitor')
    _thread.start()
    _log.info('FS22 monitor started')


def stop():
    global _running
    _running = False
    if _session_start > 0:
        _save_fs22_session_snapshot()
