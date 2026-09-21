import os
import io
import time
import subprocess
import threading
import ctypes
import pyperclip
from pathlib import Path
from datetime import datetime
from core.system import force_foreground
import pyautogui
import win32gui
import win32con
import win32clipboard
from PIL import Image
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('screenshot')
def _get_screenshots_dir() -> Path:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders')
        pics_raw, _ = winreg.QueryValueEx(key, 'My Pictures')
        winreg.CloseKey(key)
        pics = os.path.expandvars(pics_raw)
    except Exception:
        pics = os.path.join(os.path.expanduser('~'), 'Pictures')
    screenshots = Path(pics) / 'Screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    return screenshots
def _copy_image_to_clipboard(img: Image.Image):
    output = io.BytesIO()
    img.convert('RGB').save(output, 'BMP')
    bmp_data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
    win32clipboard.CloseClipboard()
def _open_in_editor(filepath: str):
    abs_path = os.path.abspath(filepath)
    try:
        subprocess.Popen(['mspaint', abs_path])
    except Exception:
        os.startfile(abs_path)
    time.sleep(1.0)
    hwnd = win32gui.GetForegroundWindow()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
def _save_and_open_screenshot(img, prefix: str) -> tuple[bool, str]:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = _get_screenshots_dir() / f'{prefix}_{ts}.png'
    img.save(str(path))
    _copy_image_to_clipboard(img)
    _open_in_editor(str(path))
    return (True, str(path))
TERMINAL_CLASSES = {'ConsoleWindowClass', 'CASCADIA_HOSTING_WINDOW_CLASS', 'mintty', 'VirtualConsoleClass', 'PseudoConsoleWindow'}
TERMINAL_KEYWORDS = ['cmd', 'powershell', 'terminal', 'python', 'командная строка', 'windows terminal', 'bash']
_IDE_KEYWORDS = ['cursor', 'visual studio code', 'antigravity', '- code']
def _is_terminal_window(hwnd) -> bool:
    try:
        cls = win32gui.GetClassName(hwnd)
        if cls in TERMINAL_CLASSES:
            return True
        title = win32gui.GetWindowText(hwnd).lower()
        if any((kw in title for kw in TERMINAL_KEYWORDS)):
            return True
    except:
        pass
    return False
def _find_ide_terminal_rect():
    try:
        import comtypes.client
        uia = comtypes.client.CreateObject('{FF48DBA4-60EF-4201-AA87-54103EEF594E}', interface=None)
        focused = uia.GetFocusedElement()
        if not focused:
            return None
        walker = uia.RawViewWalker
        el = focused
        for _ in range(20):
            try:
                name = (el.CurrentName or '').lower()
                auto_id = (el.CurrentAutomationId or '').lower()
                cls_name = (el.CurrentClassName or '').lower()
                rect = el.CurrentBoundingRectangle
                w, h = (rect.right - rect.left, rect.bottom - rect.top)
                if w > 200 and h > 50 and any((kw in name + auto_id + cls_name for kw in ['terminal', 'panel', 'console'])):
                    return (rect.left, rect.top, w, h)
                el = walker.GetParentElement(el)
                if not el:
                    break
            except:
                break
    except:
        pass
    return None
def screenshot_screen() -> tuple[bool, str]:
    try:
        img = pyautogui.screenshot()
        return _save_and_open_screenshot(img, 'screenshot')
    except Exception as e:
        _log.exception('screenshot_screen failed')
        return (False, str(e))
def screenshot_terminal() -> tuple[bool, str]:
    try:
        import pygetwindow as gw
        my_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_title = win32gui.GetWindowText(fg_hwnd).lower()
        def _capture_window(hwnd):
            rect = win32gui.GetWindowRect(hwnd)
            return pyautogui.screenshot(region=(rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]))
        def _capture_ide_bottom(hwnd):
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            panel_h = int((y2 - y) * 0.35)
            return pyautogui.screenshot(region=(x, y2 - panel_h, x2 - x, panel_h))
        if fg_hwnd != my_hwnd and any((kw in fg_title for kw in _IDE_KEYWORDS)):
            img = _capture_ide_bottom(fg_hwnd)
            return _save_and_open_screenshot(img, 'terminal')
        if fg_hwnd != my_hwnd and _is_terminal_window(fg_hwnd):
            img = _capture_window(fg_hwnd)
            return _save_and_open_screenshot(img, 'terminal')
        ide_wins = [w for w in gw.getAllWindows() if w.visible and w._hWnd != my_hwnd and any((kw in w.title.lower() for kw in _IDE_KEYWORDS))]
        if ide_wins:
            best_ide = ide_wins[0]
            force_foreground(best_ide._hWnd)
            time.sleep(0.2)
            img = _capture_ide_bottom(best_ide._hWnd)
            return _save_and_open_screenshot(img, 'terminal')
        terminals = [w for w in gw.getAllWindows() if w.visible and w._hWnd != my_hwnd and _is_terminal_window(w._hWnd)]
        if terminals:
            best = terminals[0]
            force_foreground(best._hWnd)
            time.sleep(0.3)
            img = _capture_window(best._hWnd)
            return _save_and_open_screenshot(img, 'terminal')
        if my_hwnd and win32gui.IsWindowVisible(my_hwnd):
            force_foreground(my_hwnd)
            time.sleep(0.3)
            img = _capture_window(my_hwnd)
            return _save_and_open_screenshot(img, 'terminal')
        region = _find_ide_terminal_rect()
        if region:
            img = pyautogui.screenshot(region=region)
            return _save_and_open_screenshot(img, 'terminal')
        return (False, 'Terminal not found')
    except Exception as e:
        _log.exception('screenshot_terminal failed')
        return (False, str(e))
