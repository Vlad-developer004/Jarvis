from __future__ import annotations
import ctypes
from actions import keysend
from core.system import get_foreground_process_name
from core.responses import spk
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
    keysend.press(vk)
def _sendinput_hotkey(vks: list[int]) -> None:
    keysend.hotkey(*vks)
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
    keysend.hotkey(*keys)
def _press(key: str) -> None:
    keysend.press(key)
def _type(text: str) -> None:
    import pyautogui
    pyautogui.write(text, interval=0.01)
def _palette_action(name: str) -> None:
    if name == 'mask':
        _hotkey('alt', 'l')
        _press('m')
        _press('r')

# ---------------------------------------------------------------------------
# cmd -> action lookup tables. Each entry is a zero-arg callable; to add a new
# Photoshop/Figma shortcut, add one row here instead of a new elif branch.
# ---------------------------------------------------------------------------
_VK = {
    'CTRL': 0x11, 'SHIFT': 0x10, 'ALT': 0x12,
    'F5': 0x74, 'F6': 0x75, 'F7': 0x76,
    'ESC': 0x1B,
    'PLUS': 0xBB,
    'MINUS': 0xBD,
    '0': 0x30, '1': 0x31,
}
def _vk_letter(ch: str) -> int:
    return ord(ch.upper())

_PS_ACTIONS = {
    'ps_undo': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('Z')]),
    'ps_redo': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['SHIFT'], _vk_letter('Z')]),
    'ps_save': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('S')]),
    'ps_save_as': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['SHIFT'], _vk_letter('S')]),
    'ps_export_as': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['ALT'], _VK['SHIFT'], _vk_letter('W')]),
    'ps_new_layer': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['SHIFT'], _vk_letter('N')]),
    'ps_dup_layer': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('J')]),
    'ps_merge_down': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('E')]),
    'ps_group': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('G')]),
    'ps_ungroup': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['SHIFT'], _vk_letter('G')]),
    'ps_invert': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('I')]),
    'ps_levels': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('L')]),
    'ps_curves': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('M')]),
    'ps_hue_sat': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('U')]),
    'ps_color_balance': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('B')]),
    'ps_brush': lambda: _sendinput_press(_vk_letter('B')),
    'ps_eraser': lambda: _sendinput_press(_vk_letter('E')),
    'ps_move': lambda: _sendinput_press(_vk_letter('V')),
    'ps_lasso': lambda: _sendinput_press(_vk_letter('L')),
    'ps_marquee': lambda: _sendinput_press(_vk_letter('M')),
    'ps_eyedropper': lambda: _sendinput_press(_vk_letter('I')),
    'ps_text': lambda: _sendinput_press(_vk_letter('T')),
    'ps_hand': lambda: _sendinput_press(_vk_letter('H')),
    'ps_zoom': lambda: _sendinput_press(_vk_letter('Z')),
    'ps_zoom_in': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['PLUS']]),
    'ps_zoom_out': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['MINUS']]),
    'ps_fit': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['0']]),
    'ps_100': lambda: _sendinput_hotkey([_VK['CTRL'], _VK['1']]),
    'ps_layers_panel': lambda: _sendinput_press(_VK['F7']),
    'ps_brushes_panel': lambda: _sendinput_press(_VK['F5']),
    'ps_color_panel': lambda: _sendinput_press(_VK['F6']),
    'ps_deselect': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('D')]),
    'ps_select_all': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('A')]),
    'ps_transform': lambda: _sendinput_hotkey([_VK['CTRL'], _vk_letter('T')]),
    'ps_fill': lambda: _sendinput_hotkey([_VK['SHIFT'], _VK['F5']]),
    'ps_mask': lambda: _palette_action('mask'),
    'ps_default_colors': lambda: _sendinput_press(_vk_letter('D')),
    'ps_swap_colors': lambda: _sendinput_press(_vk_letter('X')),
}

