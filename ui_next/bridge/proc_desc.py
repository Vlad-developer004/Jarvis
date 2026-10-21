"""Short description of a program for the process list: the FileDescription from the version resource of the exe (what Task Manager shows as
"Description"), e.g. "Host Process for Windows Services". Plain version.dll calls, no COM. Cached per file and file time."""
from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes

_CACHE: dict = {}


def _read(path: str) -> str:
    ver = ctypes.WinDLL('version')
    ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    ver.GetFileVersionInfoW.restype = wintypes.BOOL
    ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    ver.VerQueryValueW.restype = wintypes.BOOL
    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return ''
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, buf):
        return ''
    ptr, ln = ctypes.c_void_p(), wintypes.UINT()
    tables = []
    if ver.VerQueryValueW(buf, '\\VarFileInfo\\Translation', ctypes.byref(ptr), ctypes.byref(ln)) and ln.value >= 4:
        raw = ctypes.string_at(ptr.value, ln.value)
        tables = [struct.unpack('<HH', raw[i:i + 4]) for i in range(0, len(raw) - 3, 4)]
    tables += [(0x0409, 0x04B0), (0x0409, 0x04E4), (0x0419, 0x04B0)]
    for lang, cp in tables:
        if ver.VerQueryValueW(buf, f'\\StringFileInfo\\{lang:04x}{cp:04x}\\FileDescription', ctypes.byref(ptr), ctypes.byref(ln)) and ln.value:
            text = ctypes.wstring_at(ptr.value, ln.value).strip('\x00 ').strip()
            if text:
                return text
    return ''


def description(path: str) -> str:
    """FileDescription of the exe, '' when it has none. Never raises."""
    try:
        key = (path.lower(), os.path.getmtime(path))
    except OSError:
        return ''
    if key not in _CACHE:
        if len(_CACHE) > 800:
            _CACHE.clear()
        try:
            _CACHE[key] = _read(path)[:80]
        except Exception:
            _CACHE[key] = ''
    return _CACHE[key]
