import pyautogui
import time
import threading
MOUSE_STEP = 5
MOUSE_INTERVAL = 0.05
_mouse_moving = False
_mouse_direction = None
def change_mouse_speed(direction: str):
    global MOUSE_STEP
    if direction == 'faster':
        MOUSE_STEP = min(30, MOUSE_STEP + 5)
    elif direction == 'slower':
        MOUSE_STEP = max(2, MOUSE_STEP - 5)
    return (True, 'OK')
def _mouse_loop():
    global _mouse_moving
    screen_w, screen_h = pyautogui.size()
    while _mouse_moving:
        dx, dy = (0, 0)
        scroll_key = None
        if _mouse_direction == 'right':
            dx = MOUSE_STEP
        elif _mouse_direction == 'left':
            dx = -MOUSE_STEP
        elif _mouse_direction == 'up':
            dy = -MOUSE_STEP
            scroll_key = 'up'
        elif _mouse_direction == 'down':
            dy = MOUSE_STEP
            scroll_key = 'down'
        current_x, current_y = pyautogui.position()
        hit_top = current_y <= 100 and _mouse_direction == 'up'
        hit_bottom = current_y >= screen_h - 100 and _mouse_direction == 'down'
        if hit_top or hit_bottom:
            pyautogui.press(scroll_key)
            time.sleep(MOUSE_INTERVAL * 3)
        else:
            pyautogui.moveRel(dx, dy)
            time.sleep(MOUSE_INTERVAL)
def move_mouse(direction: str, steps: int=1):
    global _mouse_moving, _mouse_direction
    _mouse_direction = direction
    if not _mouse_moving:
        _mouse_moving = True
        t = threading.Thread(target=_mouse_loop, daemon=True)
        t.start()
    return (True, 'OK')
def stop_mouse() -> bool:
    global _mouse_moving
    if _mouse_moving:
        _mouse_moving = False
        return True
    return False
def mouse_click():
    stop_mouse()
    time.sleep(0.05)
    pyautogui.click()
    return (True, 'OK')
def mouse_double_click():
    stop_mouse()
    time.sleep(0.05)
    pyautogui.doubleClick()
    return (True, 'OK')
