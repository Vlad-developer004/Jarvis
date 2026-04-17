from __future__ import annotations
import ctypes
from ctypes import wintypes
from core.system import get_foreground_process_name
_ULONG_PTR = getattr(wintypes, 'ULONG_PTR', ctypes.c_size_t)
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR)
    ]
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', _ULONG_PTR),
    ]
class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]
class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ('ki', KEYBDINPUT),
        ('mi', MOUSEINPUT),
        ('hi', HARDWAREINPUT)
    ]
class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', _INPUT_UNION)]
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
def _get_langid_from_foreground() -> int | None:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        hkl = user32.GetKeyboardLayout(tid)
        return int(hkl) & 0xFFFF
    except Exception:
        return None
def _switch_layout_en_temporarily():
    try:
        from actions.system import change_keyboard_layout
    except Exception:
        change_keyboard_layout = None
    prev = _get_langid_from_foreground()
    try:
        if change_keyboard_layout:
            change_keyboard_layout('английский')
    except Exception:
        pass
    def _restore():
        try:
            if not change_keyboard_layout or prev is None:
                return
            if prev == 1049:
                change_keyboard_layout('русский')
            elif prev == 1033:
                change_keyboard_layout('английский')
        except Exception:
            pass
    return _restore
def _sendinput_press(vk: int) -> None:
    user32 = ctypes.windll.user32
    scan = user32.MapVirtualKeyW(vk, 0)
    down = INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=KEYEVENTF_SCANCODE, time=0, dwExtraInfo=0)))
    up   = INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))
    sent = user32.SendInput(2, ctypes.byref((INPUT * 2)(down, up)), ctypes.sizeof(INPUT))
    if sent != 2:
        raise RuntimeError(f'SendInput sent={sent}')
def _sendinput_hotkey(vks: list[int]) -> None:
    user32 = ctypes.windll.user32
    def _inp(vk: int, up: bool) -> INPUT:
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
        return INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))
    mods = vks[:-1]
    main = vks[-1]
    seq = []
    for m in mods:
        seq.append(_inp(m, False))
    seq.append(_inp(main, False))
    seq.append(_inp(main, True))
    for m in reversed(mods):
        seq.append(_inp(m, True))
    arr = (INPUT * len(seq))(*seq)
    sent = user32.SendInput(len(seq), ctypes.byref(arr), ctypes.sizeof(INPUT))
    if sent != len(seq):
        raise RuntimeError(f'SendInput sent={sent}/{len(seq)}')
def _ensure_process(expected: str) -> bool:
    p = (get_foreground_process_name() or '').lower()
    return (expected.lower() in p)
def _try_focus_photoshop() -> bool:
    try:
        import pygetwindow as gw
        from core.system import force_foreground
        wins = []
        try:
            wins = gw.getAllWindows()
        except Exception:
            wins = []
        for w in wins:
            try:
                title = (getattr(w, 'title', '') or '').lower()
                if 'photoshop' not in title:
                    continue
                if hasattr(w, 'isMinimized') and w.isMinimized:
                    try:
                        w.restore()
                    except Exception:
                        pass
                try:
                    w.activate()
                except Exception:
                    pass
                try:
                    if hasattr(w, '_hWnd'):
                        force_foreground(int(w._hWnd))
                except Exception:
                    pass
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False
def _hotkey(*keys: str) -> None:
    import pyautogui
    try:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.02
    except Exception:
        pass
    pyautogui.hotkey(*keys)
def _press(key: str) -> None:
    import pyautogui
    try:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.02
    except Exception:
        pass
    pyautogui.press(key)
def _type(text: str) -> None:
    import pyautogui
    pyautogui.write(text, interval=0.01)
def _palette_action(name: str) -> None:
    if name == 'mask':
        _hotkey('alt', 'l')
        _press('m')
        _press('r')
