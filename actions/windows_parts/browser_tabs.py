import time
import ctypes
import win32gui
import win32con
import pygetwindow as gw
from core.system import force_foreground
def close_tab() -> tuple[bool, str]:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (False, 'Нет активного окна')
        force_foreground(hwnd)
        time.sleep(0.3)
        user32 = ctypes.windll.user32
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(87, 0, 0, 0)
        time.sleep(0.3)
        user32.keybd_event(87, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        return (True, 'Вкладка закрыта')
    except Exception as e:
        return (False, str(e))
def close_tab_by_index(index: int) -> tuple[bool, str]:
    try:
        _activate_browser()
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (False, 'Нет активного окна')
        force_foreground(hwnd)
        time.sleep(0.3)
        user32 = ctypes.windll.user32
        if isinstance(index, int) and 1 <= index <= 9:
            vk_code = 48 + index
            user32.keybd_event(17, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.3)
            user32.keybd_event(vk_code, 0, 2, 0)
            user32.keybd_event(17, 0, 2, 0)
            time.sleep(0.15)
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(87, 0, 0, 0)
        time.sleep(0.3)
        user32.keybd_event(87, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        return (True, f'Вкладка {index} закрыта')
    except Exception as e:
        return (False, str(e))
def _activate_browser():
    try:
        browsers = ('google chrome', 'yandex', 'яндекс', 'edge', 'firefox', 'opera', 'brave')
        target_hwnd = [0]
        
        def enum_cb(hwnd, _):
            if target_hwnd[0]: return
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if title and any(b in title for b in browsers):
                    target_hwnd[0] = hwnd
                    
        win32gui.EnumWindows(enum_cb, None)
        
        if target_hwnd[0]:
            hwnd = target_hwnd[0]
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            print(f"[_activate_browser] activating hwnd: {hwnd}", flush=True)
            force_foreground(hwnd)
        time.sleep(0.2)
        return True
    except Exception:
        pass
    return False
def open_new_tab() -> tuple[bool, str]:
    try:
        _activate_browser()
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (False, 'Нет активного окна')
        force_foreground(hwnd)
        time.sleep(0.3)
        user32 = ctypes.windll.user32
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(84, 0, 0, 0)
        time.sleep(0.3)
        user32.keybd_event(84, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        return (True, 'Новая вкладка открыта')
    except Exception as e:
        return (False, str(e))
def goto_tab(index: int) -> tuple[bool, str]:
    try:
        _activate_browser()
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (False, 'Нет активного окна')
        force_foreground(hwnd)
        time.sleep(0.3)
        if isinstance(index, int) and 1 <= index <= 9:
            user32 = ctypes.windll.user32
            vk_code = 48 + index
            user32.keybd_event(17, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.3)
            user32.keybd_event(vk_code, 0, 2, 0)
            user32.keybd_event(17, 0, 2, 0)
            return (True, f'Перешли на вкладку {index}')
        return (False, 'Индекс вкладки должен быть от 1 до 9')
    except Exception as e:
        return (False, str(e))
def close_all_tabs() -> tuple[bool, str]:
    try:
        if not _activate_browser():
            return (False, 'Браузер не найден')
        time.sleep(0.3)
        user32 = ctypes.windll.user32
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(16, 0, 0, 0)
        user32.keybd_event(87, 0, 0, 0)
        time.sleep(0.3)
        user32.keybd_event(87, 0, 2, 0)
        user32.keybd_event(16, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        return (True, 'Все вкладки закрыты')
    except Exception as e:
        return (False, str(e))
