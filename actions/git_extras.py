"""Helpers around the commit dialog (actions/git_commit.py): warnings about files that should not be committed, a suggested message,
per-file line counts, and undoing the last local commit. Nothing here changes the repository except `undo_last_commit`."""
from __future__ import annotations

import fnmatch
import os
import re

from actions.git_commit import GitError, _git

LARGE_BYTES = 2 * 1024 * 1024
_SCAN_LIMIT_FILES = 300
_SCAN_LIMIT_BYTES = 300 * 1024

_SECRET_NAMES = ('.env', '.env.*', 'secrets.env', '*.pem', '*.key', '*.pfx', '*.p12', '*.keystore', 'id_rsa', 'id_rsa.*', 'id_ed25519', 'id_ed25519.*',
                 'credentials.json', '*.kdbx')
_BUILD_DIRS = ('target', 'node_modules', 'dist', 'build', '__pycache__', '.venv', 'venv', '.pytest_cache', '.ruff_cache')
_TEXT_SECRETS = (
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{34,}\b'),                      # Telegram bot token
    re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'),                              # OpenAI-style keys
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),                                 # AWS access key id
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),                         # GitHub tokens
    re.compile(r'(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d)["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-/+=]{20,}["\']'),
)


def _kind_by_name(path: str) -> str:
    parts = path.replace('\\', '/').split('/')
    if any(p in _BUILD_DIRS for p in parts[:-1]):
        return 'build'
    name = parts[-1].lower()
    return 'secret_name' if any(fnmatch.fnmatch(name, pat) for pat in _SECRET_NAMES) else ''


def _has_secret_text(full: str) -> bool:
    try:
        if os.path.getsize(full) > _SCAN_LIMIT_BYTES:
            return False
        with open(full, 'rb') as f:
            raw = f.read(_SCAN_LIMIT_BYTES)
        if b'\0' in raw[:4096]:
            return False
        text = raw.decode('utf-8', errors='ignore')
    except OSError:
        return False
    return any(rx.search(text) for rx in _TEXT_SECRETS)


def inspect_files(repo: str, files: list[dict]) -> dict[str, dict]:
    """{file: {'kind': 'secret_name' | 'build' | 'large' | 'secret_text'}} for files that deserve a second look. The first three are unchecked
    in the dialog by default; 'secret_text' is only flagged (code that talks about secrets trips it too)."""
    out, scanned = {}, 0
    for f in files:
        path = f['file']
        if f.get('status', '').startswith('D'):
            continue
        kind = _kind_by_name(path)
        full = os.path.join(repo, path)
        if not kind:
            try:
                if os.path.getsize(full) > LARGE_BYTES:
                    kind = 'large'
            except OSError:
                pass
        if not kind and scanned < _SCAN_LIMIT_FILES:
            scanned += 1
            if _has_secret_text(full):
                kind = 'secret_text'
        if kind:
            out[path] = {'kind': kind}
    return out


def line_counts(repo: str, files: list[dict]) -> dict[str, tuple[int, int]]:
    """{file: (added, removed)} for tracked files from `git diff --numstat HEAD`, and (lines, 0) for small new text files."""
    out: dict[str, tuple[int, int]] = {}
    try:
        r = _git(repo, 'diff', '--numstat', 'HEAD')
    except GitError:
        r = None
    if r is not None and r.returncode == 0:
        for line in r.stdout.splitlines():
            parts = line.split('\t')
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                out[parts[2]] = (int(parts[0]), int(parts[1]))
    for f in files[:500]:
        if f['file'] in out or f['status'] not in ('??', 'A'):
            continue
        full = os.path.join(repo, f['file'])
        try:
            if os.path.getsize(full) > 1024 * 1024:
                continue
            with open(full, 'rb') as fh:
                data = fh.read()
            if b'\0' not in data[:4096]:
                out[f['file']] = (data.count(b'\n') + (1 if data and not data.endswith(b'\n') else 0), 0)
        except OSError:
            pass
    return out


_TYPE_BY_DIR = (('tests/', 'test'), ('test_', 'test'), ('docs/', 'docs'), ('.github/', 'ci'), ('readme', 'docs'))


def _type_of(path: str) -> str:
    low = path.lower().replace('\\', '/')
    name = low.rsplit('/', 1)[-1]
    for key, typ in _TYPE_BY_DIR:
        if low.startswith(key) or name.startswith(key) and key != 'tests/':
            return typ
    return 'chore' if name.endswith(('.txt', '.toml', '.yml', '.yaml', '.cfg', '.ini', '.json', '.bat', '.spec')) else 'code'


def suggest_message(files: list[dict]) -> str:
    """A short English subject in the project's `type(scope): summary` style, from the paths and statuses alone (no network, no model)."""
    live = [f for f in files if f.get('file')]
    if not live:
        return ''
    kinds = {_type_of(f['file']) for f in live}
    only = kinds.pop() if len(kinds) == 1 else ''
    scopes = []
    for f in live:
        top = f['file'].replace('\\', '/').split('/')[0]
        if '/' in f['file'].replace('\\', '/') and top not in scopes:
            scopes.append(top)
    scope = f'({scopes[0]})' if len(scopes) == 1 else ''
    new = sum(1 for f in live if f['status'] in ('??', 'A'))
    gone = sum(1 for f in live if f['status'].startswith('D'))
    if only in ('test', 'docs', 'ci', 'chore'):
        typ = only
    elif gone and gone == len(live):
        typ = 'chore'
    else:
        typ = 'feat' if new and new * 2 >= len(live) else 'fix' if not new else 'chore'
    names = ', '.join(os.path.basename(f['file']) for f in live[:3]) + (f' and {len(live) - 3} more' if len(live) > 3 else '')
    verb = 'remove' if gone == len(live) else 'add' if new == len(live) else 'update'
    return f'{typ}{scope}: {verb} {names}'


def undo_last_commit(repo: str) -> tuple[bool, str]:
    """`git reset --mixed HEAD~1`: the commit disappears, the files stay as they were. Refused when the commit is already on a remote branch."""
    try:
        if not _git(repo, 'rev-parse', '--verify', '-q', 'HEAD').stdout.strip():
            return False, 'В репозитории ещё нет коммитов.'
        if _git(repo, 'branch', '-r', '--contains', 'HEAD').stdout.strip():
            return False, 'Этот коммит уже отправлен на сервер: откатить его отсюда нельзя.'
        if _git(repo, 'rev-parse', '--verify', '-q', 'HEAD~1').returncode != 0:
            _git(repo, 'update-ref', '-d', 'HEAD', check=True)     # the only commit: back to an empty history, files stay staged
        else:
            _git(repo, 'reset', '--mixed', 'HEAD~1', check=True)
    except GitError as ex:
        return False, str(ex)
    return True, 'Коммит отменён, изменения остались в файлах.'
