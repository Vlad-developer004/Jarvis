"""Tests for features/planetbase/monitor.py's real-time-based additions
(ETA prediction, real-break reminder, colonist-scaled thresholds, session
history) and the new LLM narration hooks (features/planetbase/llm.py).
"""
import time

import pytest

import features.planetbase.monitor as monitor
import features.planetbase.llm as pb_llm
from features.planetbase import session_history
from features.gaming_common.real_break import RealBreakTracker


@pytest.fixture(autouse=True)
def _no_tts_and_clean_state(monkeypatch):
    monkeypatch.setattr(monitor, '_speak', lambda text: None)
    monkeypatch.setattr(monitor, '_addr', lambda: 'сэр')
    monkeypatch.setattr(monitor, '_break_tracker', RealBreakTracker(monitor._REAL_BREAK_THRESHOLDS_MIN))


# ── _minutes_to_empty ──────────────────────────────────────────────

def test_minutes_to_empty_computes_from_observed_depletion():
    eta = monitor._minutes_to_empty(storage_now=100.0, storage_prev=120.0, wall_dt=5.0)
    assert eta == pytest.approx(100.0 / 4.0 / 60.0)


def test_minutes_to_empty_none_when_storage_not_decreasing():
    assert monitor._minutes_to_empty(storage_now=100.0, storage_prev=90.0, wall_dt=5.0) is None
    assert monitor._minutes_to_empty(storage_now=100.0, storage_prev=100.0, wall_dt=5.0) is None


def test_minutes_to_empty_none_when_tick_gap_is_abnormal():
    # A lag spike or a paused game would give a garbage rate — skip instead
    # of reporting a confidently wrong ETA.
    assert monitor._minutes_to_empty(storage_now=100.0, storage_prev=120.0, wall_dt=0.5) is None
    assert monitor._minutes_to_empty(storage_now=100.0, storage_prev=120.0, wall_dt=60.0) is None


def test_minutes_to_empty_none_when_storage_already_zero():
    assert monitor._minutes_to_empty(storage_now=0.0, storage_prev=10.0, wall_dt=5.0) is None


# ── Real-world break reminder ──────────────────────────────────────

def test_real_break_fires_after_threshold_and_resets_on_pause(monkeypatch):
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))

    monitor._check_real_break(paused=False)
    assert monitor._break_tracker.start_ts is not None
    assert spoken == []

    monitor._break_tracker.start_ts = time.time() - 91 * 60
    monitor._check_real_break(paused=False)
    assert len(spoken) == 1

    # Same threshold doesn't repeat within the same unpaused stretch.
    monitor._check_real_break(paused=False)
    assert len(spoken) == 1

    # A real pause resets the timer and the fired-thresholds set.
    monitor._check_real_break(paused=True)
    assert monitor._break_tracker.start_ts is None
    assert monitor._break_tracker.fired == set()


# ── Colonist-scaled food/medical thresholds ────────────────────────

def test_check_warns_about_low_food_for_large_colony_below_flat_threshold(monkeypatch):
    # 20 vegetables is above the old flat _FOOD_ITEM_LOW=15 constant, so it
    # never used to warn — but for 80 colonists it's a real shortage.
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))
    monkeypatch.setattr(monitor, '_engage_yellow_alert', lambda: None)
    monkeypatch.setattr(monitor, '_prev', {})
    monkeypatch.setattr(monitor, '_first_tick', True)

    data = {
        '_valid': True, 'colonists': 80, 'module_count': 10,
        'power_pct': 100, 'water_pct': 100, 'water_capacity': 100,
        'water_balance': 0, 'oxygen_gen': 200, 'res_medical': 50,
        'res_metal': 50, 'res_bioplastic': 50,
        'res_vegetables': 20, 'res_meat': 50, 'res_meals': 50,
        'low_food': False, 'any_disaster': False, 'sandstorm': False,
        'solar_flare': False, 'blizzard': False, 'paused': False,
    }
    monitor._check(data)
    assert any('овощей' in s for s in spoken)


