import time
from actions.game_input_parts.profile import _input, get_binding
def cruise_set_speed(target_kmh: int, current_kmh: float) -> tuple[bool, int]:
    current_snapped = round(current_kmh / 5.0) * 5.0
    target_snapped = round(target_kmh / 5.0) * 5.0
    diff = int(target_snapped - current_snapped)
    presses = abs(diff) // 5
    if presses == 0:
        return (True, int(target_snapped))
    key_name = 'cruise_up' if diff > 0 else 'cruise_down'
    key = get_binding(key_name, 'add' if diff > 0 else 'subtract')
    try:
        import pydirectinput as _pdi
        _pdi.PAUSE = 0
        for i in range(presses):
            _pdi.press(key)
            if presses > 1:
                time.sleep(0.07)
        return (True, int(target_snapped))
    except Exception:
        return (False, int(target_snapped))
def set_gear(target: int, current: int) -> tuple[bool, int]:
    if target < -1:
        target = -1
    if target > 18:
        target = 18
    if current < -1:
        current = -1
    if current > 18:
        current = 18
    if target == current:
        return (True, target)
    up_key = get_binding('gear_up', 'shift')
    down_key = get_binding('gear_down', 'ctrl')
    steps = abs(target - current)
    if steps > 25:
        return (False, current)
    key = up_key if target > current else down_key
    try:
        for _ in range(steps):
            _input.press(key)
            time.sleep(0.06)
        return (True, target)
    except Exception:
        return (False, current)
