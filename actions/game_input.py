from actions.game_input_parts.profile import *
from actions.game_input_parts.driving import *
from actions.game_input_parts.runtime import *
get_spell_list = get_command_list
import json
import re
import time
import threading
from pathlib import Path
try:
    import pydirectinput as _input
    _input.PAUSE = 0
except ImportError:
    import pyautogui as _input
PROFILES_DIR = Path('data') / 'game_profiles'
_profile_name: str = ''
_entries: list[dict] = []
_flat: list[tuple[str, dict]] = []
_bindings: dict = {}
_last_cast: dict[str, float] = {}
def get_binding(name: str, default: str = '') -> str:
    return _bindings.get(name, default)
def cruise_set_speed(target_kmh: int, current_kmh: float) -> tuple[bool, int]:
    from actions.ets2_telemetry import get_cruise_active
    active = get_cruise_active()
    
    if active is False:
        press_robust(get_binding('cruise', 'c'))
        time.sleep(0.1)

    current_snapped = round(current_kmh / 5.0) * 5.0
    target_snapped  = round(target_kmh  / 5.0) * 5.0
    diff    = int(target_snapped - current_snapped)
    presses = abs(diff) // 5

    if presses == 0:
        return (True, int(target_snapped))

    key_name = 'cruise_up' if diff > 0 else 'cruise_down'
    key = get_binding(key_name, 'add' if diff > 0 else 'subtract')
    try:
        for i in range(presses):
            press_robust(key)
            if presses > 1:
                time.sleep(0.04)
        return (True, int(target_snapped))
    except Exception:
        return (False, int(target_snapped))
def set_gear(target: int, current: int) -> tuple[bool, int]:
    if target < -1: target = -1
    if target > 18: target = 18
    if current < -1: current = -1
    if current > 18: current = 18
    if target == current: return (True, target)

    up_key = get_binding('gear_up', 'shift')
    down_key = get_binding('gear_down', 'ctrl')
    
    try:
        steps = abs(target - current)
        if steps > 25: return (False, current)
        
        is_up = target > current
        key = up_key if is_up else down_key
        
        c = current
        for _ in range(steps):
            # Special pause if crossing Neutral (0)
            next_g = c + 1 if is_up else c - 1
            if next_g == 0 or c == 0:
                time.sleep(0.15)
                
            press_robust(key, duration=0.12)
            c = next_g
            time.sleep(0.1)
            
        return (True, target)
    except Exception:
        return (False, current)
CAST_COOLDOWN = 1.0
_wiper_state: int = 0
def _telem_wiper_state() -> int | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return 1 if data.get("wipers") else 0
    except Exception:
        return None
def _telem_lights_low() -> bool | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return bool(data.get("lightsBeamLow"))
    except Exception:
        return None
def _telem_lights_high() -> bool | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return bool(data.get("lightsBeamHigh"))
    except Exception:
        return None
def _installed_profile_stems() -> set[str]:
    try:
        from core.extensions import ExtensionManager
        ext = ExtensionManager()
        installed_stems: set[str] = set()
        for e in ext.list_installed():
            fname = e.get('file', '')
            if fname.endswith('.json'):
                installed_stems.add(fname[:-5])
        return installed_stems
    except Exception:
        return {p.stem for p in PROFILES_DIR.glob('*.json')}
def get_available_profiles() -> list[str]:
    installed = _installed_profile_stems()
    return [p.stem for p in PROFILES_DIR.glob('*.json') if p.stem in installed]
def _strip_json_comments(text: str) -> str:
    pattern = r'(?x) "(?:\\.|[^"\\])*" | (?://[^\n]*) | (/\*.*?\*/)'
    def _replacer(match):
        s = match.group(0)
        if s.startswith('"'):
            return s
        return ""
    return re.sub(pattern, _replacer, text, flags=re.DOTALL)
