import os
import time
import subprocess
import ctypes
import pygetwindow as gw
from actions import keysend
from actions.system_parts.game_mode import deactivate_game_mode
def press_enter() -> tuple[bool, str]:
    try:
        keysend.press('enter')
        return (True, 'Отправлено')
    except Exception as e:
        return (False, str(e))
def change_keyboard_layout(lang_name: str) -> tuple[bool, str]:
    _LANGID_MAP = {'русский': 1049, 'английский': 1033, 'украинский': 1058, 'немецкий': 1031}
    ln = lang_name.lower()
    target_langid = None
    if any((x in ln for x in ['укр', 'мов'])):
        target_langid = _LANGID_MAP['украинский']
    elif any((x in ln for x in ['англ', 'ингл', 'engl'])):
        target_langid = _LANGID_MAP['английский']
    elif 'русс' in ln:
        target_langid = _LANGID_MAP['русский']
    elif 'нем' in ln:
        target_langid = _LANGID_MAP['немецкий']
    if target_langid is None:
        return (False, f"Язык '{lang_name}' не поддерживается")
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, ctypes.c_void_p]
        user32.PostMessageW.restype = wintypes.BOOL
        count = user32.GetKeyboardLayoutList(0, None)
        if count == 0:
            return (False, 'Не удалось получить список раскладок')
        hkl_array = (ctypes.c_void_p * count)()
        user32.GetKeyboardLayoutList(count, hkl_array)
        installed_hkls = list(hkl_array)
        target_hkl = None
        for hkl in installed_hkls:
            if hkl is None:
                continue
            hkl_masked = hkl & 18446744073709551615
            if hkl_masked & 65535 == target_langid:
                target_hkl = hkl_masked
                break
        if target_hkl is None:
            return (False, f"Раскладка для '{lang_name}' (LANGID {hex(target_langid)}) не установлена в системе")
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return (False, 'Не найдено активное окно')
        user32.PostMessageW(hwnd, 80, 0, ctypes.c_void_p(target_hkl))
        return (True, f'Готово, переключил на {lang_name}')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return (False, str(e))
_BROWSER_NAMES = ('brave', 'chrome', 'firefox', 'msedge', 'opera', 'yandex', 'browser')
_IDE_NAMES = ('visual studio code', 'vscode', 'code', 'pycharm', 'intellij', 'webstorm', 'rider', 'clion', 'cursor', 'sublime')
def _switch_to_hwnd(hwnd: int):
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    else:
        user32.ShowWindow(hwnd, 5)
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
    if fg_tid != cur_tid:
        user32.AttachThreadInput(fg_tid, cur_tid, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(fg_tid, cur_tid, False)
    else:
        user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
def _send_hotkey(vk1: int, vk2: int):
    keysend.hotkey(vk1, vk2)
def open_browser_history():
    hwnd = None
    for win in gw.getAllWindows():
        t = win.title.lower()
        if any((b in t for b in _BROWSER_NAMES)) and win._hWnd:
            hwnd = win._hWnd
            break
    if hwnd:
        _switch_to_hwnd(hwnd)
    else:
        os.startfile('http://')
        time.sleep(2.0)
    _send_hotkey(17, 72)
    return (True, 'История открыта')
def open_terminal():
    ide_hwnd = None
    for win in gw.getAllWindows():
        t = win.title.lower()
        if any((k in t for k in _IDE_NAMES)) and win._hWnd:
            ide_hwnd = win._hWnd
            break
    if ide_hwnd:
        _switch_to_hwnd(ide_hwnd)
        _send_hotkey(17, 192)
        return (True, 'Терминал открыт')
    try:
        subprocess.Popen(['wt'], creationflags=8)
        return (True, 'Терминал открыт')
    except FileNotFoundError:
        pass
    wt_exe = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps', 'wt.exe')
    if os.path.isfile(wt_exe):
        subprocess.Popen([wt_exe], creationflags=8)
        return (True, 'Терминал открыт')
    subprocess.Popen(['cmd.exe'], creationflags=8)
    return (True, 'Терминал открыт')
def _run_ps(cmd: str) -> str:
    return subprocess.run(
        ['powershell', '-NoProfile', '-Command', cmd],
        capture_output=True,
        text=True,
        encoding='utf-8',
        creationflags=134217728,
    ).stdout.strip()
def disable_keyboards_hardware() -> tuple[bool, str]:
    import json
    raw = _run_ps('Get-PnpDevice -Class Keyboard -Status OK | Select-Object -ExpandProperty InstanceId')
    ids = [line.strip() for line in raw.splitlines() if line.strip()]
    if not ids:
        return (False, "Активных клавиатур не обнаружено.")
    state_file = os.path.join('data', 'disabled_keyboards.json')
    os.makedirs('data', exist_ok=True)
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(ids, f)
    disabled_count = 0
    for iid in ids:
        escaped_id = iid.replace('\\', '\\\\')
        res = _run_ps(f'Disable-PnpDevice -InstanceId "{escaped_id}" -Confirm:$false 2>&1')
        if 'Access is denied' in res or 'Отказано в доступе' in res:
            return (False, "Ошибка: требуется запуск Джарвиса от имени Администратора для полного отключения устройств.")
        disabled_count += 1
    return (True, f"Клавиатура полностью отключена ({disabled_count} устр.). Ввод невозможен.")
def enable_keyboards_hardware() -> tuple[bool, str]:
    import json
    state_file = os.path.join('data', 'disabled_keyboards.json')
    if not os.path.exists(state_file):
        return (False, "Данные о заблокированных клавиатурах отсутствуют.")
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            ids = json.load(f)
        for iid in ids:
            escaped_id = iid.replace('\\', '\\\\')
            _run_ps(f'Enable-PnpDevice -InstanceId "{escaped_id}" -Confirm:$false 2>&1')
        os.remove(state_file)
    except Exception as e:
        return (False, f"Ошибка при активации: {e}")
    from core.address import get_address as _ga
    return (True, f"Клавиатура снова активна. Рад вас слышать, {_ga()}.")
def close_active_game() -> tuple[bool, str]:
    try:
        import pyautogui
        pyautogui.hotkey('alt', 'f4')
        time.sleep(1.0)
        return deactivate_game_mode()
    except Exception as e:
        return (False, str(e))
