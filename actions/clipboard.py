import time
import pyperclip
from actions import keysend
_clipboard_history = []
MAX_HISTORY = 20
def _press_keys(*vk_codes, hold_ctrl=False, hold_shift=False):
    mods = []
    if hold_ctrl:
        mods.append(0x11)
    if hold_shift:
        mods.append(0x10)
    if mods:
        keysend.hotkey(*mods, *vk_codes)
    else:
        for vk in vk_codes:
            keysend.press(vk)
def clipboard_copy() -> tuple[bool, str]:
    try:
        _press_keys(67, hold_ctrl=True)
        time.sleep(0.2)
        text = pyperclip.paste()
        if text and text.strip():
            if not _clipboard_history or _clipboard_history[0] != text:
                _clipboard_history.insert(0, text)
                if len(_clipboard_history) > MAX_HISTORY:
                    _clipboard_history.pop()
            return (True, f'Скопировано: {text[:40]}...')
        return (True, 'Скопировано')
    except Exception as e:
        return (False, str(e))
def clipboard_paste() -> tuple[bool, str]:
    try:
        _press_keys(86, hold_ctrl=True)
        return (True, 'Вставлено')
    except Exception as e:
        return (False, str(e))
def clipboard_cut() -> tuple[bool, str]:
    try:
        _press_keys(88, hold_ctrl=True)
        time.sleep(0.2)
        text = pyperclip.paste()
        if text and text.strip():
            if not _clipboard_history or _clipboard_history[0] != text:
                _clipboard_history.insert(0, text)
                if len(_clipboard_history) > MAX_HISTORY:
                    _clipboard_history.pop()
        return (True, 'Вырезано')
    except Exception as e:
        return (False, str(e))
def clipboard_paste_nth(index: int) -> tuple[bool, str]:
    if index < 0 or index >= len(_clipboard_history):
        return (False, f'В истории нет элемента с индексом {index}')
    try:
        text = _clipboard_history[index]
        pyperclip.copy(text)
        time.sleep(0.05)
        _press_keys(86, hold_ctrl=True)
        return (True, f'Вставлен элемент #{index}')
    except Exception as e:
        return (False, str(e))
def clipboard_open_history() -> tuple[bool, str]:
    try:
        keysend.hotkey('win', 86)
        return (True, 'Буфер обмена открыт')
    except Exception as e:
        return (False, str(e))
def undo_action() -> tuple[bool, str]:
    try:
        _press_keys(90, hold_ctrl=True)
        return (True, 'Отменено')
    except Exception as e:
        return (False, str(e))
def redo_action() -> tuple[bool, str]:
    try:
        _press_keys(89, hold_ctrl=True)
        return (True, 'Повторено')
    except Exception as e:
        return (False, str(e))
def select_all() -> tuple[bool, str]:
    try:
        _press_keys(65, hold_ctrl=True)
        return (True, 'Всё выделено')
    except Exception as e:
        return (False, str(e))
