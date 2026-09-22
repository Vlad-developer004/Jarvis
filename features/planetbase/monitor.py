"""Background monitor: голосовые уведомления по данным Planetbase telemetry."""

import logging
import random
import threading
import time

from features.planetbase import installer, telemetry
from features.gaming_common.real_break import RealBreakTracker
from features.planetbase.phrases_planetbase import (
    _INTROS,
    _phrases_power_low, _phrases_power_critical,
    _phrases_water_low, _phrases_water_critical, _phrases_water_deficit, _phrases_water_marginal,
    _phrases_oxygen_critical, _phrases_oxygen_low,
    _phrases_medical_critical, _phrases_medical_low,
    _phrases_materials_low, _phrases_food_low, _phrases_food_item_low,
    _phrases_sandstorm_start, _phrases_sandstorm, _phrases_solar_flare,
    _phrases_blizzard_start, _phrases_blizzard,
    _phrases_disaster_generic_start, _phrases_disaster_generic, _phrases_disaster_end,
    _phrases_arrival, _phrases_death, _phrases_milestone, _phrases_all_quiet,
)

_log = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_running = False

# ── Пороги ───────────────────────────────────────────────────
_POWER_LOW_PCT        = 20
_POWER_CRIT_PCT       = 10
_WATER_LOW_PCT        = 20
_WATER_CRIT_PCT       = 10
_WATER_BALANCE_MARGIN = 1.5
_OXYGEN_MARGIN        = 10
_MEDICAL_LOW          = 5
_MEDICAL_CRIT         = 1
_MATERIALS_LOW        = 10
_FOOD_ITEM_LOW         = 15
# Flat thresholds above under-warn a large colony (15 vegetables is nothing
# for 80 colonists) and over-warn a small one — scale the effective floor by
# headcount instead of using the flat constant alone.
_FOOD_PER_COLONIST     = 0.5
_MEDICAL_PER_COLONIST  = 0.1
# Real-world (not in-game) continuous-play reminder — resets whenever the
# player actually pauses, so it tracks real screen time, not game progress.
_REAL_BREAK_THRESHOLDS_MIN = [90, 150]

# ── Кулдауны (секунды) ───────────────────────────────────────
_COOLDOWN = {
    "power_critical":    60,
    "power_low":        120,
    "water_critical":    60,
    "water_low":        120,
    "water_deficit":    120,
    "water_marginal":   300,
    "oxygen_critical":   60,
    "oxygen_low":       180,
    "medical_critical":  60,
    "medical_low":      300,
    "materials_low":    300,
    "food_low":         180,
    "food_veg_low":     300,
    "food_meat_low":    300,
    "food_meals_low":   300,
    "disaster":          30,
    "disaster_end":      10,
    "all_quiet":       1800,
}

_COLONIST_MILESTONES = [25, 50, 100, 150, 200, 300, 500]

_last_announced:       dict = {}
_announced_milestones: set  = set()
_prev:                 dict = {}
_first_tick                 = True
_quiet_streak               = 0
_auto_alert_engaged         = False
_last_check_wall_ts: float  = 0.0
_break_tracker = RealBreakTracker(_REAL_BREAK_THRESHOLDS_MIN)
_peak_colonists              = 0
_disasters_survived          = 0
_session_start: float       = 0.0
_prev_pb_session: dict | None = None


def _focus_planetbase() -> bool:
    try:
        import pygetwindow as gw
        from core.system import force_foreground
        for w in gw.getAllWindows():
            title = (getattr(w, 'title', '') or '').lower()
            if 'planetbase' not in title:
                continue
            if getattr(w, 'isMinimized', False):
                try:
                    w.restore()
                except Exception:
                    pass
            if hasattr(w, '_hWnd'):
                force_foreground(int(w._hWnd))
            return True
    except Exception as e:
        _log.debug("Focus Planetbase error: %s", e)
    return False


