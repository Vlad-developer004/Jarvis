import os
import re
import time
import win32con
import pygetwindow as gw
from actions.windows import send_hardware_key, _ensure_en_layout, _restore_layout
from core.system import force_foreground

def search_youtube_candidates(query: str, limit: int = 5) -> list[dict]:
    """Top `limit` YouTube search results as [{'id','title','url','thumbnail'}].

    Uses yt_dlp's flat search extraction (same dependency/technique as
    _get_url_by_search below) instead of regex-scraping the search results
    page HTML — gives clean titles + thumbnails, needed to let the user pick
    when several results look like the same song (see candidates_are_ambiguous).
    Caller is responsible for appending any "песня"/"видео" disambiguator to
    `query` beforehand — this function doesn't second-guess intent.
    """
    try:
        import yt_dlp
    except Exception:
        return []
    opts = {
        'quiet': True, 'no_warnings': True, 'extract_flat': True, 'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'ytsearch{limit}:{query}', download=False)
    except Exception:
        return []
    entries = (info or {}).get('entries') or []
    results = []
    for e in entries:
        vid = e.get('id')
        if not vid:
            continue
        thumbs = e.get('thumbnails') or []
        results.append({
            'id': vid,
            'title': e.get('title') or '',
            'url': f'https://www.youtube.com/watch?v={vid}',
            'thumbnail': thumbs[-1].get('url') if thumbs else None,
        })
    return results

def _normalize_title_for_similarity(title: str) -> str:
    t = re.sub(r'[\(\[][^)\]]*[\)\]]', '', title or '')
    return re.sub(r'\s+', ' ', t).strip().lower()

def candidates_are_ambiguous(candidates: list[dict], threshold: int = 85) -> bool:
    """True if 2+ of the top results normalize to (near-)the same title —
    e.g. official video / lyrics / live / audio versions of one song —
    meaning auto-picking the first result is a real guess, not an obvious win.
    Bracketed noise like "(Official Video)"/"(Lyrics)" is stripped first so
    those don't count as a difference.

    With 0 or 1 candidates there's nothing to disambiguate — that's an
    explicit False here (not just "falls out of the loop"), so the caller
    (core/handler/yt_play.py) always just plays the single result directly
    instead of ever popping the picker for a single-video search."""
    if len(candidates) < 2:
        return False
    from rapidfuzz import fuzz
    top_norm = _normalize_title_for_similarity(candidates[0]['title'])
    if not top_norm:
        return False
    return any(
        fuzz.token_sort_ratio(top_norm, _normalize_title_for_similarity(c['title'])) >= threshold
        for c in candidates[1:]
    )

def _get_url_by_search(title: str) -> str | None:
    if not title: return None
    import yt_dlp
    search_q = title.replace(' - YouTube', '').replace('YouTube', '').strip()
    if len(search_q) < 5: return None
    print(f'[_get_url_by_search] searching for: {search_q!r}', flush=True)
    opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'ytsearch1:{search_q}', download=False)
            if info and 'entries' in info and info['entries']:
                url = info['entries'][0].get('url')
                if url:
                    if not url.startswith('http'):
                        url = f"https://www.youtube.com/watch?v={url}"
                    print(f'[_get_url_by_search] found: {url}', flush=True)
                    return url
    except Exception as e:
        print(f'[_get_url_by_search] error: {e}', flush=True)
    return None

