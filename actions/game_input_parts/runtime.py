import time
import threading
from actions import keysend
from actions.game_input_parts.profile import (
    _input,
    _flat,
    _entries,
    _last_cast,
    CAST_COOLDOWN,
    match_command,
    press_robust,
    get_command_list,
    get_loaded_profile_stem,
    get_binding,
)
_wiper_state: int = 0
_held_keys: dict[str, bool] = {}   # клавиши зажатые командой hold_start
def _switch_panel(target: int):
    press_robust(f'f{target}', duration=0.1)
    time.sleep(0.05)
def _execute_sequence(steps: list[dict]):
    for step in steps:
        if step.get('_disabled'):
            continue
        if 'wait' in step:
            time.sleep(step['wait'])
        elif 'key' in step:
            if 'hold' in step:
                keysend.key_down(step['key'])
                time.sleep(step['hold'])
                keysend.key_up(step['key'])
            else:
                press_robust(step['key'])
            time.sleep(0.05)
        elif 'keys' in step:
            ks = step['keys']
            keysend.key_down(ks[0])
            time.sleep(0.05)
            for k in ks[1:]:
                keysend.press(k)
                time.sleep(0.05)
            keysend.key_up(ks[0])
        elif step.get('mouse') == 'left':
            _input.click()
        elif step.get('mouse') == 'right':
            _input.rightClick()
def _speak_response(text: str):
    try:
        from core.speech import speak
        from core.speech.pacing import add_pauses
        speak(add_pauses(text))
    except Exception:
        pass


