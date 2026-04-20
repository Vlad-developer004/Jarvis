import json
import os
import subprocess
from pathlib import Path
def _find_git_repo(start_path: str | None=None) -> str | None:
    try:
        path = Path(start_path or os.getcwd()).resolve()
        for p in [path, *path.parents]:
            if (p / '.git').is_dir():
                return str(p)
    except Exception:
        pass
    return None
def _vscode_recent_workspaces() -> list[str]:
    candidates = []
    appdata = os.environ.get('APPDATA', '')
    storage_paths = [Path(appdata) / 'Code' / 'User' / 'globalStorage' / 'storage.json', Path(appdata) / 'Code' / 'storage.json']
    for sp in storage_paths:
        try:
            data = json.loads(sp.read_text(encoding='utf-8'))
            opened = data.get('openedPathsList', {})
            for entry in opened.get('workspaces3', []) + opened.get('entries', []):
                uri = entry if isinstance(entry, str) else entry.get('folderUri', '')
                if uri.startswith('file:///'):
                    folder = uri[8:].replace('/', '\\')
                    candidates.append(folder)
        except Exception:
            pass
    return candidates
def _repo_from_window_title(hwnd) -> str | None:
    try:
        import win32gui
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return None
        parts = [p.strip() for p in title.split(' - ')]
        if len(parts) >= 3:
            folder_name = parts[-2]
            for ws_path in _vscode_recent_workspaces():
                if Path(ws_path).name == folder_name:
                    repo = _find_git_repo(ws_path)
                    if repo:
                        return repo
    except Exception:
        pass
    return None
def _get_status(repo: str) -> list[dict]:
    r = subprocess.run(['git', '-C', repo, 'status', '--porcelain'], capture_output=True, text=True, encoding='utf-8')
    files = []
    for line in r.stdout.strip().splitlines():
        if not line.strip():
            continue
        status = line[:2].strip()
        fname = line[3:].strip()
        files.append({'status': status, 'file': fname})
    return files
def _short_names(files: list[str], limit: int=3) -> str:
    names = [Path(f).name for f in files[:limit]]
    if len(files) > limit:
        names.append(f'и ещё {len(files) - limit}')
    return ', '.join(names)
def _generate_message(changed: list[dict]) -> str:
    added = [f['file'] for f in changed if f['status'] in ('A', '??')]
    modified = [f['file'] for f in changed if 'M' in f['status']]
    deleted = [f['file'] for f in changed if 'D' in f['status']]
    parts = []
    if added:
        parts.append(f'добавлено: {_short_names(added)}')
    if modified:
        parts.append(f'изменено: {_short_names(modified)}')
    if deleted:
        parts.append(f'удалено: {_short_names(deleted)}')
    if not parts:
        return 'обновление кода'
    msg = '; '.join(parts)
    return msg[0].upper() + msg[1:]
def detect_repo_and_status(active_hwnd=None) -> tuple[str | None, list[dict]]:
    repo = None
    if active_hwnd:
        try:
            import win32process
            import psutil
            pid = win32process.GetWindowThreadProcessId(active_hwnd)[1]
            proc = psutil.Process(pid)
            repo = _find_git_repo(proc.cwd())
            if not repo:
                for arg in proc.cmdline()[1:]:
                    if Path(arg).is_dir():
                        repo = _find_git_repo(arg)
                        if repo: break
            if not repo:
                repo = _repo_from_window_title(active_hwnd)
        except Exception: pass
    
    if not repo: repo = _find_git_repo()
    if not repo: repo = _find_git_repo(os.getcwd())
    
    if not repo: return None, []
    return repo, _get_status(repo)

def git_commit_push(active_hwnd=None, custom_msg: str='', files_to_add: list[str] | None=None) -> tuple[bool, str]:
    # Use helper if no repo passed (though we usually have it from dlg now)
    repo, status = detect_repo_and_status(active_hwnd)
    
    if not repo:
        return (False, 'Репозиторий не найден. Откройте папку проекта в редакторе.')
    if not status:
        return (False, 'Нет изменений для коммита.')
    
    msg = custom_msg.strip() if custom_msg.strip() else _generate_message(status)
    try:
        if files_to_add is not None:
            # Stage only specific files
            # First reset staging to be sure we only add what was requested
            subprocess.run(['git', '-C', repo, 'reset'], capture_output=True)
            for f in files_to_add:
                subprocess.run(['git', '-C', repo, 'add', f], check=True, capture_output=True)
        else:
            # Default: add everything
            subprocess.run(['git', '-C', repo, 'add', '-A'], check=True, capture_output=True)
        
        subprocess.run(['git', '-C', repo, 'commit', '-m', msg], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b'').decode('utf-8', errors='replace').strip()
        return (False, f'Ошибка коммита: {err}')
    remotes = subprocess.run(['git', '-C', repo, 'remote'], capture_output=True, text=True).stdout.strip()
    if remotes:
        try:
            subprocess.run(['git', '-C', repo, 'push'], check=True, capture_output=True)
            return (True, f'Комм+ит отправлен: {msg}')
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode('utf-8', errors='replace').strip()
            return (False, f'Комм+ит создан, но push упал: {err}')
    return (True, f'Комм+ит создан локально: {msg}')
