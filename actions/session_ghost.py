from actions.session_ghost_parts.storage import *
from actions.session_ghost_parts.capture_restore import *
import os
import json
import time
import subprocess
import threading
from pathlib import Path
import pyautogui
import pyperclip
import pygetwindow as gw
import psutil
import ctypes
import win32process

try:
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
try:
    from actions.windows import _ensure_en_layout, _restore_layout
except ImportError:
    def _ensure_en_layout():
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            user32.PostMessageA(hwnd, 80, 0, 67699721)
            return True
        except:
            return None
    def _restore_layout(hkl):
        try:
            if not hkl: return
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            user32.PostMessageA(hwnd, 80, 0, hkl)
        except:
            pass
SESSIONS_FILE = 'data/sessions.json'
BROWSER_PROCESSES = ['brave.exe', 'chrome.exe', 'firefox.exe', 'msedge.exe', 'opera.exe', 'yandex.exe']
IDE_PROCESSES = ['antigravity.exe', 'code.exe', 'pycharm64.exe', 'idea64.exe', 'sublime_text.exe', 'devenv.exe', 'clion64.exe', 'studio64.exe', 'webstorm64.exe', 'phpstorm64.exe', 'rider64.exe', 'rustrover64.exe']
def _ensure_data_dir():
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
def _load_sessions():
    _ensure_data_dir()
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def _save_sessions(data):
    _ensure_data_dir()
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
def save_session(session_name, speak_func, play_response_func):
    speak_func('Запускаю захват. Сканирую процессы, папки и вкладки.')
    time.sleep(1)
    session_data = {'ides': [], 'urls': [], 'apps': [], 'timestamp': time.time()}
    raw_ides = []
    for p in psutil.process_iter(['name', 'exe', 'cmdline']):
        try:
            name = p.info['name'].lower()
            if any((ide in name for ide in IDE_PROCESSES)):
                cmdline = p.info.get('cmdline')
                if not cmdline:
                    continue
                cmd_str = ' '.join(cmdline).lower()
                if '--type=' in cmd_str or 'extensionhost' in cmd_str or 'crashpad' in cmd_str:
                    continue
                exe = p.info['exe']
                exe_dir = os.path.dirname(exe).lower() if exe else ''
                path = None
                for arg in cmdline[1:]:
                    if os.path.exists(arg) and os.path.isdir(arg):
                        arg_l = arg.lower()
                        if not ('appdata' in arg_l or 'windows' in arg_l) and arg_l != exe_dir:
                            path = arg
                            break
                if not path:
                    try:
                        cwd = p.cwd()
                        if cwd and os.path.isdir(cwd):
                            cwd_l = cwd.lower()
                            if not ('appdata' in cwd_l or 'windows' in cwd_l) and cwd_l != exe_dir:
                                path = cwd
                    except:
                        pass
                if path:
                    project_name = os.path.basename(path)
                    raw_ides.append({'name': name, 'project_name': project_name, 'exe': exe, 'path': path})
        except:
            pass
    seen = set()
    for ide in raw_ides:
        key = (ide['exe'], ide['path'])
        if key not in seen:
            seen.add(key)
            session_data['ides'].append(ide)
    if WIN32COM_AVAILABLE:
        try:
            shell = win32com.client.Dispatch('Shell.Application')
            for win in shell.Windows():
                try:
                    full_name = str(win.FullName).lower()
                    if 'explorer.exe' in full_name:
                        folder_path = str(win.Document.Folder.Self.Path)
                        title = str(win.LocationName)
                        if folder_path and os.path.exists(folder_path):
                            session_data['apps'].append({'type': 'folder', 'title': title, 'path': folder_path})
                        elif folder_path and folder_path.startswith('::{'):
                            session_data['apps'].append({'type': 'folder_clsid', 'title': title, 'path': folder_path})
                except:
                    pass
        except Exception as e:
            pass
    else:
        pass
    original_window = gw.getActiveWindow()
    windows = gw.getAllWindows()
    seen_urls = set()
    user32 = ctypes.windll.user32
    browser_hwnds = []
    for w in windows:
        if not w.visible or not w.title:
            continue
        if w.width <= 0 or w.height <= 0:
            continue
        hwnd = w._hWnd
        p_name = ''
        b_exe = ''
        try:
            _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
            p = psutil.Process(w_pid)
            p_name = p.name().lower()
            b_exe = p.exe()
        except:
            pass
        title_l = w.title.lower()
        is_browser = p_name in BROWSER_PROCESSES or title_l.endswith((' - brave', ' - google chrome', ' - mozilla firefox', ' - edge'))
        is_ide = p_name in IDE_PROCESSES
        is_explorer = 'explorer.exe' in p_name
        if is_browser:
            if not b_exe and 'brave' in title_l:
                b_exe = 'brave.exe'
            elif not b_exe and 'chrome' in title_l:
                b_exe = 'chrome.exe'
            browser_hwnds.append({'w': w, 'exe': b_exe})
        elif not is_ide and (not is_explorer) and b_exe:
            if 'windows' not in b_exe.lower() and 'system32' not in b_exe.lower():
                session_data['apps'].append({'type': 'exe', 'title': w.title, 'exe': b_exe})
    def force_focus(hwnd):
        user32.keybd_event(18, 0, 0, 0)
        user32.keybd_event(18, 0, 2, 0)
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    for browser_info in browser_hwnds:
        w = browser_info['w']
        b_exe = browser_info['exe']
        hwnd = w._hWnd
        old_clip = ''
        try:
            old_clip = pyperclip.paste()
        except:
            pass
        try:
            force_focus(hwnd)
            time.sleep(1.0)
            mon_w = user32.GetSystemMetrics(0)
            mon_h = user32.GetSystemMetrics(1)
            is_fullscreen = (w.width >= mon_w and w.height >= mon_h)
            if is_fullscreen:
                pyautogui.press('f11')
                time.sleep(0.6)
            if w.width > 0 and w.height > 0 and (w.left != -32000):
                click_x = w.left + w.width // 2
                click_y = w.top + 15
                pyautogui.click(click_x, click_y)
            time.sleep(0.3)
            urls_in_this_window = []
            for i in range(20):
                pyperclip.copy('')
                pyautogui.press('esc')
                time.sleep(0.1)
                pyautogui.hotkey('ctrl', 'f')
                time.sleep(0.2)
                pyautogui.press('esc')
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.3)
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(0.2)
                current_url = pyperclip.paste().strip()
                if not current_url:
                    pyautogui.press('f6')
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'insert')
                    time.sleep(0.2)
                    current_url = pyperclip.paste().strip()
                if not current_url:
                    pyautogui.hotkey('alt', 'd')
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'c')
                    time.sleep(0.2)
                    current_url = pyperclip.paste().strip()
                if not current_url:
                    break
                if not current_url or current_url in urls_in_this_window:
                    break
                urls_in_this_window.append(current_url)
                if (('://' in current_url) or ('.' in current_url and ' ' not in current_url)):
                    if not any(current_url.startswith(p) for p in ['http', 'file', 'chrome', 'edge', 'about']):
                        current_url = 'https://' + current_url
                    if current_url not in seen_urls:
                        session_data['urls'].append({'url': current_url, 'exe': b_exe})
                        seen_urls.add(current_url)
                pyautogui.hotkey('ctrl', 'tab')
                time.sleep(0.5)
        except Exception as e:
            pass
        finally:
            try:
                if is_fullscreen:
                    pyautogui.press('f11')
                    time.sleep(0.3)
            except:
                pass
            try:
                if old_clip:
                    pyperclip.copy(old_clip)
            except:
                pass
    if original_window:
        try:
            force_focus(original_window._hWnd)
        except:
            pass
    sessions = _load_sessions()
    clean_name = session_name.replace('сессию', '').replace('работу', '').strip()
    if not clean_name:
        clean_name = 'default'
    sessions[clean_name] = session_data
    _save_sessions(sessions)
    play_response_func()
