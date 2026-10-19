import os
import re
import sys
import shutil
import tempfile
import threading
import winreg
from pathlib import Path
from typing import Optional
from core.safe import swallow as _swallow
ETS2_APP_ID      = "227300"
PLUGIN_DLL_NAME  = "scs-telemetry.dll"
PLUGINS_SUBPATH  = Path("bin") / "win_x64" / "plugins"
GITHUB_API_URL   = "https://api.github.com/repos/truckermudgeon/scs-sdk-plugin/releases/latest"
GITHUB_FALLBACK_URL = "https://github.com/truckermudgeon/scs-sdk-plugin/releases/download/v1.12.2/scs-sdk-plugin-1.12.2.zip"
ZIP_DLL_PATH     = "Win64/scs-telemetry.dll"
ETS2_EXE_NAME    = "eurotrucks2.exe"
def _find_via_uninstall_key() -> Optional[str]:
    key_path = (
        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App {ETS2_APP_ID}"
    )
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "InstallLocation")
                if val and Path(val).exists():
                    return val
        except OSError:
            pass
    return None
def _find_via_steam_manifests() -> Optional[str]:
    steam_path: Optional[str] = None
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in ("SOFTWARE\\WOW6432Node\\Valve\\Steam", "SOFTWARE\\Valve\\Steam"):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as k:
                    steam_path, _ = winreg.QueryValueEx(k, "InstallPath")
                    break
            except OSError:
                pass
        if steam_path:
            break
    if not steam_path:
        return None
    lf_path = Path(steam_path) / "steamapps" / "libraryfolders.vdf"
    libraries = [Path(steam_path) / "steamapps"]
    if lf_path.exists():
        try:
            content = lf_path.read_text(encoding="utf-8")
            for p in re.findall(r'"path"\s+"([^"]+)"', content):
                lib = Path(p.replace("\\\\", "\\")) / "steamapps"
                if lib.exists() and lib not in libraries:
                    libraries.append(lib)
        except Exception:
            _swallow()
    manifest_name = f"appmanifest_{ETS2_APP_ID}.acf"
    for lib in libraries:
        manifest = lib / manifest_name
        if not manifest.exists():
            continue
        try:
            data = manifest.read_text(encoding="utf-8")
            dir_match = re.search(r'"installdir"\s+"([^"]+)"', data)
            if dir_match:
                install_dir = lib / "common" / dir_match.group(1)
                if install_dir.exists():
                    return str(install_dir)
        except Exception:
            _swallow()
    return None
def find_ets2_path() -> Optional[str]:
    return _find_via_uninstall_key() or _find_via_steam_manifests()
def validate_ets2_path(path: str) -> bool:
    p = Path(path)
    return (p / "bin" / "win_x64" / ETS2_EXE_NAME).exists() or           (p / ETS2_EXE_NAME).exists()
def _get_latest_zip_url() -> str:
    try:
        import requests
        r = requests.get(GITHUB_API_URL, timeout=10,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        for asset in r.json().get("assets", []):
            name: str = asset.get("name", "").lower()
            if "windows" in name and name.endswith(".zip"):
                return asset["browser_download_url"]
    except Exception:
        _swallow()
    return GITHUB_FALLBACK_URL
def _download_file(url: str, dest: Path) -> bool:
    try:
        import requests
        from core.download import require_https, verify_pinned
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(require_https(url), stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        verify_pinned(dest)
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False
def _extract_win64_dll(zip_path: Path, out_dir: Path) -> bool:
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            target = next(
                (m for m in members
                 if m.lower().endswith(PLUGIN_DLL_NAME.lower())),
                None
            )
            if not target:
                return False
            data = zf.read(target)
            dll_dest = out_dir / PLUGIN_DLL_NAME
            dll_dest.write_bytes(data)
            return True
    except Exception:
        return False
def _unblock_file_ps(path: str) -> None:
    try:
        import subprocess
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", f"Unblock-File -Path '{path}'"],
            capture_output=True, timeout=15
        )
    except Exception:
        _swallow()
def _install_with_admin(dll_src: Path, plugins_dir: Path) -> bool:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    dest = plugins_dir / PLUGIN_DLL_NAME
    try:
        shutil.copy2(dll_src, dest)
        _unblock_file_ps(str(dest))
        return True
    except PermissionError:
        pass
    try:
        import subprocess
        ps_cmd = (
            f"New-Item -Force -ItemType Directory -Path '{plugins_dir}'; "
            f"Copy-Item -Force '{dll_src}' '{dest}'; "
            f"Unblock-File '{dest}'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command",
             f"Start-Process powershell -Verb RunAs -Wait "
             f"-ArgumentList '-NoProfile','-NonInteractive','-Command',\"{ps_cmd}\""],
            capture_output=True, timeout=60
        )
        return dest.exists()
    except Exception:
        return False
class InstallResult:
    def __init__(self, ok: bool, message: str):
        self.ok = ok
        self.message = message
def install(game_path: str) -> InstallResult:
    plugins_dir = Path(game_path) / PLUGINS_SUBPATH
    dest_dll    = plugins_dir / PLUGIN_DLL_NAME
    url = _get_latest_zip_url()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir  = Path(tmp)
        zip_file = tmp_dir / "release.zip"
        if not _download_file(url, zip_file):
            return InstallResult(False, "download_error")
        if not _extract_win64_dll(zip_file, tmp_dir):
            return InstallResult(False, "extract_error")
        dll_src = tmp_dir / PLUGIN_DLL_NAME
        if not dll_src.exists():
            return InstallResult(False, "extract_error")
        if not _install_with_admin(dll_src, plugins_dir):
            return InstallResult(False, "copy_error")
    return InstallResult(True, "installed")
def run_installer(on_done=None) -> None:
    """Installs the telemetry plugin: into the game folder found automatically, or one the user picks in the native folder dialog."""
    def _do_install(path: str):
        def _bg():
            result = install(path)
            if on_done:
                on_done(result)
        threading.Thread(target=_bg, daemon=True, name="ets2_installer").start()

    def _ask_and_install():
        from ui_next.bridge.filepick import pick_folder
        from ui_next import host
        host.notify('ets2_plugin', 'Euro Truck Simulator 2 не найден: укажите папку с игрой', host.AMBER, duration=8000)
        chosen = pick_folder('Выберите папку с Euro Truck Simulator 2')
        if chosen and validate_ets2_path(chosen):
            _do_install(chosen)
        elif chosen:
            host.notify('ets2_plugin', 'В этой папке нет eurotrucks2.exe', host.RED, duration=6000)

    game_path = find_ets2_path()
    if game_path and validate_ets2_path(game_path):
        _do_install(game_path)
    else:
        threading.Thread(target=_ask_and_install, daemon=True, name="ets2_installer_path").start()
def is_telemetry_installed() -> bool:
    game_path = find_ets2_path()
    if not game_path:
        return False
    plugins_dir = Path(game_path) / PLUGINS_SUBPATH
    dll_path = plugins_dir / PLUGIN_DLL_NAME
    return dll_path.exists()