def _handle_telemetry_action(action: str):
    profile = get_loaded_profile_stem()
    if profile == 'farming_simulator_22':
        # FS22 has no live telemetry channel (see features/fs22/monitor.py's
        # module docstring) — only the real-time session report is available,
        # handled separately from the planetbase telemetry-dict path below.
        if action == 'session_report':
            try:
                from features.fs22.monitor import get_session_report
                _speak_response(get_session_report())
            except Exception:
                _speak_response("Ошибка получения отчёта по сессии.")
        return
    try:
        from features.planetbase import telemetry as pb_tel
        if profile != 'planetbase':
            return
        if action.startswith("build:"):
            from features.planetbase import commands as pb_cmd
            _speak_response(pb_cmd.build(action.split(":", 1)[1]))
            return
        from features.planetbase import extras as pb_extras
        extra_reply = pb_extras.handle(action)
        if extra_reply is not None:
            _speak_response(extra_reply)
            return
        if action.startswith("cmd:"):
            from features.planetbase import commands as pb_cmd
            _speak_response(pb_cmd.run(action.split(":", 1)[1]))
            return
        data = pb_tel.get()
        if not data.get("_valid"):
            _speak_response("Телеметрия недоступна. Убедитесь что игра запущена.")
            return

        if action == "full_status":
            colonists  = data.get("colonists", 0)
            modules    = data.get("module_count", 0)
            power_pct  = data.get("power_pct", 0)
            power_bal  = data.get("power_balance", 0)
            water_bal  = data.get("water_balance", 0)
            water_pct  = data.get("water_pct", 0)
            water_cap  = data.get("water_capacity", 0)
            oxy_cap    = data.get("oxygen_gen", 0)
            low_food   = data.get("low_food", False)
            any_d      = data.get("any_disaster", False)
            sandstorm  = data.get("sandstorm", False)
            solar      = data.get("solar_flare", False)
            blizzard   = data.get("blizzard", False)
            paused     = data.get("paused", False)

            # Энергия
            power_str = f"Энергия — {power_pct}%, баланс {power_bal:+d}."

            # Вода
            if water_cap > 0:
                water_str = f"Вода — {water_pct}%."
            else:
                water_str = f"Водный баланс — {float(water_bal):+.2f}."

            # Стихии
            if any_d:
                if sandstorm:   disaster_str = "Идёт песчаная буря."
                elif solar:     disaster_str = "Солнечная вспышка."
                elif blizzard:  disaster_str = "Идёт метель."
                else:           disaster_str = "Стихийное бедствие."
            else:
                disaster_str = "Стихийных бедствий нет."

            # Кислород
            if oxy_cap <= 0:
                oxy_str = "Генера́торы кислорода не работают."
            elif colonists > oxy_cap:
                oxy_str = f"Кислорода не хватает — генера́торы рассчитаны на {oxy_cap} человек."
            elif oxy_cap - colonists < 10:
                oxy_str = f"Кислород почти впритык — генера́торы рассчитаны на {oxy_cap} человек."
            else:
                oxy_str = f"Кислород в норме, генера́торы рассчитаны на {oxy_cap} человек."

            # Предупреждения
            warnings = []
            if low_food:   warnings.append("еда заканчивается")
            if paused:     warnings.append("игра на паузе")

            warn_str = f" Внимание: {', '.join(warnings)}." if warnings else ""

            _speak_response(
                f"В коло́нии {colonists} человек, {modules} модулей. "
                f"{power_str} {water_str} "
                f"{oxy_str} "
                f"{disaster_str}{warn_str}"
            )

        elif action == "colony_status":
            colonists = data.get("colonists", 0)
            modules = data.get("module_count", 0)
            power_pct = data.get("power_pct", 0)
            water_bal = data.get("water_balance", 0)
            food_str = " Продовольствие на исходе." if data.get("low_food") else ""
            _speak_response(
                f"Колони́стов {colonists}, модулей {modules}. "
                f"Энергия {power_pct}%, вода {water_bal}.{food_str}"
            )

        elif action == "power_status":
            bal = data.get("power_balance", 0)
            storage = data.get("power_storage", 0)
            capacity = data.get("power_capacity", 0)
            pct = data.get("power_pct", 0)
            if capacity > 0:
                _speak_response(f"Энергия: баланс {bal}, хранилище {pct}% — {storage} из {capacity}.")
            else:
                _speak_response(f"Энергетический баланс: {bal}. Хранилищ нет.")

        elif action == "water_status":
            bal = data.get("water_balance", 0)
            storage = data.get("water_storage", 0)
            capacity = data.get("water_capacity", 0)
            pct = data.get("water_pct", 0)
            if capacity > 0:
                _speak_response(f"Вода: баланс {bal}, хранилище {pct}% — {storage} из {capacity}.")
            else:
                _speak_response(f"Водный баланс: {bal}. Хранилищ нет.")

        elif action == "oxygen_status":
            oxy = data.get("oxygen_gen", 0)
            colonists = data.get("colonists", 0)
            if oxy <= 0:
                _speak_response("Генера́торы кислорода не производят ничего.")
            elif colonists > oxy:
                _speak_response(f"Кислорода не хватает! Генера́торы рассчитаны на {oxy} человек, а в коло́нии {colonists}.")
            elif oxy - colonists < 10:
                _speak_response(f"Кислорода почти впритык — генера́торы рассчитаны на {oxy} человек, в коло́нии {colonists}.")
            else:
                _speak_response(f"С кислородом всё в порядке — генера́торы рассчитаны на {oxy} человек, в коло́нии {colonists}.")

        elif action == "resources_status":
            veg     = data.get("res_vegetables", 0)
            meat    = data.get("res_meat", 0)
            meals   = data.get("res_meals", 0)
            starch  = data.get("res_starch", 0)
            metal   = data.get("res_metal", 0)
            ore     = data.get("res_ore", 0)
            bioplastic = data.get("res_bioplastic", 0)
            medical = data.get("res_medical", 0)

            food_total = veg + meat + meals
            food_str = f"Еды на складе {food_total} единиц." if food_total > 0 else "Еды на складе нет."

            med_str = (
                "Медикаме́нтов нет." if medical <= 0 else
                f"Медикаме́нтов осталось {medical}, это мало." if medical < 5 else
                f"Медикаме́нтов {medical}."
            )

            mat_str = f"Мета́лла {metal}, биопла́стика {bioplastic}, руды {ore}."

            _speak_response(f"{food_str} {mat_str} {med_str}")

        elif action == "colonist_status":
            colonists = data.get("colonists", 0)
            food_str = " Продовольствие заканчивается." if data.get("low_food") else ""
            _speak_response(f"В коло́нии {colonists} человек.{food_str}")

        elif action == "disaster_status":
            if not data.get("any_disaster"):
                _speak_response("Стихийных бедствий нет. Обстановка спокойная.")
            elif data.get("sandstorm"):
                _speak_response("Идёт песчаная буря!")
            elif data.get("solar_flare"):
                _speak_response("Солнечная вспышка!")
            elif data.get("blizzard"):
                _speak_response("Метель!")
            else:
                _speak_response("Внимание: стихийное бедствие!")

        elif action == "session_report":
            from features.planetbase.monitor import get_session_report
            _speak_response(get_session_report())

    except Exception:
        _speak_response("Ошибка получения телеметрии.")