def _press_key(key: str):
    try:
        from actions.game_input_parts.profile import press_robust
        _focus_planetbase()
        time.sleep(0.1)
        press_robust(key)
    except Exception as e:
        _log.debug("Key press error (%s): %s", key, e)


def _engage_yellow_alert():
    """Жёлтый код (2) — эвакуация колони́стов внутрь."""
    global _auto_alert_engaged
    _press_key("2")
    _auto_alert_engaged = True


def _disengage_alert():
    """Зелёный код (1) — отбой тревоги."""
    global _auto_alert_engaged
    _press_key("1")
    _auto_alert_engaged = False


def _cooldown_ok(key: str) -> bool:
    now = time.time()
    if now - _last_announced.get(key, 0) >= _COOLDOWN.get(key, 60):
        _last_announced[key] = now
        return True
    return False


def _speak(text: str):
    try:
        from core.speech.tts import speak
        speak(text)
    except Exception as e:
        _log.debug("TTS error: %s", e)


def _addr() -> str:
    try:
        from core.address import get_address
        return get_address()
    except Exception:
        return ""


def _alert(phrases: list[str], tone: str = "warn") -> None:
    """Произнести фразу с обращением и вступлением по тональности."""
    text  = random.choice(phrases)
    a     = _addr()
    intro = random.choice(_INTROS.get(tone, [""])).strip()

    # Первая буква фразы — строчная (продолжение после запятой/тире)
    body = text[0].lower() + text[1:] if text else text

    if a and intro:
        full = f"{a}, {intro} {body}"
    elif a:
        full = f"{a}, {body}"
    elif intro:
        full = f"{intro} {text}"
    else:
        full = text

    _speak(full)


# ── Основная проверка ─────────────────────────────────────────

def _minutes_to_empty(storage_now: float, storage_prev: float, wall_dt: float) -> float | None:
    """Estimates minutes-to-empty from the actually observed depletion rate
    between two ticks (real wall-clock seconds), instead of trusting the
    mod's power_balance/water_balance fields whose time unit isn't documented
    anywhere in this codebase — a wrong unit guess would give a confidently
    wrong ETA, which is worse than not giving one."""
    if wall_dt < 2.0 or wall_dt > 20.0:  # skip if the tick gap looks abnormal (lag/pause)
        return None
    rate_per_sec = (storage_now - storage_prev) / wall_dt
    if rate_per_sec >= 0 or storage_now <= 0:
        return None
    return storage_now / abs(rate_per_sec) / 60.0


def _check_real_break(paused: bool) -> None:
    threshold = _break_tracker.check(not paused)
    if threshold is None:
        return
    if threshold >= 150:
        _alert([
            "вы играете уже два с половиной часа подряд. Стоит встать, размяться и отдохнуть от экрана.",
            "два с половиной часа без перерыва — колония подождёт, а вот отдых лучше не откладывать.",
        ], tone="info")
    else:
        _alert([
            "вы играете полтора часа без перерыва. Хороший момент встать и размяться.",
            "полтора часа за игрой — небольшая пауза не помешает.",
        ], tone="info")


def _announce_disaster_start_fallback(sandstorm: bool, solar_flare: bool, blizzard: bool) -> None:
    if sandstorm:
        _alert(_phrases_sandstorm_start(), tone="alert")
    elif solar_flare:
        _alert(_phrases_solar_flare(), tone="alert")
    elif blizzard:
        _alert(_phrases_blizzard_start(), tone="alert")
    else:
        _alert(_phrases_disaster_generic_start(), tone="alert")


