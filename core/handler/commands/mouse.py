import pyautogui
import threading
import time
from core.system import app_state
BASE_TICK_STEP = 5
_loop_started = False
_loop_lock = threading.Lock()
def _mouse_loop():
    while True:
        if app_state.mouse_moving:
            try:
                dx = app_state.mouse_dx * BASE_TICK_STEP * app_state.mouse_speed
                dy = app_state.mouse_dy * BASE_TICK_STEP * app_state.mouse_speed
                if dx != 0 or dy != 0:
                    pyautogui.moveRel(dx, dy, _pause=False)
            except Exception as e:
                print(f"[MOUSE_LOOP] Error: {e}")
            time.sleep(0.02)
            continue
        time.sleep(0.10)
def _ensure_mouse_loop_started():
    global _loop_started
    if _loop_started:
        return
    with _loop_lock:
        if _loop_started:
            return
        threading.Thread(target=_mouse_loop, name="MouseMovementLoop", daemon=True).start()
        _loop_started = True
def handle_mouse(handler, cmd, text_lower, amount):
    _ensure_mouse_loop_started()
    if cmd == 'mouse_faster':
        app_state.mouse_speed *= 1.5
        handler.speak(f"Ускоряю. Множитель: {app_state.mouse_speed:.1f}")
        return
    elif cmd == 'mouse_slower':
        app_state.mouse_speed = max(0.1, app_state.mouse_speed / 1.5)
        handler.speak(f"Замедляю. Множитель: {app_state.mouse_speed:.1f}")
        return
    dx, dy = 0, 0
    if cmd == 'mouse_right': dx = 1
    elif cmd == 'mouse_left': dx = -1
    elif cmd == 'mouse_up': dy = -1
    elif cmd == 'mouse_down': dy = 1
    if dx != 0 or dy != 0:
        app_state.mouse_dx = dx
        app_state.mouse_dy = dy
        app_state.mouse_moving = True
        handler.play_response()
        return
    if cmd == 'mouse_click':
        pyautogui.click()
        handler.play_response()
    elif cmd == 'mouse_dblclick':
        pyautogui.doubleClick()
        handler.play_response()