def _is_lights_recommended(data: dict | None = None) -> bool:
    try:
        if data is None:
            from actions.ets2_telemetry import get_wipers, get_game_time
            if get_wipers():
                return True
            gt = get_game_time()
        else:
            if bool(data.get("wipers")):
                return True
            gt = data.get("time")
        if gt is not None:
            mins_in_day = gt % (24 * 60)
            hour = mins_in_day / 60
            if hour >= 18.5 or hour <= 7.5:
                return True
    except Exception:
        pass
    return False
def cast_command(text: str, fuzzy_threshold: float | None = None) -> tuple[bool, str, str | None]:
    """Returns (matched, entry_name, telemetry_action). telemetry_action lets callers
    avoid a second match_command() call just to check whether telemetry handling applies."""
    global _wiper_state
    if not _flat:
        return (False, '', None)
    thr = 0.75 if fuzzy_threshold is None else float(fuzzy_threshold)
    result = match_command(text, threshold=thr)
    if result is None:
        return (False, '', None)
    entry, score = result
    name = entry['name']
    telemetry_action = entry.get('telemetry_action')
    key = entry.get('key', '')
    keys = entry.get('keys')
    mouse = entry.get('mouse')
    target_set = entry.get('set')
    sequence = entry.get('sequence')
    response = entry.get('response')
    wiper_target = entry.get('wiper_target')
    lights_target = entry.get('lights_target')
    lights_target_raw = lights_target

    if name == "Код: красный (3) — боевая готовность" or name == "Макрос: Вторжение пиратов" or key == "3":
        try:
            from core.speech.sound import play_alert_sound
            play_alert_sound('red_alert')
        except Exception:
            pass

    # Common response handler (before we might return early)
    def _trigger_response():
        if response:
            threading.Thread(target=_speak_response, args=(response,), daemon=True).start()

    if wiper_target is not None or lights_target:
        now = time.time()
        if now - _last_cast.get(name, 0) < CAST_COOLDOWN:
            return (False, '', None)
        _last_cast[name] = now
        
        if sequence:
            _execute_sequence(sequence)
            sequence = None # Don't execute twice
            
        if wiper_target is not None:
            target = int(wiper_target)
            from actions.ets2_telemetry import get_wipers as _get_w_on
            w_on = _get_w_on()
            if w_on is False:
                _wiper_state = 0
            if target == 0:
                max_tries = 3
                while _get_w_on() is True and max_tries > 0:
                    press_robust(key if (key and key != 'MACRO') else 'p')
                    time.sleep(0.15)
                    max_tries -= 1
                _wiper_state = 0
            else:
                presses = (target - _wiper_state) % 4
                wiper_key = key if (key and key != 'MACRO') else 'p'
                for i in range(presses):
                    if i > 0:
                        time.sleep(0.12)
                    press_robust(wiper_key)
                _wiper_state = target
                
        if lights_target:
            if wiper_target is not None:
                time.sleep(0.2)
            from actions.ets2_telemetry import get_lights_parking, get_lights_low, get_lights_high
            p_on = get_lights_parking()
            l_on = get_lights_low()
            h_on = get_lights_high()
            if lights_target == 'low_adaptive':
                lights_target = 'low_on' if _is_lights_recommended() else 'off'
            if lights_target == 'low_on':
                if get_lights_low() is not True:
                    for _ in range(4):
                        press_robust('l')
                        time.sleep(0.14)
                        if get_lights_low() is True:
                            break
                        if get_lights_low() is None and _ > 1:
                            break
                if lights_target_raw == 'low_adaptive' and _is_lights_recommended():
                    time.sleep(0.18)
                    if get_lights_low() is True and get_lights_high() is not True:
                        press_robust('k')
            elif lights_target == 'parking_on':
                if not p_on:
                    press_robust('l')
                elif l_on:
                    press_robust('l')
                    time.sleep(0.1)
                    press_robust('l')
            elif lights_target == 'off':
                if l_on:
                    press_robust('l')
                elif p_on:
                    press_robust('l')
                    time.sleep(0.1)
                    press_robust('l')
            elif lights_target == 'high_on':
                if not h_on:
                    press_robust('k')
            elif lights_target == 'high_off':
                if h_on:
                    press_robust('k')
        
        _trigger_response()
        if not (key or keys or mouse or sequence) or key == 'MACRO':
            return (True, name, telemetry_action)

    binding_name = entry.get('binding')
    if binding_name and (not key or key == 'MACRO'):
        # Resolve from bindings with a reasonable default if possible
        # We don't have the defaults here, but get_binding handles 'MACRO' -> default
        key = get_binding(binding_name, key) # Keep 'MACRO' if no better

    has_keys = keys and len(keys) > 0
    has_key = key and key != 'MACRO'
    telemetry = telemetry_action

    if not has_key and not has_keys and not mouse and not sequence and not telemetry and not response and not binding_name:
        # If we already did wiper/lights, we returned above or continue here
        return (False, '', None) if not (wiper_target is not None or lights_target) else (True, name, telemetry_action)

    now = time.time()
    if now - _last_cast.get(name, 0) < CAST_COOLDOWN:
        return (False, '', None)
    _last_cast[name] = now
    
    try:
        if telemetry:
            threading.Thread(target=_handle_telemetry_action, args=(telemetry,), daemon=True).start()
            return (True, name, telemetry_action)

        hold_start = entry.get('hold_start')
        hold_end   = entry.get('hold_end')
        if hold_start:
            if not _held_keys.get(hold_start):
                keysend.key_down(hold_start)
                _held_keys[hold_start] = True
            _trigger_response()
            return (True, name, telemetry_action)
        if hold_end:
            if _held_keys.get(hold_end):
                keysend.key_up(hold_end)
                _held_keys[hold_end] = False
            _trigger_response()
            return (True, name, telemetry_action)

        if sequence:
            _execute_sequence(sequence)
            _trigger_response()
            return (True, name, telemetry_action)

        if target_set:
            _switch_panel(target_set)

        if mouse == 'left':
            _input.click()
        elif mouse == 'right':
            _input.rightClick()
        elif keys:
            keysend.key_down(keys[0])
            time.sleep(0.05)
            for k in keys[1:]:
                keysend.press(k)
                time.sleep(0.05)
            keysend.key_up(keys[0])
        elif has_key:
            press_robust(key)

        _trigger_response()
        return (True, name, telemetry_action)
    except Exception:
        return (False, '', None)
def execute_by_name(name: str) -> bool:
    entry = next((e for _, e, _, _ in _flat if e['name'] == name), None)
    if not entry:
        return False
    key = entry.get('key', '')
    keys = entry.get('keys')
    mouse = entry.get('mouse')
    target_set = entry.get('set')
    
    has_key = key and key != 'MACRO'
    if not has_key and (not keys) and (not mouse):
        return False
    now = time.time()
    if now - _last_cast.get(name, 0) < CAST_COOLDOWN:
        return False
    _last_cast[name] = now
    try:
        if target_set:
            _switch_panel(target_set)
        if mouse == 'left':
            _input.click()
        elif mouse == 'right':
            _input.rightClick()
        elif keys:
            keysend.key_down(keys[0])
            time.sleep(0.05)
            for k in keys[1:]:
                keysend.press(k)
                time.sleep(0.05)
            keysend.key_up(keys[0])
        elif has_key:
            press_robust(key)
        return True
    except Exception:
        return False
cast_spell = cast_command
get_spell_list = get_command_list