def _announce_disaster_start(data: dict, sandstorm: bool, solar_flare: bool, blizzard: bool) -> None:
    try:
        from .llm import has_llm_configured, build_disaster_prompt, ask_pb
        if has_llm_configured():
            kind = 'sandstorm' if sandstorm else 'solar_flare' if solar_flare else 'blizzard' if blizzard else 'generic'
            _snap = dict(data)
            def _llm_task():
                result = ask_pb(build_disaster_prompt(_snap, kind))
                if result:
                    _speak(result)
                else:
                    _announce_disaster_start_fallback(sandstorm, solar_flare, blizzard)
            threading.Thread(target=_llm_task, daemon=True).start()
            return
    except Exception:
        pass
    _announce_disaster_start_fallback(sandstorm, solar_flare, blizzard)


def _announce_milestone(data: dict, milestone: int) -> None:
    try:
        from .llm import has_llm_configured, build_milestone_prompt, ask_pb
        if has_llm_configured():
            _snap = dict(data)
            def _llm_task():
                result = ask_pb(build_milestone_prompt(_snap, milestone))
                _speak(result) if result else _alert(_phrases_milestone(milestone), tone="congrats")
            threading.Thread(target=_llm_task, daemon=True).start()
            return
    except Exception:
        pass
    _alert(_phrases_milestone(milestone), tone="congrats")


