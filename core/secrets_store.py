"""Writes API keys and passwords to the secrets file (``config.get_secrets_path()``) safely.

The file is read by python-dotenv at startup, so a value written here must survive that parser unchanged and must never be able
to add a second variable. Writes are atomic: a crash halfway leaves the previous file in place instead of an empty one.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
from pathlib import Path

_log = logging.getLogger(__name__)
_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_lock = threading.Lock()


def _escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _line_key(line: str) -> str:
    s = line.strip()
    if not s or s.startswith('#') or '=' not in s:
        return ''
    if s.startswith('export '):
        s = s[7:]
    return s.split('=', 1)[0].strip()


def set_secret(key: str, value: str, path: str | os.PathLike | None = None) -> bool:
    """Sets ``key`` in the secrets file and in ``os.environ``; returns False (nothing changed) when the key or value is not storable."""
    value = '' if value is None else str(value)
    if not _KEY_RE.match(str(key or '')):
        _log.error('secrets: refused an invalid variable name')
        return False
    if any(c in value for c in '\r\n\0'):
        _log.error('secrets: refused a value with a line break for %s', key)
        return False
    if path is None:
        from config_pack.config import get_secrets_path
        path = get_secrets_path()
    env_path = Path(path)
    with _lock:
        try:
            lines = env_path.read_text(encoding='utf-8').splitlines() if env_path.exists() else []
            new_line = f'{key}="{_escape(value)}"'
            for i, line in enumerate(lines):
                if _line_key(line) == key:
                    lines[i] = new_line
                    break
            else:
                if lines and lines[-1].strip():
                    lines.append('')
                lines.append(new_line)
            env_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.secrets-', suffix='.tmp', dir=str(env_path.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
                    f.write('\n'.join(lines) + '\n')
                os.replace(tmp, env_path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            from core.redact import describe_error
            _log.error('secrets: could not save %s: %s', key, describe_error(e))
            return False
    os.environ[key] = value
    return True
