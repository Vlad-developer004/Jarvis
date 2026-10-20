"""Snapshot of the top-level windows from the Rust lister (native/jarvis_win); there is no pywin32 path.

`snapshot()` returns `Win(hwnd, title, exe, visible, iconic, cls)` in z-order; `exe` is the lower-case file name of the owning process
("" when it cannot be read). One call replaces EnumWindows plus several Win32 calls per window from Python.
"""
from __future__ import annotations

from typing import NamedTuple

from core import native


class Win(NamedTuple):
    hwnd: int
    title: str
    exe: str
    visible: bool
    iconic: bool
    cls: str


def snapshot(visible_only: bool = False) -> list[Win]:
    """Raises native.NativeUnavailable when jarvis_win is not built."""
    return [Win(*row) for row in native.require('windows').list_windows(visible_only)]
