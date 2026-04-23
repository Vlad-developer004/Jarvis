import threading
import time
import random
from typing import Optional
from .config import *
from .phrases import _fuel_phrase, _wear_phrase
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_auto_cruise: bool = False
_auto_cruise_lock = threading.Lock()
_last_auto_limit_snapped: float = 0.0
def set_auto_cruise(enabled: bool) -> None:
    global _auto_cruise, _last_auto_limit_snapped
    with _auto_cruise_lock:
        _auto_cruise = enabled
        if enabled:
            # Reset to allow immediate trigger on current limit
            _last_auto_limit_snapped = 0.0
def _speak(text: str) -> None:
    try:
        from core.speech import speak_async
        speak_async(text)
    except Exception:
        pass
def get_wear_report() -> str:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
    except Exception:
        return "Телеметрия недоступна."
    if not data:
        return "Данные телеметрии не получены. Убедитесь, что плагин установлен и игра запущена."
    parts: list[str] = []
    critical: list[str] = []
    warning: list[str] = []
    normal: list[str] = []
    for field, name in WEAR_COMPONENTS:
        raw = float(data.get(field, 0.0))
        pct = int(round(raw * 100))
        if pct >= 75: critical.append(f"{name} — {pct}%")
        elif pct >= 25: warning.append(f"{name} — {pct}%")
        else: normal.append(f"{name} — {pct}%")
    fuel_range = int(round(float(data.get("fuelRange", 0))))
    speed = int(round(float(data.get("speed", 0)) * 3.6))
    engine_on = data.get("engineEnabled", False)
    park_brake = data.get("parkBrake", False)
    rest_stop = int(data.get("restStop", -1))
    parts.append(
        f"Двигатель {'работает' if engine_on else 'заглушен'}, "
        f"ручник {'поднят' if park_brake else 'снят'}, "
        f"скорость {speed} километров в час, "
        f"запас хода {fuel_range} километров."
    )
    if rest_stop > 0: parts.append(f"До обязательного отдыха {rest_stop} минут.")
    if critical: parts.append(f"Критический износ: {', '.join(critical)}.")
    if warning: parts.append(f"Требует внимания: {', '.join(warning)}.")
    if not critical and not warning: parts.append("Все системы в норме.")
    return " ".join(parts)
