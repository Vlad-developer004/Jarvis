import os
import time
import subprocess
import pygetwindow as gw
from core.system import force_foreground
from actions.system_parts.input_hw import _switch_to_hwnd
def _find_latest_video() -> str | None:
    VIDEO_EXTS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.wmv'}
    search_dirs = [os.path.join(os.environ['USERPROFILE'], 'Videos'), os.path.join(os.environ['USERPROFILE'], 'Downloads')]
    latest_file = None
    latest_time = 0
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        base_depth = search_dir.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(search_dir):
            if root.count(os.sep) - base_depth >= 2:
                dirs[:] = []
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() not in VIDEO_EXTS:
                    continue
                full_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(full_path)
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_file = full_path
                except OSError:
                    continue
    return latest_file
def _find_clipchamp_exe() -> str | None:
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', '(Get-AppxPackage -Name Clipchamp.Clipchamp).InstallLocation'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=134217728,
        )
        loc = result.stdout.strip()
        if loc:
            exe = os.path.join(loc, 'Clipchamp.exe')
            if os.path.exists(exe):
                return exe
    except Exception:
        pass
    return None
def _activate_clipchamp_for_file(aumid: str, video_path: str) -> bool:
    import ctypes
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    class GUID(ctypes.Structure):
        _fields_ = [('Data1', ctypes.c_ulong), ('Data2', ctypes.c_ushort), ('Data3', ctypes.c_ushort), ('Data4', ctypes.c_ubyte * 8)]
    def _guid(s):
        g, s = (GUID(), s.strip('{}'))
        p = s.split('-')
        g.Data1, g.Data2, g.Data3 = (int(p[0], 16), int(p[1], 16), int(p[2], 16))
        for i, b in enumerate(bytes.fromhex(p[3] + p[4])):
            g.Data4[i] = b
        return g
    IID_IShellItem = _guid('{43826D1E-E718-42EE-BC55-A1E261C37BFE}')
    IID_IShellItemArray = _guid('{B63EA76D-1F85-456F-A19C-48159EFA858B}')
    CLSID_AppActMgr = _guid('{45BA127D-10A8-46EA-8AB7-56EA9078943C}')
    IID_IAppActMgr = _guid('{2e941141-7f97-4756-ba1d-9decde894a3d}')
    ole32.CoInitializeEx(None, 0)
    try:
        p_item = ctypes.c_void_p()
        if shell32.SHCreateItemFromParsingName(video_path, None, ctypes.byref(IID_IShellItem), ctypes.byref(p_item)) != 0:
            return False
        p_arr = ctypes.c_void_p()
        if shell32.SHCreateShellItemArrayFromShellItem(p_item, ctypes.byref(IID_IShellItemArray), ctypes.byref(p_arr)) != 0:
            return False
        p_mgr = ctypes.c_void_p()
        if ole32.CoCreateInstance(ctypes.byref(CLSID_AppActMgr), None, 4, ctypes.byref(IID_IAppActMgr), ctypes.byref(p_mgr)) != 0:
            return False
        vtbl = ctypes.cast(ctypes.cast(p_mgr, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        ActivateForFile = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong))(vtbl[4])
        pid = ctypes.c_ulong()
        hr = ActivateForFile(p_mgr, aumid, p_arr, None, ctypes.byref(pid))
        return hr == 0
    except Exception:
        return False
    finally:
        ole32.CoUninitialize()
