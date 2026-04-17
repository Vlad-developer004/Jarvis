import ctypes
import time
import pyperclip
_clipboard_history = []
MAX_HISTORY = 20
user32 = ctypes.windll.user32
def _press_keys(*vk_codes, hold_ctrl=False, hold_shift=False):
    if hold_ctrl:
        user32.keybd_event(17, 0, 0, 0)
    if hold_shift:
        user32.keybd_event(16, 0, 0, 0)
    for vk in vk_codes:
        user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    for vk in reversed(vk_codes):
        user32.keybd_event(vk, 0, 2, 0)
    if hold_shift:
        user32.keybd_event(16, 0, 2, 0)
    if hold_ctrl:
        user32.keybd_event(17, 0, 2, 0)
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
        user32.keybd_event(91, 0, 0, 0)
        user32.keybd_event(86, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(86, 0, 2, 0)
        user32.keybd_event(91, 0, 2, 0)
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
