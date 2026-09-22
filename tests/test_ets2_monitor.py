"""Regression tests for features/ets2/monitor_checks_*.py.

2026-09 file-split bug: monitor.py was split into monitor_checks_safety.py /
monitor_checks_progress.py / monitor_checks_speed.py, each importing only
`from .config import *`. Most of the phrase functions and the `_auto_cruise`
module global these files call were never actually re-imported — they only
existed in monitor.py's own namespace. pyflakes couldn't flag this (a
wildcard import makes every name "may be defined by the star import", so it
never raises a hard error), but at runtime every one of these was a
NameError. Since `_monitor_loop` doesn't wrap its per-tick checks in
try/except, the first NameError silently killed the daemon thread for the
rest of the game session — meaning fuel/wear/rest/fines/tollgate/blinker/
gear-advice/rain-light/ETA/cruise-status announcements stopped working after
essentially the first tick with the engine on.

These tests call each check function directly with the minimal telemetry
dict that reaches its `_speak(...)` branch, patching `_speak` to a no-op so
the real TTS pipeline is never invoked. A NameError here means the
regression is back.
"""
import pytest

from features.ets2.monitor_state import _MonitorState
import features.ets2.monitor as monitor
import features.ets2.monitor_checks_speed as speed_checks
import features.ets2.monitor_checks_progress as progress_checks
import features.ets2.monitor_checks_safety as safety_checks


@pytest.fixture(autouse=True)
def _no_tts(monkeypatch):
    monkeypatch.setattr(monitor, '_speak', lambda text: None)


def test_manual_cruise_status_check_does_not_crash():
    # Regression: bare `_auto_cruise` reference, undefined in this module.
    state = _MonitorState()
    speed_checks._check_manual_cruise_status(state, {})


def test_gear_advice_check_does_not_crash():
    state = _MonitorState()
    data = {'engineRpm': 2100, 'engineRpmMax': 2200, 'gear': 5, 'gameThrottle': 0.9}
    speed_checks._check_gear_advice(state, data, speed_kmh=60.0)


def test_blinker_check_does_not_crash():
    state = _MonitorState()
    data = {'blinkerLeftOn': True, 'blinkerRightOn': False, 'lightsHazards': False}
    speed_checks._check_blinker(state, data, speed_kmh=50.0)


def test_rain_lights_check_does_not_crash():
    state = _MonitorState()
    data = {'wipers': True, 'lightsBeamLow': False, 'lightsBeamHigh': False}
    speed_checks._check_rain_lights(state, data, engine_on=True, speed_kmh=40.0)


def test_aux_lights_check_does_not_crash():
    state = _MonitorState()
    state.last_aux_front = 0
    speed_checks._check_aux_lights(state, {'lightsAuxFront': 1, 'lightsAuxRoof': 0})


def test_engine_transition_off_does_not_crash():
    # Regression: event_engine_off referenced but never imported.
    state = _MonitorState()
    state.last_engine_on = True
    data = {'engineEnabled': False, 'parkBrake': True, 'lightsBeamLow': False, 'lightsBeamHigh': False}
    assert progress_checks._check_engine_transition(state, data) is False


def test_fuel_low_range_check_does_not_crash():
    state = _MonitorState()
    state.last_fuel = 100.0
    progress_checks._check_fuel(state, {'fuel': 50.0, 'fuelRange': 90.0, 'routeDistance': 300000})


def test_rest_warning_check_does_not_crash():
    state = _MonitorState()
    state.last_rest_val = 65
    progress_checks._check_rest(state, {'restStop': 25}, engine_on=True)


def test_deadline_warning_check_does_not_crash():
    state = _MonitorState()
    progress_checks._check_deadline(state, {'time_abs_delivery': 100, 'time_abs': 200})


def test_route_progress_arrival_check_does_not_crash():
    state = _MonitorState()
    progress_checks._check_route_progress(state, {'routeDistance': 1500, 'onJob': True}, engine_on=True)


def test_idle_and_eta_checks_do_not_crash():
    state = _MonitorState()
    progress_checks._check_idle(state, {'speed': 0, 'parkBrake': False}, engine_on=True, on_job=True)
    progress_checks._check_eta(state, {'routeTime': 5000, 'routeDistance': 100000}, engine_on=True, on_job=True)


def test_fines_and_tolls_check_does_not_crash():
    # Regression: event_fine_speeding/event_tollgate/... never imported.
    state = _MonitorState()
    safety_checks._check_fines_and_tolls(state, {'fined': True, 'fineAmount': 100, 'fineOffence': 'speeding'})


def test_cargo_damage_check_does_not_crash():
    state = _MonitorState()
    safety_checks._check_cargo_damage(state, {'trailer': [{'cargoDamage': 0.05}]}, on_job=True)


