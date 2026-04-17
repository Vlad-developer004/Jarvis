import os
import json
import time
import subprocess
import logging
from pathlib import Path
import pygetwindow as gw
from core.system import force_foreground
_log = logging.getLogger('jarvis.app_launcher')
def _find_steam_via_registry() -> str | None:
    try:
        import winreg
        for key_path in ('SOFTWARE\\WOW6432Node\\Valve\\Steam', 'SOFTWARE\\Valve\\Steam'):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    install_path, _ = winreg.QueryValueEx(key, 'InstallPath')
                    exe = os.path.join(str(install_path), 'steam.exe')
                    if os.path.exists(exe):
                        _log.info('Steam found via registry: %s', exe)
                        return exe
            except (FileNotFoundError, OSError):
                continue
    except Exception as e:
        _log.warning('Registry lookup for Steam failed: %s', e)
    return None
BRAVE_PATH = 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe'
_LOCALAPP = os.environ.get('LOCALAPPDATA', '')
_APPDATA = os.environ.get('APPDATA', '')
_EXE_CACHE_PATH = Path('data') / 'exe_cache.json'
_exe_cache: dict[str, str] = {}
def _load_exe_cache():
    global _exe_cache
    try:
        if _EXE_CACHE_PATH.exists():
            _exe_cache = json.loads(_EXE_CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        _exe_cache = {}
def _save_exe_cache():
    try:
        _EXE_CACHE_PATH.write_text(json.dumps(_exe_cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass
_load_exe_cache()
APPS = {
    'explorer': {'type': 'shell', 'cmd': 'explorer', 'keywords': ['explorer', 'проводник']},
    'browser': {'type': 'exe', 'path': BRAVE_PATH, 'keywords': ['brave']},
    'youtube': {
        'type': 'lnk',
        'folders': ['Brave Apps', 'Програми Brave', 'Chrome Apps', 'Приложения Chrome'],
        'name': 'YouTube',
        'keywords': ['youtube'],
        'url': 'https://www.youtube.com'
    },
    'discord': {
        'type': 'exe_search',
        'names': ['Discord'],
        'exe': 'Discord.exe',
        'update_dir': os.path.join(_LOCALAPP, 'Discord')
    },
    'antigravity': {
        'type': 'exe_search',
        'names': ['Antigravity', 'Cursor', 'Code'],
        'exe': 'Cursor.exe'
    },
    'obs': {
        'type': 'exe_search',
        'names': ['OBS'],
        'exe': 'obs64.exe',
        'search_dirs': ['C:\\Program Files\\obs-studio\\bin\\64bit']
    },
    'photoshop': {
        'type': 'exe_search',
        'names': ['Photoshop'],
        'exe': 'Photoshop.exe',
        'search_dirs': ['C:\\Program Files\\Adobe', 'C:\\Program Files (x86)\\Adobe']
    },
    'steam': {
        'type': 'exe_search',
        'names': ['Steam'],
        'exe': 'steam.exe',
        'search_dirs': ['C:\\Program Files (x86)\\Steam', 'C:\\Program Files\\Steam', 'D:\\Steam', 'E:\\Steam'],
        'protocol_fallback': 'steam://open/main'
    },
    'vscode': {
        'type': 'exe_search',
        'names': ['Visual Studio Code', 'Code', 'VSCode'],
        'exe': 'Code.exe'
    },
    'epic': {
        'type': 'exe_search',
        'names': ['Epic Games'],
        'exe': 'EpicGamesLauncher.exe',
        'search_dirs': [
            'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64',
            'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win64',
            os.path.join(_LOCALAPP, 'EpicGamesLauncher\\Portal\\Binaries\\Win64')
        ]
    },
    'xbox': {
        'type': 'protocol',
        'uri': 'xbox:',
        'names': ['Xbox', 'Game Pass']
    },
    'curseforge': {
        'type': 'exe_search',
        'names': ['CurseForge'],
        'exe': 'CurseForge.exe',
        'search_dirs': [
            os.path.join(_LOCALAPP, 'Programs\\CurseForge'),
            os.path.join(_LOCALAPP, 'CurseForge'),
            'C:\\Program Files (x86)\\Overwolf',
            'C:\\Program Files\\Overwolf'
        ]
    },
    'telegram': {
        'type': 'exe_search',
        'names': ['Telegram'],
        'exe': 'Telegram.exe',
        'search_dirs': [
            os.path.join(_LOCALAPP, 'Programs\\Telegram Desktop'),
            os.path.join(_APPDATA, 'Telegram Desktop'),
            os.path.join(_LOCALAPP, 'Telegram Desktop')
        ]
    },
    'viber': {
        'type': 'exe_search',
        'names': ['Viber'],
        'exe': 'Viber.exe',
        'search_dirs': [
            os.path.join(_LOCALAPP, 'Viber'),
            'C:\\Program Files\\Viber',
            'C:\\Program Files (x86)\\Viber'
        ]
    },
    'whatsapp': {
        'type': 'exe_search',
        'names': ['WhatsApp'],
        'exe': 'WhatsApp.exe',
        'search_dirs': [
            os.path.join(_LOCALAPP, 'WhatsApp'),
            os.path.join(_APPDATA, 'WhatsApp')
        ]
    },
    'word': {
        'type': 'exe_search',
        'names': ['Word', 'Microsoft Word'],
        'exe': 'WINWORD.EXE',
        'search_dirs': [
            'C:\\Program Files\\Microsoft Office\\root\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\root\\Office16',
            'C:\\Program Files\\Microsoft Office\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\Office16'
        ]
    },
    'excel': {
        'type': 'exe_search',
        'names': ['Excel', 'Microsoft Excel'],
        'exe': 'EXCEL.EXE',
        'search_dirs': [
            'C:\\Program Files\\Microsoft Office\\root\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\root\\Office16',
            'C:\\Program Files\\Microsoft Office\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\Office16'
        ]
    },
    'powerpoint': {
        'type': 'exe_search',
        'names': ['PowerPoint', 'Microsoft PowerPoint'],
        'exe': 'POWERPNT.EXE',
        'search_dirs': [
            'C:\\Program Files\\Microsoft Office\\root\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\root\\Office16',
            'C:\\Program Files\\Microsoft Office\\Office16',
            'C:\\Program Files (x86)\\Microsoft Office\\Office16'
        ]
    }
}
SYSTEM_WHITELIST = ['program manager', 'settings', 'параметры', 'jarvis', 'explorer', 'проводник', 'taskbar', 'панель задач', 'windows input', 'text input', 'nvidia', 'realtek', 'discord', 'brave', 'youtube']
def _focus_and_maximize(title_keywords: list[str], timeout: float=3.0):
    end = time.time() + timeout
    while time.time() < end:
        for w in gw.getAllWindows():
            if w.visible and w.title:
                t = w.title.lower()
                if any((kw in t for kw in title_keywords)):
                    try:
                        w.maximize()
                        force_foreground(w._hWnd)
                        return True
                    except Exception:
                        pass
        time.sleep(0.3)
    return False
def open_app(app_name: str) -> tuple[bool, str]:
    app = APPS.get(app_name)
    if not app:
        return (False, f'Неизвестное приложение: {app_name}')
    try:
        app_type = app['type']
        keywords = app.get('keywords', app.get('names', []))
        if keywords:
            for w in gw.getAllWindows():
                if w.visible and w.title:
                    t = w.title.lower()
                    if any((kw.lower() in t for kw in keywords)):
                        try:
                            w.maximize()
                            force_foreground(w._hWnd)
                            return (True, app_name)
                        except Exception:
                            pass
        if app_type == 'shell':
            subprocess.Popen(app['cmd'])
            time.sleep(0.5)
            _focus_and_maximize(['explorer', 'проводник'])
            return (True, app_name)
        elif app_type == 'exe':
            path = app['path']
            if os.path.exists(path):
                subprocess.Popen([path])
                time.sleep(1)
                _focus_and_maximize(['brave'])
                return (True, app_name)
            return (False, f'Файл не найден: {path}')
        elif app_type == 'lnk':
            start_menu = os.path.join(os.environ['APPDATA'], 'Microsoft\\Windows\\Start Menu\\Programs')
            folder_candidates = app.get('folders', [app.get('folder', '')])
            name = app.get('name', '')
            lnk_path = None
            for folder in folder_candidates:
                lnk_dir = os.path.join(start_menu, folder) if folder else start_menu
                if os.path.isdir(lnk_dir):
                    for f in os.listdir(lnk_dir):
                        if f.lower().endswith('.lnk') and name.lower() in f.lower():
                            lnk_path = os.path.join(lnk_dir, f)
                            break
                if lnk_path: break
            if lnk_path:
                os.startfile(lnk_path)
                time.sleep(1)
                _focus_and_maximize([name.lower()])
                return (True, app_name)
            if 'url' in app:
                from actions.youtube import _open_youtube_url
                _open_youtube_url(app['url'])
                return (True, f"{app_name} (browser fallback)")
            return (False, f'Ярлык {name} не найден в стандартных папках')
        elif app_type == 'exe_search':
            exe = app.get('exe', '')
            cached_path = _exe_cache.get(app_name)
            if cached_path and os.path.exists(cached_path):
                cwd = os.path.dirname(cached_path)
                subprocess.Popen([cached_path], cwd=cwd)
                time.sleep(1.5)
                _focus_and_maximize([n.lower() for n in app['names']])
                return (True, app_name)
            elif cached_path:
                del _exe_cache[app_name]
                _save_exe_cache()
            search_locations = []
            update_dir = app.get('update_dir', '')
            if update_dir and os.path.isdir(update_dir):
                search_locations.append(update_dir)
            for sd in app.get('search_dirs', []):
                if sd and os.path.isdir(sd):
                    search_locations.append(sd)
            MAX_DEPTH = 3
            for search_dir in search_locations:
                base_depth = search_dir.rstrip(os.path.sep).count(os.path.sep)
                for root, dirs, files in os.walk(search_dir):
                    if root.count(os.path.sep) - base_depth >= MAX_DEPTH:
                        dirs[:] = []
                    if exe in files:
                        full = os.path.join(root, exe)
                        _exe_cache[app_name] = full
                        _save_exe_cache()
                        subprocess.Popen([full], cwd=root)
                        time.sleep(2)
                        _focus_and_maximize([n.lower() for n in app['names']])
                        return (True, app_name)
            start_menu = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft\\Windows\\Start Menu\\Programs')
            if os.path.isdir(start_menu):
                base_depth = start_menu.rstrip(os.path.sep).count(os.path.sep)
                for root, dirs, files in os.walk(start_menu):
                    if root.count(os.path.sep) - base_depth >= 3:
                        dirs[:] = []
                    for f in files:
                        if f.lower().endswith('.lnk'):
                            for name in app.get('names', []):
                                if name.lower() in f.lower():
                                    lnk = os.path.join(root, f)
                                    os.startfile(lnk)
                                    time.sleep(2)
                                    _focus_and_maximize([n.lower() for n in app['names']])
                                    return (True, app_name)
            if exe:
                reg_path = None
                if app_name == 'steam':
                    reg_path = _find_steam_via_registry()
                if reg_path:
                    _exe_cache[app_name] = reg_path
                    _save_exe_cache()
                    try:
                        subprocess.Popen([reg_path], cwd=os.path.dirname(reg_path))
                        time.sleep(2)
                        _focus_and_maximize([n.lower() for n in app['names']])
                        return (True, app_name)
                    except Exception as reg_err:
                        _log.error('Steam registry launch failed: %s', reg_err)
            fallback_uri = app.get('protocol_fallback')
            if fallback_uri:
                _log.info('Trying protocol fallback: %s', fallback_uri)
                try:
                    os.startfile(fallback_uri)
                    time.sleep(2)
                    _focus_and_maximize([n.lower() for n in app['names']])
                    return (True, app_name)
                except Exception as uri_err:
                    _log.error('Protocol fallback %s failed: %s', fallback_uri, uri_err)
                    return (False, f'{app_name}: протокол {fallback_uri} недоступен — {uri_err}')
            return (False, f'{app_name} не найден')
        elif app_type == 'protocol':
            os.startfile(app['uri'])
            time.sleep(2)
            _focus_and_maximize([n.lower() for n in app.get('names', [])])
            return (True, app_name)
    except Exception as e:
        return (False, str(e))
def close_app(app_name: str) -> tuple[bool, str]:
    app = APPS.get(app_name)
    if not app:
        return (False, f'Неизвестное приложение: {app_name}')
    try:
        import psutil
        keywords = app.get('keywords', app.get('names', []))
        exe_name = app.get('exe')
        closed_any = False
        for w in gw.getAllWindows():
            if w.title:
                t = w.title.lower()
                if any((kw.lower() in t for kw in keywords)):
                    try:
                        w.close()
                        closed_any = True
                    except Exception:
                        pass
        if closed_any:
            time.sleep(0.5)
        if exe_name and exe_name.lower() not in ['explorer.exe', 'python.exe']:
            killed = 0
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == exe_name.lower():
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if killed or closed_any:
                return (True, app_name)
        if closed_any:
            return (True, app_name)
        return (False, f'{app_name} не найден среди активных')
    except Exception as e:
        return (False, str(e))
