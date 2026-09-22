"""Tests for features/fs22/* — the FS22 integration brought to partial parity
with ETS2/Planetbase (real-break reminder + session-length report, both built
on features/gaming_common/). FS22 has no telemetry data source (no SCS-style
shared memory, no custom mod like Planetbase's), so unlike ETS2/Planetbase
there's no fuel/damage/job data to check — only real-time foreground-focus
tracking is possible, which is what these tests cover."""
import time

import pytest

import features.fs22.monitor as monitor
from features.fs22.phrases_fs22 import event_real_break_reminder, session_report_text
from features.fs22 import session_history


@pytest.fixture(autouse=True)
def _no_tts_and_clean_state(monkeypatch):
    monkeypatch.setattr(monitor, '_speak', lambda text: None)
    from features.gaming_common.real_break import RealBreakTracker
    from features.fs22.config import REAL_BREAK_THRESHOLDS_MIN
    monitor._break_tracker = RealBreakTracker(REAL_BREAK_THRESHOLDS_MIN)
    monitor._session_start = 0.0
    monitor._prev_fs22_session = None
    yield


# ── foreground detection ────────────────────────────────────────────

def test_is_foreground_true_for_known_fs22_exe(monkeypatch):
    monkeypatch.setattr(monitor, 'get_foreground_process_name', lambda: 'FarmingSimulator22.exe')
    assert monitor._is_foreground() is True


def test_is_foreground_false_for_other_process(monkeypatch):
    monkeypatch.setattr(monitor, 'get_foreground_process_name', lambda: 'explorer.exe')
    assert monitor._is_foreground() is False


def test_is_foreground_false_when_lookup_fails(monkeypatch):
    def _boom():
        raise RuntimeError('no window')
    monkeypatch.setattr(monitor, 'get_foreground_process_name', _boom)
    assert monitor._is_foreground() is False


# ── real-break reminder ─────────────────────────────────────────────

def test_real_break_fires_after_90_minutes_and_resets_on_blur():
    spoken = []
    import features.fs22.monitor as m
    m._speak = lambda text: spoken.append(text)

    monitor._check_real_break(True)
    assert monitor._break_tracker.start_ts is not None

    monitor._break_tracker.start_ts = time.time() - 91 * 60
    monitor._check_real_break(True)
    assert spoken  # fired once past 90 min
    assert 90 in monitor._break_tracker.fired

    spoken.clear()
    monitor._check_real_break(False)  # blur resets the tracker
    assert monitor._break_tracker.start_ts is None
    assert not spoken


def test_event_real_break_reminder_returns_nonempty_text_for_each_threshold():
    assert event_real_break_reminder(90)
    assert event_real_break_reminder(150)


# ── session report / history ────────────────────────────────────────

def test_session_report_text_without_previous_session():
    text = session_report_text(42.0, 0)
    assert '42' in text
    assert 'прошл' not in text.lower()


def test_session_report_text_compares_to_longer_previous_session():
    text = session_report_text(20.0, 50.0)
    assert 'дольше' in text.lower()
    assert '50' in text


def test_session_report_text_compares_to_shorter_previous_session():
    text = session_report_text(50.0, 20.0)
    assert 'дольше' in text.lower()


def test_get_session_report_reflects_elapsed_time():
    monitor._session_start = time.time() - 5 * 60
    text = monitor.get_session_report()
    assert '5' in text or '4' in text  # rounding


def test_session_history_round_trip(tmp_path, monkeypatch):
    settings_path = str(tmp_path / 'jarvis_settings.json')
    import features.gaming_common.session_history as shared_history
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    assert session_history.load_last_session() is None
    session_history.save_session(37.5)
    loaded = session_history.load_last_session()
    assert loaded['minutes'] == 37.5


# ── start/stop lifecycle ────────────────────────────────────────────

def test_start_launches_monitor_thread_and_stop_saves_snapshot(monkeypatch, tmp_path):
    settings_path = str(tmp_path / 'jarvis_settings.json')
    import features.gaming_common.session_history as shared_history
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)
    monkeypatch.setattr(monitor, 'get_foreground_process_name', lambda: '')

    monitor.start()
    try:
        assert monitor._thread is not None and monitor._thread.is_alive()
        assert monitor._session_start > 0
    finally:
        monitor.stop()

    saved = session_history.load_last_session()
    assert saved is not None
    assert saved['minutes'] >= 0
