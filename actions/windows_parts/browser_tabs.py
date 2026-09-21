import time
import win32gui
import win32con
from actions import keysend
from core.system import force_foreground

_BROWSERS = ('google chrome', 'yandex', 'яндекс', 'edge', 'firefox', 'opera', 'brave')

# VK codes
_VK_CTRL  = 0x11
_VK_SHIFT = 0x10
_VK_T     = 0x54
_VK_W     = 0x57
_VK_TAB   = 0x09

def _key_down(vk): keysend.key_down(vk)
def _key_up(vk):   keysend.key_up(vk)

def _send_ctrl(vk):
    _key_down(_VK_CTRL)
    time.sleep(0.03)
    _key_down(vk)
    time.sleep(0.03)
    _key_up(vk)
    time.sleep(0.03)
    _key_up(_VK_CTRL)

def _send_ctrl_shift(vk):
    _key_down(_VK_CTRL)
    _key_down(_VK_SHIFT)
    time.sleep(0.03)
    _key_down(vk)
    time.sleep(0.03)
    _key_up(vk)
    time.sleep(0.03)
    _key_up(_VK_SHIFT)
    _key_up(_VK_CTRL)

def _find_browser_hwnd() -> int:
    target = [0]
    def _cb(hwnd, _):
        if target[0]: return
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if title and any(b in title for b in _BROWSERS):
                target[0] = hwnd
    win32gui.EnumWindows(_cb, None)
    return target[0]

def _activate_browser() -> int:
    """Activate browser window. Returns hwnd on success, 0 on failure."""
    hwnd = _find_browser_hwnd()
    if not hwnd:
        return 0
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.15)
    force_foreground(hwnd)
    time.sleep(0.3)
    return hwnd

def close_tab() -> tuple[bool, str]:
    try:
        if not _activate_browser():
            return False, 'Браузер не найден'
        _send_ctrl(_VK_W)
        return True, 'Вкладка закрыта'
    except Exception as e:
        return False, str(e)

def close_tab_by_index(index: int) -> tuple[bool, str]:
    try:
        if not isinstance(index, int) or index < 1:
            return False, 'Некорректный номер вкладки'
        ok, msg = goto_tab(index)
        if not ok:
            return False, msg
        time.sleep(0.1)
        _send_ctrl(_VK_W)
        return True, f'Вкладка {index} закрыта'
    except Exception as e:
        return False, str(e)

def open_new_tab() -> tuple[bool, str]:
    try:
        if not _activate_browser():
            return False, 'Браузер не найден'
        _send_ctrl(_VK_T)
        return True, 'Новая вкладка открыта'
    except Exception as e:
        return False, str(e)

def goto_tab(index: int) -> tuple[bool, str]:
    try:
        if not _activate_browser():
            return False, 'Браузер не найден'
        if not isinstance(index, int) or index < 1:
            return False, 'Некорректный номер вкладки'
        # Ctrl+1..8 → exact tab; for index >= 9 use Ctrl+1 then Ctrl+Tab repeats
        if index <= 8:
            vk = 0x31 + (index - 1)  # '1'..'8'
            _send_ctrl(vk)
        else:
            _send_ctrl(0x31)  # Ctrl+1
            for _ in range(index - 1):
                time.sleep(0.04)
                _send_ctrl(_VK_TAB)
        return True, f'Перешли на вкладку {index}'
    except Exception as e:
        return False, str(e)

def close_all_tabs() -> tuple[bool, str]:
    try:
        if not _activate_browser():
            return False, 'Браузер не найден'
        _send_ctrl_shift(_VK_W)
        return True, 'Все вкладки закрыты'
    except Exception as e:
        return False, str(e)