def test_check_does_not_warn_about_food_for_small_colony_above_floor(monkeypatch):
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))
    monkeypatch.setattr(monitor, '_engage_yellow_alert', lambda: None)
    monkeypatch.setattr(monitor, '_prev', {})
    monkeypatch.setattr(monitor, '_first_tick', True)

    data = {
        '_valid': True, 'colonists': 5, 'module_count': 2,
        'power_pct': 100, 'water_pct': 100, 'water_capacity': 100,
        'water_balance': 0, 'oxygen_gen': 200, 'res_medical': 50,
        'res_metal': 50, 'res_bioplastic': 50,
        'res_vegetables': 20, 'res_meat': 50, 'res_meals': 50,
        'low_food': False, 'any_disaster': False, 'sandstorm': False,
        'solar_flare': False, 'blizzard': False, 'paused': False,
    }
    monitor._check(data)
    assert not any('овощей' in s for s in spoken)


# ── Session history ─────────────────────────────────────────────────

def test_session_history_round_trip(tmp_path, monkeypatch):
    from features.gaming_common import session_history as shared_history
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    assert session_history.load_last_session() is None

    session_history.save_session(peak_colonists=42, disasters_survived=3, session_minutes=55.0)
    loaded = session_history.load_last_session()
    assert loaded['peak_colonists'] == 42
    assert loaded['disasters_survived'] == 3
    assert loaded['session_minutes'] == 55.0


def test_get_session_report_compares_peak_to_previous_session(monkeypatch):
    monkeypatch.setattr(monitor, '_session_start', time.time() - 10 * 60)
    monkeypatch.setattr(monitor, '_peak_colonists', 55)
    monkeypatch.setattr(monitor, '_disasters_survived', 2)
    monkeypatch.setattr(monitor, '_prev_pb_session', {'peak_colonists': 40})

    text = monitor.get_session_report()
    assert 'больше' in text
    assert '40' in text


# ── LLM narration hooks (fallback + happy path) ─────────────────────

def test_announce_disaster_start_falls_back_when_llm_not_configured(monkeypatch):
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))
    monkeypatch.setattr(pb_llm, 'has_llm_configured', lambda: False)

    monitor._announce_disaster_start({'colonists': 10}, sandstorm=True, solar_flare=False, blizzard=False)
    assert len(spoken) == 1


def test_announce_disaster_start_speaks_llm_result_when_configured(monkeypatch):
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))
    monkeypatch.setattr(pb_llm, 'has_llm_configured', lambda: True)
    monkeypatch.setattr(pb_llm, 'ask_pb', lambda prompt, timeout=12: 'Песчаная буря приближается.')

    monitor._announce_disaster_start({'colonists': 10}, sandstorm=True, solar_flare=False, blizzard=False)
    for _ in range(50):
        if spoken:
            break
        time.sleep(0.02)
    assert spoken == ['Песчаная буря приближается.']


def test_announce_disaster_start_falls_back_when_llm_returns_empty(monkeypatch):
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))
    monkeypatch.setattr(pb_llm, 'has_llm_configured', lambda: True)
    monkeypatch.setattr(pb_llm, 'ask_pb', lambda prompt, timeout=12: '')

    monitor._announce_disaster_start({'colonists': 10}, sandstorm=False, solar_flare=True, blizzard=False)
    for _ in range(50):
        if spoken:
            break
        time.sleep(0.02)
    assert len(spoken) == 1


def test_build_disaster_prompt_mentions_the_disaster_kind():
    prompt = pb_llm.build_disaster_prompt({'colonists': 30, 'power_pct': 50, 'water_pct': 60}, 'sandstorm')
    assert 'песчаная буря' in prompt.lower()


def test_build_milestone_prompt_mentions_the_milestone_number():
    prompt = pb_llm.build_milestone_prompt({'module_count': 12}, 100)
    assert '100' in prompt
