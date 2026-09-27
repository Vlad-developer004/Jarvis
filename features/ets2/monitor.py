import re
import threading
import time
import random
from dataclasses import dataclass, field as _field
from typing import Optional
from .config import *
from .config import BLINKER_REPEAT_SECONDS
from .phrases import (
    _fuel_phrase, _wear_phrase, _pct_str, _r,
    event_engine_off, event_speed_over, event_speed_limit_drop, event_speed_limit_rise,
    event_cruise_auto, event_cruise_on, event_cruise_off,
    event_cargo_damaged, event_fine_speeding, event_fine_other,
    event_tollgate, event_ferry, event_train,
    event_almost_there, event_destination, event_idle,
    event_startup_wear, event_component_damaged,
    event_rest_warning, event_post_rest,
    event_deadline_warning, event_eta,
    event_gear_high_rpm, event_gear_low_rpm,
    event_rain_no_lights, event_blinker_on, event_fuel_shortage,
    event_lights_aux_front, event_lights_aux_roof,
    event_oil_pressure, event_water_temp,
    event_air_pressure_emergency, event_air_pressure_warning,
    event_battery_warning, event_adblue_warning,
)
_job_real_start: float = 0.0
_job_planned_income: int = 0
_job_fines: list = []
_job_harsh_brakes: int = 0
_job_speeding_events: int = 0
_job_gear_warnings: int = 0
_session_start: float = 0.0
_session_jobs: int = 0
_session_revenue: int = 0
_session_dist_km: float = 0.0
_prev_session: Optional[dict] = None
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_auto_cruise: bool = False
_auto_cruise_lock = threading.Lock()
_last_auto_limit_snapped: float = 0.0
_cruise_user_explicitly_disabled: bool = False

def get_auto_cruise() -> bool:
    return _auto_cruise


def set_auto_cruise(enabled: bool, by_user: bool = False) -> None:
    global _auto_cruise, _last_auto_limit_snapped, _cruise_user_explicitly_disabled
    with _auto_cruise_lock:
        _auto_cruise = enabled
        if by_user:
            _cruise_user_explicitly_disabled = not enabled
        if enabled:
            _last_auto_limit_snapped = 0.0
            _cruise_user_explicitly_disabled = False
