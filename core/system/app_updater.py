import json
import sys
import threading
import zipfile
from pathlib import Path
from typing import Optional

from config_pack import config
from core.system.version import APP_VERSION

GITHUB_REPO     = "Vlad-developer004/Jarvis"
UPDATE_DIR      = Path("data") / "app_update"
UPDATE_READY    = UPDATE_DIR / "ready.json"
CHECK_DELAY_SEC = 15
RECHECK_HOURS   = 6

_lock = threading.Lock()
_available_version: Optional[str] = None


def get_available_version() -> Optional[str]:
    """Version staged/detected as newer than APP_VERSION, or None."""
    with _lock:
        return _available_version


def _set_available_version(version: Optional[str]) -> None:
    global _available_version
    with _lock:
        _available_version = version


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    for member in zf.infolist():
        member_path = (dest_root / member.filename).resolve()
        try:
            member_path.relative_to(dest_root)
        except ValueError as exc:
            raise RuntimeError(f"Blocked zip path traversal: {member.filename}") from exc
    zf.extractall(dest_root)


def _parse_version(tag: str) -> tuple[int, ...]:
    tag = tag.lstrip("v").strip()
    parts = []
    for p in tag.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _fetch_latest_release() -> Optional[dict]:
    try:
        import requests
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _find_zip_asset(assets: list[dict]) -> Optional[dict]:
    for asset in assets:
        if asset.get("name", "").lower().endswith(".zip"):
            return asset
    return None


def _download(url: str, dest: Path) -> bool:
    try:
        import requests
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        return True
    except Exception:
        return False


def _stage_update(asset: dict, tag: str) -> bool:
    name: str = asset["name"]
    url: str = asset["browser_download_url"]
    archive = UPDATE_DIR / name
    staged_dir = UPDATE_DIR / "staged"

    if UPDATE_READY.exists():
        try:
            existing = json.loads(UPDATE_READY.read_text(encoding="utf-8"))
            if existing.get("version") == tag:
                return True
        except Exception:
            pass

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    if not _download(url, archive):
        return False

    import shutil
    if staged_dir.exists():
        shutil.rmtree(staged_dir, ignore_errors=True)
    staged_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            _safe_extract_zip(zf, staged_dir)
    except Exception:
        return False
    finally:
        archive.unlink(missing_ok=True)

    UPDATE_READY.write_text(
        json.dumps({"version": tag, "staged_dir": str(staged_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def check_for_update() -> None:
    release = _fetch_latest_release()
    if not release:
        return
    tag: str = release.get("tag_name", "0.0.0")
    if _parse_version(tag) <= _parse_version(APP_VERSION):
        return
    _set_available_version(tag.lstrip("v"))
    if not config.AUTO_UPDATE_ENABLED:
        return
    assets: list[dict] = release.get("assets", [])
    asset = _find_zip_asset(assets)
    if not asset:
        return
    _stage_update(asset, tag)


def is_update_staged() -> bool:
    return UPDATE_READY.exists()


def apply_and_restart() -> bool:
    """Write a helper .bat that swaps files in after this process exits, then
    exit. Only meaningful for a frozen (PyInstaller) build."""
    if not UPDATE_READY.exists() or not getattr(sys, "frozen", False):
        return False
    try:
        info = json.loads(UPDATE_READY.read_text(encoding="utf-8"))
    except Exception:
        return False
    staged_dir = Path(info.get("staged_dir", ""))
    if not staged_dir.exists():
        return False

    app_dir = Path(sys.executable).parent
    exe_path = Path(sys.executable)
    bat_path = UPDATE_DIR / "apply_update.bat"
    bat_path.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'robocopy "{staged_dir}" "{app_dir}" /E /IS /IT >nul\r\n'
        f'rmdir /S /Q "{staged_dir}"\r\n'
        f'del "{UPDATE_READY}"\r\n'
        f'start "" "{exe_path}"\r\n',
        encoding="utf-8",
    )

    import subprocess
    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    return True


_stop = threading.Event()


def _scheduler_loop() -> None:
    if _stop.wait(CHECK_DELAY_SEC):
        return
    while not _stop.is_set():
        try:
            check_for_update()
        except Exception:
            pass
        if _stop.wait(RECHECK_HOURS * 3600):
            break


def start() -> None:
    threading.Thread(target=_scheduler_loop, daemon=True, name="app_updater").start()


def stop() -> None:
    _stop.set()
