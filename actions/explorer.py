import os
import win32com.client
import win32gui
import subprocess
from rapidfuzz import fuzz
from core.system import get_active_explorer_path
USER_HOME = os.path.expanduser('~')
SYSTEM_FOLDERS = {'загрузки': os.path.join(USER_HOME, 'Downloads'), 'downloads': os.path.join(USER_HOME, 'Downloads'), 'скачанное': os.path.join(USER_HOME, 'Downloads'), 'видео': os.path.join(USER_HOME, 'Videos'), 'videos': os.path.join(USER_HOME, 'Videos'), 'фото': os.path.join(USER_HOME, 'Pictures'), 'фотографии': os.path.join(USER_HOME, 'Pictures'), 'картинки': os.path.join(USER_HOME, 'Pictures'), 'изображения': os.path.join(USER_HOME, 'Pictures'), 'pictures': os.path.join(USER_HOME, 'Pictures'), 'музыка': os.path.join(USER_HOME, 'Music'), 'music': os.path.join(USER_HOME, 'Music'), 'документы': os.path.join(USER_HOME, 'Documents'), 'documents': os.path.join(USER_HOME, 'Documents'), 'рабочий стол': os.path.join(USER_HOME, 'Desktop'), 'desktop': os.path.join(USER_HOME, 'Desktop'), 'корзина': 'shell:RecycleBinFolder', 'корзину': 'shell:RecycleBinFolder', 'назад': '..', 'наверх': '..', '..': '..', 'выйди': '..', 'выше': '..'}
def open_in_explorer(path: str) -> bool:
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
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
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
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
        # Search for the folder: active Explorer window first, then standard user dirs
        try:
            from core.system.windows import get_known_folder_path
            from actions.filesystem import _find_folder_anywhere, _get_search_depth
            depth = _get_search_depth()
            search_roots = []
            # Priority 1: currently open Explorer window (context-aware search)
            active = get_active_explorer_path()
            if active and os.path.isdir(active):
                search_roots.append(active)
            # Priority 2: standard user folders as fallback
            for k in ('desktop', 'documents', 'downloads', 'onedrive'):
                p = get_known_folder_path(k)
                if p and p not in search_roots:
                    search_roots.append(p)
            for candidate in (
                os.path.join(USER_HOME, 'OneDrive'),
                os.path.join(USER_HOME, 'Desktop'),
                os.path.join(USER_HOME, 'Documents'),
                os.path.join(USER_HOME, 'Downloads'),
            ):
                if os.path.isdir(candidate) and candidate not in search_roots:
                    search_roots.append(candidate)
            found = _find_folder_anywhere(search_roots, folder_name, max_depth=depth)
            if found and found.is_dir():
                target = str(found)
        except Exception:
            pass
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
