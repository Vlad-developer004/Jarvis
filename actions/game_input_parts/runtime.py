import time
import threading
from actions.game_input_parts.profile import (
    _input,
    _flat,
    _entries,
    _last_cast,
    CAST_COOLDOWN,
    match_command,
    press_robust,
)
_wiper_state: int = 0
def _switch_panel(target: int):
    press_robust(f'f{target}', duration=0.1)
    time.sleep(0.05)
def _execute_sequence(steps: list[dict]):
    for step in steps:
        if 'wait' in step:
            time.sleep(step['wait'])
        elif 'key' in step:
            if 'hold' in step:
                _input.keyDown(step['key'])
                time.sleep(step['hold'])
                _input.keyUp(step['key'])
            else:
                press_robust(step['key'])
            time.sleep(0.05)
        elif 'keys' in step:
            ks = step['keys']
            _input.keyDown(ks[0])
            time.sleep(0.05)
            for k in ks[1:]:
                _input.press(k)
                time.sleep(0.05)
            _input.keyUp(ks[0])
        elif step.get('mouse') == 'left':
            _input.click()
        elif step.get('mouse') == 'right':
            _input.rightClick()
def _speak_response(text: str):
    try:
        from core.speech import speak
        speak(text)
    except Exception:
        pass
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
def cast_command(text: str, fuzzy_threshold: float | None = None) -> tuple[bool, str]:
    global _wiper_state
    if not _flat:
        return (False, '')
    thr = 0.75 if fuzzy_threshold is None else float(fuzzy_threshold)
    result = match_command(text, threshold=thr)
    if result is None:
        return (False, '')
    entry, score = result
    name = entry['name']
    key = entry.get('key', '')
    keys = entry.get('keys')
    mouse = entry.get('mouse')
    target_set = entry.get('set')
    sequence = entry.get('sequence')
    response = entry.get('response')
    wiper_target = entry.get('wiper_target')
    lights_target = entry.get('lights_target')
    lights_target_raw = lights_target
    if wiper_target is not None or lights_target:
        now = time.time()
        if now - _last_cast.get(name, 0) < CAST_COOLDOWN:
            return (False, '')
        _last_cast[name] = now
        if sequence:
            _execute_sequence(sequence)
            sequence = None
        if wiper_target is not None:
            target = int(wiper_target)
            from actions.ets2_telemetry import get_wipers as _get_w_on
            w_on = _get_w_on()
            if w_on is False:
                _wiper_state = 0
            if target == 0:
                max_tries = 3
                while _get_w_on() is True and max_tries > 0:
                    press_robust(key or 'p')
                    time.sleep(0.15)
                    max_tries -= 1
                _wiper_state = 0
            else:
                presses = (target - _wiper_state) % 4
                wiper_key = key or 'p'
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
        if response:
            threading.Thread(target=_speak_response, args=(response,), daemon=True).start()
        if not (key or keys or mouse or sequence):
            return (True, name)
    if not key and (not keys) and (not mouse) and (not sequence):
        return (False, '')
    now = time.time()
    if now - _last_cast.get(name, 0) < CAST_COOLDOWN:
        return (False, '')
    _last_cast[name] = now
    try:
        if sequence:
            _execute_sequence(sequence)
            if response:
                threading.Thread(target=_speak_response, args=(response,), daemon=True).start()
            return (True, name)
        if target_set:
            _switch_panel(target_set)
        if mouse == 'left':
            _input.click()
        elif mouse == 'right':
            _input.rightClick()
        elif keys:
            _input.keyDown(keys[0])
            time.sleep(0.05)
            for k in keys[1:]:
                _input.press(k)
                time.sleep(0.05)
            _input.keyUp(keys[0])
        else:
            press_robust(key)
        return (True, name)
    except Exception:
        return (False, '')
def execute_by_name(name: str) -> bool:
    entry = next((e for _, e in _flat if e['name'] == name), None)
    if not entry:
        return False
    key = entry.get('key', '')
    keys = entry.get('keys')
    mouse = entry.get('mouse')
    target_set = entry.get('set')
    if not key and (not keys) and (not mouse):
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
            _input.keyDown(keys[0])
            time.sleep(0.05)
            for k in keys[1:]:
                _input.press(k)
                time.sleep(0.05)
            _input.keyUp(keys[0])
        else:
            press_robust(key)
        return True
    except Exception:
        return False
cast_spell = cast_command
