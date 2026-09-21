import ctypes
import ctypes.wintypes
import win32process
import win32api
import win32con
import sys
import os
import winreg
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('windows')
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
def get_hwnd_process_name(hwnd) -> str:
    try:
        import os
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # 0x0400 = PROCESS_QUERY_INFORMATION, 0x0010 = PROCESS_VM_READ
        h_proc = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
        try:
            return os.path.basename(win32process.GetModuleFileNameEx(h_proc, 0)).lower()
        finally:
            win32api.CloseHandle(h_proc)
    except:
        return ""

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
    tgt_tid = _user32.GetWindowThreadProcessId(hwnd, None)
    fg_hwnd = _user32.GetForegroundWindow()
    fg_tid  = _user32.GetWindowThreadProcessId(fg_hwnd, None)
    # Attach both threads so SetFocus works cross-thread
    if fg_tid and fg_tid != cur_tid:
        _user32.AttachThreadInput(fg_tid, cur_tid, True)
    if tgt_tid and tgt_tid != cur_tid:
        _user32.AttachThreadInput(tgt_tid, cur_tid, True)
    _user32.BringWindowToTop(hwnd)
    _user32.SetForegroundWindow(hwnd)
    _user32.SetFocus(hwnd)
    if tgt_tid and tgt_tid != cur_tid:
        _user32.AttachThreadInput(tgt_tid, cur_tid, False)
    if fg_tid and fg_tid != cur_tid:
        _user32.AttachThreadInput(fg_tid, cur_tid, False)

def get_known_folder_path(folder_guid: str) -> str | None:
    import ctypes
    from ctypes import wintypes
    
    # GUIDs for common folders
    GUIDS = {
        'desktop': '{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}',
        'documents': '{FDD39AD0-238F-46AF-ADB4-6C85480369C7}',
        'downloads': '{374DE290-123F-4565-9164-39C4925E467B}',
        'music': '{4BD8C170-6A38-442C-907E-0535F275C6E9}',
        'pictures': '{33E28130-4E1E-4676-835A-98395C3BC3BB}',
        'videos': '{18989B1D-99B5-455B-841C-AB7C74E4DDFC}',
    }
    
    guid_str = GUIDS.get(folder_guid.lower(), folder_guid)
    
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8)
        ]

    def string_to_guid(s):
        import re
        m = re.match(r"\{?([0-9a-fA-F]{8})-([0-9a-fA-F]{4})-([0-9a-fA-F]{4})-([0-9a-fA-F]{4})-([0-9a-fA-F]{12})\}?", s)
        if not m: return None
        d1, d2, d3, d4_12, d4_38 = m.groups()
        return GUID(
            int(d1, 16), int(d2, 16), int(d3, 16),
            (ctypes.c_ubyte * 8)(*[int(d4_12[i:i+2], 16) for i in (0, 2)] + [int(d4_38[i:i+2], 16) for i in range(0, 12, 2)])
        )

    try:
        CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
        CoTaskMemFree.restype = None
        CoTaskMemFree.argtypes = [ctypes.c_void_p]

        SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
        SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
        ]

        pkf = string_to_guid(guid_str)
        if not pkf: return None
        
        path_ptr = ctypes.c_wchar_p()
        # 0x00008000 = KF_FLAG_DEFAULT
        hr = SHGetKnownFolderPath(ctypes.byref(pkf), 0, None, ctypes.byref(path_ptr))
        if hr == 0:
            path = path_ptr.value
            CoTaskMemFree(path_ptr)
            return path
    except Exception:
        pass
    return None

def get_active_explorer_path(any_open: bool = False) -> str | None:
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import win32gui
        import win32com.client
        import urllib.parse
        hwnd_fg = win32gui.GetForegroundWindow()
        
        # Check if foreground is literal Desktop
        fg_class = win32gui.GetClassName(hwnd_fg)
        if fg_class in ('Progman', 'WorkerW'):
            from core.system.windows import get_known_folder_path
            return get_known_folder_path('desktop')
            
        shell = win32com.client.Dispatch('Shell.Application')
        best_path = None
        for w in shell.Windows():
            try:
                if not w or not w.LocationURL:
                    continue
                if not str(w.FullName).lower().endswith('explorer.exe'):
                    continue
                url = str(w.LocationURL)
                if url.lower().startswith('file:///'):
                    path = urllib.parse.unquote(url.replace('file:///', '')).replace('/', '\\')
                    if int(w.HWND) == hwnd_fg:
                        return path # Exact match found
                    if not best_path:
                        best_path = path
            except Exception:
                continue
        return best_path if any_open else None
    except Exception:
        return None
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass
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
        _log.error(f"[set_process_priority] Error: {e}")
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
def get_foreground_window_title() -> str | None:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: return None
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return None

def get_installed_apps() -> list[dict]:
    apps = []
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    seen_names = set()
    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                        if not name or name in seen_names: continue
                        
                        exe_hint = ""
                        try:
                            icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                            if icon and ".exe" in icon.lower():
                                exe_hint = os.path.basename(icon.split(",")[0].strip("\""))
                        except: pass
                        
                        if not exe_hint:
                            try:
                                un_str, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                if un_str and ".exe" in un_str.lower():
                                    parts = un_str.split("\\")
                                    for p in reversed(parts):
                                        if ".exe" in p.lower():
                                            exe_hint = p.split("\"")[-1].split(" ")[0].strip()
                                            if not exe_hint.lower().startswith("unins"):
                                                break
                            except: pass

                        # Final ignore list for "noise"
                        noise_keywords = [
                            "driver", "printer", "service", "uninstall", "redistributable", 
                            "canon", "library", "directx", "framework", "software development kit",
                            "runtime", "component", "msiexec", "host", "updater", "redist", 
                            "resolver", "license", "licensing", "extensibility", "click-to-run",
                            "clicktorun", "microsoft .net", "java auto", "webview2", "help",
                            "manual", "documentation", "vcredist", "vsto", "git", "windhawk",
                            "start11", "redragon", "reg organizer", "stardock", "officeclicktorun",
                            "python 3.", "microsoft office ltsc", "sdk", "api", "tools", "web engine"
                        ]
                        low_name = name.lower()
                        is_noise = any(kw in low_name for kw in noise_keywords)
                        
                        # Mark as noise if name looks like a system entry (long with versions)
                        if not is_noise and len(name) > 40 and any(c.isdigit() for c in name):
                             # Very long technical names are usually system components
                             is_noise = True
                        
                        # Also check the EXE itself for common installer/system patterns
                        low_exe = (exe_hint or "").lower()
                        installer_signs = ["msiexec.exe", "setup", "install", "unins", "format", "update", "patch", "helper", "engine"]
                        if any(sign in low_exe for sign in installer_signs):
                            is_noise = True
                        
                        # Identify IDEs/Development tools
                        ide_keywords = ["code", "studio", "intellij", "pycharm", "phpstorm", "sublime", "webstorm", "clion", "eclipse", "atom", "rider", "antigravity", "cursor", "development", "workbench"]
                        is_ide = any(kw in low_name for kw in ide_keywords) and not is_noise
                        
                        apps.append({"name": name, "exe": exe_hint, "is_noise": is_noise, "is_ide": is_ide})
                        seen_names.add(name)
                    finally: winreg.CloseKey(subkey)
                except: pass
            winreg.CloseKey(key)
        except: pass
    return sorted(apps, key=lambda x: x["name"])
