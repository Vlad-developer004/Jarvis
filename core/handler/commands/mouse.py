import pyautogui
import threading
import time
from core.system import app_state
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('mouse')
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
                _log.error(f"[MOUSE_LOOP] Error: {e}")
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
_MOUSE_DIRECTIONS = {
    'mouse_right': (1, 0),
    'mouse_left': (-1, 0),
    'mouse_up': (0, -1),
    'mouse_down': (0, 1),
}

def _mouse_faster(handler, text_lower, amount):
    app_state.mouse_speed *= 1.5
    handler.speak(spk('mouse.faster_v2', mult=f'{app_state.mouse_speed:.1f}'))

def _mouse_slower(handler, text_lower, amount):
    app_state.mouse_speed = max(0.1, app_state.mouse_speed / 1.5)
    handler.speak(spk('mouse.slower_v2', mult=f'{app_state.mouse_speed:.1f}'))

def _mouse_click(handler, text_lower, amount):
    pyautogui.click()
    handler.play_response()

def _mouse_dblclick(handler, text_lower, amount):
    pyautogui.doubleClick()
    handler.play_response()

_MOUSE_ACTIONS = {
    'mouse_faster': _mouse_faster,
    'mouse_slower': _mouse_slower,
    'mouse_click': _mouse_click,
    'mouse_dblclick': _mouse_dblclick,
}

def handle_mouse(handler, cmd, text_lower, amount):
    _ensure_mouse_loop_started()
    direction = _MOUSE_DIRECTIONS.get(cmd)
    if direction is not None:
        app_state.mouse_dx, app_state.mouse_dy = direction
        app_state.mouse_moving = True
        handler.play_response()
        return
    action = _MOUSE_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, amount)
