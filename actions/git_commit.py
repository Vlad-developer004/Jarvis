import json
import os
import subprocess
import webbrowser
from pathlib import Path

def _find_git_repo(start_path: str | None = None) -> str | None:
    try:
        path = Path(start_path or os.getcwd()).resolve()
        for p in [path, *path.parents]:
            if (p / '.git').is_dir():
                return str(p)
    except Exception:
        pass
    return None

def _get_all_recent_workspaces() -> list[str]:
    candidates = []
    appdata = os.environ.get('APPDATA', '')
    import urllib.parse
    import sqlite3
    import xml.etree.ElementTree as ET

    # 1. JetBrains IDEs
    jb_path = Path(appdata) / 'JetBrains'
    if jb_path.exists():
        for ide_dir in jb_path.iterdir():
            if not ide_dir.is_dir(): continue
            for xml_name in ['recentProjects.xml', 'recentProjectDirectories.xml']:
                rp = ide_dir / 'options' / xml_name
                if rp.exists():
                    try:
                        tree = ET.parse(rp)
                        root = tree.getroot()
                        for entry in root.iter('entry'):
                            key = entry.attrib.get('key', '')
                            if key and ('/' in key or '\\' in key):
                                key = key.replace('$USER_HOME$', os.environ.get('USERPROFILE', ''))
                                candidates.append(str(Path(key).resolve()))
                        for option in root.iter('option'):
                            val = option.attrib.get('value', '')
                            if val and ('/' in val or '\\' in val):
                                val = val.replace('$USER_HOME$', os.environ.get('USERPROFILE', ''))
                                candidates.append(str(Path(val).resolve()))
                    except Exception:
                        pass

    # 2. Try sqlite database (newer VS Code)
    db_path = Path(appdata) / 'Code' / 'User' / 'globalStorage' / 'state.vscdb'
    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT value FROM ItemTable WHERE key='history.recentlyOpenedPathsList'")
                res = cur.fetchone()
                if res and res[0]:
                    data = json.loads(res[0])
                    for entry in data.get('entries', []):
                        uri = entry if isinstance(entry, str) else entry.get('folderUri', '')
                        if uri.startswith('file:///'):
                            folder = urllib.parse.unquote(uri[8:]).replace('/', '\\')
                            candidates.append(folder)
        except Exception:
            pass

    # 3. Try older JSON files
    storage_paths = [
        Path(appdata) / 'Code' / 'User' / 'globalStorage' / 'storage.json',
        Path(appdata) / 'Code' / 'storage.json',
    ]
    for sp in storage_paths:
        if not sp.exists(): continue
        try:
            data = json.loads(sp.read_text(encoding='utf-8'))
            opened = data.get('openedPathsList', {})
            if 'backupWorkspaces' in data:
                for folder_obj in data['backupWorkspaces'].get('folders', []):
                    uri = folder_obj.get('folderUri', '')
                    if uri.startswith('file:///'):
                        folder = urllib.parse.unquote(uri[8:]).replace('/', '\\')
                        candidates.append(folder)
            for entry in opened.get('workspaces3', []) + opened.get('entries', []):
                uri = entry if isinstance(entry, str) else entry.get('folderUri', '')
                if uri.startswith('file:///'):
                    folder = urllib.parse.unquote(uri[8:]).replace('/', '\\')
                    candidates.append(folder)
        except Exception:
            pass

    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]

def _repo_from_window_title(hwnd) -> str | None:
    try:
        import win32gui
        import re
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return None
        parts = [p.strip() for p in re.split(r'\s*[-–—|:]\s*', title) if p.strip()]
        if not parts:
            return None
        known_workspaces = _get_all_recent_workspaces()
        for folder_name in parts:
            for ws_path in known_workspaces:
                if Path(ws_path).name.lower() == folder_name.lower():
                    repo = _find_git_repo(ws_path)
                    if repo:
                        return repo
    except Exception:
        pass
    return None

def _get_status(repo: str) -> list[dict]:
    r = subprocess.run(
        ['git', '-C', repo, 'status', '--porcelain'],
        capture_output=True, text=True, encoding='utf-8'
    )
    files = []
    # NOTE: do not .strip() the whole blob before splitlines() — porcelain
    # status codes for the first entry are often space-prefixed (e.g. ' M'),
    # and stripping the blob eats that leading space, shifting the fixed
    # line[3:] slice by one character and truncating the filename.
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip()
        fname = line[3:].strip()
        files.append({'status': status, 'file': fname})
    return files

def _short_names(files: list[str], limit: int = 3) -> str:
    names = [Path(f).name for f in files[:limit]]
    if len(files) > limit:
        names.append(f'и ещё {len(files) - limit}')
    return ', '.join(names)

def _generate_message(changed: list[dict]) -> str:
    added    = [f['file'] for f in changed if f['status'] in ('A', '??')]
    modified = [f['file'] for f in changed if 'M' in f['status']]
    deleted  = [f['file'] for f in changed if 'D' in f['status']]
    parts = []
    if added:    parts.append(f'добавлено: {_short_names(added)}')
    if modified: parts.append(f'изменено: {_short_names(modified)}')
    if deleted:  parts.append(f'удалено: {_short_names(deleted)}')
    if not parts:
        return 'обновление кода'
    msg = '; '.join(parts)
    return msg[0].upper() + msg[1:]

# ── branch helpers ──────────────────────────────────────────────────────────