def _get_url_from_history(window_title: str = '') -> str | None:
    import sqlite3, shutil, tempfile
    from pathlib import Path
    profiles = [
        Path.home() / 'AppData/Local/BraveSoftware/Brave-Browser/User Data',
        Path.home() / 'AppData/Local/Google/Chrome/User Data',
        Path.home() / 'AppData/Local/Microsoft/Edge/User Data',
    ]
    best_url, best_time = None, 0
    title_match_url = None
    title_hint = window_title.replace(' - YouTube', '').replace('YouTube', '').replace(' - Brave', '').replace(' - Chrome', '').strip()
    title_hint_clean = title_hint.lower() if title_hint else ''
    
    for base in profiles:
        if not base.exists():
            continue
        for hist_path in base.glob('*/History'):
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmpf:
                    tmp = Path(tmpf.name)
                shutil.copy2(hist_path, tmp)
                with sqlite3.connect(tmp) as con:
                    rows = con.execute(
                        "SELECT url, title, last_visit_time FROM urls "
                        "WHERE url LIKE '%youtube.com/watch%' "
                        "ORDER BY last_visit_time DESC LIMIT 30"
                    ).fetchall()
                for url, title, ts in rows:
                    if ts > best_time:
                        best_url, best_time = url, ts
                    if title_hint_clean and title and title_hint_clean in title.lower() and not title_match_url:
                        title_match_url = url
            except Exception:
                pass
            finally:
                if tmp is not None:
                    try:
                        time.sleep(0.1)
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
    
    result = title_match_url or best_url
    print(f'[_get_url_from_history] hint={title_hint_clean!r} match={title_match_url!r} best={best_url!r}', flush=True)
    
    # Fallback to search if history is useless or title was specific but didn't match history
    if not result and len(title_hint_clean) > 8:
        result = _get_url_by_search(title_hint)
        
    return result
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
        print('[_get_current_url] no browser found', flush=True)
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
        print(f'[_get_current_url] hwnd={hwnd} actual_fg={actual_fg} match={actual_fg==hwnd}', flush=True)
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
            print(f'[_get_current_url] after F11: left={left} top={top}', flush=True)
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
        print(f'[_get_current_url] ctrl+l got: {url!r}', flush=True)
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
            print(f'[_get_current_url] alt+d got: {url!r}', flush=True)
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)
        print(f'[_get_current_url] got: {url!r}', flush=True)
        if url.startswith('http'):
            return url
    except Exception as e:
        print(f'[_get_current_url] error: {e}', flush=True)
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
def _open_youtube_url(url: str, background: bool = False):
    import subprocess
    from pathlib import Path

    browser_paths = [
        Path(r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe'),
        Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
        Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'),
        Path.home() / r'AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe',
        Path.home() / r'AppData\Local\Google\Chrome\Application\chrome.exe',
    ]
    browser_exe = next((str(p) for p in browser_paths if p.exists()), None)

    # If just opening YouTube, open in app-mode window (works with or without PWA installed)
    if url == 'https://www.youtube.com' and browser_exe:
        subprocess.Popen([browser_exe, '--app=https://www.youtube.com'])
        return True

    # If playing a specific video/song, force a new browser tab
    # (Because Chromium completely blocks CLI deep-linking into existing PWAs)
    if browser_exe:
        if background:
            # Open without stealing focus from the game (SW_SHOWNOACTIVATE = 4)
            si = subprocess.STARTUPINFO()
            si.dwFlags = subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 4
            subprocess.Popen([browser_exe, '--new-tab', url], startupinfo=si)
        else:
            subprocess.Popen([browser_exe, '--new-tab', url])
    else:
        import os
        try:
            os.startfile(url)
        except Exception:
            import webbrowser
            webbrowser.open(url)
    return True
def open_youtube_channel(channel_name: str, background: bool = False):
    import urllib.parse
    import urllib.request
    import re

    q_encoded = urllib.parse.quote(channel_name)
    url = None
    try:
        req = urllib.request.Request(
            f'https://www.youtube.com/results?search_query={q_encoded}&sp=EgIQAg%3D%3D',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                     'Accept-Language': 'en-US,en;q=0.9',
                     # Bypasses the EU cookie-consent interstitial, which otherwise
                     # returns a consent page with no channel data in the markup.
                     'Cookie': 'CONSENT=YES+1'}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            html = r.read().decode('utf-8', errors='ignore')
            match = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html)
            if match:
                url = f'https://www.youtube.com{match.group(1)}'
            else:
                match = re.search(r'"channelId":"(UC[^"]+)"', html)
                if match:
                    url = f'https://www.youtube.com/channel/{match.group(1)}'
    except Exception as e:
        print(f'[open_youtube_channel] error: {e}', flush=True)

    if url:
        _open_youtube_url(url, background=background)
    else:
        _open_youtube_url(f'https://www.youtube.com/results?search_query={q_encoded}&sp=EgIQAg%3D%3D', background=background)
    return (True, 'OK')
def download_youtube_video():
    import pyperclip
    import yt_dlp
    url = _get_current_url()
    
    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        # NEW: Try to find by active window title
        active_win = gw.getActiveWindow()
        if active_win and active_win.title:
            url = _get_url_from_history(active_win.title)
            
        if not url or ('youtube.com' not in url and 'youtu.be' not in url):
            url = pyperclip.paste() or ''
            if 'youtube.com' not in url and 'youtu.be' not in url:
                return (False, 'Не удалось найти ссылку на видео')
    import re as _re
    url = _re.sub(r'[&?]list=[^&]*', '', url)
    url = _re.sub(r'[&?]start_radio=[^&]*', '', url)
    url = _re.sub(r'[&?]index=[^&]*', '', url)
    save_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return (True, 'OK')
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = str(e)
        if 'HTTP Error 403' in msg:
            return (False, 'Доступ запрещён, видео защищено')
        if 'HTTP Error 429' in msg:
            return (False, 'YouTube заблокировал запрос, попробуй позже')
        if 'not a valid URL' in msg:
            return (False, 'Не удалось получить ссылку на видео')
        return (False, 'Ошибка скачивания')
