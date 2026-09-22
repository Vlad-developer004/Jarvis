"""Tests for actions/game_input_parts/runtime.py::_handle_telemetry_action's
profile dispatch. Previously hardcoded to Planetbase only (`if
get_loaded_profile_stem() != 'planetbase': return`); extended to also route
FS22's 'session_report' telemetry_action to features/fs22/monitor.py, without
touching the planetbase data-dict path (which would crash if fed FS22's
profile, since planetbase telemetry would never be valid there)."""
import actions.game_input_parts.runtime as runtime


def test_fs22_session_report_speaks_the_session_report(monkeypatch):
    monkeypatch.setattr(runtime, 'get_loaded_profile_stem', lambda: 'farming_simulator_22')
    spoken = []
    monkeypatch.setattr(runtime, '_speak_response', lambda text: spoken.append(text))
    monkeypatch.setattr('features.fs22.monitor.get_session_report', lambda: 'Session is 10 minutes.')

    runtime._handle_telemetry_action('session_report')

    assert spoken == ['Session is 10 minutes.']


def test_fs22_unknown_telemetry_action_is_a_noop(monkeypatch):
    monkeypatch.setattr(runtime, 'get_loaded_profile_stem', lambda: 'farming_simulator_22')
    spoken = []
    monkeypatch.setattr(runtime, '_speak_response', lambda text: spoken.append(text))

    runtime._handle_telemetry_action('full_status')  # not a valid FS22 action

    assert spoken == []


def test_fs22_session_report_speaks_error_on_exception(monkeypatch):
    monkeypatch.setattr(runtime, 'get_loaded_profile_stem', lambda: 'farming_simulator_22')
    spoken = []
    monkeypatch.setattr(runtime, '_speak_response', lambda text: spoken.append(text))

    def _boom():
        raise RuntimeError('boom')
    monkeypatch.setattr('features.fs22.monitor.get_session_report', _boom)

    runtime._handle_telemetry_action('session_report')

    assert spoken == ['Ошибка получения отчёта по сессии.']


def test_non_planetbase_non_fs22_profile_is_a_noop(monkeypatch):
    monkeypatch.setattr(runtime, 'get_loaded_profile_stem', lambda: 'euro_truck_simulator_2')
    spoken = []
    monkeypatch.setattr(runtime, '_speak_response', lambda text: spoken.append(text))

    runtime._handle_telemetry_action('session_report')

    assert spoken == []
