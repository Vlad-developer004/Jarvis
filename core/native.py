"""The native (Rust) parts of Jarvis: the extension modules and the sidecar program from native/ (see docs/native.md).

There is no Python fallback: file search, window listing, volume control and the output-device check exist only in Rust. `require()`
raises `NativeUnavailable` when a part is not built or does not load, so a broken install fails loudly where the part is used,
while the rest of the app keeps running. Modules are imported on first use, never at import time, so the startup order in main.py
is unaffected.
"""
from __future__ import annotations

import importlib
import os
import sys
import threading

MODULES = {'files': 'jarvis_files', 'windows': 'jarvis_win'}
SIDECARS = {'audio': 'jarvis_audio.exe'}

_lock = threading.Lock()
_loaded: dict[str, object] = {}


class NativeUnavailable(RuntimeError):
    """A native part is missing or cannot run: build it with build.bat (or see docs/native.md)."""


def require(name: str):
    """The loaded extension module for `name` ('files', 'windows'); raises NativeUnavailable."""
    mod_name = MODULES.get(name)
    if mod_name is None:
        raise NativeUnavailable(f'unknown native part: {name}')
    with _lock:
        mod = _loaded.get(name)
        if mod is None:
            try:
                mod = importlib.import_module(mod_name)
                mod.version()   # a stub that imports but cannot run is as good as missing
            except Exception as e:
                raise NativeUnavailable(f'native module {mod_name} is not available: {e}') from e
            _loaded[name] = mod
        return mod


def sidecar_path(name: str) -> str | None:
    """Path of the sidecar program: next to the frozen app (native/), or the cargo output in a source checkout."""
    exe = SIDECARS.get(name)
    if exe is None:
        return None
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.path.join(here, 'native', 'target', 'release', exe)]
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)   # PyInstaller keeps data files next to the exe or in _internal/
        candidates = [os.path.join(base, 'native', exe), os.path.join(base, '_internal', 'native', exe)] + candidates
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def require_sidecar(name: str) -> str:
    path = sidecar_path(name)
    if path is None:
        raise NativeUnavailable(f'native program {SIDECARS.get(name, name)} is not built')
    return path


def status() -> dict[str, dict]:
    """For diagnostics: per part, whether it is present and its version."""
    out: dict[str, dict] = {}
    for name in MODULES:
        try:
            out[name] = {'present': True, 'version': require(name).version()}
        except NativeUnavailable:
            out[name] = {'present': False, 'version': None}
    for name in SIDECARS:
        out[name] = {'present': sidecar_path(name) is not None, 'version': None}
    return out
