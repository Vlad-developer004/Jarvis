import os
import re
import json
import subprocess
import winreg
from typing import List
from core.safe import swallow as _swallow
class GameInfo:
    def __init__(self, name: str, launcher: str, launch_uri: str, last_played: int=0, install_dir: str=''):
        self.name = name
        self.launcher = launcher
        self.launch_uri = launch_uri
        self.last_played = last_played
        self.install_dir = install_dir
    def __repr__(self):
        return f'GameInfo({self.name}, {self.launcher}, lp={self.last_played})'
def get_steam_games() -> List[GameInfo]:
    games = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Valve\\Steam')
        steam_path, _ = winreg.QueryValueEx(key, 'InstallPath')
    except WindowsError:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Valve\\Steam')
            steam_path, _ = winreg.QueryValueEx(key, 'InstallPath')
        except WindowsError:
            return games
    library_folders_path = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
    libraries = [os.path.join(steam_path, 'steamapps')]
    if os.path.exists(library_folders_path):
        try:
            with open(library_folders_path, 'r', encoding='utf-8') as f:
                content = f.read()
                paths = re.findall('"path"\\s+"([^"]+)"', content)
                for p in paths:
                    clean_path = p.replace('\\\\', '\\')
                    apps_path = os.path.join(clean_path, 'steamapps')
                    if apps_path not in libraries and os.path.exists(apps_path):
                        libraries.append(apps_path)
        except Exception:
            _swallow()
    for lib in libraries:
        if not os.path.exists(lib): continue
        for entry in os.listdir(lib):
            if entry.startswith('appmanifest_') and entry.endswith('.acf'):
                manifest_path = os.path.join(lib, entry)
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        data = f.read()
                        name_match = re.search('"name"\\s+"([^"]+)"', data)
                        id_match = re.search('"appid"\\s+"(\\d+)"', data)
                        lp_match = re.search('"LastPlayed"\\s+"(\\d+)"', data)
                        dir_match = re.search('"installdir"\\s+"([^"]+)"', data)
                        if name_match and id_match:
                            name = name_match.group(1)
                            if 'redistributable' in name.lower() or 'steamworks' in name.lower(): continue
                            app_id = id_match.group(1)
                            last_played = int(lp_match.group(1)) if lp_match else 0
                            install_dir = os.path.join(lib, 'common', dir_match.group(1)) if dir_match else ''
                            games.append(GameInfo(name=name, launcher='Steam', launch_uri=f'steam://rungameid/{app_id}', last_played=last_played, install_dir=install_dir))
                except Exception: continue
    return games
def get_epic_games() -> List[GameInfo]:
    games = []
    manifests_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests')
    if not os.path.exists(manifests_dir): return games
    for entry in os.listdir(manifests_dir):
        if entry.endswith('.item'):
            try:
                with open(os.path.join(manifests_dir, entry), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    name = data.get('DisplayName')
                    app_name = data.get('AppName')
                    catalog_id = data.get('CatalogItemId')
                    namespace = data.get('CatalogNamespace')
                    install_location = data.get('InstallLocation')
                    if name and app_name:
                        games.append(GameInfo(name=name, launcher='Epic Games', launch_uri=f'com.epicgames.launcher://apps/{namespace}%3A{catalog_id}%3A{app_name}?action=launch&silent=true', last_played=0, install_dir=install_location or ''))
            except Exception: continue
    return games
def _read_game_config(install_dir: str):
    """(display name, app id) from an Xbox/Microsoft Store game's MicrosoftGame.config, or None when the package is not a game."""
    from defusedxml import ElementTree as ET
    cfg = os.path.join(install_dir, 'MicrosoftGame.config')
    if not install_dir or not os.path.isfile(cfg):
        return None
    try:
        root = ET.parse(cfg).getroot()
    except Exception:
        return None
    visuals = root.find('ShellVisuals')
    name = (visuals.get('DefaultDisplayName') if visuals is not None else '') or ''
    exe = root.find('ExecutableList/Executable')
    app_id = (exe.get('Id') if exe is not None else '') or 'Game'
    return name, app_id
def get_xbox_games() -> List[GameInfo]:
    """Games installed through the Xbox app / Microsoft Store. Only packages that ship a MicrosoftGame.config count:
    filtering by publisher alone returns every Microsoft system package (Paint, runtimes, codecs)."""
    games = []
    try:
        ps_script = (
            "Get-AppxPackage | Where-Object { -not $_.IsFramework -and $_.InstallLocation -and "
            "(Test-Path -LiteralPath (Join-Path $_.InstallLocation 'MicrosoftGame.config')) } | "
            "Select-Object Name, PackageFamilyName, InstallLocation | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True, text=True, shell=False, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        out = result.stdout.strip()
        if result.returncode == 0 and out:
            data = json.loads(out)
            for pkg in (data if isinstance(data, list) else [data]):
                install_dir = pkg.get('InstallLocation') or ''
                cfg = _read_game_config(install_dir)
                if cfg is None:
                    continue
                title, app_id = cfg
                name = title if title and not title.startswith('ms-resource:') else pkg.get('Name', '')
                if name:
                    games.append(GameInfo(name=name, launcher='Xbox', launch_uri=f"shell:AppsFolder\\{pkg['PackageFamilyName']}!{app_id}", last_played=0, install_dir=install_dir))
    except Exception: _swallow()
    return games
_GAMES_CACHE: List[GameInfo] = []
_LAST_SCAN: float = 0
SCAN_COOLDOWN = 600
def scan_all_games(force: bool = False) -> List[GameInfo]:
    global _GAMES_CACHE, _LAST_SCAN
    import time
    now = time.time()
    if not force and _GAMES_CACHE and (now - _LAST_SCAN < SCAN_COOLDOWN):
        return _GAMES_CACHE
    import threading
    results: dict[str, list] = {'steam': [], 'epic': [], 'xbox': []}
    def _s(): results['steam'] = get_steam_games()
    def _e(): results['epic']  = get_epic_games()
    def _x(): results['xbox']  = get_xbox_games()
    threads = [threading.Thread(target=f, daemon=True) for f in (_s, _e, _x)]
    for t in threads: t.start()
    for t in threads: t.join()
    all_games = results['steam'] + results['epic'] + results['xbox']
    _GAMES_CACHE = all_games
    _LAST_SCAN = now
    return all_games
def get_most_recently_played(games: List[GameInfo]) -> GameInfo:
    if not games: return None
    played_games = [g for g in games if g.last_played > 0]
    if not played_games: return games[0] if games else None
    played_games.sort(key=lambda g: g.last_played, reverse=True)
    return played_games[0]
def get_overall_last_played() -> GameInfo:
    games = scan_all_games()
    return get_most_recently_played(games)