_FIGMA_ACTIONS = {
    'figma_undo': lambda: _hotkey('ctrl', 'z'),
    'figma_redo': lambda: _hotkey('ctrl', 'shift', 'z'),
    'figma_save': lambda: _hotkey('ctrl', 's'),
    'figma_duplicate': lambda: _hotkey('ctrl', 'd'),
    'figma_group': lambda: _hotkey('ctrl', 'g'),
    'figma_ungroup': lambda: _hotkey('ctrl', 'shift', 'g'),
    'figma_copy': lambda: _hotkey('ctrl', 'c'),
    'figma_paste': lambda: _hotkey('ctrl', 'v'),
    'figma_component': lambda: _hotkey('ctrl', 'alt', 'k'),
    'figma_detach_instance': lambda: _hotkey('ctrl', 'alt', 'b'),
    'figma_auto_layout': lambda: _hotkey('shift', 'a'),
    'figma_align_left': lambda: _hotkey('alt', 'a'),
    'figma_align_center': lambda: _hotkey('alt', 'h'),
    'figma_align_right': lambda: _hotkey('alt', 'd'),
    'figma_align_top': lambda: _hotkey('alt', 'w'),
    'figma_align_middle': lambda: _hotkey('alt', 'v'),
    'figma_align_bottom': lambda: _hotkey('alt', 's'),
    'figma_bring_front': lambda: _hotkey('ctrl', 'shift', ']'),
    'figma_send_back': lambda: _hotkey('ctrl', 'shift', '['),
    'figma_bring_forward': lambda: _hotkey('ctrl', ']'),
    'figma_send_backward': lambda: _hotkey('ctrl', '['),
    'figma_frame': lambda: _press('f'),
    'figma_rect': lambda: _press('r'),
    'figma_ellipse': lambda: _press('o'),
    'figma_line': lambda: _press('l'),
    'figma_arrow': lambda: _hotkey('shift', 'l'),
    'figma_pen': lambda: _press('p'),
    'figma_text': lambda: _press('t'),
    'figma_hand': lambda: _press('h'),
    'figma_zoom': lambda: _press('z'),
    'figma_zoom_in': lambda: _hotkey('ctrl', '+'),
    'figma_zoom_out': lambda: _hotkey('ctrl', '-'),
    'figma_fit': lambda: _hotkey('shift', '1'),
    'figma_select_all': lambda: _hotkey('ctrl', 'a'),
    'figma_deselect': lambda: _press('esc'),
    'figma_lock': lambda: _hotkey('ctrl', 'shift', 'l'),
    'figma_hide': lambda: _hotkey('ctrl', 'shift', 'h'),
    'figma_toggle_ui': lambda: _hotkey('ctrl', '\\'),
    'figma_export': lambda: _hotkey('ctrl', 'shift', 'e'),
}

def _run_creative_action(handler, cmd: str, action, error_key: str) -> None:
    restore_layout = _switch_layout_en_temporarily()
    try:
        action()
    except Exception as exc:
        try:
            fg = get_foreground_process_name() or ''
        except Exception:
            fg = ''
        print(f'[{cmd.split("_")[0]}] error cmd={cmd!r} fg={fg!r} err={exc!r}', flush=True)
        handler.speak(spk(error_key))
        return
    finally:
        try:
            if restore_layout:
                restore_layout()
        except Exception:
            pass
    handler.play_response()

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
                handler.speak(spk('ps.not_active_v2'))
                return
        action = _PS_ACTIONS.get(cmd)
        if action is None:
            handler.speak(spk('ps.unknown_cmd'))
            return
        _run_creative_action(handler, cmd, action, 'ps.send_error_v2')
        return
    if cmd.startswith('figma_'):
        if not (_ensure_process('figma') or _ensure_process('chrome') or _ensure_process('brave') or _ensure_process('msedge')):
            handler.speak(spk('figma.not_active'))
            return
        action = _FIGMA_ACTIONS.get(cmd)
        if action is None:
            handler.speak(spk('figma.unknown_cmd'))
            return
        _run_creative_action(handler, cmd, action, 'figma.send_error_v2')
        return
    handler.speak(spk('cmd.not_supported'))