def control_youtube(action: str, amount: int=5):
    import win32gui
    import win32con
    import pyautogui
    from core.system.windows import get_hwnd_process_name
    
    # 1. Robust window search
    all_windows = []
    def _enum_cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if title or get_hwnd_process_name(hwnd):
            all_windows.append(hwnd)
        return True
    
    try:
        win32gui.EnumWindows(_enum_cb, None)
    except:
        pass

    fg_hwnd = win32gui.GetForegroundWindow()
    browser_exes = ('brave.exe', 'chrome.exe', 'msedge.exe', 'opera.exe', 'browser.exe', 'firefox.exe')
    media_kw = ('youtube', 'ютуб', 'video', 'видео', 'netflix', 'twitch', 'rutube')

    # Score every candidate: foreground > YouTube title > any browser
    candidates: list[tuple[int, int]] = []  # (score, hwnd)
    for hwnd in all_windows:
        title = win32gui.GetWindowText(hwnd).lower()
        p_name = get_hwnd_process_name(hwnd)
        if p_name not in browser_exes:
            continue
        score = 0
        if hwnd == fg_hwnd:
            score += 10_000   # user was here when they spoke
        if any(k in title for k in media_kw):
            score += 100      # has media-related title
        if title:
            score += 1        # prefer windows with any title over empty
        candidates.append((score, hwnd))

    if not candidates:
        return False

    candidates.sort(reverse=True)
    target_hwnd = candidates[0][1]

    # 2. Silent vs Focused control
    if action == 'play_pause':
        # Silent control: WM_APPCOMMAND (no focus needed)
        win32gui.SendMessage(target_hwnd, 0x0319, 0, 14 << 16)
        return True

    # For seek and fullscreen: save foreground, focus browser briefly, restore.
    # This avoids permanently stealing focus while still delivering key events.
    prev_hwnd = win32gui.GetForegroundWindow()
    if win32gui.IsIconic(target_hwnd):
        win32gui.ShowWindow(target_hwnd, 9)
    force_foreground(target_hwnd)
    time.sleep(0.12)
    if action == 'fullscreen':
        hkl = _ensure_en_layout()
        send_hardware_key(70)
        _restore_layout(hkl)
    elif action == 'forward':
        # YouTube: L = +10s, Right arrow = +5s. Use L for the bulk of a big seek
        # so a 2-minute jump is ~12 keypresses instead of 24 — fewer, more reliable.
        amount = max(amount, 5)
        tens, rem = divmod(amount, 10)
        fives = rem // 5 or (1 if tens == 0 else 0)
        hkl = _ensure_en_layout()
        for _ in range(tens):
            send_hardware_key(0x4C)  # VK_L = +10s
            time.sleep(0.05)
        for _ in range(fives):
            send_hardware_key(win32con.VK_RIGHT)
            time.sleep(0.05)
        _restore_layout(hkl)
    elif action == 'backward':
        amount = max(amount, 5)
        tens, rem = divmod(amount, 10)
        fives = rem // 5 or (1 if tens == 0 else 0)
        hkl = _ensure_en_layout()
        for _ in range(tens):
            send_hardware_key(0x4A)  # VK_J = -10s
            time.sleep(0.05)
        for _ in range(fives):
            send_hardware_key(win32con.VK_LEFT)
            time.sleep(0.05)
        _restore_layout(hkl)
    elif action == 'next_video':
        from actions.windows import send_hotkey_hardware
        hkl = _ensure_en_layout()
        send_hotkey_hardware(0x10, 0x4E)
        _restore_layout(hkl)
    elif action == 'prev_video':
        from actions.windows import send_hotkey_hardware
        hkl = _ensure_en_layout()
        send_hotkey_hardware(0x10, 0x50)
        _restore_layout(hkl)
    elif action == 'close':
        pyautogui.hotkey('ctrl', 'w')

    # Restore previous focus so the browser disappears from foreground
    time.sleep(0.05)
    if prev_hwnd and prev_hwnd != target_hwnd:
        try:
            force_foreground(prev_hwnd)
        except Exception:
            pass
    return True
