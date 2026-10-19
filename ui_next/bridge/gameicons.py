"""Game icons for the Games screen: the icon of the game's main .exe as a small PNG data URI.

Best effort: a game without a usable exe (store apps, a missing folder) simply gets no icon and the UI shows initials.
"""
from __future__ import annotations

import base64
import ctypes
import io
import logging
import os
from ctypes import wintypes

_log = logging.getLogger(__name__)
_SKIP = ('unins', 'crash', 'redist', 'setup', 'vc_', 'vcredist', 'dxsetup', 'easyanticheat', 'eac', 'helper', 'report', 'cefprocess', 'webhelper', 'ue4prereq', 'dotnet', 'notification')
_SIZE = 64


def find_exe(install_dir: str) -> str:
    """Largest plausible .exe within two levels of the install folder ('' when none)."""
    if not install_dir or not os.path.isdir(install_dir):
        return ''
    best, best_size = '', 0
    base_depth = install_dir.rstrip('\\/').count(os.sep)
    for root, dirs, files in os.walk(install_dir):
        if root.count(os.sep) - base_depth >= 2:
            dirs[:] = []
        for f in files:
            low = f.lower()
            if not low.endswith('.exe') or any(s in low for s in _SKIP):
                continue
            try:
                size = os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
            if size > best_size:
                best, best_size = os.path.join(root, f), size
    return best


def _icon_png(exe: str) -> bytes:
    from PIL import Image
    import win32gui
    import win32ui
    user32 = ctypes.windll.user32
    hicon = wintypes.HICON()
    iid = wintypes.UINT()
    got = user32.PrivateExtractIconsW(exe, 0, _SIZE, _SIZE, ctypes.byref(hicon), ctypes.byref(iid), 1, 0)
    if got < 1 or not hicon.value:
        return b''
    try:
        info = win32gui.GetIconInfo(hicon.value)
        try:
            bm = win32ui.CreateBitmapFromHandle(info[4])
            w, h = bm.GetInfo()['bmWidth'], bm.GetInfo()['bmHeight']
            img = Image.frombuffer('RGBA', (w, h), bm.GetBitmapBits(True), 'raw', 'BGRA', 0, 1)
            if not any(img.getchannel('A').getdata()):      # legacy icon without alpha: opaque, masked by the 1-bit mask
                img.putalpha(255)
                if info[3]:
                    mask = win32ui.CreateBitmapFromHandle(info[3])
                    mm = Image.frombuffer('1', (w, h), mask.GetBitmapBits(True), 'raw', '1', 0, 1)
                    img.putalpha(mm.point(lambda v: 0 if v else 255))
        finally:
            for hb in info[3:5]:
                if hb:
                    win32gui.DeleteObject(hb)
        out = io.BytesIO()
        img.resize((_SIZE, _SIZE)).save(out, 'PNG', optimize=True)
        return out.getvalue()
    finally:
        user32.DestroyIcon(hicon)


def icon_uri(install_dir: str) -> str:
    try:
        exe = find_exe(install_dir)
        png = _icon_png(exe) if exe else b''
        return 'data:image/png;base64,' + base64.b64encode(png).decode('ascii') if png else ''
    except Exception:
        _log.debug('icon extraction failed for %s', install_dir, exc_info=True)
        return ''