def get_current_branch(repo: str) -> str:
    r = subprocess.run(
        ['git', '-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, encoding='utf-8'
    )
    return r.stdout.strip() or 'main'

def get_branches(repo: str) -> list[str]:
    """Return local branch names, current branch first."""
    current = get_current_branch(repo)
    r = subprocess.run(
        ['git', '-C', repo, 'branch', '--format=%(refname:short)'],
        capture_output=True, text=True, encoding='utf-8'
    )
    branches = [b.strip() for b in r.stdout.splitlines() if b.strip()]
    if current in branches:
        branches.remove(current)
    return [current] + branches

def create_branch(repo: str, name: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            ['git', '-C', repo, 'checkout', '-b', name],
            check=True, capture_output=True, encoding='utf-8'
        )
        return True, name
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or '').strip()

def checkout_branch(repo: str, name: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            ['git', '-C', repo, 'checkout', name],
            check=True, capture_output=True, encoding='utf-8'
        )
        return True, name
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or '').strip()

# ── PR URL helper ────────────────────────────────────────────────────────────

def open_pull_request_url(repo: str, branch: str, pr_title: str = '') -> None:
    """Open browser to create a PR on GitHub or GitLab for the given branch."""
    try:
        r = subprocess.run(
            ['git', '-C', repo, 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, encoding='utf-8'
        )
        remote_url = r.stdout.strip()
        if not remote_url:
            return

        # Normalise SSH → HTTPS
        if remote_url.startswith('git@github.com:'):
            remote_url = 'https://github.com/' + remote_url[len('git@github.com:'):]
        elif remote_url.startswith('git@gitlab.com:'):
            remote_url = 'https://gitlab.com/' + remote_url[len('git@gitlab.com:'):]

        remote_url = remote_url.rstrip('/')
        if remote_url.endswith('.git'):
            remote_url = remote_url[:-4]

        if 'github.com' in remote_url:
            url = f'{remote_url}/compare/{branch}?expand=1'
            if pr_title:
                import urllib.parse
                url += '&title=' + urllib.parse.quote(pr_title)
        elif 'gitlab.com' in remote_url:
            import urllib.parse
            url = f'{remote_url}/-/merge_requests/new?merge_request[source_branch]={urllib.parse.quote(branch)}'
            if pr_title:
                url += '&merge_request[title]=' + urllib.parse.quote(pr_title)
        else:
            return

        webbrowser.open(url)
    except Exception:
        pass

# ── main API ──────────────────────────────────────────────────────────────────

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
                try:
                    for child in proc.children(recursive=True):
                        try:
                            repo = _find_git_repo(child.cwd())
                            if repo: break
                        except Exception: pass
                except Exception: pass

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


def git_commit_push(
    active_hwnd=None,
    custom_msg: str = '',
    files_to_add: list[str] | None = None,
    target_branch: str = '',
    push_enabled: bool = True,
    force_push: bool = False,
    set_upstream: bool = False,
) -> tuple[bool, str]:
    repo, status = detect_repo_and_status(active_hwnd)

    if not repo:
        return False, 'Репозиторий не найден. Откройте папку проекта в редакторе.'
    if not status:
        return False, 'Нет изменений для коммита.'

    msg = custom_msg.strip() if custom_msg.strip() else _generate_message(status)

    # Switch branch if requested
    if target_branch:
        current = get_current_branch(repo)
        if target_branch != current:
            branches = get_branches(repo)
            if target_branch in branches:
                ok, err = checkout_branch(repo, target_branch)
            else:
                ok, err = create_branch(repo, target_branch)
            if not ok:
                return False, f'Не удалось переключить ветку: {err}'

    try:
        if files_to_add is not None:
            subprocess.run(['git', '-C', repo, 'reset'], capture_output=True)
            for f in files_to_add:
                subprocess.run(['git', '-C', repo, 'add', f], check=True, capture_output=True)
        else:
            subprocess.run(['git', '-C', repo, 'add', '-A'], check=True, capture_output=True)

        subprocess.run(['git', '-C', repo, 'commit', '-m', msg], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b'').decode('utf-8', errors='replace').strip()
        return False, f'Ошибка коммита: {err}'

    if not push_enabled:
        return True, f'Комм+ит создан локально: {msg}'

    remotes = subprocess.run(
        ['git', '-C', repo, 'remote'], capture_output=True, text=True
    ).stdout.strip()
    if not remotes:
        return True, f'Комм+ит создан (нет remote): {msg}'

    push_branch = target_branch or get_current_branch(repo)
    push_cmd = ['git', '-C', repo, 'push', 'origin', push_branch]
    if force_push:
        push_cmd.append('--force')
    if set_upstream:
        push_cmd.insert(4, '--set-upstream')  # push --set-upstream origin branch

    try:
        subprocess.run(push_cmd, check=True, capture_output=True)
        return True, f'Комм+ит отправлен: {msg}'
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b'').decode('utf-8', errors='replace').strip()
        # Common case: upstream not set — retry with --set-upstream automatically
        if 'no upstream' in err.lower() or 'set-upstream' in err.lower():
            try:
                push_cmd2 = ['git', '-C', repo, 'push', '--set-upstream', 'origin', push_branch]
                if force_push:
                    push_cmd2.append('--force')
                subprocess.run(push_cmd2, check=True, capture_output=True)
                return True, f'Комм+ит отправлен (upstream установлен): {msg}'
            except subprocess.CalledProcessError as e2:
                err = (e2.stderr or b'').decode('utf-8', errors='replace').strip()
        return False, f'Комм+ит создан, но push упал: {err}'