def test_critical_warnings_check_does_not_crash():
    state = _MonitorState()
    safety_checks._check_critical_warnings(state, {
        'oilPressureWarning': True, 'waterTemperatureWarning': True,
        'airPressureEmergency': True, 'batteryVoltageWarning': True, 'adblueWarning': True,
    })


def test_wear_check_high_wear_does_not_crash():
    state = _MonitorState()
    safety_checks._check_wear(state, {'wearEngine': 0.8})


def test_trailer_attach_then_detach_announces_and_does_not_crash():
    state = _MonitorState()
    safety_checks._check_trailer(state, {'trailer': []})
    assert state.last_trailer_attached is False
    safety_checks._check_trailer(state, {'trailer': [{'cargoDamage': 0}]})
    assert state.last_trailer_attached is True
    safety_checks._check_trailer(state, {'trailer': []})
    assert state.last_trailer_attached is False


def test_harsh_braking_is_counted_for_the_driving_score():
    monitor._clear_job_fines()
    state = _MonitorState()
    monitor._check_speed_limit_and_cruise(state, {'speed': 80 / 3.6, 'speedLimit': 90 / 3.6})
    monitor._check_speed_limit_and_cruise(state, {'speed': 40 / 3.6, 'speedLimit': 90 / 3.6})
    assert monitor.get_job_driving_stats()['harsh_brakes'] == 1


def test_gradual_slowdown_is_not_counted_as_harsh_braking():
    monitor._clear_job_fines()
    state = _MonitorState()
    for speed_kmh in (80, 70, 60, 50, 40):
        monitor._check_speed_limit_and_cruise(state, {'speed': speed_kmh / 3.6, 'speedLimit': 90 / 3.6})
    assert monitor.get_job_driving_stats()['harsh_brakes'] == 0


def test_speeding_event_is_counted_once_per_episode():
    monitor._clear_job_fines()
    state = _MonitorState()
    monitor._check_speed_limit_and_cruise(state, {'speed': 40 / 3.6, 'speedLimit': 90 / 3.6})
    monitor._check_speed_limit_and_cruise(state, {'speed': 110 / 3.6, 'speedLimit': 90 / 3.6})
    monitor._check_speed_limit_and_cruise(state, {'speed': 110 / 3.6, 'speedLimit': 90 / 3.6})
    assert monitor.get_job_driving_stats()['speeding_events'] == 1


def test_gear_advice_bumps_driving_stat():
    monitor._clear_job_fines()
    state = _MonitorState()
    speed_checks._check_gear_advice(
        state, {'engineRpm': 2100, 'engineRpmMax': 2200, 'gear': 5, 'gameThrottle': 0.9}, speed_kmh=60.0,
    )
    assert monitor.get_job_driving_stats()['gear_warnings'] == 1


def test_job_start_resets_driving_stats():
    state = _MonitorState()
    monitor._check_speed_limit_and_cruise(state, {'speed': 80 / 3.6, 'speedLimit': 90 / 3.6})
    monitor._check_speed_limit_and_cruise(state, {'speed': 40 / 3.6, 'speedLimit': 90 / 3.6})
    assert monitor.get_job_driving_stats()['harsh_brakes'] >= 1
    monitor._clear_job_fines()
    assert monitor.get_job_driving_stats() == {'harsh_brakes': 0, 'speeding_events': 0, 'gear_warnings': 0}


def test_announce_job_delivered_accepts_driving_stats_without_crashing():
    from features.ets2.phrases_job import announce_job_delivered
    text = announce_job_delivered(
        {'jobDeliveredCargoDamage': 0, 'jobDeliveredRevenue': 5000, 'jobDeliveredDistanceKm': 300},
        elapsed_min=20,
        driving_stats={'harsh_brakes': 5, 'speeding_events': 3, 'gear_warnings': 0},
    )
    assert 'агрессивным' in text


def test_schedule_status_reports_comfortable_margin(monkeypatch):
    import actions.ets2_telemetry
    monkeypatch.setattr(actions.ets2_telemetry, 'get', lambda: {
        'onJob': True, 'routeDistance': 180000, 'routeTime': 150 * 60,
        'speed': 80 / 3.6, 'time_abs_delivery': 1240, 'time_abs': 1000,
    })
    text = monitor.get_schedule_status()
    assert 'запасом' in text
    assert '180 километров' in text


