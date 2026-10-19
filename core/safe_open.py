"""Opening a file or link the user named by voice or from a saved session.

`os.startfile` runs whatever Windows associates with the file: an .exe or .bat found by a voice search would simply start. Files that can
execute code are refused here; documents, media and folders open normally. Links must be http(s) or mailto.
"""
from __future__ import annotations

import os
from pathlib import Path

RUNNABLE_EXTS = frozenset({
    'exe', 'com', 'scr', 'pif', 'bat', 'cmd', 'ps1', 'psm1', 'psd1', 'vbs', 'vbe', 'js', 'jse', 'wsf', 'wsh', 'msi', 'msp', 'mst', 'hta', 'reg',
    'cpl', 'jar', 'dll', 'sys', 'lnk', 'url', 'scf', 'inf', 'gadget', 'application', 'appref-ms', 'msc', 'ocx', 'drv', 'chm', 'sh',
})
LINK_SCHEMES = ('http://', 'https://', 'mailto:')


def is_runnable(path: str | os.PathLike) -> bool:
    """True when opening this file may execute code (by extension; double extensions such as `report.pdf.exe` count by the last one)."""
    name = Path(str(path)).name.strip().rstrip('. ')
    return name.rsplit('.', 1)[-1].lower() in RUNNABLE_EXTS if '.' in name else False


def open_user_file(path: str | os.PathLike) -> None:
    """Opens `path` with its default program. Raises PermissionError for files that can run code, OSError when Windows cannot open it."""
    p = os.path.normpath(str(path))
    if is_runnable(p):
        raise PermissionError('files that can run code are not opened from commands')
    os.startfile(p)   # nosec B606


def open_user_link(url: str) -> None:
    u = str(url or '').strip()
    if not u.lower().startswith(LINK_SCHEMES) or any(c in u for c in '\r\n\0') or len(u) > 2000:
        raise PermissionError('only http, https and mailto links are opened')
    os.startfile(u)   # nosec B606
