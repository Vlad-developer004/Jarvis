"""Shared safety checks for model and plugin downloads: HTTPS only, optional pinned SHA-256, and archive extraction that cannot
write outside its folder (path traversal, absolute paths, links, device names, zip bombs)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import zipfile
from pathlib import Path

MAX_MEMBERS = 200_000
MAX_UNPACKED = 12 * 1024 ** 3
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_HASHES_FILE = 'model_hashes.json'


class UnsafeArchive(RuntimeError):
    pass


def require_https(url: str) -> str:
    if not str(url).lower().startswith('https://'):
        raise ValueError('only https downloads are allowed')
    return url


def check_member_name(name: str) -> None:
    norm = str(name).replace('\\', '/')
    parts = [p for p in norm.split('/') if p]
    if norm.startswith('/') or re.match(r'^[A-Za-z]:', norm) or '..' in parts or '\0' in norm:
        raise UnsafeArchive(f'unsafe path in archive: {name}')
    for p in parts:
        if p.split('.')[0].upper() in _RESERVED:
            raise UnsafeArchive(f'reserved name in archive: {name}')


def _inside(root: Path, name: str) -> None:
    try:
        (root / name).resolve().relative_to(root)
    except ValueError as exc:
        raise UnsafeArchive(f'path traversal in archive: {name}') from exc


def safe_extract_zip(zf: zipfile.ZipFile, dest: str | os.PathLike) -> None:
    root = Path(dest).resolve()
    members = zf.infolist()
    if len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_UNPACKED:
        raise UnsafeArchive('archive is too large')
    for m in members:
        check_member_name(m.filename)
        _inside(root, m.filename)
    zf.extractall(root)  # nosec B202


def safe_extract_tar(tar: tarfile.TarFile, dest: str | os.PathLike) -> None:
    """Regular files and folders only: links and device nodes are refused (a link inside the archive could point outside)."""
    root = Path(dest).resolve()
    members = tar.getmembers()
    if len(members) > MAX_MEMBERS or sum(m.size for m in members) > MAX_UNPACKED:
        raise UnsafeArchive('archive is too large')
    for m in members:
        check_member_name(m.name)
        _inside(root, m.name)
        if not (m.isfile() or m.isdir()):
            raise UnsafeArchive(f'links and special files are not allowed: {m.name}')
    if hasattr(tarfile, 'data_filter'):
        tar.extractall(root, members=members, filter='data')  # nosec B202
    else:
        tar.extractall(root, members=members)  # nosec B202


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def bundled_data_file(name: str) -> Path:
    """data/<name> next to the program, else inside the PyInstaller bundle folder (jarvis.spec puts static data files there, and build.bat clears the
    JSON files next to the exe). Raises OSError when neither has it."""
    import sys
    from config_pack.config import get_project_root
    roots = [Path(get_project_root())]
    if getattr(sys, '_MEIPASS', None):
        roots.append(Path(sys._MEIPASS))
    for root in roots:
        f = root / 'data' / name
        if f.is_file():
            return f
    raise OSError(f'data/{name} not found')


def pinned_hash(name: str) -> str | None:
    """The SHA-256 pinned for a download by file name in data/model_hashes.json, or None when none is pinned."""
    try:
        data = json.loads(bundled_data_file(_HASHES_FILE).read_text(encoding='utf-8'))
        h = str(data.get(name, '')).strip().lower()
        return h if re.fullmatch(r'[0-9a-f]{64}', h) else None
    except (OSError, ValueError):
        return None


def verify_pinned(path: str | os.PathLike, name: str | None = None) -> None:
    """Raises when a hash is pinned for this file name (`name`, or the file's own) and the file does not match; a file without a pin passes."""
    want = pinned_hash(name or Path(path).name)
    if want and sha256_file(path) != want:
        raise ValueError(f'checksum mismatch for {Path(path).name}')