def screenshot_full_page() -> tuple[bool, str]:
    try:
        from actions.windows import _ensure_en_layout, _restore_layout, send_hardware_key
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if not win or not any((b in win.title.lower() for b in ['chrome', 'brave', 'edge', 'firefox', 'opera', 'browser'])):
            return (False, 'Browser window not active.')
        hkl = _ensure_en_layout()
        send_hardware_key(123)
        time.sleep(1.2)
        user32 = ctypes.windll.user32
        for vk in [17, 16, 80]:
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        for vk in [80, 16, 17]:
            user32.keybd_event(vk, 0, 2, 0)
        time.sleep(1.0)
        old_clip = pyperclip.paste()
        pyperclip.copy('Capture full size screenshot')
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(86, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(86, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        time.sleep(0.8)
        pyautogui.press('enter')
        _restore_layout(hkl)
        def _finish_screenshot():
            try:
                _finish_screenshot_inner()
            except Exception:
                _log.exception('screenshot_full_page background finisher failed')
            finally:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass
        def _finish_screenshot_inner():
            downloads_dir = Path.home() / 'Downloads'
            screenshots_dir = _get_screenshots_dir()
            dest_path = screenshots_dir / f'fullpage_{int(time.time())}.png'
            start_time = time.time() - 2
            saved_file = None
            for _ in range(30):
                time.sleep(0.5)
                hwnd = win32gui.GetForegroundWindow()
                if hwnd and win32gui.GetClassName(hwnd) == '#32770':
                    pyperclip.copy(str(dest_path))
                    time.sleep(0.2)
                    user32.keybd_event(17, 0, 0, 0)
                    user32.keybd_event(86, 0, 0, 0)
                    time.sleep(0.05)
                    user32.keybd_event(86, 0, 2, 0)
                    user32.keybd_event(17, 0, 2, 0)
                    time.sleep(0.5)
                    pyautogui.press('enter')
                    saved_file = dest_path
                    break
                pngs = list(downloads_dir.glob('*.png'))
                new_pngs = [p for p in pngs if p.stat().st_mtime > start_time]
                if new_pngs:
                    latest = max(new_pngs, key=lambda p: p.stat().st_mtime)
                    import shutil
                    try:
                        shutil.move(str(latest), str(dest_path))
                        saved_file = dest_path
                        break
                    except:
                        pass
            time.sleep(1.0)
            send_hardware_key(123)
            if saved_file:
                _open_in_editor(str(saved_file))
        threading.Thread(target=_finish_screenshot, daemon=True).start()
        return (True, 'Screenshooting page...')
    except Exception as e:
        _log.exception('screenshot_full_page failed')
        return (False, str(e))
def start_video_recording(with_mic: bool=False, monitor_index: int=0) -> tuple[bool, str]:
    try:
        from actions.windows import get_monitors
        monitors = get_monitors()
        mon = monitors[monitor_index] if monitor_index < len(monitors) else monitors[0]
        user32 = ctypes.windll.user32
        pyautogui.FAILSAFE = False
        user32.keybd_event(91, 0, 0, 0)
        user32.keybd_event(16, 0, 0, 0)
        user32.keybd_event(82, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(82, 0, 2, 0)
        user32.keybd_event(16, 0, 2, 0)
        user32.keybd_event(91, 0, 2, 0)
        time.sleep(2.0)
        x0 = mon['left'] + 5
        y0 = mon['top'] + 5
        x1 = mon['right'] - 5
        y1 = mon['bottom'] - 5
        pyautogui.moveTo(x0, y0)
        pyautogui.mouseDown()
        pyautogui.moveTo(x1, y1, duration=0.5)
        pyautogui.mouseUp()
        time.sleep(1.0)
        for _ in range(5):
            pyautogui.press('tab')
            time.sleep(0.1)
        if with_mic:
            pyautogui.keyDown('shift')
            pyautogui.press('tab')
            pyautogui.press('tab')
            pyautogui.keyUp('shift')
            time.sleep(0.1)
            pyautogui.press('space')
            time.sleep(0.1)
            pyautogui.press('tab')
            pyautogui.press('tab')
            time.sleep(0.1)
        pyautogui.press('enter')
        return (True, 'Recording started')
    except Exception as e:
        return (False, str(e))
def stop_video_recording(cancel: bool=False) -> tuple[bool, str]:
    import time
    import pyautogui
    import win32gui
    import win32con
    tabs = 1 if cancel else 3
    def _find_snipping():
        result = []
        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if title:
                    pass
                if any((k in title for k in ['snipping', 'ножниц', 'snip', 'screen snip', 'захват', 'recording toolbar'])):
                    result.append(hwnd)
        win32gui.EnumWindows(_cb, None)
        return result[0] if result else None
    hwnd = _find_snipping()
    if not hwnd:
        return (False, 'Snipping Tool не найден')
    import ctypes
    user32 = ctypes.windll.user32
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.8)
    for _ in range(tabs):
        pyautogui.press('tab')
        time.sleep(0.15)
    pyautogui.press('enter')
    return (True, 'Запись остановлена')
def _find_snipping_hwnd():
    result = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd).lower()
            if any((k in t for k in ['snipping', 'ножниц', 'recording toolbar', 'snip'])):
                result.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    return result[0] if result else None
def handle_stop_video_cmd(is_cancel: bool, speak_fn, set_interactive_fn) -> None:
    ok, _ = stop_video_recording(cancel=is_cancel)
    if not ok:
        return
    time.sleep(0.5)
    if is_cancel:
        hwnd = _find_snipping_hwnd()
        if hwnd:
            win32gui.PostMessage(hwnd, 16, 0, 0)
        speak_fn('Запись отменена.')
    else:
        speak_fn('Запись остановлена. Хотите редактировать?')
        set_interactive_fn('edit_video')
