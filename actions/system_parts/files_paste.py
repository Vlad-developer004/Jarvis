import os
import time
import subprocess
def find_and_paste_file(file_type: str = None, target_filename: str = None) -> tuple[bool, str]:
    import pyautogui
    from rapidfuzz import fuzz
    user_prof = os.environ['USERPROFILE']
    desktop = os.path.join(user_prof, 'Desktop')
    onedrive_desktop = os.path.join(user_prof, 'OneDrive', 'Desktop')
    downloads = os.path.join(user_prof, 'Downloads')
    documents = os.path.join(user_prof, 'Documents')
    videos = os.path.join(user_prof, 'Videos')
    pictures = os.path.join(user_prof, 'Pictures')
    ext_filters: list[str] = []
    if file_type == 'video':
        search_dirs = [downloads, videos, desktop, onedrive_desktop]
        ext_filters = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
    elif file_type == 'photo':
        search_dirs = [pictures, downloads, desktop, onedrive_desktop]
        ext_filters = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    elif file_type == 'document':
        search_dirs = [desktop, onedrive_desktop, downloads, documents]
        ext_filters = ['.doc', '.docx', '.pdf', '.txt', '.xlsx', '.pptx', '.rtf']
    else:
        search_dirs = [desktop, onedrive_desktop, downloads, documents, pictures, videos]
    best_file = None
    best_time = 0.0
    best_score = 0
    _BAD_DIRS = {'jarvis', '.git', 'venv', '.gemini', 'appdata', 'node_modules', '__pycache__'}
    def _bad_dir(path: str) -> bool:
        low = path.lower()
        return any((b in low for b in _BAD_DIRS))
    def _bad_file(name: str) -> bool:
        return name.startswith(('~', '.')) or name.endswith(('.tmp', '.crdownload', '.part'))
    if target_filename:
        target_filename = target_filename.lower().replace('документ', '').replace('видео', '').replace('фото', '').strip()
    if target_filename:
        max_depth = 3
        for s_dir in search_dirs:
            if not os.path.isdir(s_dir):
                continue
            base_depth = s_dir.rstrip(os.path.sep).count(os.path.sep)
            for root, dirs, files in os.walk(s_dir):
                if _bad_dir(root):
                    dirs[:] = []
                    continue
                if root.count(os.path.sep) - base_depth >= max_depth:
                    dirs[:] = []
                for file in files:
                    if _bad_file(file):
                        continue
                    _, ext = os.path.splitext(file)
                    if ext_filters and ext.lower() not in ext_filters:
                        continue
                    full_path = os.path.join(root, file)
                    name_clean = os.path.splitext(file)[0].lower().replace('_', ' ')
                    score = fuzz.token_set_ratio(target_filename, name_clean)
                    if 'диплом' in target_filename:
                        score += 20 if 'диплом' in name_clean else -20
                    if 'записка' in target_filename:
                        score += 20 if 'записка' in name_clean or 'поясн' in name_clean else -20
                    if score > 65 and score > best_score:
                        best_score = score
                        best_file = full_path
    else:
        for s_dir in search_dirs:
            if not os.path.isdir(s_dir) or _bad_dir(s_dir):
                continue
            try:
                with os.scandir(s_dir) as it:
                    for entry in it:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if _bad_file(entry.name):
                            continue
                        _, ext = os.path.splitext(entry.name)
                        if ext_filters and ext.lower() not in ext_filters:
                            continue
                        try:
                            mtime = entry.stat().st_mtime
                            if mtime > best_time:
                                best_time = mtime
                                best_file = entry.path
                        except OSError:
                            pass
            except PermissionError:
                pass
            try:
                with os.scandir(s_dir) as it:
                    subdirs = [e for e in it if e.is_dir(follow_symlinks=False) and (not _bad_dir(e.path))]
            except PermissionError:
                subdirs = []
            for sub in subdirs:
                try:
                    with os.scandir(sub.path) as it2:
                        for entry in it2:
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            if _bad_file(entry.name):
                                continue
                            _, ext = os.path.splitext(entry.name)
                            if ext_filters and ext.lower() not in ext_filters:
                                continue
                            try:
                                mtime = entry.stat().st_mtime
                                if mtime > best_time:
                                    best_time = mtime
                                    best_file = entry.path
                            except OSError:
                                pass
                except PermissionError:
                    pass
    if not best_file:
        return (False, 'Файлы не найдены')
    try:
        ps_command = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $col = New-Object System.Collections.Specialized.StringCollection
        $col.Add('{best_file}')
        [System.Windows.Forms.Clipboard]::SetFileDropList($col)
        """
        subprocess.run(['powershell', '-NoProfile', '-Command', ps_command], creationflags=134217728)
        time.sleep(0.5)
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(17, 0, 0, 0)
        user32.keybd_event(86, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(86, 0, 2, 0)
        user32.keybd_event(17, 0, 2, 0)
        return (True, f'Вставлен {os.path.basename(best_file)}')
    except Exception as e:
        return (False, str(e))