def _check(data: dict):
    global _prev, _first_tick, _quiet_streak, _last_check_wall_ts
    global _peak_colonists, _disasters_survived

    if not data.get("_valid"):
        _quiet_streak = 0
        return

    _check_real_break(bool(data.get("paused", False)))
    wall_now = time.time()
    wall_dt = wall_now - _last_check_wall_ts if _last_check_wall_ts > 0 else 0.0

    colonists   = data.get("colonists", 0)
    modules     = data.get("module_count", 0)
    power_pct   = data.get("power_pct", 100)
    water_pct   = data.get("water_pct", 100)
    water_bal   = float(data.get("water_balance", 0))
    water_cap   = float(data.get("water_capacity", 0))
    oxygen_cap  = data.get("oxygen_gen", 0)
    medical     = data.get("res_medical", 0)
    metal       = data.get("res_metal", 0)
    bioplastic  = data.get("res_bioplastic", 0)
    veg         = data.get("res_vegetables", 0)
    meat        = data.get("res_meat", 0)
    meals       = data.get("res_meals", 0)
    low_food    = data.get("low_food", False)
    any_d       = data.get("any_disaster", False)
    sandstorm   = data.get("sandstorm", False)
    solar_flare = data.get("solar_flare", False)
    blizzard    = data.get("blizzard", False)

    alert_fired = False

    # ── Энергия ─────────────────────────────────────────────
    if power_pct <= _POWER_CRIT_PCT and _cooldown_ok("power_critical"):
        _alert(_phrases_power_critical(power_pct), tone="critical")
        eta = _minutes_to_empty(float(data.get("power_storage", 0)), float(_prev.get("power_storage", 0)), wall_dt)
        if eta is not None:
            _speak(f"При текущем расходе энергии хватит примерно на {int(round(eta))} минут.")
        alert_fired = True
    elif power_pct <= _POWER_LOW_PCT and _cooldown_ok("power_low"):
        _alert(_phrases_power_low(power_pct), tone="warn")
        alert_fired = True

    # ── Вода ────────────────────────────────────────────────
    if water_cap > 0:
        if water_pct <= _WATER_CRIT_PCT and _cooldown_ok("water_critical"):
            _alert(_phrases_water_critical(water_pct), tone="critical")
            eta = _minutes_to_empty(float(data.get("water_storage", 0)), float(_prev.get("water_storage", 0)), wall_dt)
            if eta is not None:
                _speak(f"При текущем расходе воды хватит примерно на {int(round(eta))} минут.")
            alert_fired = True
        elif water_pct <= _WATER_LOW_PCT and _cooldown_ok("water_low"):
            _alert(_phrases_water_low(water_pct), tone="warn")
            alert_fired = True
        elif 0 < water_bal <= _WATER_BALANCE_MARGIN and _cooldown_ok("water_marginal"):
            _alert(_phrases_water_marginal(), tone="warn")
            alert_fired = True
    else:
        if water_bal < 0 and _cooldown_ok("water_deficit"):
            _alert(_phrases_water_deficit(), tone="warn")
            alert_fired = True
        elif 0 <= water_bal <= _WATER_BALANCE_MARGIN and _cooldown_ok("water_marginal"):
            _alert(_phrases_water_marginal(), tone="warn")
            alert_fired = True

    # ── Кислород ────────────────────────────────────────────
    if oxygen_cap > 0:
        if colonists > oxygen_cap and _cooldown_ok("oxygen_critical"):
            _alert(_phrases_oxygen_critical(colonists, oxygen_cap), tone="critical")
            alert_fired = True
        elif oxygen_cap - colonists < _OXYGEN_MARGIN and _cooldown_ok("oxygen_low"):
            _alert(_phrases_oxygen_low(colonists, oxygen_cap), tone="warn")
            alert_fired = True

    # ── Медикаме́нты ─────────────────────────────────────────
    # Flat _MEDICAL_LOW/_MEDICAL_CRIT under-warn a large colony — scale the
    # floor by headcount so "medical <= 5" doesn't stay silent at 80 colonists.
    medical_low_thr  = max(_MEDICAL_LOW, round(colonists * _MEDICAL_PER_COLONIST))
    medical_crit_thr = max(_MEDICAL_CRIT, round(colonists * _MEDICAL_PER_COLONIST * 0.3))
    if medical <= medical_crit_thr and _cooldown_ok("medical_critical"):
        _alert(_phrases_medical_critical(), tone="critical")
        alert_fired = True
    elif medical <= medical_low_thr and _cooldown_ok("medical_low"):
        _alert(_phrases_medical_low(medical), tone="warn")
        alert_fired = True

    # ── Стройматериалы ──────────────────────────────────────
    if metal <= _MATERIALS_LOW and bioplastic <= _MATERIALS_LOW and _cooldown_ok("materials_low"):
        _alert(_phrases_materials_low(), tone="warn")
        alert_fired = True

    # ── Еда ─────────────────────────────────────────────────
    if low_food and _cooldown_ok("food_low"):
        _alert(_phrases_food_low(), tone="warn")
        alert_fired = True

    food_item_thr = max(_FOOD_ITEM_LOW, round(colonists * _FOOD_PER_COLONIST))
    if veg <= food_item_thr and _cooldown_ok("food_veg_low"):
        _alert(_phrases_food_item_low("Овощей", veg), tone="warn")
        alert_fired = True
    if meat <= food_item_thr and _cooldown_ok("food_meat_low"):
        _alert(_phrases_food_item_low("Мяса", meat), tone="warn")
        alert_fired = True
    if meals <= food_item_thr and _cooldown_ok("food_meals_low"):
        _alert(_phrases_food_item_low("Готовых блюд", meals), tone="warn")
        alert_fired = True

    # ── Катастрофы ──────────────────────────────────────────
    prev_any_d = _prev.get("any_disaster", False)
    is_weather_hazard = sandstorm or blizzard or (any_d and not solar_flare)

    if any_d and not prev_any_d:
        if is_weather_hazard:
            _engage_yellow_alert()
        _announce_disaster_start(data, sandstorm, solar_flare, blizzard)
        alert_fired = True
    elif any_d and _cooldown_ok("disaster"):
        if sandstorm:
            _alert(_phrases_sandstorm(), tone="alert")
        elif solar_flare:
            _alert(_phrases_solar_flare(), tone="alert")
        elif blizzard:
            _alert(_phrases_blizzard(), tone="alert")
        else:
            _alert(_phrases_disaster_generic(), tone="alert")
        alert_fired = True
    elif not any_d and prev_any_d:
        _disengage_alert()
        _disasters_survived += 1
        _save_pb_session_snapshot()
        if _cooldown_ok("disaster_end"):
            _alert(_phrases_disaster_end(), tone="good")
        alert_fired = True

    # ── Колони́сты ───────────────────────────────────────────
    prev_col = _prev.get("colonists", colonists)
    if colonists > _peak_colonists:
        _peak_colonists = colonists

    if not _first_tick:
        if colonists > prev_col:
            arrived = colonists - prev_col
            _alert(_phrases_arrival(arrived), tone="good")

        elif colonists < prev_col and prev_col > 0:
            lost = prev_col - colonists
            _alert(_phrases_death(lost), tone="warn")
            alert_fired = True

        for milestone in _COLONIST_MILESTONES:
            if prev_col < milestone <= colonists and milestone not in _announced_milestones:
                _announced_milestones.add(milestone)
                _announce_milestone(data, milestone)
                break

    # ── "Всё спокойно" ──────────────────────────────────────
    if not alert_fired and not any_d and colonists > 0:
        _quiet_streak += 1
    else:
        _quiet_streak = 0

    if _quiet_streak >= 6 and _cooldown_ok("all_quiet"):
        _alert(_phrases_all_quiet(colonists, modules), tone="info")

    _first_tick = False
    _prev = dict(data)
    _last_check_wall_ts = wall_now


