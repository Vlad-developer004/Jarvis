import time
import win32gui
import win32con
import win32api
import ctypes
import pygetwindow as gw
from core.system import force_foreground
_LAST_MINIMIZED_HWND = None
def minimize_all_windows() -> tuple[bool, str]:
    global _LAST_MINIMIZED_HWND
    errors: list[str] = []
    shell_sent = False
    try:
        hwnd = win32gui.FindWindow('Shell_TrayWnd', None)
        if hwnd:
            win32gui.SendMessage(hwnd, win32con.WM_COMMAND, 416, 0)
            shell_sent = True
    except Exception as e:
        errors.append(f'shell_command: {e}')
    count = 0
    try:
        def _should_skip(hwnd: int) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                cls = win32gui.GetClassName(hwnd)
            except Exception:
                cls = ''
            if cls in ('Shell_TrayWnd', 'Progman', 'WorkerW', 'TrayNotifyWnd', 'ReBarWindow32'):
                return True
            try:
                ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if ex & win32con.WS_EX_TOOLWINDOW:
                    return True
            except Exception:
                pass
            try:
                title = win32gui.GetWindowText(hwnd) or ''
            except Exception:
                title = ''
            if not title.strip():
                return True
            if title in ('Program Manager', 'Settings', 'Параметры', 'Windows Shell Experience Host'):
                return True
            return False
        def _enum_cb(hwnd: int, _):
            nonlocal count
            if _should_skip(hwnd):
                return True
            try:
                if win32gui.IsIconic(hwnd):
                    return True
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                count += 1
            except Exception:
                pass
            return True
        win32gui.EnumWindows(_enum_cb, None)
    except Exception as e:
        errors.append(f'enumwindows: {e}')
    try:
        for win in gw.getAllWindows():
            if win.visible and win.title and not win.isMinimized:
                if win.title not in ('Program Manager', 'Settings', 'Параметры'):
                    try:
                        win.minimize()
                        count += 1
                    except Exception:
                        pass
    except Exception as e:
        errors.append(f'pygetwindow_all: {e}')
    if count > 0 or shell_sent:
        return (True, f'Все окна свернуты (свёрнуто: {count})')
    try:
        import pyautogui
        pyautogui.hotkey('win', 'd')
        return (True, 'Отправлен сигнал Win+D')
    except Exception as e:
        errors.append(f'pyautogui: {e}')
    try:
        user32 = ctypes.windll.user32
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        VK_LWIN = 0x5B
        VK_D = 0x44
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ('wVk', ctypes.c_ushort),
                ('wScan', ctypes.c_ushort),
                ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
            ]
        class INPUT_UNION(ctypes.Union):
            _fields_ = [('ki', KEYBDINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [('type', ctypes.c_ulong), ('union', INPUT_UNION)]
        extra = ctypes.c_ulong(0)
        inputs = (INPUT * 4)(
            INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(VK_LWIN, 0, 0, 0, ctypes.pointer(extra)))),
            INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(VK_D, 0, 0, 0, ctypes.pointer(extra)))),
            INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(VK_D, 0, KEYEVENTF_KEYUP, 0, ctypes.pointer(extra)))),
            INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(VK_LWIN, 0, KEYEVENTF_KEYUP, 0, ctypes.pointer(extra)))),
        )
        sent = user32.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        if sent == 4:
            return (True, 'Окна свернуты через SendInput')
    except Exception as e:
        errors.append(f'sendinput: {e}')
    return (False, '; '.join(errors) if errors else 'Не удалось свернуть окна')
def maximize_current_window() -> tuple[bool, str]:
    try:
        win = gw.getActiveWindow()
        if win:
            win.maximize()
            return (True, 'Окно развернуто')
        return (False, 'Активное окно не найдено')
    except Exception as e:
        return (False, str(e))
def minimize_current_window() -> tuple[bool, str]:
    global _LAST_MINIMIZED_HWND
    try:
        win = gw.getActiveWindow()
        if win:
            if not win.isMinimized:
                _LAST_MINIMIZED_HWND = win._hWnd
                win.minimize()
            return (True, 'Окно свернуто')
        return (False, 'Нет активного окна')
    except Exception as e:
        return (False, str(e))
def unminimize_last_window() -> tuple[bool, str]:
    global _LAST_MINIMIZED_HWND
    try:
        if _LAST_MINIMIZED_HWND and win32gui.IsWindow(_LAST_MINIMIZED_HWND):
            win32gui.ShowWindow(_LAST_MINIMIZED_HWND, win32con.SW_RESTORE)
            force_foreground(_LAST_MINIMIZED_HWND)
            _LAST_MINIMIZED_HWND = None
            return (True, 'Окно развернуто')
        return (False, 'Нет сохранённого свернутого окна')
    except Exception as e:
        return (False, str(e))
def close_current_window() -> tuple[bool, str]:
    try:
        win = gw.getActiveWindow()
        if win:
            win.close()
            return (True, 'Окно закрыто')
        return (False, 'Нет активного окна')
    except Exception as e:
        return (False, str(e))
