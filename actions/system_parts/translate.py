import time
import urllib.parse
import webbrowser
from core.system import force_foreground
LANG_MAP = {'английский': 'en', 'немецкий': 'de', 'французский': 'fr', 'испанский': 'es', 'итальянский': 'it', 'португальский': 'pt', 'китайский': 'zh-CN', 'японский': 'ja', 'корейский': 'ko', 'польский': 'pl', 'турецкий': 'tr', 'арабский': 'ar', 'украинский': 'uk', 'русский': 'ru', 'чешский': 'cs', 'голландский': 'nl', 'шведский': 'sv', 'финский': 'fi', 'норвежский': 'no', 'датский': 'da', 'греческий': 'el', 'хинди': 'hi', 'вьетнамский': 'vi', 'тайский': 'th', 'румынский': 'ro', 'венгерский': 'hu', 'болгарский': 'bg'}
def translate_selected(target_lang: str, user_hwnd=None) -> tuple[bool, str]:
    try:
        import pyperclip
        import win32gui
        import ctypes
        user32 = ctypes.windll.user32
        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        current_fg = win32gui.GetForegroundWindow()
        target = user_hwnd if user_hwnd else current_fg
        target_title = win32gui.GetWindowText(target) if target else '???'
        if target and current_fg != target:
            try:
                current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                target_thread = user32.GetWindowThreadProcessId(target, None)
                if current_thread != target_thread:
                    user32.AttachThreadInput(current_thread, target_thread, True)
                win32gui.ShowWindow(target, 9)
                user32.keybd_event(18, 0, 1, 0)
                user32.keybd_event(18, 0, 1 | 2, 0)
                user32.SetForegroundWindow(target)
                if current_thread != target_thread:
                    user32.AttachThreadInput(current_thread, target_thread, False)
            except Exception:
                pass
            time.sleep(0.5)
        pyperclip.copy('')
        focus_target = target if target else current_fg
        if focus_target:
            force_foreground(focus_target)
            time.sleep(0.3)
        _actual = win32gui.GetForegroundWindow()
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)
        user32.keybd_event(17, 29, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(67, 46, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(67, 46, 2, 0)
        time.sleep(0.05)
        user32.keybd_event(17, 29, 2, 0)
        time.sleep(0.3)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
        text = pyperclip.paste()
        if not text or not text.strip():
            if 'word' in target_title.lower():
                try:
                    import win32com.client
                    word_app = win32com.client.Dispatch('Word.Application')
                    text = word_app.Selection.Text
                    if text:
                        pass
                except Exception:
                    pass
        if not text or not text.strip():
            return (False, 'Текст не скопирован')
        lang_code = LANG_MAP.get(target_lang.lower(), target_lang)
        encoded = urllib.parse.quote(text.strip())
        url = f'https://translate.google.com/?sl=auto&tl={lang_code}&text={encoded}&op=translate'
        webbrowser.open(url)
        return (True, f'Перевод на {target_lang}')
    except Exception as e:
        return (False, str(e))
