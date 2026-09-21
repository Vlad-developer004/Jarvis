"""Job-lifecycle/fuel/rest/deadline/route-progress checks for the ETS2
telemetry monitor. Split out of the old monitor.py purely for file size;
no behavior change.
"""
import threading
import time
from .config import *
from .monitor_state import _MonitorState
from .phrases import (
    event_engine_off, _fuel_phrase, event_fuel_shortage, event_post_rest, event_rest_warning,
    event_deadline_warning, event_almost_there, event_destination, event_idle, event_eta,
)

def _check_engine_transition(state: _MonitorState, data: dict) -> bool:
    from .monitor import _speak
    engine_on = bool(data.get("engineEnabled", False))
    if state.last_engine_on is False and engine_on is True:
        state.startup_wear_spoken = False
    if state.last_engine_on is True and engine_on is False:
        state.startup_wear_spoken = False
        p_brake = bool(data.get("parkBrake", False))
        lights_low = bool(data.get("lightsBeamLow", False))
        lights_high = bool(data.get("lightsBeamHigh", False))
        _speak(event_engine_off(p_brake, lights_low or lights_high))
    state.last_engine_on = engine_on
    return engine_on


def _check_job_lifecycle(state: _MonitorState, data: dict) -> None:
    from .monitor import _announce_job_start, _announce_job_delivered
    is_cargo_loaded = bool(data.get("isCargoLoaded", False))
    if state.last_cargo_loaded is None:
        state.last_cargo_loaded = is_cargo_loaded
    elif is_cargo_loaded and not state.last_cargo_loaded:
        _announce_job_start(data)
    state.last_cargo_loaded = is_cargo_loaded

    delivered_rev = int(data.get("jobDeliveredRevenue", 0))
    if state.last_delivered_rev is None:
        state.last_delivered_rev = delivered_rev
    elif delivered_rev != state.last_delivered_rev and delivered_rev > 0:
        _announce_job_delivered(data)
        state.last_delivered_rev = delivered_rev