def _open_in_clipchamp(video_path: str) -> tuple[bool, str]:
    import threading
    import shutil
    fname = os.path.basename(video_path)
    aumid = subprocess.run(
        ['powershell', '-NoProfile', '-Command', "(Get-StartApps | Where-Object {$_.Name -like '*Clipchamp*'}).AppId"],
        capture_output=True,
        text=True,
        timeout=6,
        creationflags=134217728,
    ).stdout.strip()
    def _try_activate(path: str) -> bool:
        return bool(aumid and _activate_clipchamp_for_file(aumid, path))
    if _try_activate(video_path):
        return (True, fname)
    _FFMPEG = next((p for p in [shutil.which('ffmpeg') or '', 'C:\\Program Files\\obs-studio\\bin\\64bit\\ffmpeg.exe', 'C:\\ffmpeg\\bin\\ffmpeg.exe'] if p and os.path.exists(p)), None)
    if _FFMPEG and os.path.splitext(video_path)[1].lower() != '.mp4':
        temp_mp4 = os.path.splitext(video_path)[0] + '__cc.mp4'
        activated = False
        try:
            if os.path.exists(temp_mp4):
                os.unlink(temp_mp4)
            subprocess.run([_FFMPEG, '-i', video_path, '-c', 'copy', '-movflags', 'faststart', '-y', temp_mp4], capture_output=True, timeout=60, creationflags=134217728)
            if os.path.exists(temp_mp4):
                activated = _try_activate(temp_mp4)
                if activated:
                    threading.Thread(target=lambda p=temp_mp4: (time.sleep(15), os.path.exists(p) and os.unlink(p)), daemon=True).start()
                    return (True, fname)
        except Exception:
            pass
        finally:
            if not activated and os.path.exists(temp_mp4):
                try:
                    os.unlink(temp_mp4)
                except Exception:
                    pass
    ps = f'$f="{video_path.replace(chr(39), "")}";$sh=New-Object -ComObject Shell.Application;$it=$sh.Namespace([IO.Path]::GetDirectoryName($f)).ParseName([IO.Path]::GetFileName($f));foreach($v in $it.Verbs()){{  if($v.Name -match "Clipchamp|клипчамп"){{  $v.DoIt();exit 0}}  }}  ;exit 1'
    if subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=8, creationflags=134217728).returncode == 0:
        return (True, fname)
    try:
        exe = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "$p=Get-AppxPackage|?{$_.Name -like '*Clipchamp*'}|Select -First 1;if($p){ls $p.InstallLocation -Filter Clipchamp.exe -r 2>$null|Select -First 1 -Exp FullName}"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=134217728,
        ).stdout.strip()
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, video_path])
            time.sleep(3.0)
            wins = [w for w in gw.getAllWindows() if 'clipchamp' in w.title.lower() and w.visible]
            if wins:
                force_foreground(wins[0]._hWnd)
                return (True, fname)
    except Exception:
        pass
    if not aumid:
        return (False, 'Clipchamp не установлен')
    import pyautogui
    import win32gui
    import win32api
    import win32con as _wc
    existing = [w for w in gw.getAllWindows() if 'clipchamp' in w.title.lower() and w.visible]
    if not existing:
        subprocess.Popen(['powershell', '-NoProfile', '-Command', f'Start-Process "shell:AppsFolder\\{aumid}"'], creationflags=134217728)
        for _ in range(20):
            time.sleep(0.5)
            existing = [w for w in gw.getAllWindows() if 'clipchamp' in w.title.lower() and w.visible]
            if existing:
                break
    if not existing:
        return (False, 'Clipchamp не запустился')
    hwnd = existing[0]._hWnd
    force_foreground(hwnd)
    time.sleep(3.5)
    def _find_file_dialog():
        found = []
        win32gui.EnumWindows(lambda h, _: found.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == '#32770' else None, None)
        return found[0] if found else None
    def _fill_dialog(dlg):
        force_foreground(dlg)
        time.sleep(0.3)
        edits = []
        win32gui.EnumChildWindows(dlg, lambda h, _: edits.append(h) if win32gui.GetClassName(h) == 'Edit' else None, None)
        if edits:
            win32api.SendMessage(edits[-1], _wc.WM_SETTEXT, 0, video_path)
        else:
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')
    rect = win32gui.GetWindowRect(hwnd)
    x, y, x2, y2 = rect
    ww, wh = (x2 - x, y2 - y)
    for cx, cy in [(x + int(ww * 0.22), y + int(wh * 0.3)), (x + int(ww * 0.22), y + int(wh * 0.22)), (x + int(ww * 0.5), y + int(wh * 0.4))]:
        force_foreground(hwnd)
        time.sleep(0.15)
        pyautogui.click(cx, cy)
        for _ in range(8):
            time.sleep(0.5)
            dlg = _find_file_dialog()
            if dlg:
                _fill_dialog(dlg)
                return (True, fname)
    force_foreground(hwnd)
    time.sleep(0.5)
    for cx, cy in [(x + int(ww * 0.12), y + int(wh * 0.13)), (x + int(ww * 0.08), y + int(wh * 0.15)), (x + int(ww * 0.22), y + int(wh * 0.1)), (x + int(ww * 0.12), y + int(wh * 0.2)), (x + ww // 2, y + int(wh * 0.45))]:
        force_foreground(hwnd)
        time.sleep(0.2)
        pyautogui.click(cx, cy)
        for _ in range(4):
            time.sleep(0.5)
            dlg = _find_file_dialog()
            if dlg:
                _fill_dialog(dlg)
                return (True, fname)
    return (False, 'Не удалось импортировать файл в Clipchamp')
_MEDIA_TITLES = ('vlc', 'media player', 'wmplayer', 'mpc', 'groove', 'кино', 'films', 'potplayer', 'zeno', 'windows media')
def _focus_new_media_window(existing_hwnds: set, timeout: float = 6.0):
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.3)
        for w in gw.getAllWindows():
            if w.visible and w._hWnd not in existing_hwnds and w.title:
                title = w.title.lower()
                if any((kw in title for kw in _MEDIA_TITLES)) or any((title.endswith(ext) for ext in ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v'))):
                    force_foreground(w._hWnd)
                    return True
    return False
def open_last_video_file(app: str = 'default') -> tuple[bool, str]:
    try:
        latest = _find_latest_video()
        if not latest:
            return (False, 'Видеофайлы не найдены')
        fname = os.path.basename(latest)
        if app == 'clipchamp':
            return _open_in_clipchamp(latest)
        elif app == 'vlc':
            for vlc_path in ['C:\\Program Files\\VideoLAN\\VLC\\vlc.exe', 'C:\\Program Files (x86)\\VideoLAN\\VLC\\vlc.exe']:
                if os.path.exists(vlc_path):
                    subprocess.Popen([vlc_path, latest])
                    return (True, fname)
            os.startfile(latest)
            return (True, fname)
        else:
            existing = {w._hWnd for w in gw.getAllWindows() if w.visible}
            os.startfile(latest)
            _focus_new_media_window(existing, timeout=6.0)
            return (True, fname)
    except Exception as e:
        return (False, str(e))
def open_latest_clipchamp_video() -> tuple[bool, str]:
    try:
        videos_dir = os.path.join(os.environ['USERPROFILE'], 'Videos')
        if not os.path.isdir(videos_dir):
            return (False, 'Папка Videos не найдена')
        latest_file = None
        latest_time = 0
        base_depth = videos_dir.rstrip(os.path.sep).count(os.path.sep)
        for root, dirs, files in os.walk(videos_dir):
            if root.count(os.path.sep) - base_depth >= 2:
                dirs[:] = []
            for file in files:
                if not file.lower().endswith('.mp4'):
                    continue
                fp = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(fp)
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_file = fp
                except OSError:
                    continue
        if not latest_file:
            return (False, 'Файлы не найдены')
        os.startfile(latest_file)
        return (True, f'Окрыто видео: {os.path.basename(latest_file)}')
    except Exception as e:
        return (False, str(e))
from core.system.windows import get_hwnd_process_name

def send_play_pause_to_video(prefer: str | None = None, action: str = 'toggle') -> bool:
    import win32gui
    import win32con
    
    # Removed the global pycaw check. It was flawed because Jarvis's own TTS response 
    # (or background apps like Discord) made it falsely believe media was already playing,
    # causing explicit 'play' commands to be incorrectly skipped.

    # 14 = Play/Pause toggle, 46 = Play, 47 = Pause
    cmd_val = 14
    if action == 'play': cmd_val = 46
    elif action == 'pause': cmd_val = 47
    
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.01
    except Exception:
        pyautogui = None

    all_windows = []
    def _enum_cb(hwnd, _):
        # We check both visible and minimized (Iconic) windows
        title = win32gui.GetWindowText(hwnd)
        if title or get_hwnd_process_name(hwnd):
            all_windows.append(hwnd)
        return True
    
    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception as e:
        print(f"[Media] EnumWindows error: {e}", flush=True)

    if not all_windows:
        print("[Media] No windows found at all. Global fallback.", flush=True)
        if pyautogui: pyautogui.press('playpause'); return True
        return False

    yt_pwa_wins = []
    yt_browser_wins = []
    browser_media_wins = []
    pure_browser_wins = []
    general_media_wins = []
    
    browsers = ('brave', 'chrome', 'msedge', 'performance', 'opera', 'yandex', 'firefox')
    browser_exes = ('brave.exe', 'chrome.exe', 'msedge.exe', 'opera.exe', 'browser.exe', 'firefox.exe')
    media_kw = ('video', 'видео', 'netflix', 'twitch', 'vk video', 'вк видео', 'rutube', 'rtvi', 'spotify', 'soundcloud', 'ядро', 'музыка', 'music', 'player')
    junk_kw = ('msctfime ui', 'default ime', 'dde server', 'mediametadata', 'gdi+ window', 'olemainthreadwndword', 'msctfime ui')

    print(f"[Media] Scanning {len(all_windows)} windows...", flush=True)

    for hwnd in all_windows:
        try:
            p_name = get_hwnd_process_name(hwnd)
            t = win32gui.GetWindowText(hwnd) or ""
            tl = t.lower()
            
            # Skip empty or junk windows early
            if not tl and p_name in browser_exes: continue
            if any(jk in tl for jk in junk_kw): continue
            
            is_browser = any(k in tl for k in browsers) or p_name in browser_exes
            is_youtube = 'youtube' in tl or 'ютуб' in tl
            is_pwa = is_youtube and not any(k in tl for k in browsers)
            is_generic_media = any(k in tl for k in media_kw)
            is_minimized = win32gui.IsIconic(hwnd)

            if is_pwa:
                yt_pwa_wins.append((hwnd, t, p_name, is_minimized, True))
            elif is_youtube:
                yt_browser_wins.append((hwnd, t, p_name, is_minimized, True))
            elif is_browser:
                if is_generic_media:
                    browser_media_wins.append((hwnd, t, p_name, is_minimized, False))
                elif len(t) > 3: # Must have some meaningful title to be a tab
                    pure_browser_wins.append((hwnd, t, p_name, is_minimized, False))
            elif is_generic_media:
                general_media_wins.append((hwnd, t, p_name, is_minimized, False))
        except Exception:
            continue

    print(f"[Media] Prefer: {prefer}", flush=True)
    print(f"[Media] Categorized: YTPWA={len(yt_pwa_wins)}, YTBrowser={len(yt_browser_wins)}, BrowserMedia={len(browser_media_wins)}, PureBrowser={len(pure_browser_wins)}, General={len(general_media_wins)}", flush=True)

    # Heuristic: Sort by title length and minimized state
    def _rank_and_sort(lst, boost_minimized=False):
        def score(item):
            s = len(item[1])
            if boost_minimized and item[3]: # item[3] is is_minimized
                s += 1000
            return s
        lst.sort(key=score, reverse=True)
        return lst

    boost_min = (prefer == 'browser')
    yt_pwa_wins = _rank_and_sort(yt_pwa_wins, boost_minimized=(prefer == 'youtube'))
    yt_browser_wins = _rank_and_sort(yt_browser_wins, boost_minimized=boost_min)
    browser_media_wins = _rank_and_sort(browser_media_wins, boost_minimized=boost_min)
    pure_browser_wins = _rank_and_sort(pure_browser_wins, boost_minimized=boost_min)
    general_media_wins = _rank_and_sort(general_media_wins, boost_minimized=False)

    if prefer == 'youtube':
        target_objs = yt_pwa_wins or yt_browser_wins or browser_media_wins or pure_browser_wins or general_media_wins
    elif prefer == 'browser':
        target_objs = yt_browser_wins or browser_media_wins or pure_browser_wins or yt_pwa_wins or general_media_wins
    else:
        # Default global fallback priority
        target_objs = yt_pwa_wins or yt_browser_wins or browser_media_wins or general_media_wins or pure_browser_wins

    if not target_objs:
        print("[Media] No targeted windows identified. Global fallback.", flush=True)
        if pyautogui: pyautogui.press('playpause'); return True
        return False

    success = False
    for hwnd, title, p_name, is_min, is_yt in target_objs[:5]:
        try:
            status = "Minimized" if is_min else "Visible"
            print(f"[Media] Targeting: {title} ({p_name}, {status}, HWND: {hwnd}, Action: {action})", flush=True)
            
            # Chromium browsers handle WM_APPCOMMAND globally per profile.
            # If the user explicitly asks for youtube or browser, we bypass the global media
            # controller by foregrounding the specific window and sending the 'k' key.
            if prefer in ('youtube', 'browser') and is_yt and pyautogui:
                if is_min:
                    win32gui.ShowWindow(hwnd, 9)
                from core.system import force_foreground
                force_foreground(hwnd)
                time.sleep(0.15)
                pyautogui.press('k')
            else:
                root_hwnd = win32gui.GetAncestor(hwnd, 2) 
                win32gui.PostMessage(root_hwnd, 0x0319, 0, cmd_val << 16)
            
            success = True
            break 
        except Exception as e:
            print(f"[Media] Error targeting {hwnd}: {e}", flush=True)
            continue

    if not success and pyautogui:
        print("[Media] Silent target failed. Global fallback.", flush=True)
        pyautogui.press('playpause')
        return True

    return success