def delete_session(session_name):
    sessions = _load_sessions()
    clean_name = session_name.replace('сессию', '').replace('работу', '').strip()
    if not clean_name:
        clean_name = 'default'
    if clean_name in sessions:
        del sessions[clean_name]
        _save_sessions(sessions)
        return True
    return False
def restore_session(session_name, play_response_func):
    sessions = _load_sessions()
    clean_name = session_name.lower()
    for word in ['восстанови', 'востанови', 'сессию']:
        clean_name = clean_name.replace(word, '')
    clean_name = clean_name.strip()
    if not clean_name:
        clean_name = 'default'
    if clean_name not in sessions:
        return
    session_data = sessions[clean_name]
    open_urls = set()
    windows = gw.getAllWindows()
    user32 = ctypes.windll.user32
    browser_hwnds = []
    for w in windows:
        if not w.visible or not w.title:
            continue
        hwnd = w._hWnd
        try:
            _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
            p_name = psutil.Process(w_pid).name().lower()
            title_l = w.title.lower()
            if p_name in BROWSER_PROCESSES or title_l.endswith((' - brave', ' - google chrome', ' - mozilla firefox', ' - edge')):
                browser_hwnds.append(w)
        except:
            pass
    if browser_hwnds:
        original_window = gw.getActiveWindow()
        old_clip = ''
        try:
            old_clip = pyperclip.paste()
        except:
            pass
        for w in browser_hwnds:
            hwnd = w._hWnd
            try:
                user32.keybd_event(18, 0, 0, 0)
                user32.keybd_event(18, 0, 2, 0)
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                time.sleep(0.4)
                mon_w = user32.GetSystemMetrics(0)
                mon_h = user32.GetSystemMetrics(1)
                is_fs = (w.width >= mon_w and w.height >= mon_h)
                if is_fs:
                    pyautogui.press('f11')
                    time.sleep(0.6)
                if w.width > 0 and w.height > 0 and (w.left != -32000):
                    pyautogui.click(w.left + w.width // 2, w.top + 15)
                time.sleep(0.2)
                urls_in_this_window = []
                for i in range(20):
                    pyperclip.copy('')
                    pyautogui.press('esc')
                    time.sleep(0.05)
                    pyautogui.hotkey('ctrl', 'l')
                    time.sleep(0.15)
                    pyautogui.hotkey('ctrl', 'c')
                    time.sleep(0.1)
                    current_url = pyperclip.paste().strip()
                    if not current_url:
                        pyautogui.press('f6')
                        time.sleep(0.15)
                        pyautogui.hotkey('ctrl', 'insert')
                        time.sleep(0.1)
                        current_url = pyperclip.paste().strip()
                    if not current_url or current_url in urls_in_this_window:
                        break
                    urls_in_this_window.append(current_url)
                    if current_url.lower().startswith(('http', 'file', 'chrome', 'edge')):
                        open_urls.add(current_url.rstrip('/'))
                    pyautogui.hotkey('ctrl', 'tab')
                    time.sleep(0.15)
            except:
                pass
            finally:
                try:
                    if is_fs:
                        pyautogui.press('f11')
                        time.sleep(0.3)
                except:
                    pass
        try:
            if old_clip:
                pyperclip.copy(old_clip)
        except:
            pass
        if original_window:
            try:
                user32.keybd_event(18, 0, 0, 0)
                user32.keybd_event(18, 0, 2, 0)
                if user32.IsIconic(original_window._hWnd):
                    user32.ShowWindow(original_window._hWnd, 9)
                user32.SetForegroundWindow(original_window._hWnd)
            except:
                pass
    ide_exes = {Path(ide['exe']).name.lower() for ide in session_data.get('ides', []) if ide.get('exe')}
    if ide_exes:
        killed = False
        my_pid = os.getpid()
        parent_pid = psutil.Process(my_pid).ppid() if my_pid > 0 else -1
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                p_info = proc.info
                p_name = p_info['name'].lower()
                p_pid = p_info['pid']
                if p_pid == my_pid or p_pid == parent_pid:
                    continue
                if p_name in ide_exes:
                    if 'antigravity' in p_name:
                        continue
                    proc.terminate()
                    killed = True
            except Exception:
                pass
        if killed:
            time.sleep(2.5)
    def _is_ide_open(exe_path: str, project_path: str) -> bool:
        try:
            exe_name = Path(exe_path).name.lower()
            proj_norm = str(Path(project_path)).lower()
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    if proc.info['name'].lower() != exe_name:
                        continue
                    cmdline = proc.info['cmdline'] or []
                    for arg in cmdline:
                        if str(Path(arg)).lower() == proj_norm:
                            return True
                except Exception:
                    pass
        except Exception:
            pass
        return False
    def _launch(item_type, data):
        try:
            if item_type == 'ide':
                if data.get('path') and data.get('exe'):
                    already = _is_ide_open(data['exe'], data['path'])
                    if already:
                        pass
                    else:
                        proc = subprocess.Popen([data['exe'], data['path']], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                        time.sleep(3.5)
                elif data.get('exe'):
                    subprocess.Popen([data['exe']], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            elif item_type == 'url':
                saved_url = data.get('url', '')
                normalized_saved = saved_url.rstrip('/')
                if normalized_saved in open_urls:
                    pass
                elif data.get('exe') and data.get('url'):
                    subprocess.Popen([data['exe'], data['url']], creationflags=8)
                else:
                    os.startfile(saved_url)
            elif item_type == 'app':
                if data.get('type') == 'folder' and data.get('path'):
                    os.startfile(data['path'])
                elif data.get('type') == 'folder_clsid' and data.get('path'):
                    subprocess.Popen(['explorer.exe', '/root,', str(data['path'])], creationflags=8)
                elif data.get('exe'):
                    subprocess.Popen([data['exe']], creationflags=8)
        except Exception as e:
            pass
    threads = []
    for ide in session_data.get('ides', []):
        threads.append(threading.Thread(target=_launch, args=('ide', ide)))
    for url_obj in session_data.get('urls', []):
        threads.append(threading.Thread(target=_launch, args=('url', url_obj)))
    for app in session_data.get('apps', []):
        threads.append(threading.Thread(target=_launch, args=('app', app)))
    for t in threads:
        t.start()
        time.sleep(0.5)
    play_response_func()