def _check_fuel(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    current_fuel = float(data.get("fuel", 0))
    if state.last_fuel is not None and current_fuel > state.last_fuel + 5.0:
        state.fired_fuel.clear()
        state.fired_fuel_shortage = False
    state.last_fuel = current_fuel
    fuel_range = float(data.get("fuelRange", 0))
    if fuel_range <= 0:
        return
    for threshold in FUEL_THRESHOLDS:
        if threshold in state.fired_fuel: continue
        if fuel_range <= threshold:
            state.fired_fuel.add(threshold)
            _speak(_fuel_phrase(fuel_range))
            break
    # Distance vs Fuel Range check
    route_dist_m = float(data.get("routeDistance", 0))
    if route_dist_m > 2000:  # Only if route is significant
        route_km = route_dist_m / 1000.0
        if fuel_range < route_km:
            if not state.fired_fuel_shortage:
                state.fired_fuel_shortage = True
                _speak(event_fuel_shortage(int(fuel_range), int(route_km)))
        elif fuel_range > route_km + 40:  # Buffer to reset if refueled
            state.fired_fuel_shortage = False


def _check_rest(state: _MonitorState, data: dict, engine_on: bool) -> None:
    from .monitor import _speak
    rest_val = int(data.get("restStop", -1))
    if rest_val > 0 and engine_on:
        prev_rest = state.last_rest_val
        state.last_rest_val = rest_val
        if rest_val > prev_rest + 30:
            state.fired_rest.clear()
        if prev_rest != 9999 and rest_val >= prev_rest + 300:
            _speak(event_post_rest())
        for threshold in sorted(REST_THRESHOLDS, reverse=True):
            if threshold in state.fired_rest:
                continue
            if prev_rest > threshold and rest_val <= threshold:
                state.fired_rest.add(threshold)
                _speak(event_rest_warning(threshold))
                break
    else:
        state.last_rest_val = rest_val


def _check_deadline(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    deadline_abs = int(data.get("time_abs_delivery", 0))
    cur_abs = int(data.get("time_abs", 0))
    if deadline_abs > 0 and cur_abs > 0 and deadline_abs > cur_abs:
        if state.last_deadline_abs == 0:
            state.last_deadline_abs = deadline_abs
        remaining_gmin = deadline_abs - cur_abs
        if deadline_abs != state.last_deadline_abs:
            state.fired_deadline.clear()
            state.last_deadline_abs = deadline_abs
        for thr in sorted(DEADLINE_THRESHOLDS, reverse=True):
            if thr in state.fired_deadline:
                continue
            if remaining_gmin <= thr:
                state.fired_deadline.add(thr)
                _speak(event_deadline_warning(thr))
                break
    elif deadline_abs == 0:
        state.fired_deadline.clear()
        state.last_deadline_abs = 0


def _check_route_progress(state: _MonitorState, data: dict, engine_on: bool) -> bool:
    from .monitor import _speak
    route_dist = float(data.get("routeDistance", 0))
    on_job = bool(data.get("onJob", False))
    if route_dist > state.last_route_dist + 5000:
        state.fired_arrival = False
        state.fired_destination = False
    state.last_route_dist = route_dist
    if 100 < route_dist <= 2000 and not state.fired_arrival and engine_on:
        state.fired_arrival = True
        _speak(event_almost_there())
    if 0 <= route_dist <= 50 and not state.fired_destination and on_job and engine_on:
        state.fired_destination = True
        try:
            from actions.game_input import press_robust, get_binding as _gb
            key = _gb('action', 'enter')
            press_robust(key)
        except Exception:
            pass
        _speak(event_destination())
    return on_job


def _check_idle(state: _MonitorState, data: dict, engine_on: bool, on_job: bool) -> None:
    from .monitor import _speak
    now_ts = time.monotonic()
    cur_speed = abs(float(data.get("speed", 0)) * 3.6)
    park_brake = bool(data.get("parkBrake", False))
    is_standing = cur_speed < 1.0 and engine_on and not park_brake and on_job
    if is_standing:
        if state.idle_start_time == 0.0:
            state.idle_start_time = now_ts
        elif not state.idle_warned and (now_ts - state.idle_start_time) >= IDLE_WARN_SECONDS:
            state.idle_warned = True
            idle_mins = int((now_ts - state.idle_start_time) / 60)
            _speak(event_idle(idle_mins))
    else:
        state.idle_start_time, state.idle_warned = 0.0, False


def _check_eta(state: _MonitorState, data: dict, engine_on: bool, on_job: bool) -> None:
    from .monitor import _speak
    now_ts = time.monotonic()
    route_time_s = float(data.get("routeTime", 0))
    if on_job and engine_on and route_time_s > 900 and float(data.get("routeDistance", 0)) > 2000 \
            and (now_ts - state.last_eta_spoken_ts) >= ETA_INTERVAL_SECONDS:
        state.last_eta_spoken_ts = now_ts
        eta_h = route_time_s / 3600
        _speak(event_eta(eta_h))


def _check_live_commentary(state: _MonitorState, data: dict, engine_on: bool, on_job: bool, speed_kmh: float) -> None:
    """Occasional ambient remark on long highway stretches — purely flavor,
    never a warning, so it stays silent unless the LLM narrator is configured
    and there's nothing more important to say (long enough since the last
    remark, well clear of arrival/destination chatter)."""
    from .monitor import _speak
    now_ts = time.monotonic()
    route_dist = float(data.get("routeDistance", 0))
    if not (on_job and engine_on and speed_kmh >= LIVE_COMMENT_MIN_SPEED_KMH
            and route_dist > LIVE_COMMENT_MIN_ROUTE_DIST_M
            and (now_ts - state.last_live_comment_ts) >= LIVE_COMMENT_INTERVAL_SECONDS):
        return
    try:
        from .llm import has_llm_configured, build_live_commentary_prompt, ask_ets2
    except Exception:
        return
    if not has_llm_configured():
        return
    # Set the cooldown before the (blocking, background-threaded) LLM call
    # returns, so a slow response can't cause a second trigger to stack up.
    state.last_live_comment_ts = now_ts
    _snap = dict(data)

    def _llm_comment():
        result = ask_ets2(build_live_commentary_prompt(_snap))
        if result:
            _speak(result)

    threading.Thread(target=_llm_comment, daemon=True).start()