def save_current_video():
    from config_pack.config import MAX_SAVED_VIDEOS
    import ctypes as _ctypes
    import win32process as _w32p
    import psutil as _psutil
    _BROWSER_PROCS = {'brave.exe', 'chrome.exe', 'firefox.exe', 'msedge.exe'}
    _user32 = _ctypes.windll.user32
    _mon_w = _user32.GetSystemMetrics(0)
    _mon_h = _user32.GetSystemMetrics(1)
    _browser_title = ''
    _is_fs = False
    _is_pwa = False
    for _w in gw.getAllWindows():
        if not _w.visible or not _w.title or _w.width <= 0:
            continue
        try:
            _, _pid = _w32p.GetWindowThreadProcessId(_w._hWnd)
            _pname = _psutil.Process(_pid).name().lower()
            if _pname not in _BROWSER_PROCS:
                continue
            _title_lower = _w.title.lower()
            _is_pwa_win = ('youtube' not in _title_lower and
                           'brave' not in _title_lower and
                           'chrome' not in _title_lower and
                           _w.width < _mon_w)
            _is_fs_win = (_w.width >= _mon_w and _w.height >= _mon_h)
            if _is_fs_win or _is_pwa_win:
                _browser_title = _w.title
                _is_fs = _is_fs_win
                _is_pwa = _is_pwa_win
                break
            if not _browser_title:
                _browser_title = _w.title
        except Exception:
            pass
    if _is_fs or _is_pwa:
        url = _get_url_from_history(_browser_title)
    else:
        url = _get_current_url()
        if not url:
            url = _get_url_from_history(_browser_title)
    print(f'[save_current_video] url={url!r}', flush=True)
    if not url or ('youtube.com' not in url and 'youtu.be' not in url):
        return False
    import re as _re2
    url = _re2.sub(r'[&?](list|index|start_radio|rv|pp)=[^&]*', '', url).rstrip('?&')
    save_path = os.path.join(os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')
    lines = []
    if os.path.exists(save_path):
        with open(save_path, 'r', encoding='utf-8') as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    for line in lines:
        if ' - ' in line and line.split(' - ', 1)[1].strip() == url:
            return True
    lines.append(f'{time.strftime("%Y-%m-%d %H:%M:%S")} - {url}')
    try:
        from config_pack.config import _read_max_saved_videos
        _limit = _read_max_saved_videos()
    except Exception:
        _limit = MAX_SAVED_VIDEOS
    lines = lines[-_limit:]
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return True
def open_last_watched_video(background: bool = False) -> bool:
    import webbrowser, sqlite3, shutil, tempfile, glob
    from pathlib import Path
    profiles = [Path.home() / 'AppData/Local/BraveSoftware/Brave-Browser/User Data', Path.home() / 'AppData/Local/Google/Chrome/User Data', Path.home() / 'AppData/Local/Microsoft/Edge/User Data']
    candidates: list[Path] = []
    for base in profiles:
        candidates += base.glob('*/History') if base.exists() else []
    best_url: str | None = None
    best_time: int = 0
    for hist_path in candidates:
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmpf:
                tmp = Path(tmpf.name)
            shutil.copy2(hist_path, tmp)
            with sqlite3.connect(tmp) as con:
                row = con.execute("SELECT url, last_visit_time FROM urls WHERE url LIKE '%youtube.com/watch%' ORDER BY last_visit_time DESC LIMIT 1").fetchone()
            if row and row[1] > best_time:
                best_url, best_time = (row[0], row[1])
        except Exception:
            pass
        finally:
            if tmp is not None:
                try:
                    time.sleep(0.2)
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
    if best_url:
        _open_youtube_url(best_url, background=background)
        return True
    _open_youtube_url('https://www.youtube.com/feed/history', background=background)
    return True
def open_saved_video(index: int = -1, background: bool = False):
    save_path = os.path.join(os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')
    print(f'[open_saved_video] index={index}, path={save_path}', flush=True)
    if not os.path.exists(save_path):
        return False
    with open(save_path, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f.read().splitlines() if l.strip() and ' - ' in l]
    if not lines:
        return False
    if index <= 0:
        index = 1
    idx = len(lines) - index
    if idx < 0 or idx >= len(lines):
        return False
    line = lines[idx]
    url = line.split(' - ', 1)[1].strip()
    _open_youtube_url(url, background=background)
    return True
