import re
import ctypes
import time
from core.system import app_state
DICTATION_STOP_WORDS = ['закончили', 'стоп диктовка', 'хватит', 'конец диктовки', 'заверши диктовку', 'прекрати', 'стоп']
DICTATION_SUBMIT_WORDS = ['отправь', 'отправить', 'отправляй', 'нажми ввод', 'ввод', 'нажми enter', 'нажми энтер', 'энтер', 'enter', 'нажимай энтер']
_PUNCTUATION_MAP = {'точка': '.', 'запятая': ',', 'вопросительный знак': '?', 'знак вопроса': '?', 'восклицательный знак': '!', 'новая строка': '\n', 'абзац': '\n'}
def is_dictation_active() -> bool:
    return app_state.dictation_mode
def start_dictation() -> None:
    app_state.dictation_mode = True
def stop_dictation() -> None:
    app_state.dictation_mode = False
def _press_enter_dictation():
    user32 = ctypes.windll.user32
    user32.keybd_event(13, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(13, 0, 2, 0)
def _type_text(text: str):
    import pyperclip
    user32 = ctypes.windll.user32
    old = pyperclip.paste()
    pyperclip.copy(text)
    time.sleep(0.05)
    user32.keybd_event(17, 0, 0, 0)
    user32.keybd_event(86, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(86, 0, 2, 0)
    user32.keybd_event(17, 0, 2, 0)
    time.sleep(0.05)
    try:
        pyperclip.copy(old if old else '')
    except Exception:
        pass
def handle_dictation_text(text: str) -> dict:
    text_lower = text.lower().strip()
    if any((text_lower == sw or text_lower.startswith(sw) for sw in DICTATION_STOP_WORDS)):
        stop_dictation()
        return {'stop': True, 'submit': False, 'text': ''}
    if any((text_lower == sw for sw in DICTATION_SUBMIT_WORDS)):
        _press_enter_dictation()
        return {'stop': False, 'submit': True, 'text': ''}
    text_to_type = text_lower
    for word, symbol in _PUNCTUATION_MAP.items():
        text_to_type = re.sub(f'\\b{word}\\b', symbol, text_to_type)
    text_to_type = re.sub('\\s+([.,?!])', '\\1', text_to_type)
    if text_to_type:
        text_to_type = text_to_type[0].upper() + text_to_type[1:]
    _type_text(text_to_type + ' ')
    return {'stop': False, 'submit': False, 'text': text_to_type}
