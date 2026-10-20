"""The address of the browser's current tab, read by driving the browser: foreground, Ctrl+L, Ctrl+C, then the clipboard (the clipboard and
fullscreen state are restored). Slow (about 3 s of key-press pauses) and it moves the window, so callers try the browser history first."""
import time

import pygetwindow as gw

import logging
_log = logging.getLogger(__name__)


def _get_current_url() -> str | None:
    import pyautogui
    import pyperclip
    import ctypes
    import win32process
    import psutil
    BROWSER_PROCESSES = ['brave.exe', 'chrome.exe', 'firefox.exe', 'msedge.exe', 'opera.exe']
    user32 = ctypes.windll.user32
    browser_win = None
    for w in gw.getAllWindows():
        if not w.visible or not w.title or w.width <= 0:
            continue
        try:
            _, pid = win32process.GetWindowThreadProcessId(w._hWnd)
            pname = psutil.Process(pid).name().lower()
            if pname in BROWSER_PROCESSES:
                browser_win = w
                break
        except Exception:
            continue
    if not browser_win:
        _log.debug('[_get_current_url] no browser found')
        return None
    hwnd = browser_win._hWnd
    old_clip = ''
    try:
        old_clip = pyperclip.paste()
    except Exception:
        pass
    fs_toggled_off = False
    try:
        import win32process
        import win32api
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        cur_tid = win32api.GetCurrentThreadId()
        fg_hwnd = user32.GetForegroundWindow()
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
        if fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if fg_tid != cur_tid:
            user32.AttachThreadInput(fg_tid, cur_tid, False)
        time.sleep(0.5)
        actual_fg = user32.GetForegroundWindow()
        _log.debug(f'[_get_current_url] hwnd={hwnd} actual_fg={actual_fg} match={actual_fg==hwnd}')
        mon_w = user32.GetSystemMetrics(0)
        mon_h = user32.GetSystemMetrics(1)
        is_fullscreen = (browser_win.width >= mon_w and browser_win.height >= mon_h)
        VK_CONTROL = 0x11
        VK_L = 0x4C
        VK_C = 0x43
        VK_D = 0x44
        VK_ESCAPE = 0x1B
        KEYEVENTF_KEYUP = 2
        def _ctrl_key(vk):
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        if is_fullscreen:
            import win32gui as _wg
            user32.keybd_event(0x7A, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x7A, 0, 2, 0)
            fs_toggled_off = True
            for _ in range(30):
                left, top, right, bottom = _wg.GetWindowRect(hwnd)
                if top > 0:
                    break
                time.sleep(0.1)
            _log.debug(f'[_get_current_url] after F11: left={left} top={top}')
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            time.sleep(0.3)
            click_x = (left + right) // 2
            click_y = top + 70
            pyautogui.click(click_x, click_y)
            time.sleep(0.4)
        pyperclip.copy('')
        time.sleep(0.2)
        _ctrl_key(VK_L)
        time.sleep(0.5)
        _ctrl_key(VK_C)
        time.sleep(0.3)
        url = pyperclip.paste().strip()
        _log.debug(f'[_get_current_url] ctrl+l got: {url!r}')
        if not url.startswith('http'):
            pyperclip.copy('')
            VK_MENU = 0x12
            user32.keybd_event(VK_MENU, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_D, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.5)
            _ctrl_key(VK_C)
            time.sleep(0.3)
            url = pyperclip.paste().strip()
            _log.debug(f'[_get_current_url] alt+d got: {url!r}')
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)
        _log.debug(f'[_get_current_url] got: {url!r}')
        if url.startswith('http'):
            return url
    except Exception as e:
        _log.debug(f'[_get_current_url] error: {e}')
    finally:
        # Always restore fullscreen if we toggled it off, even if something above raised.
        if fs_toggled_off:
            try:
                user32.keybd_event(0x7A, 0, 0, 0)
                time.sleep(0.05)
                user32.keybd_event(0x7A, 0, 2, 0)
                time.sleep(0.3)
            except Exception:
                pass
        try:
            if old_clip:
                pyperclip.copy(old_clip)
        except Exception:
            pass
    return None