def _resolve_addr(text: str) -> str:
    try:
        from core.address import get_address
        addr = get_address()
        text = re.sub(r'\bсэр\b', addr, text, flags=re.IGNORECASE)
        text = re.sub(r'\bсер\b', addr, text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text

def _speak(text: str) -> None:
    try:
        from core.speech import speak_async
        speak_async(_resolve_addr(text))
    except Exception:
        pass
def get_session_report() -> str:
    elapsed = time.monotonic() - _session_start if _session_start > 0 else 0
    h = int(elapsed // 3600)
    m = int((elapsed % 3600) // 60)
    time_str = f"{h} ч {m} мин" if h > 0 else f"{m} минут"
    parts = [_r(
        [f"Сессия идёт {time_str}."],
        [f"Сесія триває {time_str}."]
    )]
    if _session_jobs > 0:
        parts.append(_r(
            [f"Выполнено рейсов: {_session_jobs}."],
            [f"Виконано рейсів: {_session_jobs}."]
        ))
    if _session_revenue > 0:
        from features.ets2.phrases import _fmt_euro as _fe
        parts.append(_r(
            [f"Заработано за сессию: {_fe(_session_revenue)}."],
            [f"Зароблено за сесію: {_fe(_session_revenue)}."]
        ))
    if _session_dist_km > 0:
        from features.ets2.phrases import _fmt_km as _fkm
        parts.append(_r(
            [f"Пройдено: {_fkm(int(round(_session_dist_km)))}."],
            [f"Пройдено: {_fkm(int(round(_session_dist_km)))}."]
        ))
    if _prev_session and _session_revenue > 0:
        prev_rev = int(_prev_session.get('revenue', 0))
        if prev_rev > 0:
            diff_pct = round((_session_revenue - prev_rev) / prev_rev * 100)
            if abs(diff_pct) >= 5:
                if diff_pct > 0:
                    parts.append(_r(
                        [f"Это на {diff_pct}% больше, чем за прошлую сессию."],
                        [f"Це на {diff_pct}% більше, ніж за минулу сесію."]
                    ))
                else:
                    parts.append(_r(
                        [f"Это на {abs(diff_pct)}% меньше, чем за прошлую сессию."],
                        [f"Це на {abs(diff_pct)}% менше, ніж за минулу сесію."]
                    ))
    return _resolve_addr(" ... ".join(parts))

def get_wear_report() -> str:
    from .phrases import _WEAR_NAMES_UK
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
    except Exception:
        return _r(["Телеметрия недоступна."], ["Телеметрія недоступна."])
    if not data:
        return _r(
            ["Данные телеметрии не получены. Убедитесь, что плагин установлен и игра запущена."],
            ["Дані телеметрії не отримано. Переконайтесь, що плагін встановлено і гру запущено."]
        )
    critical: list[str] = []
    warning: list[str] = []
    for field, name_ru in WEAR_COMPONENTS:
        name = _r([name_ru], [_WEAR_NAMES_UK.get(name_ru, name_ru)])
        raw = float(data.get(field, 0.0))
        pct = int(round(raw * 100))
        if pct >= 75:   critical.append(f"{name} — {pct}%")
        elif pct >= 25: warning.append(f"{name} — {pct}%")
    fuel_range = int(round(float(data.get("fuelRange", 0))))
    speed = int(round(float(data.get("speed", 0)) * 3.6))
    engine_on = data.get("engineEnabled", False)
    park_brake = data.get("parkBrake", False)
    rest_stop = int(data.get("restStop", -1))
    parts = [_r(
        [
            f"Двигатель {'работает' if engine_on else 'заглушен'}, "
            f"ручник {'поднят' if park_brake else 'снят'}, "
            f"скорость {speed} километров в час, запас хода {fuel_range} километров."
        ],
        [
            f"Двигун {'працює' if engine_on else 'заглушено'}, "
            f"ручник {'піднятий' if park_brake else 'знятий'}, "
            f"швидкість {speed} кілометрів на годину, запас ходу {fuel_range} кілометрів."
        ]
    )]
    if rest_stop > 0:
        parts.append(_r(
            [f"До обязательного отдыха {rest_stop} минут."],
            [f"До обов'язкового відпочинку {rest_stop} хвилин."]
        ))
    if critical:
        parts.append(_r(
            [f"Критический износ: {', '.join(critical)}."],
            [f"Критичне зношення: {', '.join(critical)}."]
        ))
    if warning:
        parts.append(_r(
            [f"Требует внимания: {', '.join(warning)}."],
            [f"Потребує уваги: {', '.join(warning)}."]
        ))
    if not critical and not warning:
        parts.append(_r(["Все системы в норме."], ["Всі системи в нормі."]))
    return _resolve_addr(" ... ".join(parts))
def _fmt_hm(total_min: int) -> str:
    """Digit-based "2 ч 15 мин" / "2 год 15 хв" duration — deliberately not
    format_duration_russian() (core/nlp/russian.py), which spells numbers
    out via num2words(lang='ru') only and would leak Russian words into a
    Ukrainian sentence."""
    total_min = max(0, int(total_min))
    h, m = total_min // 60, total_min % 60
    from .phrases_common import _decline_ru, _decline_uk
    if h > 0:
        return _r(
            [f"{h} {_decline_ru(h, 'час', 'часа', 'часов')} {m} {_decline_ru(m, 'минуту', 'минуты', 'минут')}"],
            [f"{h} {_decline_uk(h, 'годину', 'години', 'годин')} {m} {_decline_uk(m, 'хвилину', 'хвилини', 'хвилин')}"]
        )
    return _r(
        [f"{m} {_decline_ru(m, 'минуту', 'минуты', 'минут')}"],
        [f"{m} {_decline_uk(m, 'хвилину', 'хвилини', 'хвилин')}"]
    )


def get_schedule_status() -> str:
    """On-demand answer to "укладываемся в график?" — remaining distance,
    deadline margin at the current pace, and current speed. Uses ETS2's own
    routeTime estimate (accounts for the actual road route) rather than a
    naive distance/current-speed calculation, which would be thrown off by
    a red light or a ferry queue."""
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
    except Exception:
        data = None
    if not data:
        return _r(
            ["Данные телеметрии не получены. Убедитесь, что плагин установлен и игра запущена."],
            ["Дані телеметрії не отримано. Переконайтесь, що плагін встановлено і гру запущено."]
        )
    if not bool(data.get("onJob", False)):
        return _r(["Сейчас нет активного рейса."], ["Зараз немає активного рейсу."])

    dist_km = float(data.get("routeDistance", 0)) / 1000.0
    if dist_km <= 0:
        return _r(["Маршрут не определён."], ["Маршрут не визначено."])

    route_min = float(data.get("routeTime", 0)) / 60.0
    speed_kmh = float(data.get("speed", 0)) * 3.6
    deadline_abs = int(data.get("time_abs_delivery", 0))
    cur_abs = int(data.get("time_abs", 0))

    parts = []
    has_deadline = deadline_abs > 0 and cur_abs > 0 and deadline_abs > cur_abs
    if has_deadline:
        deadline_min = deadline_abs - cur_abs
        parts.append(_r(
            [f"До дедлайна {_fmt_hm(int(round(deadline_min)))}, до цели {int(round(dist_km))} километров."],
            [f"До дедлайну {_fmt_hm(int(round(deadline_min)))}, до цілі {int(round(dist_km))} кілометрів."]
        ))
    else:
        parts.append(_r(
            [f"До цели {int(round(dist_km))} километров."],
            [f"До цілі {int(round(dist_km))} кілометрів."]
        ))
    if speed_kmh > 1:
        parts.append(_r(
            [f"Текущая скорость — {int(round(speed_kmh))} километров в час."],
            [f"Поточна швидкість — {int(round(speed_kmh))} кілометрів на годину."]
        ))
    if route_min > 0:
        parts.append(_r(
            [f"Расчётное время в пути — {_fmt_hm(int(round(route_min)))}."],
            [f"Розрахунковий час у дорозі — {_fmt_hm(int(round(route_min)))}."]
        ))
        if has_deadline:
            margin_min = deadline_min - route_min
            if margin_min >= 15:
                parts.append(_r(
                    [f"При текущем темпе успеваем с запасом {_fmt_hm(int(round(margin_min)))}."],
                    [f"У поточному темпі встигаємо із запасом {_fmt_hm(int(round(margin_min)))}."]
                ))
            elif margin_min >= 0:
                parts.append(_r(
                    ["Успеваем впритык — лучше не задерживаться в пути."],
                    ["Встигаємо впритул — краще не затримуватись у дорозі."]
                ))
            else:
                # "сэр"/"сер" here is the same literal-placeholder convention
                # every other function in this file uses (get_wear_report,
                # phrases_job.py, ...) — _resolve_addr() below swaps it for
                # the configured address form, no direct _addr() call needed.
                parts.append(_r(
                    [f"сэр, при текущем темпе не успеваем — опоздание примерно {_fmt_hm(int(round(-margin_min)))}."],
                    [f"сер, у поточному темпі не встигаємо — запізнення приблизно {_fmt_hm(int(round(-margin_min)))}."]
                ))
    return _resolve_addr(" ".join(parts))


def _clear_job_fines() -> None:
    global _job_fines, _job_planned_income, _job_harsh_brakes, _job_speeding_events, _job_gear_warnings
    _job_fines = []
    _job_planned_income = 0
    _job_harsh_brakes = 0
    _job_speeding_events = 0
    _job_gear_warnings = 0


def _add_job_fine(reason_ru: str, reason_uk: str, amount: int) -> None:
    _job_fines.append({'ru': reason_ru, 'uk': reason_uk, 'amount': amount})


def get_job_fines() -> list:
    return list(_job_fines)


def bump_driving_stat(kind: str) -> None:
    """Count one harsh-braking/speeding/gear-advice event toward the
    end-of-job driving-score summary. Called from monitor_checks_speed.py
    (gear advice) and this module's own _check_speed_limit_and_cruise
    (speeding, harsh braking) — kept as one entry point so a future stat
    doesn't need its own global+function pair."""
    global _job_harsh_brakes, _job_speeding_events, _job_gear_warnings
    if kind == 'harsh_brake':
        _job_harsh_brakes += 1
    elif kind == 'speeding':
        _job_speeding_events += 1
    elif kind == 'gear_warning':
        _job_gear_warnings += 1


def get_job_driving_stats() -> dict:
    return {
        'harsh_brakes': _job_harsh_brakes,
        'speeding_events': _job_speeding_events,
        'gear_warnings': _job_gear_warnings,
    }


def _announce_job_start_fallback(data: dict) -> None:
    from features.ets2.phrases import announce_job_start
    text = announce_job_start(data)
    if text:
        _speak(text)



def _announce_job_delivered_fallback(data: dict) -> None:
    from features.ets2.phrases import announce_job_delivered
    elapsed_min = (time.monotonic() - _job_real_start) / 60 if _job_real_start > 0 else 0
    text = announce_job_delivered(data, elapsed_min, driving_stats=get_job_driving_stats())
    if text:
        global _session_jobs, _session_revenue, _session_dist_km
        _session_jobs += 1
        _session_revenue += int(data.get("jobDeliveredRevenue", 0))
        _session_dist_km += float(data.get("jobDeliveredDistanceKm", 0))
        _speak(text)
        _save_session_snapshot()


def _announce_job_start(data: dict) -> None:
    global _job_real_start, _job_planned_income
    _job_real_start = time.monotonic()
    _clear_job_fines()
    _job_planned_income = int(data.get("jobIncome", 0))
    if not str(data.get("cargo", "")).strip():
        return
    try:
        from features.ets2.llm import has_llm_configured, build_job_start_prompt, ask_ets2
        if has_llm_configured():
            _snap = dict(data)
            def _llm_job():
                result = ask_ets2(build_job_start_prompt(_snap))
                _speak(result) if result else _announce_job_start_fallback(_snap)
            threading.Thread(target=_llm_job, daemon=True).start()
            return
    except Exception:
        pass
    _announce_job_start_fallback(data)


def _announce_job_delivered(data: dict) -> None:
    cargo_dmg   = float(data.get("jobDeliveredCargoDamage", 0)) * 100
    dist_km     = float(data.get("jobDeliveredDistanceKm", 0))
    revenue     = int(data.get("jobDeliveredRevenue", 0))
    xp          = int(data.get("jobDeliveredEarnedXp", 0))
    autopark    = bool(data.get("jobDeliveredAutoparkUsed", False))
    elapsed_min = (time.monotonic() - _job_real_start) / 60 if _job_real_start > 0 else 0
    fines       = get_job_fines()
    planned_income = _job_planned_income
    driving_stats = get_job_driving_stats()
    try:
        from features.ets2.llm import has_llm_configured, build_job_delivered_prompt, ask_ets2
        if has_llm_configured():
            _snap = dict(data)
            _dmg, _dist, _rev, _xp, _elap, _auto = cargo_dmg, dist_km, revenue, xp, elapsed_min, autopark
            _fines, _planned, _driving = fines, planned_income, driving_stats
            def _llm_delivery():
                result = ask_ets2(build_job_delivered_prompt(
                    _snap, _dmg, _dist, _rev, _xp, _elap, _auto,
                    fines=_fines, planned_income=_planned, driving_stats=_driving,
                ))
                if result:
                    _speak(result)
                    global _session_jobs, _session_revenue, _session_dist_km
                    _session_jobs += 1
                    _session_revenue += _rev
                    _session_dist_km += _dist
                    _save_session_snapshot()
                else:
                    _announce_job_delivered_fallback(_snap)
            threading.Thread(target=_llm_delivery, daemon=True).start()
            return
    except Exception:
        pass
    _announce_job_delivered_fallback(data)


from .monitor_state import _MonitorState
from .monitor_checks_speed import (
    _check_gear_advice, _check_manual_cruise_status, _check_blinker, _check_rain_lights, _check_aux_lights, _check_adaptive_lights,
)
from .monitor_checks_safety import (
    _check_fines_and_tolls, _check_cargo_damage, _check_critical_warnings, _check_wear, _check_trailer,
)
from .monitor_checks_progress import (
    _check_engine_transition, _check_job_lifecycle, _check_fuel, _check_rest, _check_deadline, _check_route_progress, _check_idle, _check_eta,
    _check_live_commentary, _check_real_break,
)

def _check_speed_limit_and_cruise(state: _MonitorState, data: dict) -> float:
    global _last_auto_limit_snapped
    speed_kmh = float(data.get("speed", 0)) * 3.6
    limit_kmh = float(data.get("speedLimit", 0)) * 3.6

    # Harsh-braking detector for the end-of-job driving score: a big speed
    # drop between two polls (~POLL_INTERVAL apart), starting from a real
    # driving speed so ordinary stop-and-go traffic doesn't count.
    if state.last_speed_for_brake >= HARSH_BRAKE_MIN_SPEED_KMH and \
            (state.last_speed_for_brake - speed_kmh) >= HARSH_BRAKE_DROP_KMH:
        bump_driving_stat('harsh_brake')
    state.last_speed_for_brake = speed_kmh

    if speed_kmh >= 5.0:
        if limit_kmh > 0 and state.last_speed_limit > 0:
            limit_drop = state.last_speed_limit - limit_kmh
            limit_rise = limit_kmh - state.last_speed_limit
            now_lim = time.monotonic()
            if limit_drop >= 20:
                # "Brake!" phrasing only makes sense if the driver is actually
                # over the NEW limit right now — a big sign drop (e.g. 70->50)
                # while already doing 15 needs no braking at all, so it must
                # not get the urgent variant just because the drop itself was
                # sharp (previously compared drop magnitude only, so it fired
                # "тормозите!" even at speeds nowhere near the new limit).
                _speak(event_speed_limit_drop(int(round(limit_kmh)), sharp=(speed_kmh > limit_kmh)))
            elif limit_drop >= 15:
                _speak(event_speed_limit_drop(int(round(limit_kmh)), sharp=False))
            elif limit_rise >= 20 and (now_lim - state.last_limit_increase_ts) > 30.0:
                state.last_limit_increase_ts = now_lim
                _speak(event_speed_limit_rise(int(round(limit_kmh))))
        if limit_kmh > 0:
            state.last_speed_limit = limit_kmh
        if limit_kmh > 0:
            over = speed_kmh - limit_kmh
            now = time.monotonic()

            # Cruise Control Support (Selective)
            cruise_active = False
            if _auto_cruise and not _cruise_user_explicitly_disabled and speed_kmh >= 30.0:
                cruise_active = True

            # Over speed warning
            if over >= SPEED_OVER_LIMIT:
                if not state.speed_was_over and (now - state.last_speed_warn >= SPEED_COOLDOWN):
                    state.speed_was_over = True
                    state.last_speed_warn = now
                    bump_driving_stat('speeding')
                    if not cruise_active:
                        _speak(event_speed_over(int(round(limit_kmh)), int(round(speed_kmh))))
            else:
                state.speed_was_over = False

            if cruise_active:
                new_snapped = round(limit_kmh / 5.0) * 5.0
                if new_snapped != state.last_auto_limit_snapped:
                    state.last_auto_limit_snapped = new_snapped
                    _last_auto_limit_snapped = new_snapped
                    from actions.game_input_parts.driving import cruise_set_speed
                    cruise_set_speed(int(new_snapped), speed_kmh, auto_mode=True)
                    _speak(event_cruise_auto(int(new_snapped)))
            elif _last_auto_limit_snapped != 0.0:
                # User manually turned it off, reset memory to allow sync when turned back on
                _last_auto_limit_snapped = 0.0
    else:
        state.last_speed_limit = limit_kmh if limit_kmh > 0 else 0.0
        state.speed_was_over = False
    return speed_kmh



def _monitor_loop() -> None:
    from actions.ets2_telemetry import get
    state = _MonitorState()
    while not _stop_event.is_set():
        try:
            _stop_event.wait(POLL_INTERVAL)
            if _stop_event.is_set(): break
            data = get()
        except Exception:
            data = None
        if data is None:
            state.reset_on_telemetry_loss()
            continue

        try:
            engine_on = _check_engine_transition(state, data)
            _check_job_lifecycle(state, data)
            _check_fuel(state, data)
            speed_kmh = _check_speed_limit_and_cruise(state, data)
            _check_trailer(state, data)
            if not engine_on:
                continue

            _check_wear(state, data)
            _check_rest(state, data, engine_on)
            _check_real_break(state, data, engine_on)
            _check_deadline(state, data)
            on_job = _check_route_progress(state, data, engine_on)
            _check_cargo_damage(state, data, on_job)
            _check_fines_and_tolls(state, data)
            _check_aux_lights(state, data)
            _check_adaptive_lights(state, data, engine_on)
            _check_idle(state, data, engine_on, on_job)
            _check_critical_warnings(state, data)
            _check_blinker(state, data, speed_kmh)
            _check_eta(state, data, engine_on, on_job)
            _check_gear_advice(state, data, speed_kmh)
            _check_rain_lights(state, data, engine_on, speed_kmh)
            _check_manual_cruise_status(state, data)
            _check_live_commentary(state, data, engine_on, on_job, speed_kmh)
        except Exception as e:
            # A single bad tick must never kill this daemon thread for the rest
            # of the session — it silently did exactly that before this guard
            # existed (see the 2026-09 file-split regression where several
            # _check_* helpers referenced phrase functions that were never
            # actually imported into their module: NameError here was uncaught
            # and _monitor_loop simply exited, permanently disabling every
            # proactive ETS2 announcement — fuel/wear/rest/fines/etc — after
            # the very first engine start).
            print(f'[ETS2-MONITOR] tick error (monitor keeps running): {e}', flush=True)



def _save_session_snapshot() -> None:
    try:
        from .session_history import save_session
        save_session(_session_jobs, _session_revenue, _session_dist_km)
    except Exception:
        pass


def start() -> None:
    global _thread, _session_start, _session_jobs, _session_revenue, _session_dist_km, _prev_session
    if _thread and _thread.is_alive(): return
    _session_start = time.monotonic()
    _session_jobs = 0
    _session_revenue = 0
    _session_dist_km = 0.0
    try:
        from .session_history import load_last_session
        _prev_session = load_last_session()
    except Exception:
        _prev_session = None
    _stop_event.clear()
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="ets2_navigator")
    _thread.start()
def stop() -> None:
    _stop_event.set()
    if _session_jobs > 0:
        _save_session_snapshot()
