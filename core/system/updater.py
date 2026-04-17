import json
import os
import sys
import threading
import zipfile
from pathlib import Path
from typing import Optional
GITHUB_REPO     = "truckermudgeon/scs-sdk-plugin"
VERSION_FILE    = Path("data") / "version.json"
UPDATE_DIR      = Path("data") / "update"
UPDATE_READY    = Path("data") / "update_ready.json"
CHECK_DELAY_SEC = 12
RECHECK_HOURS   = 6
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
def get_local_version() -> str:
    try:
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"
def set_local_version(version: str) -> None:
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    try:
        existing = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    existing["version"] = version
    VERSION_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
def _fetch_latest_release() -> Optional[dict]:
    try:
        import requests
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 404: return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
def _find_asset(assets: list[dict]) -> Optional[dict]:
    for asset in assets:
        name: str = asset.get("name", "").lower()
        if name.endswith(".zip") or name.endswith(".exe"):
            return asset
    return None
def _download(url: str, dest: Path) -> bool:
    try:
        import requests
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        return True
    except Exception:
        return False
def _stage_update(asset: dict, tag: str) -> bool:
    name: str = asset["name"]
    url:  str = asset["browser_download_url"]
    dest = UPDATE_DIR / name
    if UPDATE_READY.exists():
        try:
            existing = json.loads(UPDATE_READY.read_text(encoding="utf-8"))
            if existing.get("version") == tag: return True
        except Exception: pass
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    for old in UPDATE_DIR.iterdir():
        try: old.unlink()
        except Exception: pass
    if not _download(url, dest): return False
    UPDATE_READY.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_READY.write_text(json.dumps({"version": tag, "file": str(dest)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return True
def check_and_download() -> None:
    release = _fetch_latest_release()
    if not release: return
    tag: str = release.get("tag_name", "0.0.0")
    local = get_local_version()
    if _parse_version(tag) <= _parse_version(local): return
    assets: list[dict] = release.get("assets", [])
    asset = _find_asset(assets)
    if not asset: return
    _stage_update(asset, tag)
def apply_if_ready() -> bool:
    if not UPDATE_READY.exists(): return False
    try:
        info = json.loads(UPDATE_READY.read_text(encoding="utf-8"))
    except Exception: return False
    staged_file = Path(info.get("file", ""))
    new_version = info.get("version", "")
    if not staged_file.exists():
        UPDATE_READY.unlink(missing_ok=True)
        return False
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    try:
        if staged_file.suffix.lower() == ".zip":
            with zipfile.ZipFile(staged_file, "r") as zf:
                _safe_extract_zip(zf, app_dir)
        elif staged_file.suffix.lower() == ".exe":
            import shutil
            shutil.copy2(staged_file, app_dir / staged_file.name)
    except Exception: return False
    if new_version: set_local_version(new_version)
    UPDATE_READY.unlink(missing_ok=True)
    try: staged_file.unlink(missing_ok=True)
    except Exception: pass
    return True
_stop = threading.Event()
def _scheduler_loop() -> None:
    if _stop.wait(CHECK_DELAY_SEC): return
    while not _stop.is_set():
        try: check_and_download()
        except Exception: pass
        if _stop.wait(RECHECK_HOURS * 3600): break
def start() -> None:
    threading.Thread(target=_scheduler_loop, daemon=True, name="auto_updater").start()
def stop() -> None:
    _stop.set()
