"""Tests for the shared features/gaming_common/* modules extracted from
features/ets2/* and features/planetbase/* (item 3 of the 2026-09
"what would you improve" follow-up): RealBreakTracker, the generic session
history JSON I/O, and the shared LLM-narration plumbing."""
import time

import pytest

from features.gaming_common.real_break import RealBreakTracker
from features.gaming_common import session_history as shared_history
from features.gaming_common import llm_narration


# ── RealBreakTracker ────────────────────────────────────────────────

def test_real_break_tracker_starts_timer_on_first_active_tick():
    tracker = RealBreakTracker([90, 150])
    assert tracker.check(active=True) is None
    assert tracker.start_ts is not None


def test_real_break_tracker_fires_lowest_threshold_first():
    tracker = RealBreakTracker([90, 150])
    tracker.check(active=True)
    tracker.start_ts = time.time() - 91 * 60
    assert tracker.check(active=True) == 90
    assert 90 in tracker.fired


def test_real_break_tracker_does_not_refire_same_threshold():
    tracker = RealBreakTracker([90, 150])
    tracker.check(active=True)
    tracker.start_ts = time.time() - 91 * 60
    assert tracker.check(active=True) == 90
    assert tracker.check(active=True) is None


def test_real_break_tracker_fires_next_threshold_once_reached():
    tracker = RealBreakTracker([90, 150])
    tracker.check(active=True)
    tracker.start_ts = time.time() - 151 * 60
    assert tracker.check(active=True) == 90
    assert tracker.check(active=True) == 150


def test_real_break_tracker_resets_on_inactive():
    tracker = RealBreakTracker([90, 150])
    tracker.check(active=True)
    tracker.start_ts = time.time() - 91 * 60
    tracker.check(active=True)
    assert tracker.fired == {90}

    assert tracker.check(active=False) is None
    assert tracker.start_ts is None
    assert tracker.fired == set()


# ── session_history generic I/O ─────────────────────────────────────

def test_save_and_load_json_round_trip(tmp_path, monkeypatch):
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    assert shared_history.load_json('some_game_history.json') is None

    shared_history.save_json('some_game_history.json', {'foo': 1, 'bar': 'baz'})
    loaded = shared_history.load_json('some_game_history.json')
    assert loaded['foo'] == 1
    assert loaded['bar'] == 'baz'
    assert 'ts' in loaded


def test_load_json_returns_none_on_corrupt_file(tmp_path, monkeypatch):
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    bad_path = tmp_path / 'broken.json'
    bad_path.write_text('{not valid json', encoding='utf-8')
    assert shared_history.load_json('broken.json') is None


def test_different_games_use_independent_filenames(tmp_path, monkeypatch):
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    shared_history.save_json('game_a.json', {'v': 1})
    shared_history.save_json('game_b.json', {'v': 2})
    assert shared_history.load_json('game_a.json')['v'] == 1
    assert shared_history.load_json('game_b.json')['v'] == 2


# ── llm_narration plumbing ──────────────────────────────────────────

def test_has_llm_configured_false_when_feature_disabled(monkeypatch):
    monkeypatch.setattr(llm_narration, '_load_settings', lambda: {'my_game_llm_enabled': False})
    assert llm_narration.has_llm_configured('my_game_llm_enabled') is False


def test_has_llm_configured_true_when_key_present_and_not_disabled(monkeypatch):
    monkeypatch.setattr(llm_narration, '_load_settings', lambda: {})
    import features.qa.llm_processor as llm_processor
    monkeypatch.setattr(llm_processor, '_load_api_key', lambda provider: 'fake-key')
    assert llm_narration.has_llm_configured('my_game_llm_enabled') is True


def test_has_llm_configured_false_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_narration, '_load_settings', lambda: {})
    import features.qa.llm_processor as llm_processor
    monkeypatch.setattr(llm_processor, '_load_api_key', lambda provider: '')
    assert llm_narration.has_llm_configured('my_game_llm_enabled') is False


def test_ask_llm_narration_returns_empty_string_on_failure(monkeypatch):
    import features.qa.llm_processor as llm_processor

    def _boom(**kwargs):
        raise RuntimeError('network down')

    monkeypatch.setattr(llm_processor, 'ask_llm', _boom)
    assert llm_narration.ask_llm_narration('sys prompt', 'user prompt') == ''
