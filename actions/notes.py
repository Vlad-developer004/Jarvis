import os
import threading
import winsound
from datetime import datetime
from pathlib import Path
ONEDRIVE_DESKTOP = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
if not os.path.isdir(ONEDRIVE_DESKTOP):
    ONEDRIVE_DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
NOTES_FILE = os.path.join(ONEDRIVE_DESKTOP, 'jarvis_notes.txt')
_active_reminders = []
def save_note(text: str) -> tuple[bool, str]:
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        line = f'[{ts}] {text}\n'
        with open(NOTES_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
        return (True, f'Записано: {text[:50]}')
    except Exception as e:
        return (False, str(e))
def _reminder_fire(message: str, reminder_info: dict):
    try:
        _active_reminders.remove(reminder_info)
    except ValueError:
        pass
    import ctypes
    import time
    for _ in range(2):
        winsound.Beep(800, 150)
        winsound.Beep(1000, 150)
        winsound.Beep(1200, 150)
        winsound.Beep(1500, 300)
        time.sleep(0.3)
    try:
        from core.speech import speak
        display_msg = message if message else 'Время вышло'
        speak(f'Сэр, напоминание: {display_msg}')
    except Exception as e:
        pass
    display_msg = message if message else 'Время вышло!'
    ctypes.windll.user32.MessageBoxW(0, display_msg, 'Джарвис — Напоминание', 64 | 4096)
def set_reminder(minutes: int, message: str='') -> tuple[bool, str]:
    try:
        if minutes < 1:
            minutes = 1
        msg = message if message else f'Таймер на {minutes} мин.'
        reminder_info = {'timer': None, 'message': msg, 'minutes': minutes}
        t = threading.Timer(minutes * 60, _reminder_fire, args=[msg, reminder_info])
        t.daemon = True
        reminder_info['timer'] = t
        t.start()
        _active_reminders.append(reminder_info)
        return (True, f'Напомню через {minutes} мин.')
    except Exception as e:
        return (False, str(e))
def cancel_reminders() -> tuple[bool, str]:
    if not _active_reminders:
        return (False, 'Нет активных напоминаний')
    count = len(_active_reminders)
    for r in _active_reminders:
        try:
            r['timer'].cancel()
        except Exception:
            pass
    _active_reminders.clear()
    return (True, f'Отменено: {count}')