def handle_creative(handler, cmd: str, text_lower: str) -> None:
    if cmd.startswith('ps_'):
        if not _ensure_process('photoshop'):
            if _try_focus_photoshop():
                try:
                    import time as _t
                    _t.sleep(0.25)
                except Exception:
                    pass
            if not _ensure_process('photoshop'):
                handler.speak('Окно Photoshop не активно. Откройте Photoshop и сделайте его активным.')
                return
        restore_layout = _switch_layout_en_temporarily()
        try:
            VK = {
                'CTRL': 0x11, 'SHIFT': 0x10, 'ALT': 0x12,
                'F5': 0x74, 'F6': 0x75, 'F7': 0x76,
                'ESC': 0x1B,
                'PLUS': 0xBB,
                'MINUS': 0xBD,
                '0': 0x30, '1': 0x31,
            }
            def _vk_letter(ch: str) -> int:
                return ord(ch.upper())
            if cmd == 'ps_undo': _sendinput_hotkey([VK['CTRL'], _vk_letter('Z')])
            elif cmd == 'ps_redo': _sendinput_hotkey([VK['CTRL'], VK['SHIFT'], _vk_letter('Z')])
            elif cmd == 'ps_save': _sendinput_hotkey([VK['CTRL'], _vk_letter('S')])
            elif cmd == 'ps_save_as': _sendinput_hotkey([VK['CTRL'], VK['SHIFT'], _vk_letter('S')])
            elif cmd == 'ps_export_as': _sendinput_hotkey([VK['CTRL'], VK['ALT'], VK['SHIFT'], _vk_letter('W')])
            elif cmd == 'ps_new_layer': _sendinput_hotkey([VK['CTRL'], VK['SHIFT'], _vk_letter('N')])
            elif cmd == 'ps_dup_layer': _sendinput_hotkey([VK['CTRL'], _vk_letter('J')])
            elif cmd == 'ps_merge_down': _sendinput_hotkey([VK['CTRL'], _vk_letter('E')])
            elif cmd == 'ps_group': _sendinput_hotkey([VK['CTRL'], _vk_letter('G')])
            elif cmd == 'ps_ungroup': _sendinput_hotkey([VK['CTRL'], VK['SHIFT'], _vk_letter('G')])
            elif cmd == 'ps_invert': _sendinput_hotkey([VK['CTRL'], _vk_letter('I')])
            elif cmd == 'ps_levels': _sendinput_hotkey([VK['CTRL'], _vk_letter('L')])
            elif cmd == 'ps_curves': _sendinput_hotkey([VK['CTRL'], _vk_letter('M')])
            elif cmd == 'ps_hue_sat': _sendinput_hotkey([VK['CTRL'], _vk_letter('U')])
            elif cmd == 'ps_color_balance': _sendinput_hotkey([VK['CTRL'], _vk_letter('B')])
            elif cmd == 'ps_brush': _sendinput_press(_vk_letter('B'))
            elif cmd == 'ps_eraser': _sendinput_press(_vk_letter('E'))
            elif cmd == 'ps_move': _sendinput_press(_vk_letter('V'))
            elif cmd == 'ps_lasso': _sendinput_press(_vk_letter('L'))
            elif cmd == 'ps_marquee': _sendinput_press(_vk_letter('M'))
            elif cmd == 'ps_eyedropper': _sendinput_press(_vk_letter('I'))
            elif cmd == 'ps_text': _sendinput_press(_vk_letter('T'))
            elif cmd == 'ps_hand': _sendinput_press(_vk_letter('H'))
            elif cmd == 'ps_zoom': _sendinput_press(_vk_letter('Z'))
            elif cmd == 'ps_zoom_in': _sendinput_hotkey([VK['CTRL'], VK['PLUS']])
            elif cmd == 'ps_zoom_out': _sendinput_hotkey([VK['CTRL'], VK['MINUS']])
            elif cmd == 'ps_fit': _sendinput_hotkey([VK['CTRL'], VK['0']])
            elif cmd == 'ps_100': _sendinput_hotkey([VK['CTRL'], VK['1']])
            elif cmd == 'ps_layers_panel': _sendinput_press(VK['F7'])
            elif cmd == 'ps_brushes_panel': _sendinput_press(VK['F5'])
            elif cmd == 'ps_color_panel': _sendinput_press(VK['F6'])
            elif cmd == 'ps_deselect': _sendinput_hotkey([VK['CTRL'], _vk_letter('D')])
            elif cmd == 'ps_select_all': _sendinput_hotkey([VK['CTRL'], _vk_letter('A')])
            elif cmd == 'ps_transform': _sendinput_hotkey([VK['CTRL'], _vk_letter('T')])
            elif cmd == 'ps_fill': _sendinput_hotkey([VK['SHIFT'], VK['F5']])
            elif cmd == 'ps_mask': _palette_action('mask')
            elif cmd == 'ps_default_colors': _sendinput_press(_vk_letter('D'))
            elif cmd == 'ps_swap_colors': _sendinput_press(_vk_letter('X'))
            else:
                handler.speak('Команда Photoshop не распознана.')
                return
        except Exception as exc:
            try:
                fg = get_foreground_process_name() or ''
            except Exception:
                fg = ''
            print(f'[ps] error cmd={cmd!r} fg={fg!r} err={exc!r}', flush=True)
            handler.speak('Не получилось отправить команду в Photoshop. Проверьте, что Photoshop не запущен от администратора.')
            return
        finally:
            try:
                if restore_layout:
                    restore_layout()
            except Exception:
                pass
        handler.play_response()
        return
    if cmd.startswith('figma_'):
        if not (_ensure_process('figma') or _ensure_process('chrome') or _ensure_process('brave') or _ensure_process('msedge')):
            handler.speak('Сэр, активируйте окно Figma.')
            return
        restore_layout = _switch_layout_en_temporarily()
        try:
            if cmd == 'figma_undo': _hotkey('ctrl', 'z')
            elif cmd == 'figma_redo': _hotkey('ctrl', 'shift', 'z')
            elif cmd == 'figma_save': _hotkey('ctrl', 's')
            elif cmd == 'figma_duplicate': _hotkey('ctrl', 'd')
            elif cmd == 'figma_group': _hotkey('ctrl', 'g')
            elif cmd == 'figma_ungroup': _hotkey('ctrl', 'shift', 'g')
            elif cmd == 'figma_copy': _hotkey('ctrl', 'c')
            elif cmd == 'figma_paste': _hotkey('ctrl', 'v')
            elif cmd == 'figma_component': _hotkey('ctrl', 'alt', 'k')
            elif cmd == 'figma_detach_instance': _hotkey('ctrl', 'alt', 'b')
            elif cmd == 'figma_auto_layout': _hotkey('shift', 'a')
            elif cmd == 'figma_align_left': _hotkey('alt', 'a')
            elif cmd == 'figma_align_center': _hotkey('alt', 'h')
            elif cmd == 'figma_align_right': _hotkey('alt', 'd')
            elif cmd == 'figma_align_top': _hotkey('alt', 'w')
            elif cmd == 'figma_align_middle': _hotkey('alt', 'v')
            elif cmd == 'figma_align_bottom': _hotkey('alt', 's')
            elif cmd == 'figma_bring_front': _hotkey('ctrl', 'shift', ']')
            elif cmd == 'figma_send_back': _hotkey('ctrl', 'shift', '[')
            elif cmd == 'figma_bring_forward': _hotkey('ctrl', ']')
            elif cmd == 'figma_send_backward': _hotkey('ctrl', '[')
            elif cmd == 'figma_frame': _press('f')
            elif cmd == 'figma_rect': _press('r')
            elif cmd == 'figma_ellipse': _press('o')
            elif cmd == 'figma_line': _press('l')
            elif cmd == 'figma_arrow': _hotkey('shift', 'l')
            elif cmd == 'figma_pen': _press('p')
            elif cmd == 'figma_text': _press('t')
            elif cmd == 'figma_hand': _press('h')
            elif cmd == 'figma_zoom': _press('z')
            elif cmd == 'figma_zoom_in': _hotkey('ctrl', '+')
            elif cmd == 'figma_zoom_out': _hotkey('ctrl', '-')
            elif cmd == 'figma_fit': _hotkey('shift', '1')
            elif cmd == 'figma_select_all': _hotkey('ctrl', 'a')
            elif cmd == 'figma_deselect': _press('esc')
            elif cmd == 'figma_lock': _hotkey('ctrl', 'shift', 'l')
            elif cmd == 'figma_hide': _hotkey('ctrl', 'shift', 'h')
            elif cmd == 'figma_toggle_ui': _hotkey('ctrl', '\\')
            elif cmd == 'figma_export': _hotkey('ctrl', 'shift', 'e')
            else:
                handler.speak('Команда Figma не распознана.')
                return
        except Exception as exc:
            try:
                fg = get_foreground_process_name() or ''
            except Exception:
                fg = ''
            print(f'[figma] error cmd={cmd!r} fg={fg!r} err={exc!r}', flush=True)
            handler.speak('Не получилось отправить команду в Figma. Проверьте, что приложение не запущено от администратора.')
            return
        finally:
            try:
                if restore_layout:
                    restore_layout()
            except Exception:
                pass
        handler.play_response()
        return
    handler.speak('Команда не поддерживается.')
