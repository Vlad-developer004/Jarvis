"""ETS2: waking the truck after a rest stop must start the engine exactly once, and filling the tank must not chatter or warn mid-fill."""
import pytest

from core.engine import ets2_commands
from features.ets2 import monitor
from features.ets2 import monitor_checks_progress as progress
from features.ets2.monitor_state import _MonitorState


@pytest.fixture
def wake(monkeypatch):
    """Runs _wake_up_truck against a fake telemetry frame; returns the list of (kind, arg) the truck was asked to do."""
    calls = []

    def run(frame):
        import actions.ets2_telemetry as tel
        import actions.game_input as gi
        import core.speech as speech
        monkeypatch.setattr(tel, 'get', lambda: frame)
        monkeypatch.setattr(gi, 'get_binding', lambda name, default=None: default)
        monkeypatch.setattr(gi, 'press_robust', lambda key, **kw: calls.append(('press', key)))
        monkeypatch.setattr(gi, 'cast_command', lambda text, **kw: calls.append(('cast', text)))
        monkeypatch.setattr(speech, 'speak_async', lambda text: calls.append(('say', text)))
        monkeypatch.setattr(ets2_commands.time, 'sleep', lambda s: None)
        ets2_commands._wake_up_truck(8, 600)
        return calls
    return run


def test_wake_up_starts_the_engine_only_through_the_prepare_command(wake):
    calls = wake({'engineEnabled': False, 'parkBrake': False})
    assert [c for c in calls if c[0] == 'cast'] == [('cast', 'подготовь тягач')]
    assert ('press', 'e') not in calls          # a second engine press toggled the engine straight back off


def test_wake_up_releases_the_handbrake_and_still_runs_the_prepare_command(wake):
    calls = wake({'engineEnabled': True, 'parkBrake': True})
    assert ('press', 'space') in calls
    assert ('press', 'e') not in calls and [c for c in calls if c[0] == 'cast'] == [('cast', 'подготовь тягач')]   # the profile skips the engine step itself


@pytest.fixture
def said(monkeypatch):
    out = []
    monkeypatch.setattr(monitor, '_speak', out.append)
    clock = {'t': 1000.0}
    monkeypatch.setattr(progress.time, 'monotonic', lambda: clock['t'])
    return out, clock


def frame(fuel, rng, route=900_000):
    return {'fuel': fuel, 'fuelRange': rng, 'routeDistance': route}


def test_filling_a_tank_is_silent_until_the_pump_stops(said):
    out, clock = said
    state = _MonitorState()
    progress._check_fuel(state, frame(60, 150))                  # low tank: one range warning is fine
    before = len(out)
    for litres in range(80, 400, 20):                            # the pump runs for a while, the route is far longer than the range
        clock['t'] += 1.0
        progress._check_fuel(state, frame(litres, litres * 2.5))
    assert len(out) == before                                    # no shortage warning, no range phrase mid-fill


def test_after_the_fill_the_shortage_is_judged_once_on_the_final_level(said):
    out, clock = said
    state = _MonitorState()
    progress._check_fuel(state, frame(380, 950))
    for litres in (390, 400):
        clock['t'] += 1.0
        progress._check_fuel(state, frame(litres, litres * 2.5))
    assert not out
    clock['t'] += progress.REFUEL_HOLD_SECONDS + 1
    progress._check_fuel(state, frame(400, 1000, route=1_400_000))    # full tank, the route is still longer
    progress._check_fuel(state, frame(400, 1000, route=1_400_000))
    assert len(out) == 1 and '1' in out[0]


def test_range_warnings_are_armed_again_after_a_fill(said):
    out, clock = said
    state = _MonitorState()
    progress._check_fuel(state, frame(20, 40, route=0))
    assert len(out) == 1 and state.fired_fuel
    clock['t'] += 1.0
    progress._check_fuel(state, frame(200, 500, route=0))                 # filled up
    assert not state.fired_fuel
    clock['t'] += progress.REFUEL_HOLD_SECONDS + 1
    progress._check_fuel(state, frame(200, 90, route=0))         # driven low again
    assert len(out) == 2
