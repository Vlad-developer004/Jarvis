import time
from actions import keysend
def send_hardware_key(vk_code: int):
    keysend.press(vk_code)
def send_hotkey_hardware(modifier_vk: int, key_vk: int):
    keysend.hotkey(modifier_vk, key_vk)
def _ensure_en_layout() -> int:
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, 0)
    hkl_prev = user32.GetKeyboardLayout(tid)
    count = user32.GetKeyboardLayoutList(0, None)
    hkl_arr = (ctypes.c_void_p * count)()
    user32.GetKeyboardLayoutList(count, hkl_arr)
    en_hkl = None
    for hkl in hkl_arr:
        if hkl & 65535 == 1033:
            en_hkl = hkl
            break
    if en_hkl and en_hkl != hkl_prev:
        user32.PostMessageW(hwnd, 80, 0, en_hkl)
        time.sleep(0.08)
    return hkl_prev
def _restore_layout(hkl_prev: int):
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, 0)
    current_hkl = user32.GetKeyboardLayout(tid)
    if current_hkl != hkl_prev:
        user32.PostMessageW(hwnd, 80, 0, hkl_prev)
