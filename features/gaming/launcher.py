import os
import winreg
import time
from typing import Dict
def wait_for_launcher_window(launcher_name: str, timeout: float = 15.0) -> bool:
    import pygetwindow as gw
    title_map = {
        'Steam': ['steam'],
        'Epic Games': ['epic games', 'epicgames'],
        'Ubisoft Connect': ['ubisoft', 'uplay'],
        'GOG Galaxy': ['gog galaxy', 'goggalaxy'],
        'Xbox': ['xbox']
    }
    keywords = title_map.get(launcher_name, [launcher_name.lower()])
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        for w in gw.getAllWindows():
            if w.visible and w.title:
                t = w.title.lower()
                if any(kw in t for kw in keywords):
                    return True
        time.sleep(0.5)
    return False
def get_available_launchers() -> Dict[str, str]:
    launchers = {}
    steam_exe = None
    for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        for subkey in ['SOFTWARE\\Valve\\Steam', 'SOFTWARE\\WOW6432Node\\Valve\\Steam']:
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                    path, _ = winreg.QueryValueEx(key, 'InstallPath')
                    exe = os.path.join(path, 'steam.exe')
                    if os.path.exists(exe):
                        steam_exe = exe
                        break
            except Exception: continue
        if steam_exe: break
    if not steam_exe:
        for p in ['C:\\Program Files (x86)\\Steam\\steam.exe', 'C:\\Program Files\\Steam\\steam.exe']:
            if os.path.exists(p): steam_exe = p; break
    if steam_exe: launchers['Steam'] = steam_exe
    epic_exe = None
    for p in [
        'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe',
        'C:\\Program Files\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe',
        'D:\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe'
    ]:
        if os.path.exists(p): epic_exe = p; break
    if epic_exe: launchers['Epic Games'] = epic_exe
    ubi_exe = None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Ubisoft\\Launcher', 0, winreg.KEY_READ) as key:
            path, _ = winreg.QueryValueEx(key, 'InstallDir')
            exe = os.path.join(path, 'UbisoftConnect.exe')
            if os.path.exists(exe): ubi_exe = exe
    except Exception: pass
    if not ubi_exe:
        p = 'C:\\Program Files (x86)\\Ubisoft\\Ubisoft Game Launcher\\UbisoftConnect.exe'
        if os.path.exists(p): ubi_exe = p
    if ubi_exe: launchers['Ubisoft Connect'] = ubi_exe
    gog_exe = None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\GOG.com\\GalaxyClient\\paths', 0, winreg.KEY_READ) as key:
            path, _ = winreg.QueryValueEx(key, 'client')
            exe = os.path.join(path, 'GalaxyClient.exe')
            if os.path.exists(exe): gog_exe = exe
    except Exception: pass
    if gog_exe: launchers['GOG Galaxy'] = gog_exe
    xbox_exists = False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\XboxApp.exe', 0, winreg.KEY_READ) as key:
            xbox_exists = True
    except Exception: pass
    if not xbox_exists:
        if os.path.exists(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps', 'XboxApp.exe')):
            xbox_exists = True
    if xbox_exists: launchers['Xbox'] = 'shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.GamingApp'
    return launchers