def _monitor_loop() -> None:
    from actions.ets2_telemetry import get
    fired_fuel: set[int] = set()
    last_fuel: Optional[float] = None
    last_speed_warn: float = 0.0
    speed_was_over: bool = False
    fired_wear: set[tuple[str, int]] = set()
    last_engine_on: Optional[bool] = None
    fired_rest: set[int] = set()
    last_rest_val: int = 9999
    startup_wear_spoken: bool = False
    last_wear_pct: dict[str, int] = {}
    fired_arrival: bool = False
    fired_destination: bool = False
    last_route_dist: float = 0.0
    last_fined: bool = False
    last_tollgate: bool = False
    last_ferry: bool = False
    last_train: bool = False
    last_aux_front: int = -1
    last_aux_roof: int = -1
    route_snapshot_dist: float = 0.0
    route_snapshot_time: float = 0.0
    fired_diverge: bool = False
    fired_fuel_shortage: bool = False
    idle_start_time: float = 0.0
    idle_warned: bool = False
    last_speed_abs: float = 0.0
    last_auto_limit_snapped: float = 0.0
    last_auto_lights: float = 0.0
    global _last_auto_limit_snapped
    while not _stop_event.is_set():

        try:
            _stop_event.wait(POLL_INTERVAL)
            if _stop_event.is_set(): break
            data = get()
        except Exception:
            data = None
        if data is None:
            last_fuel = None
            fired_fuel.clear()
            speed_was_over = False
            last_engine_on = None
            fired_rest.clear()
            last_rest_val = 9999
            fired_arrival = False
            fired_destination = False
            last_route_dist = 0.0
            last_fined = False
            last_tollgate = False
            last_ferry = False
            last_train = False
            last_aux_front = -1
            last_aux_roof = -1
            route_snapshot_dist = 0.0
            route_snapshot_time = 0.0
            fired_diverge = False
            idle_start_time = 0.0
            idle_warned = False
            last_speed_abs = 0.0
            last_auto_limit_snapped = 0.0
            fired_fuel_shortage = False
            continue
        engine_on: bool = bool(data.get("engineEnabled", False))
        if last_engine_on is False and engine_on is True:
            startup_wear_spoken = False
        if last_engine_on is True and engine_on is False:
            startup_wear_spoken = False
        last_engine_on = engine_on
        current_fuel: float = float(data.get("fuel", 0))
        if last_fuel is not None and current_fuel > last_fuel + 5.0:
            fired_fuel.clear()
            fired_fuel_shortage = False
        last_fuel = current_fuel
        fuel_range: float = float(data.get("fuelRange", 0))
        if fuel_range > 0:
            for threshold in FUEL_THRESHOLDS:
                if threshold in fired_fuel: continue
                if fuel_range <= threshold:
                    fired_fuel.add(threshold)
                    _speak(_fuel_phrase(fuel_range))
                    break
            
            # Distance vs Fuel Range check
            route_dist_m = float(data.get("routeDistance", 0))
            if route_dist_m > 2000: # Only if route is significant
                route_km = route_dist_m / 1000.0
                if fuel_range < route_km:
                    if not fired_fuel_shortage:
                        fired_fuel_shortage = True
                        _speak(f"Сэр, запас хода {int(fuel_range)} километров, а до цели — {int(route_km)}. Топлива может не хватить до конца пути. Рекомендую заправиться.")
                elif fuel_range > route_km + 40: # Buffer to reset if refueled
                    fired_fuel_shortage = False
        speed_kmh = float(data.get("speed", 0)) * 3.6
        limit_kmh = float(data.get("speedLimit", 0)) * 3.6
        if limit_kmh > 0:
            over = speed_kmh - limit_kmh
            now = time.monotonic()
            
            # 2. Cruise Control Support (Selective)
            cruise_active = False
            if _auto_cruise and speed_kmh >= 30.0:
                from actions.ets2_telemetry import get_cruise_active
                # We try to use auto-cruise even if not currently active, 
                # cruise_set_speed will handle engagement.
                cruise_active = True 

            # 1. Over speed warning
            if over >= SPEED_OVER_LIMIT:
                if not speed_was_over and (now - last_speed_warn >= SPEED_COOLDOWN):
                    speed_was_over = True
                    last_speed_warn = now
                    # Skip verbal warning if auto-cruise is handling the situation
                    if not cruise_active:
                        _speak(f"Сэр, превышение скорости. Лимит {int(round(limit_kmh))}, ваша скорость {int(round(speed_kmh))}.")
            else:
                speed_was_over = False

            if cruise_active:
                new_snapped = round(limit_kmh / 5.0) * 5.0
                if new_snapped != last_auto_limit_snapped:
                    # Sync local and global memory
                    last_auto_limit_snapped = new_snapped
                    _last_auto_limit_snapped = new_snapped
                    from actions.game_input_parts.driving import cruise_set_speed
                    cruise_set_speed(int(new_snapped), speed_kmh, auto_mode=True)
            elif _last_auto_limit_snapped != 0.0:
                # User manually turned it off, reset memory to allow sync when turned back on
                _last_auto_limit_snapped = 0.0
        if not engine_on: continue
        if not startup_wear_spoken:
            try:
                high: list[str] = []
                for field, name in WEAR_COMPONENTS:
                    pct = int(round(float(data.get(field, 0.0)) * 100))
                    last_wear_pct[field] = pct
                    if pct >= 75:
                        high.append(f"{name} — {pct}%")
                if high:
                    _speak("Сэр, высокий износ: " + ", ".join(high) + ". Рекомендую сервис.")
            except Exception:
                pass
            startup_wear_spoken = True
        for field, name in WEAR_COMPONENTS:
            raw = float(data.get(field, 0.0))
            pct = int(round(raw * 100))
            prev = last_wear_pct.get(field)
            last_wear_pct[field] = pct
            if prev is not None and (prev - pct) >= 10:
                for th in WEAR_THRESHOLDS:
                    fired_wear.discard((field, th))
            for threshold in sorted(WEAR_THRESHOLDS, reverse=True):
                key = (field, threshold)
                if key in fired_wear: continue
                if threshold < 75:
                    fired_wear.add(key)
                    continue
                if pct >= threshold:
                    fired_wear.add(key)
                    for lower in WEAR_THRESHOLDS:
                        if lower <= threshold: fired_wear.add((field, lower))
                    _speak(_wear_phrase(name, pct))
                    break
        rest_val: int = int(data.get("restStop", -1))
        if rest_val > 0 and engine_on:
            prev_rest = last_rest_val
            last_rest_val = rest_val
            if rest_val > prev_rest + 30:
                fired_rest.clear()
            for threshold in sorted(REST_THRESHOLDS, reverse=True):
                if threshold in fired_rest:
                    continue
                if prev_rest > threshold and rest_val <= threshold:
                    fired_rest.add(threshold)
                    if threshold >= 180:
                        _speak("Сэр, напоминаю: до обязательного отдыха три часа.")
                    elif threshold >= 60:
                        _speak("Сэр, до обязательного отдыха остался один час. Рекомендую планировать остановку.")
                    else:
                        _speak("Сэр, до обязательного отдыха осталось меньше получаса. Водитель очень устал.")
                    break
        else:
            last_rest_val = rest_val
        route_dist: float = float(data.get("routeDistance", 0))
        on_job: bool = bool(data.get("onJob", False))
        if route_dist > last_route_dist + 5000:
            fired_arrival = False
            fired_destination = False
        last_route_dist = route_dist
        if 100 < route_dist <= 2000 and not fired_arrival and engine_on:
            fired_arrival = True
            _speak("Сэр, мы почти на месте.")
        if 0 <= route_dist <= 50 and not fired_destination and on_job and engine_on:
            fired_destination = True
            try:
                from actions.game_input import press_robust, get_binding as _gb
                key = _gb('action', 'enter')
                press_robust(key)
            except Exception:
                pass
            phrases = [
                "Мы на месте, сэр. Можно приступать к парковке.",
                "Пункт назначения достигнут. Пожалуйста, припаркуйтесь.",
                "Финиш маршрута. Жду завершения маневра."
            ]
            _speak(random.choice(phrases))
        fined_event = bool(data.get("fined", False) or data.get("finedActive", False))
        if fined_event and not last_fined:
            amount = int(data.get("fineAmount", 0))
            offence = str(data.get("fineOffence", "")).strip()
            offence_map = {"crash": "аварию", "fatigue": "нарушение режима сна", "wrong_way": "движение по встречной полосе", "speeding": "превышение скорости", "speeding_camera": "превышение скорости", "no_lights": "езду без фар", "red_light": "проезд на красный свет", "avoid_weighting": "уклонение от взвешивания", "illegal_trailer": "нелегальный прицеп"}
            ru_offence = "нарушение ПДД"
            for k, v in offence_map.items():
                if offence.lower().startswith(k.lower()):
                    ru_offence = v
                    break
            if "speeding" in offence.lower():
                _speak(f"Сэр, вы снова превысили скорость. Списано {amount} евро.")
            else:
                _speak(f"Сэр, зафиксирован штраф за {ru_offence}. Списано {amount} евро.")
        last_fined = fined_event
        tollgate_event = bool(data.get("tollgate", False))
        if tollgate_event and not last_tollgate:
            amount = int(data.get("tollgatePayAmount", 0))
            _speak(f"Оплата проезда прошла успешно. Списано {amount} евро.")
        last_tollgate = tollgate_event
        ferry_event = bool(data.get("ferry", False))
        if ferry_event and not last_ferry:
            amount, target = int(data.get("ferryPayAmount", 0)), str(data.get("ferryTargetName", "")).strip()
            dest_str = f" до пункта {target}" if target else ""
            _speak(f"Билет на паром{dest_str} оплачен. Списано {amount} евро.")
        last_ferry = ferry_event
        train_event = bool(data.get("train", False))
        if train_event and not last_train:
            amount, target = int(data.get("trainPayAmount", 0)), str(data.get("trainTargetName", "")).strip()
            dest_str = f" до пункта {target}" if target else ""
            _speak(f"Билет на поезд{dest_str} оплачен. Списано {amount} евро.")
        last_train = train_event
        cur_aux_front, cur_aux_roof = int(data.get("lightsAuxFront", 0)), int(data.get("lightsAuxRoof", 0))
        if last_aux_front != -1 and cur_aux_front != last_aux_front:
            if cur_aux_front == 0: _speak("Дополнительные передние фары выключены.")
            elif cur_aux_front == 1: _speak("Противотуманные фары включены.")
            elif cur_aux_front >= 2: _speak("Дополнительный передний свет включён.")
        last_aux_front = cur_aux_front
        if last_aux_roof != -1 and cur_aux_roof != last_aux_roof:
            if cur_aux_roof == 0: _speak("Люстра выключена.")
            else: _speak("Люстра включена.")
        last_aux_roof = cur_aux_roof
        # Adaptive Lights (Night auto-on)
        game_time = int(data.get("time", 0))
        hour = (game_time % 1440) // 60
        is_night = (hour >= 20 or hour < 7)
        lights_low = bool(data.get("lightsBeamLow", False))
        
        if is_night and not lights_low and engine_on:
            now_ts = time.monotonic()
            if now_ts - last_auto_lights >= 15.0:
                last_auto_lights = now_ts
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

        now_ts, rd = time.monotonic(), float(data.get("routeDistance", 0))
        route_snapshot_dist, route_snapshot_time, fired_diverge = 0.0, 0.0, False
        cur_speed = abs(float(data.get("speed", 0)) * 3.6)
        park_brake = bool(data.get("parkBrake", False))
        is_standing = cur_speed < 1.0 and engine_on and not park_brake and on_job
        if is_standing:
            if idle_start_time == 0.0: idle_start_time = now_ts
            elif not idle_warned and (now_ts - idle_start_time) >= IDLE_WARN_SECONDS:
                idle_warned = True
                idle_mins = int((now_ts - idle_start_time) / 60)
                _speak(f"Сэр, мы уже {idle_mins} минут стоим на месте. Рекомендую продолжать движение.")
        else: idle_start_time, idle_warned = 0.0, False
def start() -> None:
    global _thread
    if _thread and _thread.is_alive(): return
    _stop_event.clear()
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="ets2_navigator")
    _thread.start()
def stop() -> None:
    _stop_event.set()
