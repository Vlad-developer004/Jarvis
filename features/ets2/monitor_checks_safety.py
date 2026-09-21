"""Fines/damage/wear/critical-warning checks for the ETS2 telemetry
monitor. Split out of the old monitor.py purely for file size; no
behavior change.
"""
import time
from .config import *
from .monitor_state import _MonitorState
from .phrases import (
    event_fine_speeding, event_fine_other, event_tollgate, event_ferry, event_train,
    event_cargo_damaged, event_oil_pressure, event_water_temp, event_air_pressure_emergency,
    event_air_pressure_warning, event_battery_warning, event_adblue_warning,
    event_trailer_attached, event_trailer_detached, event_startup_wear, event_component_damaged,
    _wear_phrase, _r,
)

def _check_fines_and_tolls(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak, _add_job_fine
    fined_event = bool(data.get("fined", False) or data.get("finedActive", False))
    if fined_event and not state.last_fined:
        amount = int(data.get("fineAmount", 0))
        offence = str(data.get("fineOffence", "")).strip()
        offence_map = {
            "crash":           ("аварию",                      "аварію"),
            "fatigue":         ("нарушение режима сна",         "порушення режиму сну"),
            "wrong_way":       ("движение по встречной полосе", "рух по зустрічній смузі"),
            "speeding":        ("превышение скорости",          "перевищення швидкості"),
            "speeding_camera": ("превышение скорости",          "перевищення швидкості"),
            "no_lights":       ("езду без фар",                 "їзду без фар"),
            "red_light":       ("проезд на красный свет",       "проїзд на червоний сигнал"),
            "avoid_weighting": ("уклонение от взвешивания",     "ухилення від зважування"),
            "illegal_trailer": ("нелегальный прицеп",           "нелегальний причіп"),
        }
        ru_off, uk_off = "нарушение ПДД", "порушення ПДР"
        for k, (rv, ukv) in offence_map.items():
            if offence.lower().startswith(k.lower()):
                ru_off, uk_off = rv, ukv
                break
        if "speeding" in offence.lower():
            _speak(event_fine_speeding(amount))
        else:
            _speak(event_fine_other(ru_off, uk_off, amount))
        _add_job_fine(ru_off, uk_off, amount)
    state.last_fined = fined_event

    tollgate_event = bool(data.get("tollgate", False))
    if tollgate_event and not state.last_tollgate:
        amount = int(data.get("tollgatePayAmount", 0))
        _speak(event_tollgate(amount))
    state.last_tollgate = tollgate_event

    ferry_event = bool(data.get("ferry", False))
    if ferry_event and not state.last_ferry:
        amount = int(data.get("ferryPayAmount", 0))
        target = str(data.get("ferryTargetName", "")).strip()
        _speak(event_ferry(amount, target))
    state.last_ferry = ferry_event

    train_event = bool(data.get("train", False))
    if train_event and not state.last_train:
        amount = int(data.get("trainPayAmount", 0))
        target = str(data.get("trainTargetName", "")).strip()
        _speak(event_train(amount, target))
    state.last_train = train_event


def _check_cargo_damage(state: _MonitorState, data: dict, on_job: bool) -> None:
    from .monitor import _speak
    if on_job:
        trailer_list = data.get("trailer")
        if trailer_list and len(trailer_list) > 0:
            raw_dmg = float(trailer_list[0].get("cargoDamage", 0.0))
            cargo_dmg_pct = round(raw_dmg * 100, 1)
            if state.last_cargo_damage < 0:
                state.last_cargo_damage = cargo_dmg_pct
            elif cargo_dmg_pct >= state.last_cargo_damage + 0.1:
                state.last_cargo_damage = cargo_dmg_pct
                state.pending_cargo_dmg = cargo_dmg_pct
                state.pending_cargo_dmg_ts = time.monotonic()
    dmg_now = time.monotonic()
    if state.pending_cargo_dmg >= 0 and (dmg_now - state.pending_cargo_dmg_ts) >= 3.0:
        _speak(event_cargo_damaged(state.pending_cargo_dmg))
        state.pending_cargo_dmg = -1.0


def _check_critical_warnings(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    oil_warn = bool(data.get("oilPressureWarning", False))
    if oil_warn and not state.last_oil_warn:
        _speak(event_oil_pressure())
    state.last_oil_warn = oil_warn

    water_warn = bool(data.get("waterTemperatureWarning", False))
    if water_warn and not state.last_water_warn:
        _speak(event_water_temp())
    state.last_water_warn = water_warn

    air_emergency = bool(data.get("airPressureEmergency", False))
    if air_emergency and not state.last_air_emergency:
        _speak(event_air_pressure_emergency())
    state.last_air_emergency = air_emergency

    air_warn = bool(data.get("airPressureWarning", False))
    if air_warn and not state.last_air_warn and not air_emergency:
        _speak(event_air_pressure_warning())
    state.last_air_warn = air_warn

    battery_warn = bool(data.get("batteryVoltageWarning", False))
    if battery_warn and not state.last_battery_warn:
        _speak(event_battery_warning())
    state.last_battery_warn = battery_warn

    adblue_warn = bool(data.get("adblueWarning", False))
    if adblue_warn and not state.last_adblue_warn:
        _speak(event_adblue_warning())
    state.last_adblue_warn = adblue_warn


def _check_trailer(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    trailer_list = data.get("trailer")
    attached = bool(trailer_list and len(trailer_list) > 0)
    if state.last_trailer_attached is None:
        # First read after startup/reconnect — record baseline, don't announce.
        state.last_trailer_attached = attached
        return
    if attached != state.last_trailer_attached:
        state.last_trailer_attached = attached
        _speak(event_trailer_attached() if attached else event_trailer_detached())


def _check_wear(state: _MonitorState, data: dict) -> None:
    from .monitor import _speak
    if not state.startup_wear_spoken:
        try:
            from .phrases import _WEAR_NAMES_UK as _wnu
            high: list[str] = []
            for field, name_ru in WEAR_COMPONENTS:
                pct = int(round(float(data.get(field, 0.0)) * 100))
                state.last_wear_pct[field] = pct
                if pct >= 75:
                    name = _r([name_ru], [_wnu.get(name_ru, name_ru)])
                    high.append(f"{name} — {pct}%")
            if high:
                _speak(event_startup_wear(high))
        except Exception:
            pass
        state.startup_wear_spoken = True
    for field, name in WEAR_COMPONENTS:
        raw = float(data.get(field, 0.0))
        pct = int(round(raw * 100))
        prev = state.last_wear_pct.get(field)
        state.last_wear_pct[field] = pct
        if prev is not None:
            if (prev - pct) >= 10:
                for th in WEAR_THRESHOLDS:
                    state.fired_wear.discard((field, th))
            elif pct > prev:
                diff = pct - prev
                min_diff = 2 if field == "wearWheels" else 1
                if diff >= min_diff:
                    try:
                        from .phrases import _WEAR_NAMES_UK as _wnu
                        comp_name = _r([name], [_wnu.get(name, name)])
                        _speak(event_component_damaged(comp_name, pct))
                    except Exception:
                        pass
        for threshold in sorted(WEAR_THRESHOLDS, reverse=True):
            key = (field, threshold)
            if key in state.fired_wear: continue
            if threshold < 75:
                state.fired_wear.add(key)
                continue
            if pct >= threshold:
                state.fired_wear.add(key)
                for lower in WEAR_THRESHOLDS:
                    if lower <= threshold: state.fired_wear.add((field, lower))
                _speak(_wear_phrase(name, pct))
                break


