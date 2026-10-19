"""Starts and stops the window process (the Tauri shell) for the core.

The shell is a single-instance program: starting it while a window is already open just brings that window forward and exits at once.
The core therefore only treats an exit as "the user chose Quit in the tray" when the process lived for a while.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_started_at = 0.0
_MIN_LIFETIME = 5.0
_NAMES = ('jarvis-ui.exe',)


def _roots() -> list[Path]:
    here = Path(__file__).resolve().parent
    out = []
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).resolve().parent
        out += [base / 'shell', base / '_internal' / 'shell']
    out += [here / 'shell' / 'src-tauri' / 'target' / 'release']
    return out


def find_exe() -> Path | None:
    override = os.environ.get('JARVIS_SHELL_EXE', '').strip()
    if override and Path(override).is_file():
        return Path(override)
    for root in _roots():
        for name in _NAMES:
            p = root / name
            if p.is_file():
                return p
    return None


def is_running() -> bool:
    with _lock:
        return _proc is not None and _proc.poll() is None


def launch() -> bool:
    """Starts the window process; False when there is no shell program or it could not be started."""
    global _proc, _started_at
    exe = find_exe()
    if exe is None:
        _log.warning('window shell not found: the assistant runs without a window')
        return False
    env = dict(os.environ)
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        proc = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent), creationflags=flags, close_fds=True)   # nosec B603
    except OSError as e:
        _log.warning('window shell did not start: %s', e)
        return False
    with _lock:
        _proc, _started_at = proc, time.monotonic()
    return True


def ensure_running() -> bool:
    """A window exists afterwards: already connected, already started, or started now."""
    try:
        from ui_next import bridge
        if bridge.connected() or is_running():
            return True
    except Exception:
        _swallow()
    return launch()


def watch(on_quit) -> None:
    """Calls `on_quit()` once when the window process ends after living long enough to be a real window (the user chose Quit in the tray)."""
    def run():
        while True:
            with _lock:
                proc, started = _proc, _started_at
            if proc is None:
                time.sleep(0.5)
                continue
            proc.wait()
            if time.monotonic() - started >= _MIN_LIFETIME:
                try:
                    on_quit()
                except Exception:
                    _swallow()
                return
            with _lock:
                if _proc is proc:
                    return          # forwarded to a window that was already open: nothing to watch
    threading.Thread(target=run, name='ui-shell-watch', daemon=True).start()


def stop() -> None:
    """Closes the window process (the core is exiting)."""
    with _lock:
        proc = _proc
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            _swallow()