def test_schedule_status_warns_when_running_late(monkeypatch):
    # Regression: this branch called a bare _addr() that was never imported
    # into monitor.py's namespace — the exact "leftover reference" bug class
    # already fixed elsewhere in this file, caught here by actually
    # exercising the late-running branch instead of only the happy path.
    import actions.ets2_telemetry
    monkeypatch.setattr(actions.ets2_telemetry, 'get', lambda: {
        'onJob': True, 'routeDistance': 180000, 'routeTime': 150 * 60,
        'speed': 80 / 3.6, 'time_abs_delivery': 1100, 'time_abs': 1000,
    })
    text = monitor.get_schedule_status()
    assert 'не успеваем' in text


def test_schedule_status_handles_no_deadline_and_no_active_job(monkeypatch):
    import actions.ets2_telemetry
    monkeypatch.setattr(actions.ets2_telemetry, 'get', lambda: {
        'onJob': True, 'routeDistance': 50000, 'routeTime': 40 * 60,
        'speed': 90 / 3.6, 'time_abs_delivery': 0, 'time_abs': 1000,
    })
    assert '50 километров' in monitor.get_schedule_status()

    monkeypatch.setattr(actions.ets2_telemetry, 'get', lambda: {'onJob': False})
    assert monitor.get_schedule_status() == 'Сейчас нет активного рейса.'

    monkeypatch.setattr(actions.ets2_telemetry, 'get', lambda: None)
    assert 'не получены' in monitor.get_schedule_status()


def test_build_job_start_prompt_reports_deadline_and_rest():
    # Regression: read jobDeadline/nextRestStop, fields that do not exist in
    # the truck_telemetry SDK struct — deadline_line/rest_line were always
    # empty in practice. Real fields are time_abs_delivery/time_abs (both
    # absolute in-game minutes) and restStop.
    from features.ets2.llm import build_job_start_prompt
    prompt = build_job_start_prompt({
        'cargo': 'Стройматериалы', 'cargoMass': 5000, 'citySrc': 'Берлин', 'cityDst': 'Гамбург',
        'jobIncome': 3000, 'plannedDistanceKm': 300, 'routeTime': 10000,
        'time_abs': 1000, 'time_abs_delivery': 1150, 'restStop': 90,
    })
    assert 'Дедлайн: 2 ч 30 мин' in prompt
    assert 'Отдых: через 1 ч 30 мин' in prompt


def test_build_job_delivered_prompt_accepts_driving_stats_without_crashing():
    from features.ets2.llm import build_job_delivered_prompt
    prompt = build_job_delivered_prompt(
        {'jobDeliveredCargoDamage': 0, 'jobDeliveredRevenue': 5000, 'jobDeliveredDistanceKm': 300},
        0, 300, 5000, 50, 20, False,
        driving_stats={'harsh_brakes': 1, 'speeding_events': 2, 'gear_warnings': 0},
    )
    assert 'резких торможений — 1' in prompt


def test_real_break_reminder_fires_after_threshold_and_resets_on_engine_off(monkeypatch):
    import time as _time
    state = _MonitorState()
    spoken = []
    monkeypatch.setattr(monitor, '_speak', lambda text: spoken.append(text))

    progress_checks._check_real_break(state, {}, engine_on=True)
    assert state.real_break.start_ts is not None
    assert spoken == []

    # Fast-forward: pretend driving started 91 real-world minutes ago.
    state.real_break.start_ts = _time.time() - 91 * 60
    progress_checks._check_real_break(state, {}, engine_on=True)
    assert len(spoken) == 1
    assert 90 in state.real_break.fired

    # Same threshold must not fire twice in the same driving stretch.
    progress_checks._check_real_break(state, {}, engine_on=True)
    assert len(spoken) == 1

    # Turning the engine off is a real break — timer and fired set reset.
    progress_checks._check_real_break(state, {}, engine_on=False)
    assert state.real_break.start_ts is None
    assert state.real_break.fired == set()


def test_session_history_round_trip(tmp_path, monkeypatch):
    from features.ets2 import session_history
    from features.gaming_common import session_history as shared_history

    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(shared_history, 'get_settings_path', lambda: settings_path)

    assert session_history.load_last_session() is None

    session_history.save_session(jobs=3, revenue=15000, dist_km=245.5)
    loaded = session_history.load_last_session()
    assert loaded['jobs'] == 3
    assert loaded['revenue'] == 15000
    assert loaded['dist_km'] == 245.5


def test_session_report_compares_to_previous_session(monkeypatch):
    monkeypatch.setattr(monitor, '_session_start', __import__('time').monotonic())
    monkeypatch.setattr(monitor, '_session_jobs', 2)
    monkeypatch.setattr(monitor, '_session_revenue', 1500)
    monkeypatch.setattr(monitor, '_session_dist_km', 300.0)
    monkeypatch.setattr(monitor, '_prev_session', {'revenue': 1000})

    text = monitor.get_session_report()
    assert 'на 50%' in text
    assert 'больше' in text
