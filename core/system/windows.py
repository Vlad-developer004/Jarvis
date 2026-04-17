import ctypes
import ctypes.wintypes
import sys
import os
import winreg
_AUTOSTART_KEY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Run'
_AUTOSTART_NAME = 'Jarvis'
def _exe_path() -> str:
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'main.py')
def autostart_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _AUTOSTART_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
def autostart_set(enable: bool) -> None:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
    if enable:
        path = _exe_path()
        cmd = f'pythonw "{path}"' if path.endswith('.py') else f'"{path}"'
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, cmd)
    else:
        try:
            winreg.DeleteValue(key, _AUTOSTART_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)
def add_defender_exclusion() -> bool:
    try:
        if getattr(sys, 'frozen', False):
            path = os.path.dirname(sys.executable)
        else:
            path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import subprocess
        subprocess.run(['powershell', '-WindowStyle', 'Hidden', '-Command', f"Add-MpPreference -ExclusionPath '{path}'"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False
_DEFENDER_DONE_KEY = 'Software\\Jarvis'
_DEFENDER_DONE_NAME = 'DefenderExclusionAdded'
def defender_exclusion_needed() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _DEFENDER_DONE_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _DEFENDER_DONE_NAME)
        winreg.CloseKey(key)
        return False
    except Exception:
        return True
def mark_defender_exclusion_done() -> None:
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _DEFENDER_DONE_KEY)
        winreg.SetValueEx(key, _DEFENDER_DONE_NAME, 0, winreg.REG_SZ, '1')
        winreg.CloseKey(key)
    except Exception:
        pass
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
SW_RESTORE = 9
def force_foreground(hwnd: int) -> None:
    if not hwnd: return
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)
    cur_tid = _kernel32.GetCurrentThreadId()
    fg_hwnd = _user32.GetForegroundWindow()
    fg_tid = _user32.GetWindowThreadProcessId(fg_hwnd, None)
    if fg_tid and fg_tid != cur_tid:
        _user32.AttachThreadInput(fg_tid, cur_tid, True)
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
        _user32.AttachThreadInput(fg_tid, cur_tid, False)
    else:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
def get_active_explorer_path() -> str | None:
    try:
        import win32gui
        import win32com.client
        import urllib.parse
        hwnd_fg = win32gui.GetForegroundWindow()
        shell = win32com.client.Dispatch('Shell.Application')
        for w in shell.Windows():
            try:
                if not w or not w.LocationURL:
                    continue
                if int(w.HWND) != hwnd_fg:
                    continue
                if not str(w.FullName).lower().endswith('explorer.exe'):
                    continue
                url = str(w.LocationURL)
                if url.lower().startswith('file:///'):
                    path = urllib.parse.unquote(url.replace('file:///', '')).replace('/', '\\')
                    return path
            except Exception:
                continue
    except Exception:
        return None
    return None
def set_process_priority(level: str) -> bool:
    import ctypes
    levels = {
        'high': 0x00000080,
        'above_normal': 0x00008000,
        'normal': 0x00000020,
        'idle': 0x00000040
    }
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.kernel32.SetPriorityClass(handle, levels.get(level.lower(), 0x00000020))
        return bool(ok)
    except Exception as e:
        print(f"[set_process_priority] Error: {e}")
        return False
def get_foreground_process_name() -> str | None:
    try:
        import psutil
        hwnd = _user32.GetForegroundWindow()
        if not hwnd: return None
        pid = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0: return None
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return None
def get_foreground_process_exe() -> str | None:
    try:
        import psutil
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return None
        exe = psutil.Process(pid.value).exe()
        return exe if exe and os.path.isfile(exe) else None
    except Exception:
        return None
