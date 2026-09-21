"""Global push-to-talk: holding Right Ctrl acts like saying the wake word,
letting the user skip "Jarvis" while the key is held. Uses a low-level
keyboard hook (same technique as actions/keyboard_lock.py) so it works
system-wide, including while a game has focus.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time
from core.system import app_state

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_RCONTROL = 0xA3

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ctypes.wintypes has never defined LRESULT (a signed, pointer-sized
# integer on Win32) despite having WPARAM/LPARAM — define it ourselves.
LRESULT = ctypes.c_ssize_t


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode', wt.DWORD),
        ('scanCode', wt.DWORD),
        ('flags', wt.DWORD),
        ('time', wt.DWORD),
        ('dwExtraInfo', ctypes.POINTER(wt.ULONG)),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = wt.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT


class _PTTState:
    def __init__(self):
        self.hook = None
        self.proc = None
        self.held = False


_state = _PTTState()


def _hook_callback(nCode, wParam, lParam):
    if nCode >= 0:
        kb = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
        if kb.vkCode == VK_RCONTROL:
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                # Windows auto-repeats KEYDOWN while the key stays held, which
                # keeps refreshing last_command_time so the active window
                # doesn't expire mid-hold.
                _state.held = True
                app_state.jarvis_active = True
                app_state.last_command_time = time.time()
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                _state.held = False
    return user32.CallNextHookEx(_state.hook, nCode, wParam, lParam)


def _message_loop():
    _state.proc = HOOKPROC(_hook_callback)
    _state.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _state.proc, None, 0)
    if not _state.hook:
        err = kernel32.GetLastError()
        print(f"[PTT] Failed to set keyboard hook. Error code: {err}", flush=True)
        return
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def start_push_to_talk() -> None:
    if _state.hook is None:
        threading.Thread(target=_message_loop, daemon=True, name='PTT-Hook').start()
