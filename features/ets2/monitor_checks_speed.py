"""Speed/cruise/lighting driving-behavior checks for the ETS2 telemetry
monitor. Split out of the old monitor.py purely for file size; no
behavior change. See monitor_checks_safety.py / monitor_checks_progress.py
for the other check groups; _check_speed_limit_and_cruise stays in
monitor.py itself because it mutates module-level state via `global`.
"""
import time
from .config import *
from .config import BLINKER_REPEAT_SECONDS
from .monitor_state import _MonitorState
from .phrases import (
    event_gear_high_rpm, event_gear_low_rpm, event_cruise_on, event_cruise_off,
    event_blinker_on, event_rain_no_lights, event_lights_aux_front, event_lights_aux_roof,
)

def _check_gear_advice(state: _MonitorState, data: dict, speed_kmh: float) -> None:
    from .monitor import _speak, bump_driving_stat
    rpm = float(data.get("engineRpm", 0))
    rpm_max = float(data.get("engineRpmMax", 0))
    gear = int(data.get("gear", 0))
    throttle = float(data.get("gameThrottle", data.get("userThrottle", 0)))
    if rpm_max > 0 and speed_kmh > 25.0 and gear > 0 \
            and (time.monotonic() - state.last_gear_advice_ts) >= GEAR_ADVICE_COOLDOWN:
        if rpm > rpm_max * RPM_HIGH_FACTOR:
            state.last_gear_advice_ts = time.monotonic()
            bump_driving_stat('gear_warning')
            _speak(event_gear_high_rpm())
        elif rpm < rpm_max * RPM_LOW_FACTOR and throttle > RPM_LOW_THROTTLE_MIN:
            state.last_gear_advice_ts = time.monotonic()
            bump_driving_stat('gear_warning')
            _speak(event_gear_low_rpm())


def _check_manual_cruise_status(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak, get_auto_cruise
    if get_auto_cruise():
        state.last_cruise_active = None
        return
    cruise_active_now = False
    for field in ("cruiseControl", "cruise_control", "cruiseControlOn", "cruiseControlEnabled"):
        v = data.get(field)
        if v is not None:
            cruise_active_now = bool(v)
            break
    if state.last_cruise_active is not None and cruise_active_now != state.last_cruise_active:
        if cruise_active_now:
            cruise_speed = 0.0
            for field in ("cruiseControlSpeed", "cruise_control_speed", "cruiseSpeed"):
                v = data.get(field)
                if v is not None:
                    cruise_speed = float(v) * 3.6
                    break
            _speak(event_cruise_on(int(round(cruise_speed))))
        else:
            _speak(event_cruise_off())
    state.last_cruise_active = cruise_active_now


def _check_blinker(state: _MonitorState, data: dict, speed_kmh: float) -> None:
    from .monitor import _speak
    blinker_on = (bool(data.get("blinkerLeftOn", False)) or bool(data.get("blinkerRightOn", False))) \
                 and not bool(data.get("lightsHazards", False))
    if blinker_on and speed_kmh > 30.0:
        now_bl = time.monotonic()
        if not state.blinker_was_on:
            state.blinker_on_since = now_bl
            state.blinker_was_on = True
            state.blinker_warned_once = False
        else:
            elapsed_bl = now_bl - state.blinker_on_since
            if not state.blinker_warned_once and elapsed_bl >= BLINKER_WARN_SECONDS:
                state.blinker_warned_once = True
                state.blinker_on_since = now_bl
                _speak(event_blinker_on(first=True))
            elif state.blinker_warned_once and elapsed_bl >= BLINKER_REPEAT_SECONDS:
                state.blinker_on_since = now_bl
                _speak(event_blinker_on(first=False))
    else:
        state.blinker_was_on = False
        state.blinker_on_since = 0.0
        state.blinker_warned_once = False


def _check_rain_lights(state: _MonitorState, data: dict, engine_on: bool, speed_kmh: float) -> None:
    from .monitor import _speak
    if engine_on and speed_kmh >= 5.0 and bool(data.get("wipers", False)):
        l_low = bool(data.get("lightsBeamLow", False))
        l_high = bool(data.get("lightsBeamHigh", False))
        if not l_low and not l_high:
            now_wip = time.monotonic()
            if now_wip - state.last_wipers_warn_ts >= 300.0:
                state.last_wipers_warn_ts = now_wip
                _speak(event_rain_no_lights())


def _check_aux_lights(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    cur_aux_front = int(data.get("lightsAuxFront", 0))
    cur_aux_roof = int(data.get("lightsAuxRoof", 0))
    if state.last_aux_front != -1 and cur_aux_front != state.last_aux_front:
        _speak(event_lights_aux_front(cur_aux_front))
    state.last_aux_front = cur_aux_front
    if state.last_aux_roof != -1 and cur_aux_roof != state.last_aux_roof:
        _speak(event_lights_aux_roof(cur_aux_roof != 0))
    state.last_aux_roof = cur_aux_roof


def _check_adaptive_lights(state: _MonitorState, data: dict, engine_on: bool) -> None:
    """Auto-toggle low beams at night (game time 20:00-07:00)."""
    from actions.ets2_telemetry import get
    game_time = int(data.get("time", 0))
    hour = (game_time % 1440) // 60
    is_night = (hour >= 20 or hour < 7)
    lights_low = bool(data.get("lightsBeamLow", False))
    if is_night and not lights_low and engine_on:
        now_ts = time.monotonic()
        if now_ts - state.last_auto_lights >= 15.0:
            state.last_auto_lights = now_ts
            try:
                from actions.game_input import press_robust, get_binding as _gb
                # Press 'L' (lights) until low beam is on
                l_key = _gb('lights', 'l')
                press_robust(l_key)
                time.sleep(0.2)
                data_check = get()
                if data_check and not data_check.get("lightsBeamLow"):
                    press_robust(l_key)
            except Exception:
                pass


