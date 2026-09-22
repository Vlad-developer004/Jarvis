"""Deep-cleanup orphan scan: leftover AppData folders of uninstalled programs.

Only scans one level deep in %LOCALAPPDATA% and %APPDATA% and never deletes
anything itself — it returns candidates for the review dialog, which deletes
only what the user leaves checked.
"""
from __future__ import annotations
import os
import re
import time
import shutil

MIN_AGE_DAYS = 30  # candidate must be untouched for at least this long

# Folders that are part of Windows or common runtimes/shared libs and must
# never be offered for deletion, even if no matching registry entry is found.
# Matched as an exact name AND as a prefix of the normalized folder name, so
# "Microsoft SDKs" is caught by the "microsoft" entry the same way plain
# "Microsoft" would be.
_SAFE_SKIP = {
    'microsoft', 'packages', 'temp',
    'temporaryinternetfiles', 'connecteddevicesplatform', 'comms',
    'crashdumps', 'd3dscache', 'iconcache', 'elevateddiagnostics',
    'programs', 'programshortcuts', 'placeholdertilelogofolder',
    'jarvis', 'nvidia', 'intel', 'amd', 'google', 'mozilla', 'windows',
    'apppatch', 'assembly', 'vault', 'diagnostics', 'lastactivefeedback',
    'historicalappprovider', 'syncbackup', 'downloadedinstallations',
    'dotnet', 'nuget', 'pip', 'python', 'jetbrains', 'vscode',
    'codeinsiders', 'steam', 'discord', 'spotify', 'epicgames',
    'battlenet', 'eadesktop',
    # OneDrive / VirtualStore hold live sync state or Windows compat
    # redirection data — deleting them can break sync or app behavior even
    # though they rarely show up in the Uninstall registry.
    'onedrive', 'virtualstore', 'onedrivesetup',
}


def _norm(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())


def get_installed_program_names() -> set[str]:
    """Read DisplayName values from the Uninstall registry hives."""
    names: set[str] = set()
    try:
        import winreg
    except ImportError:
        return names

    hives = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    ]
    for hive, path in hives:
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(key, sub_name) as sub_key:
                            display_name, _ = winreg.QueryValueEx(sub_key, 'DisplayName')
                            if display_name:
                                names.add(_norm(display_name))
                    except OSError:
                        continue
        except OSError:
            continue
    return names


def _is_known(dir_name: str, installed: set[str]) -> bool:
    norm = _norm(dir_name)
    if not norm:
        return True
    if dir_name.startswith('.') or dir_name.startswith('{'):
        return True
    if 'jarvis' in norm:  # never flag our own app data, whatever the bundle id
        return True
    if any(norm == tok or norm.startswith(tok) for tok in _SAFE_SKIP):
        return True
    for prog in installed:
        if not prog:
            continue
        if norm in prog or prog in norm:
            return True
    try:
        from rapidfuzz import fuzz
        for prog in installed:
            if prog and fuzz.partial_ratio(norm, prog) >= 85:
                return True
    except ImportError:
        pass
    return False


def _dir_size(path: str, cap_files: int = 20000) -> int:
    total = 0
    count = 0
    for dp, _dn, fs in os.walk(path):
        for f in fs:
            count += 1
            if count > cap_files:
                return total
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def find_orphan_candidates() -> list[dict]:
    """Return leftover top-level AppData folders with no matching installed program."""
    installed = get_installed_program_names()
    roots = [os.environ.get('LOCALAPPDATA', ''), os.environ.get('APPDATA', '')]
    now = time.time()
    candidates: list[dict] = []
    seen_paths: set[str] = set()

    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for name in entries:
            full = os.path.join(root, name)
            if full in seen_paths or not os.path.isdir(full):
                continue
            seen_paths.add(full)
            if _is_known(name, installed):
                continue
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            age_days = (now - mtime) / 86400
            if age_days < MIN_AGE_DAYS:
                continue
            candidates.append({
                'path': full,
                'name': name,
                'size_bytes': _dir_size(full),
                'age_days': int(age_days),
            })

    candidates.sort(key=lambda c: c['size_bytes'], reverse=True)
    return candidates


def delete_candidates(paths: list[str]) -> tuple[int, int]:
    """Delete the given directories. Returns (freed_bytes, error_count)."""
    freed = 0
    errors = 0
    for path in paths:
        try:
            size = _dir_size(path)
            shutil.rmtree(path, ignore_errors=False)
            freed += size
        except Exception:
            errors += 1
    return freed, errors