def _monitor_loop():
    while _running:
        try:
            data = telemetry.get()
            _check(data)
        except Exception as e:
            _log.debug("Monitor error: %s", e)
        time.sleep(5)


def get_session_report() -> str:
    elapsed_min = (time.time() - _session_start) / 60.0 if _session_start > 0 else 0.0
    parts = [f"Текущая сессия идёт {int(elapsed_min)} минут. Пик населения — {_peak_colonists} колони́стов."]
    if _disasters_survived > 0:
        parts.append(f"Пережито катастроф: {_disasters_survived}.")
    if _prev_pb_session:
        prev_peak = int(_prev_pb_session.get('peak_colonists', 0))
        if prev_peak > 0:
            if _peak_colonists > prev_peak:
                parts.append(f"Это больше, чем рекорд прошлой сессии — {prev_peak} колони́стов.")
            elif _peak_colonists < prev_peak:
                parts.append(f"В прошлой сессии пик был выше — {prev_peak} колони́стов.")
            else:
                parts.append("Ровно как в прошлой сессии.")
    text = " ".join(parts)
    a = _addr()
    return f"{a}, {text[0].lower()}{text[1:]}" if a else text


def _save_pb_session_snapshot() -> None:
    try:
        from .session_history import save_session
        elapsed_min = (time.time() - _session_start) / 60.0 if _session_start > 0 else 0.0
        save_session(_peak_colonists, _disasters_survived, elapsed_min)
    except Exception:
        pass


def start():
    global _thread, _running, _first_tick, _prev, _last_announced, _announced_milestones, _quiet_streak, _auto_alert_engaged
    global _peak_colonists, _disasters_survived, _session_start, _prev_pb_session, _break_tracker

    if not installer.ensure_installed():
        _log.warning("Planetbase mod not installed — monitor running without telemetry")

    telemetry.start()

    if _thread and _thread.is_alive():
        return

    _first_tick           = True
    _prev                 = {}
    _last_announced       = {}
    _announced_milestones = set()
    _quiet_streak         = 0
    _auto_alert_engaged   = False
    _peak_colonists        = 0
    _disasters_survived    = 0
    _session_start         = time.time()
    _break_tracker         = RealBreakTracker(_REAL_BREAK_THRESHOLDS_MIN)
    try:
        from .session_history import load_last_session
        _prev_pb_session = load_last_session()
    except Exception:
        _prev_pb_session = None

    _running = True
    _thread  = threading.Thread(target=_monitor_loop, daemon=True, name="PBMonitor")
    _thread.start()
    _log.info("Planetbase monitor started")


def stop():
    global _running
    _running = False
    if _peak_colonists > 0:
        _save_pb_session_snapshot()
    telemetry.stop()
