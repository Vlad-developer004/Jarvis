"""Auto-installer for PlanetbaseTelemetry mod and PBPatcher."""

import hashlib
import logging
import shutil
import subprocess
import winreg
from pathlib import Path

_log = logging.getLogger(__name__)

_MOD_DLL = "PlanetbaseTelemetry.dll"
_ASSETS = Path(__file__).parent.parent.parent / "data" / "integrations" / "planetbase"
_PBPATCHER_EXE = _ASSETS / "PBPatcher" / "PBPatcher.exe"


def find_planetbase_path() -> Path | None:
    """Find Planetbase installation via Steam registry then common paths."""
    steam_path = None
    for reg_path in (
        r"SOFTWARE\WOW6432Node\Valve\Steam",
        r"SOFTWARE\Valve\Steam",
    ):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            break
        except OSError:
            pass

    candidate_roots = []
    if steam_path:
        candidate_roots.append(Path(steam_path))
    for drive in ["C:", "D:", "E:", "F:"]:
        for sub in [r"\Steam", r"\SteamLibrary", r"\Games\Steam"]:
            candidate_roots.append(Path(drive + sub))

    for root in candidate_roots:
        candidate = root / "steamapps" / "common" / "Planetbase"
        if candidate.exists():
            _log.info("Found Planetbase at %s", candidate)
            return candidate
    return None


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_patched(managed: Path) -> bool:
    """True if Assembly-CSharp.dll has already been patched (backup exists)."""
    return (managed / "Assembly-CSharp.bak").exists()


def _install_mod(managed: Path) -> bool:
    """Copy PlanetbaseTelemetry.dll into the Managed folder."""
    src = _ASSETS / _MOD_DLL
    if not src.exists():
        _log.error("Mod DLL not found at %s", src)
        return False

    dst = managed / _MOD_DLL
    if dst.exists() and _file_hash(src) == _file_hash(dst):
        _log.debug("Mod DLL already up to date")
        return True

    shutil.copy2(src, dst)
    _log.info("Installed %s to %s", _MOD_DLL, managed)
    return True


def _apply_patcher(managed: Path) -> bool:
    """Run PBPatcher.exe to inject TelemetryMod.Init() into Assembly-CSharp.dll."""
    if not _PBPATCHER_EXE.exists():
        _log.error("PBPatcher.exe not found at %s", _PBPATCHER_EXE)
        return False

    try:
        result = subprocess.run(
            [str(_PBPATCHER_EXE), str(managed)],
            capture_output=True, text=True, timeout=30
        )
        _log.debug("PBPatcher stdout: %s", result.stdout.strip())
        if result.returncode != 0:
            _log.error("PBPatcher failed: %s", result.stderr.strip())
            return False
        _log.info("PBPatcher applied successfully")
        return True
    except Exception as e:
        _log.error("PBPatcher error: %s", e)
        return False


def ensure_installed() -> bool:
    """Install mod DLL and patch Assembly-CSharp if needed. Returns True if ready."""
    pb_path = find_planetbase_path()
    if not pb_path:
        _log.warning("Planetbase not found — skipping mod install")
        return False

    managed = pb_path / "Planetbase_Data" / "Managed"

    # DLL must be in Managed/ before patching (patcher reads it from there)
    if not _install_mod(managed):
        return False

    if not _is_patched(managed):
        _log.info("Applying PBPatcher...")
        if not _apply_patcher(managed):
            return False

    return True
