"""Self-update from GitHub releases.

A release is trusted only when it carries two extra assets next to the .zip: ``SHA256SUMS`` (``<sha256>  <file name>`` lines) and
``SHA256SUMS.sig`` (base64 ed25519 signature of that file). The public key ships with the app (``data/update_pubkey.txt``, 64 hex
characters), the private key stays with the owner (``tools/sign_release.py``). Without a valid signature, a matching hash, and a safe
archive nothing is staged; a missing public key means updates are announced but never installed.
"""
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import sys
import threading
import zipfile
from pathlib import Path
from typing import Optional

from config_pack import config
from core.redact import describe_error
from core.system.version import APP_VERSION

_log = logging.getLogger(__name__)

GITHUB_REPO     = "Vlad-developer004/Jarvis"
UPDATE_DIR      = Path(config.get_app_data_root()) / "app_update"
UPDATE_READY    = UPDATE_DIR / "ready.json"
CHECK_DELAY_SEC = 15
RECHECK_HOURS   = 6
SUMS_NAME       = "SHA256SUMS"
SIG_NAME        = "SHA256SUMS.sig"
PUBKEY_FILE     = "update_pubkey.txt"
MAX_ZIP_BYTES   = 4 * 1024 ** 3
MAX_UNPACKED    = 8 * 1024 ** 3
MAX_MEMBERS     = 200_000
MAX_SMALL_BYTES = 1 << 20
_DOWNLOAD_PREFIX = f"https://github.com/{GITHUB_REPO}/releases/download/"
_TAG_RE = re.compile(r"^v?\d+(\.\d+){0,3}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

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


def _check_member_name(name: str) -> None:
    norm = name.replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or ".." in parts or "\0" in name:
        raise RuntimeError(f"Blocked unsafe path in archive: {name}")
    for p in parts:
        if p.split(".")[0].upper() in _RESERVED:
            raise RuntimeError(f"Blocked reserved name in archive: {name}")


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    members = zf.infolist()
    if len(members) > MAX_MEMBERS:
        raise RuntimeError("Archive has too many entries")
    if sum(m.file_size for m in members) > MAX_UNPACKED:
        raise RuntimeError("Archive is too large when unpacked")
    for member in members:
        _check_member_name(member.filename)
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
    except Exception as e:
        _log.info("update check failed: %s", describe_error(e))
        return None


def _find_zip_asset(assets: list[dict]) -> Optional[dict]:
    for asset in assets:
        if asset.get("name", "").lower().endswith(".zip"):
            return asset
    return None


def _find_asset(assets: list[dict], name: str) -> Optional[dict]:
    for asset in assets:
        if asset.get("name") == name:
            return asset
    return None


def _allowed_url(url: str) -> bool:
    return isinstance(url, str) and url.startswith(_DOWNLOAD_PREFIX)


def _load_pubkey() -> Optional[bytes]:
    """The release-signing public key (32 bytes) or None when the app was built without one."""
    try:
        text = (Path(config.get_project_root()) / "data" / PUBKEY_FILE).read_text(encoding="utf-8").strip()
        key = bytes.fromhex(text)
        return key if len(key) == 32 else None
    except (OSError, ValueError):
        return None


def _verify_signature(message: bytes, signature_b64: bytes, public_key: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        sig = base64.b64decode(signature_b64.strip(), validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(sig, message)
        return True
    except (InvalidSignature, binascii.Error, ValueError, ImportError):
        return False


def _parse_sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if m:
            out[m.group(2)] = m.group(1).lower()
    return out


def _download_small(url: str) -> Optional[bytes]:
    """A short text asset (checksums, signature), size-capped; None on any failure."""
    if not _allowed_url(url):
        return None
    try:
        import requests
        with requests.get(url, timeout=30, stream=True) as r:
            r.raise_for_status()
            data = r.raw.read(MAX_SMALL_BYTES + 1, decode_content=True)
        return data if len(data) <= MAX_SMALL_BYTES else None
    except Exception as e:
        _log.info("update asset download failed: %s", describe_error(e))
        return None


def _download(url: str, dest: Path) -> Optional[str]:
    """Streams the archive to ``dest`` and returns its SHA-256 (None on failure or when it exceeds the size cap)."""
    if not _allowed_url(url):
        return None
    try:
        import requests
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest, size = hashlib.sha256(), 0
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > MAX_ZIP_BYTES:
                        raise RuntimeError("download is larger than allowed")
                    digest.update(chunk)
                    f.write(chunk)
        return digest.hexdigest()
    except Exception as e:
        _log.info("update download failed: %s", describe_error(e))
        dest.unlink(missing_ok=True)
        return None


def _trusted_hash(assets: list[dict], zip_name: str) -> Optional[str]:
    """The signed SHA-256 for ``zip_name``, or None when the release is not signed by our key."""
    pub = _load_pubkey()
    if pub is None:
        _log.warning("update refused: this build has no release public key")
        return None
    sums_asset, sig_asset = _find_asset(assets, SUMS_NAME), _find_asset(assets, SIG_NAME)
    if not sums_asset or not sig_asset:
        _log.warning("update refused: the release has no %s / %s", SUMS_NAME, SIG_NAME)
        return None
    sums = _download_small(sums_asset.get("browser_download_url", ""))
    sig = _download_small(sig_asset.get("browser_download_url", ""))
    if sums is None or sig is None or not _verify_signature(sums, sig, pub):
        _log.warning("update refused: the checksum list is missing or its signature is wrong")
        return None
    return _parse_sums(sums.decode("utf-8", errors="replace")).get(zip_name)


def _stage_update(asset: dict, tag: str, assets: Optional[list] = None) -> bool:
    if not _TAG_RE.match(tag or ""):
        return False
    name = Path(str(asset.get("name", ""))).name
    url: str = asset.get("browser_download_url", "")
    if not name:
        return False
    archive = UPDATE_DIR / name
    staged_dir = UPDATE_DIR / "staged"

    if UPDATE_READY.exists():
        try:
            existing = json.loads(UPDATE_READY.read_text(encoding="utf-8"))
            if existing.get("version") == tag and Path(existing.get("staged_dir", "")).exists():
                return True
        except Exception:
            pass

    expected = _trusted_hash(assets or [], name)
    if not expected:
        return False

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    got = _download(url, archive)
    if got != expected:
        if got is not None:
            _log.warning("update refused: archive hash does not match the signed list")
        archive.unlink(missing_ok=True)
        return False

    import shutil
    if staged_dir.exists():
        shutil.rmtree(staged_dir, ignore_errors=True)
    staged_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            _safe_extract_zip(zf, staged_dir)
    except Exception as e:
        _log.warning("update refused: unsafe or broken archive: %s", describe_error(e))
        shutil.rmtree(staged_dir, ignore_errors=True)
        return False
    finally:
        archive.unlink(missing_ok=True)

    tmp = UPDATE_READY.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": tag, "staged_dir": str(staged_dir)}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, UPDATE_READY)
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
    _stage_update(asset, tag, assets)


def is_update_staged() -> bool:
    return UPDATE_READY.exists()


def _bat_path(p: Path) -> str:
    return str(p).replace("%", "%%")


def apply_and_restart() -> bool:
    """Write a helper .bat that swaps files in after this process exits, then
    exit. Only meaningful for a frozen (PyInstaller) build. The staged folder is
    deleted only when robocopy reports success (exit code below 8)."""
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
        f'robocopy "{_bat_path(staged_dir)}" "{_bat_path(app_dir)}" /E /IS /IT >nul\r\n'
        "if errorlevel 8 exit /b 1\r\n"
        f'rmdir /S /Q "{_bat_path(staged_dir)}"\r\n'
        f'del "{_bat_path(UPDATE_READY)}"\r\n'
        f'start "" "{_bat_path(exe_path)}"\r\n',
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
        except Exception as e:
            _log.warning("update check crashed: %s", describe_error(e))
        if _stop.wait(RECHECK_HOURS * 3600):
            break


def start() -> None:
    threading.Thread(target=_scheduler_loop, daemon=True, name="app_updater").start()


def stop() -> None:
    _stop.set()
