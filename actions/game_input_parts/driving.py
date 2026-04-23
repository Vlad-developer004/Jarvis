import time
from actions.game_input_parts.profile import _input, get_binding, press_robust

def cruise_set_speed(target_kmh: int, current_kmh: float, auto_mode: bool = False) -> tuple[bool, int]:
    from actions.ets2_telemetry import get_cruise_active, get_cruise_speed_kmh
    active = get_cruise_active()
    
    if active is False:
        # If auto_mode, only engage if speed is sufficient
        if auto_mode and current_kmh < 30.0:
            return (False, 0)
        
        # Enable cruise
        press_robust(get_binding('cruise', 'c'))
        time.sleep(0.12)
        # Refresh state
        active = get_cruise_active()

    # Use actual cruise speed from telemetry if available, otherwise fallback to current speed
    telem_cruise = get_cruise_speed_kmh()
    base_speed = telem_cruise if telem_cruise and telem_cruise > 0 else current_kmh
    
    current_snapped = round(base_speed / 5.0) * 5.0
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
            press_robust(key)
            if presses > 1:
                time.sleep(0.1)  # Slightly slower for better registration
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
        import pydirectinput as _pdi
        _pdi.PAUSE = 0
        for i in range(steps):
            # Final step to N or R gets extra careful treatment
            is_final_critical = (i == steps - 1) and (target <= 0)
            
            if is_final_critical:
                press_robust(key, duration=0.2)
            else:
                press_robust(key)
                
            if steps > 1:
                time.sleep(0.12 if is_final_critical else 0.1)
        return (True, target)
    except Exception:
        return (False, current)
