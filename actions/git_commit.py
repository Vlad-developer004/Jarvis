import json
import os
import subprocess
import time
import webbrowser
from pathlib import Path

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)     # the packaged app has no console: do not flash one per git call
_GIT_ENV = {'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}     # never wait for a password prompt nobody can see


def _git(repo: str, *args: str, timeout: float = 60.0, check: bool = False) -> subprocess.CompletedProcess:
    """Runs `git -C repo ...` with the list form (no shell), UTF-8 paths unescaped, a timeout, and stdout/stderr as text.
    Raises GitError (never a bare CalledProcessError or TimeoutExpired) so callers can show one readable line."""
    cmd = ['git', '-c', 'core.quotepath=false', '-C', repo, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                           env={**os.environ, **_GIT_ENV}, creationflags=_NO_WINDOW)
    except FileNotFoundError as ex:
        raise GitError('Git не найден. Установите Git for Windows и перезапустите Jarvis.') from ex
    except subprocess.TimeoutExpired as ex:
        raise GitError(f'git {args[0]} не ответил за {int(timeout)} с (хук, сеть или запрос пароля).') from ex
    if check and r.returncode != 0:
        raise GitError(explain_error((r.stderr or '') + (r.stdout or '')))
    return r


class GitError(RuntimeError):
    """A git failure with a message fit to show or speak."""


def explain_error(text: str) -> str:
    """The readable form of git's output for the failures people actually hit; anything else is passed through, trimmed."""
    t = (text or '').strip()
    low = t.lower()
    if 'please tell me who you are' in low or 'unable to auto-detect email' in low:
        return 'Git не знает, кто вы. Выполните: git config --global user.name "Имя" и git config --global user.email "почта".'
    if 'index.lock' in low:
        return 'Другая программа сейчас работает с репозиторием (файл index.lock). Подождите несколько секунд: редактор обновляет индекс.'
    if 'dubious ownership' in low or 'safe.directory' in low:
        return 'Git считает папку небезопасной. Выполните: git config --global --add safe.directory "путь к репозиторию".'
    if 'authentication failed' in low or 'could not read username' in low or 'permission denied' in low:
        return 'Нет доступа к удалённому репозиторию: войдите в Git Credential Manager или проверьте ключ SSH.'
    if 'non-fast-forward' in low or 'fetch first' in low or 'rejected' in low and 'behind' in low:
        return 'На сервере есть изменения, которых нет у вас. Сначала git pull, затем отправьте снова.'
    if 'nothing to commit' in low:
        return 'Нет изменений для коммита.'
    if 'hook' in low and ('failed' in low or 'declined' in low):
        return 'Хук (например pre-commit) отклонил коммит:\n' + t[-600:]
    return t[-600:] or 'git завершился с ошибкой'


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
    from defusedxml import ElementTree as ET

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
    # -z: records end with NUL and paths are never quoted, so spaces, quotes and non-ASCII names survive; -uall lists the files of a new folder
    # one by one. A rename or copy ("R", "C") is followed by a second record with the old path. Do not .strip() a record: the status code of the
    # first entry is often space-prefixed (' M').
    r = _git(repo, 'status', '--porcelain=v1', '-z', '-uall')
    files, records = [], r.stdout.split('\0')
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 4:
            continue
        status, fname = rec[:2].strip(), rec[3:]
        if status[:1] in ('R', 'C'):
            i += 1
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
    try:
        r = _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    except GitError:
        return 'main'
    name = r.stdout.strip()
    if name == 'HEAD':      # a repository without commits (rev-parse fails to name the branch) or a detached HEAD
        return _unborn_branch(repo) or 'HEAD'
    return name or _unborn_branch(repo) or 'main'


def _unborn_branch(repo: str) -> str:
    """The branch a repository without commits is on (`git branch --show-current` works there; rev-parse does not)."""
    try:
        return _git(repo, 'branch', '--show-current').stdout.strip()
    except GitError:
        return ''


def get_branches(repo: str) -> list[str]:
    """Return local branch names, current branch first."""
    current = get_current_branch(repo)
    try:
        r = _git(repo, 'branch', '--format=%(refname:short)')
    except GitError:
        return [current]
    branches = [b.strip() for b in r.stdout.splitlines() if b.strip() and not b.startswith('(')]     # "(HEAD detached at ...)" is not a branch
    if current in branches:
        branches.remove(current)
    return [current] + branches


def _switch(repo: str, *args: str) -> tuple[bool, str]:
    try:
        _git(repo, *args, check=True)
        return True, args[-1]
    except GitError as ex:
        return False, str(ex)


def create_branch(repo: str, name: str) -> tuple[bool, str]:
    return _switch(repo, 'checkout', '-b', name)


def checkout_branch(repo: str, name: str) -> tuple[bool, str]:
    return _switch(repo, 'checkout', name)

# ── PR URL helper ────────────────────────────────────────────────────────────

def open_pull_request_url(repo: str, branch: str, pr_title: str = '') -> None:
    """Open browser to create a PR on GitHub or GitLab for the given branch."""
    try:
        remote_url = _git(repo, 'remote', 'get-url', 'origin').stdout.strip()
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


def _stage(repo: str, files: list[str] | None) -> None:
    """Index = exactly the chosen files (or everything when None). Paths go after `--`, so a name that starts with a dash is still a path."""
    if files is None:
        _git(repo, 'add', '-A', check=True)
        return
    _git(repo, 'reset', '-q')       # fails in a repository without commits: nothing to unstage there anyway
    for i in range(0, len(files), 200):      # keeps the command line short on Windows
        _git(repo, 'add', '-A', '--', *files[i:i + 200], check=True)


def _commit(repo: str, msg: str) -> None:
    """One retry when another program (the editor refreshing its view) holds index.lock for a moment."""
    for attempt in (1, 2):
        r = _git(repo, 'commit', '-m', msg, timeout=180.0)      # a pre-commit hook may run linters and tests
        if r.returncode == 0:
            return
        out = (r.stderr or '') + (r.stdout or '')
        if attempt == 1 and 'index.lock' in out:
            time.sleep(1.5)
            continue
        raise GitError(explain_error(out))


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

    try:
        # Switch branch if requested
        if target_branch:
            if target_branch != get_current_branch(repo):
                ok, err = (checkout_branch if target_branch in get_branches(repo) else create_branch)(repo, target_branch)
                if not ok:
                    return False, f'Не удалось переключить ветку: {err}'
        _stage(repo, files_to_add)
        _commit(repo, msg)
    except GitError as ex:
        return False, f'Ошибка коммита: {ex}'

    if not push_enabled:
        return True, f'Комм+ит создан локально: {msg}'

    try:
        remotes = _git(repo, 'remote').stdout.strip()
    except GitError:
        remotes = ''
    if not remotes:
        return True, f'Комм+ит создан (нет remote): {msg}'

    push_branch = target_branch or get_current_branch(repo)
    if push_branch == 'HEAD':
        return True, f'Комм+ит создан, но HEAD отсоединён: выберите или создайте ветку, чтобы отправить его. {msg}'
    remote = 'origin' if 'origin' in remotes.split() else remotes.split()[0]
    base = ['push', '--force-with-lease'] if force_push else ['push']       # a plain --force would also overwrite work that appeared on the server meanwhile
    first = base + (['--set-upstream'] if set_upstream else [])
    try:
        _git(repo, *first, remote, push_branch, timeout=120.0, check=True)
        return True, f'Комм+ит отправлен: {msg}'
    except GitError as ex:
        err = str(ex)
        # Common case: upstream not set — retry with --set-upstream automatically
        if not set_upstream and ('no upstream' in err.lower() or 'set-upstream' in err.lower()):
            try:
                _git(repo, *base, '--set-upstream', remote, push_branch, timeout=120.0, check=True)
                return True, f'Комм+ит отправлен (upstream установлен): {msg}'
            except GitError as ex2:
                err = str(ex2)
        return False, f'Комм+ит создан, но push не прошёл: {err}'
