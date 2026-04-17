import ctypes
import ctypes.wintypes as wt
import threading
import time
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
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
user32.DispatchMessageW.restype = wt.LRESULT
kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wt.DWORD
class _KeyboardState:
    def __init__(self):
        self.hook = None
        self.locked = False
        self.proc = None
_state = _KeyboardState()
def _hook_callback(nCode, wParam, lParam):
    if nCode >= 0 and _state.locked:
        return 1
    return user32.CallNextHookEx(_state.hook, nCode, wParam, lParam)
def _message_loop():
    _state.proc = HOOKPROC(_hook_callback)
    _state.hook = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL,
        _state.proc,
        None,
        0
    )
    if not _state.hook:
        err = kernel32.GetLastError()
        print(f"[LOCK] Failed to set keyboard hook. Error code: {err}", flush=True)
        return
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
def start_lock_service():
    if _state.hook is None:
        t = threading.Thread(target=_message_loop, daemon=True)
        t.start()
def lock_keyboard() -> tuple[bool, str]:
    if not _state.hook:
        start_lock_service()
        time.sleep(0.2)
    if not _state.hook:
        return (False, "Не удалось инициализировать систему блокировки.")
    _state.locked = True
    return (True, "Клавиатура заблокирована. Сэр, чтобы разблокировать, скажите: разблокируй клавиатуру.")
def unlock_keyboard() -> tuple[bool, str]:
    _state.locked = False
    return (True, "Клавиатура разблокирована.")
def is_keyboard_locked() -> bool:
    return _state.locked
