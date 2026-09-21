"""Unified synthetic key-press transport.

Single SendInput+scancode implementation (the only mechanism in this codebase
already proven to work across browsers, regular apps, and DirectX games — see
the Photoshop hotkey table this was lifted from) replacing the previously
fragmented keybd_event / pyautogui / pydirectinput call sites.
"""
import ctypes
import time
from ctypes import wintypes
from actions.keysend_parts.keymap import resolve_vk, _EXTENDED_VKS

_ULONG_PTR = getattr(wintypes, 'ULONG_PTR', ctypes.c_size_t)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', _ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG), ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD), ('dwExtraInfo', _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', _KEYBDINPUT), ('mi', _MOUSEINPUT), ('hi', _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', _INPUT_UNION)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_SCANCODE = 0x0008
_KEYEVENTF_EXTENDEDKEY = 0x0001
_MAPVK_VK_TO_VSC = 0
_MAPVK_VK_TO_VSC_EX = 4

_user32 = ctypes.windll.user32


def _build_input(vk: int, key_up: bool) -> _INPUT:
    extended = vk in _EXTENDED_VKS
    mapcode = _MAPVK_VK_TO_VSC_EX if extended else _MAPVK_VK_TO_VSC
    scan = _user32.MapVirtualKeyW(vk, mapcode)
    flags = _KEYEVENTF_SCANCODE | (_KEYEVENTF_KEYUP if key_up else 0)
    if extended:
        flags |= _KEYEVENTF_EXTENDEDKEY
    return _INPUT(type=_INPUT_KEYBOARD, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))


def _send(inputs: list[_INPUT]) -> None:
    arr = (_INPUT * len(inputs))(*inputs)
    sent = _user32.SendInput(len(inputs), ctypes.byref(arr), ctypes.sizeof(_INPUT))
    if sent != len(inputs):
        raise RuntimeError(f'SendInput sent={sent}/{len(inputs)}')


def key_down(key) -> None:
    _send([_build_input(resolve_vk(key), key_up=False)])


def key_up(key) -> None:
    _send([_build_input(resolve_vk(key), key_up=True)])


def press(key) -> None:
    vk = resolve_vk(key)
    _send([_build_input(vk, key_up=False), _build_input(vk, key_up=True)])


def hold(key, duration: float = 0.15) -> None:
    vk = resolve_vk(key)
    _send([_build_input(vk, key_up=False)])
    time.sleep(duration)
    _send([_build_input(vk, key_up=True)])


def hotkey(*keys) -> None:
    """Modifiers (all but the last key) held down, last key tapped, released in reverse order."""
    vks = [resolve_vk(k) for k in keys]
    mods, main = vks[:-1], vks[-1]
    seq = [_build_input(m, key_up=False) for m in mods]
    seq.append(_build_input(main, key_up=False))
    seq.append(_build_input(main, key_up=True))
    seq.extend(_build_input(m, key_up=True) for m in reversed(mods))
    _send(seq)
