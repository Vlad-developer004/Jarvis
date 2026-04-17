import os
import urllib.parse
import win32com.client
import win32gui
import subprocess
from rapidfuzz import fuzz
from core.system import get_active_explorer_path
USER_HOME = os.path.expanduser('~')
SYSTEM_FOLDERS = {'загрузки': os.path.join(USER_HOME, 'Downloads'), 'downloads': os.path.join(USER_HOME, 'Downloads'), 'скачанное': os.path.join(USER_HOME, 'Downloads'), 'видео': os.path.join(USER_HOME, 'Videos'), 'videos': os.path.join(USER_HOME, 'Videos'), 'фото': os.path.join(USER_HOME, 'Pictures'), 'фотографии': os.path.join(USER_HOME, 'Pictures'), 'картинки': os.path.join(USER_HOME, 'Pictures'), 'изображения': os.path.join(USER_HOME, 'Pictures'), 'pictures': os.path.join(USER_HOME, 'Pictures'), 'музыка': os.path.join(USER_HOME, 'Music'), 'music': os.path.join(USER_HOME, 'Music'), 'документы': os.path.join(USER_HOME, 'Documents'), 'documents': os.path.join(USER_HOME, 'Documents'), 'рабочий стол': os.path.join(USER_HOME, 'Desktop'), 'desktop': os.path.join(USER_HOME, 'Desktop'), 'корзина': 'shell:RecycleBinFolder', 'корзину': 'shell:RecycleBinFolder', 'назад': '..', 'наверх': '..'}
def open_in_explorer(path: str) -> bool:
    try:
        hwnd_fg = win32gui.GetForegroundWindow()
        shell = win32com.client.Dispatch('Shell.Application')
        for w in shell.Windows():
            try:
                if int(w.HWND) == hwnd_fg and str(w.FullName).lower().endswith('explorer.exe'):
                    w.Navigate(path)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    try:
        subprocess.Popen(['explorer', path])
        return True
    except Exception:
        return False
def navigate_to_system_folder(folder_name: str) -> tuple[bool, str]:
    folder_name = folder_name.lower().strip()
    target = None
    if folder_name in SYSTEM_FOLDERS:
        target = SYSTEM_FOLDERS[folder_name]
    else:
        best_score = 0
        best_key = None
        for key in SYSTEM_FOLDERS:
            score = fuzz.ratio(folder_name, key)
            if score > best_score and score >= 70:
                best_score = score
                best_key = key
        if best_key:
            target = SYSTEM_FOLDERS[best_key]
    if not target:
        return (False, 'Папка не найдена')
    if target == '..':
        current = get_active_explorer_path()
        if current:
            parent = os.path.dirname(current)
            if parent and parent != current:
                target = parent
            else:
                return (False, 'Уже в корне')
        else:
            return (False, 'Нет активного окна проводника')
    ok = open_in_explorer(target)
    return (True, target) if ok else (False, 'Ошибка навигации')