def close_all_windows() -> tuple[bool, str]:
    try:
        count = 0
        for win in gw.getAllWindows():
            if win.title and win.visible and (win.title not in ['Program Manager', 'Settings', 'Параметры']):
                try:
                    win.close()
                    count += 1
                except Exception:
                    pass
        return (True, f'Закрыто окон: {count}')
    except Exception as e:
        return (False, str(e))
def close_other_windows(keep_apps: list[str] = None) -> tuple[bool, str]:
    try:
        active_hwnd = win32gui.GetForegroundWindow()
        count = 0
        keep_apps_lower = [app.lower() for app in keep_apps] if keep_apps else []
        for win in gw.getAllWindows():
            hwnd = win._hWnd
            if win.title and win.visible and win32gui.IsWindowVisible(hwnd):
                title_lower = win.title.lower()
                if win.title not in ['Program Manager', 'Settings', 'Параметры'] and hwnd != active_hwnd:
                    should_keep = False
                    for app in keep_apps_lower:
                        if app in title_lower:
                            should_keep = True
                            break
                    if not should_keep:
                        try:
                            win.close()
                            count += 1
                        except Exception:
                            pass
        return (True, f'Закрыто остальных окон: {count}')
    except Exception as e:
        return (False, str(e))
def minimize_other_windows(keep_apps: list[str] = None) -> tuple[bool, str]:
    try:
        active_hwnd = win32gui.GetForegroundWindow()
        count = 0
        keep_apps_lower = [app.lower() for app in keep_apps] if keep_apps else []
        for win in gw.getAllWindows():
            hwnd = win._hWnd
            if win.title and win.visible and win32gui.IsWindowVisible(hwnd):
                title_lower = win.title.lower()
                if win.title not in ['Program Manager', 'Settings', 'Параметры'] and hwnd != active_hwnd:
                    if not win.isMinimized:
                        should_keep = False
                        for app in keep_apps_lower:
                            if app in title_lower:
                                should_keep = True
                                break
                        if not should_keep:
                            try:
                                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                                count += 1
                            except Exception:
                                pass
        return (True, f'Свернуто остальных окон: {count}')
    except Exception as e:
        return (False, str(e))
def get_monitors() -> list[dict]:
    monitors = []
    for hmon, _, rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(hmon)
        work = info['Work']
        is_primary = bool(info.get('Flags', 0) & 1)
        monitors.append({'left': work[0], 'top': work[1], 'right': work[2], 'bottom': work[3], 'width': work[2] - work[0], 'height': work[3] - work[1], 'name': info.get('Device', ''), 'primary': is_primary})
    monitors.sort(key=lambda m: m['left'])
    return monitors
def move_to_monitor(index: int) -> tuple[bool, str]:
    try:
        monitors = get_monitors()
        if not monitors:
            return (False, 'Мониторы не найдены')
        if index < 1 or index > len(monitors):
            return (False, f'Монитор {index} не найден. Доступно мониторов: {len(monitors)}')
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return (False, 'Нет активного окна')
        mon = monitors[index - 1]
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMAXIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
        win32gui.SetWindowPos(hwnd, None, mon['left'], mon['top'], mon['width'], mon['height'], win32con.SWP_NOZORDER)
        time.sleep(0.1)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return (True, f'Окно перемещено на монитор {index}')
    except Exception as e:
        return (False, str(e))
def snap_window(side: str) -> tuple[bool, str]:
    try:
        win = gw.getActiveWindow()
        if not win:
            return (False, 'Нет активного окна')
        h_mon = win32api.MonitorFromWindow(win._hWnd, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(h_mon)
        work = info['Work']
        width = work[2] - work[0]
        height = work[3] - work[1]
        if win.isMaximized:
            win.restore()
        if side == 'left':
            win.moveTo(work[0], work[1])
            win.resizeTo(width // 2, height)
            return (True, 'Окно прижато влево')
        elif side == 'right':
            win.moveTo(work[0] + width // 2, work[1])
            win.resizeTo(width // 2, height)
            return (True, 'Окно прижато вправо')
        elif side == 'top-left':
            win.moveTo(work[0], work[1])
            win.resizeTo(width // 2, height // 2)
            return (True, 'Окно в левый верхний угол')
        elif side == 'top-right':
            win.moveTo(work[0] + width // 2, work[1])
            win.resizeTo(width // 2, height // 2)
            return (True, 'Окно в правый верхний угол')
        elif side == 'bottom-left':
            win.moveTo(work[0], work[1] + height // 2)
            win.resizeTo(width // 2, height // 2)
            return (True, 'Окно в левый нижний угол')
        elif side == 'bottom-right':
            win.moveTo(work[0] + width // 2, work[1] + height // 2)
            win.resizeTo(width // 2, height // 2)
            return (True, 'Окно в правый нижний угол')
        return (False, 'Неизвестная сторона')
    except Exception as e:
        return (False, str(e))