def load_profile(profile_name: str) -> tuple[bool, str]:
    global _profile_name, _entries, _flat, _bindings
    if profile_name not in _installed_profile_stems():
        return (False, f"Расширение для профиля '{profile_name}' не установлено. Откройте Менеджер расширений в HUD и установите нужный профиль.")
    path = PROFILES_DIR / f'{profile_name}.json'
    if not path.exists():
        available = get_available_profiles()
        return (False, f"Профиль '{profile_name}' не найден. Доступны: {', '.join(available)}")
    try:
        raw_text = path.read_text(encoding='utf-8')
        clean_text = _strip_json_comments(raw_text)
        data = json.loads(clean_text)
        bindings: dict = data.get('bindings', {})
        _bindings = dict(bindings)
        _entries = data.get('spells', [])
        def _resolve(entry: dict) -> dict:
            e = dict(entry)
            if 'binding' in e and (not e.get('key')) and (not e.get('keys')):
                e['key'] = bindings.get(e['binding'], '')
            if 'sequence' in e:
                resolved_seq = []
                for step in e['sequence']:
                    s = dict(step)
                    if 'binding' in s and (not s.get('key')) and (not s.get('keys')):
                        s['key'] = bindings.get(s['binding'], '')
                    resolved_seq.append(s)
                e['sequence'] = resolved_seq
            return e
        _flat = []
        skipped = 0
        for raw_entry in _entries:
            entry = _resolve(raw_entry)
            has_action = (entry.get('key') or entry.get('keys') or entry.get('mouse') or
                          entry.get('sequence') or entry.get('lights_target') or
                          entry.get('wiper_target') or entry.get('response'))
            if not has_action:
                skipped += 1
                continue
            for variant in entry.get('variants', [entry['name']]):
                _flat.append((variant.lower().strip(), entry))
        _flat.sort(key=lambda x: len(x[0]), reverse=True)
        _profile_name = data.get('game', profile_name)
        return (True, _profile_name)
    except Exception as e:
        return (False, f'Ошибка загрузки профиля: {e}')
def unload_profile():
    global _profile_name, _entries, _flat, _bindings
    _profile_name = ''
    _entries = []
    _flat = []
    _bindings = {}
def match_command(text: str, threshold: float=0.75) -> tuple[dict, float] | None:
    if not _flat:
        return None
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None
    text_lower = text.lower().strip()
    if not text_lower:
        return None
    text_nospace = text_lower.replace(' ', '')
    for variant, entry in _flat:
        if text_lower == variant:
            return (entry, 1.0)
        if variant in text_lower and len(variant) > 4:
            return (entry, 1.0)
        variant_nospace = variant.replace(' ', '')
        if text_nospace == variant_nospace and len(variant_nospace) > 5:
            return (entry, 0.95)
        if len(variant_nospace) > 6 and variant_nospace in text_nospace:
            return (entry, 0.9)
    best_score = 0.0
    best_entry = None
    if _fuzz:
        for variant, entry in _flat:
            ratio        = _fuzz.ratio(text_lower, variant) / 100.0
            partial      = _fuzz.partial_ratio(text_lower, variant) / 100.0
            token_set    = _fuzz.token_set_ratio(text_lower, variant) / 100.0
            score = (ratio + partial + token_set) / 3.0
            if score > best_score:
                best_score = score
                best_entry = entry
    else:
        for variant, entry in _flat:
            if variant in text_lower or text_lower in variant:
                score = min(len(variant), len(text_lower)) / max(len(variant), len(text_lower))
                if score > best_score:
                    best_score = score
                    best_entry = entry
    if best_entry and best_score >= threshold:
        return (best_entry, best_score)
    return None
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
    except Exception as e:
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
                    if i > 0: time.sleep(0.12)
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
    except Exception as e:
        return (False, '')
def get_command_list() -> str:
    if not _entries:
        return 'Профиль не загружен.'
    active = [e['name'] for e in _entries if e.get('key') or e.get('keys') or e.get('sequence')]
    return f'Доступно {len(active)} команд: {', '.join(active[:8])}{('...' if len(active) > 8 else '')}.'
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
    except Exception as e:
        return False
def get_hotwords() -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for variant, _ in _flat:
        if variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result
cast_spell = cast_command
get_spell_list = get_command_list
