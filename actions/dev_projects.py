"""
Developer projects — list of projects for 'за работу' command.
Stored in jarvis_settings.json:
  "dev_projects": [{"name": "Jarvis", "path": "C:/...", "editor": "code"}]
  "dev_default_editor": "code"

Editor keys (cmd to launch):
  "code"       — VS Code
  "webstorm"   — WebStorm
  "pycharm"    — PyCharm
  "idea"       — IntelliJ IDEA
  "subl"       — Sublime Text
  "cursor"     — Cursor
  "custom:<exe>" — arbitrary exe path
"""
from __future__ import annotations
import json
import os
import subprocess

# Absolute path regardless of CWD
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
_SETTINGS_PATH = os.path.join(_DATA_DIR, 'jarvis_settings.json')
_EXE_CACHE_PATH = os.path.join(_DATA_DIR, 'exe_cache.json')

# All known editors: cmd → (display name, common exe names, common install paths)
_KNOWN_EDITORS: list[tuple[str, str, list[str], list[str]]] = [
    # ── VS Code & forks ──────────────────────────────────────────────────
    ('code',        'VS Code',          ['code.exe', 'code'],              [
        r'C:\Program Files\Microsoft VS Code',
        r'C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code',
    ]),
    ('cursor',      'Cursor',           ['cursor.exe', 'cursor'],          [
        r'C:\Users\{user}\AppData\Local\Programs\cursor',
        r'C:\Users\{user}\AppData\Local\Programs\Cursor',
        r'C:\Program Files\Cursor',
    ]),
    ('windsurf',    'Windsurf',         ['windsurf.exe', 'windsurf'],      [
        r'C:\Users\{user}\AppData\Local\Programs\Windsurf',
        r'C:\Program Files\Windsurf',
    ]),
    ('vscodium',    'VSCodium',         ['codium.exe', 'vscodium'],        [
        r'C:\Program Files\VSCodium',
        r'C:\Users\{user}\AppData\Local\Programs\VSCodium',
    ]),
    ('positron',    'Positron',         ['positron.exe', 'positron'],      [
        r'C:\Users\{user}\AppData\Local\Programs\Positron',
    ]),
    ('code-insiders','VS Code Insiders',['code-insiders.exe','code-insiders'],[
        r'C:\Program Files\Microsoft VS Code Insiders',
        r'C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code Insiders',
    ]),
    # ── JetBrains ────────────────────────────────────────────────────────
    ('webstorm',    'WebStorm',         ['webstorm64.exe', 'webstorm'],    [
        r'C:\Program Files\JetBrains\WebStorm*',
    ]),
    ('pycharm',     'PyCharm',          ['pycharm64.exe', 'pycharm'],      [
        r'C:\Program Files\JetBrains\PyCharm*',
    ]),
    ('idea',        'IntelliJ IDEA',    ['idea64.exe', 'idea'],            [
        r'C:\Program Files\JetBrains\IntelliJ IDEA*',
    ]),
    ('clion',       'CLion',            ['clion64.exe', 'clion'],          [
        r'C:\Program Files\JetBrains\CLion*',
    ]),
    ('rider',       'Rider',            ['rider64.exe', 'rider'],          [
        r'C:\Program Files\JetBrains\JetBrains Rider*',
    ]),
    ('fleet',       'JetBrains Fleet',  ['fleet.exe', 'fleet'],            [
        r'C:\Users\{user}\AppData\Local\Programs\Fleet',
    ]),
    # ── Other ────────────────────────────────────────────────────────────
    ('subl',        'Sublime Text',     ['sublime_text.exe', 'subl'],      [
        r'C:\Program Files\Sublime Text',
        r'C:\Program Files (x86)\Sublime Text*',
    ]),
    ('notepad++',   'Notepad++',        ['notepad++.exe'],                  [
        r'C:\Program Files\Notepad++',
        r'C:\Program Files (x86)\Notepad++',
    ]),
    ('vim',         'Vim / NeoVim',     ['nvim.exe', 'vim.exe', 'nvim', 'vim'], [
        r'C:\Program Files\Neovim\bin',
        r'C:\Program Files\Vim\vim*',
    ]),
    ('zed',         'Zed',              ['zed.exe', 'zed'],                [
        r'C:\Users\{user}\AppData\Local\Zed',
    ]),
]


def detect_installed_editors() -> list[tuple[str, str]]:
    """Return list of (cmd_key, display_name) for editors found on this machine."""
    import shutil
    import glob as _glob
    user = os.environ.get('USERNAME', '')
    found_keys: set[str] = set()
    found: list[tuple[str, str]] = []

    # Build a set of exe basenames from exe_cache.json for fast lookup
    _cached_exes: set[str] = set()
    try:
        cache_path = os.path.join('data', 'exe_cache.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
            for v in _cache.values():
                if isinstance(v, str):
                    _cached_exes.add(os.path.basename(v).lower())
    except Exception:
        pass

    for cmd, name, exes, paths in _KNOWN_EDITORS:
        if cmd in found_keys:
            continue
        exe_names_lower = {e.lower() for e in exes}
        # 1. shutil.which (covers PATH installs)
        if any(shutil.which(e) for e in exes):
            found.append((cmd, name)); found_keys.add(cmd); continue
        # 2. exe_cache hit (Jarvis already found this exe)
        if exe_names_lower & _cached_exes:
            found.append((cmd, name)); found_keys.add(cmd); continue
        # 3. Common install paths (supports {user} and glob wildcards)
        for p in paths:
            p = p.replace('{user}', user)
            matches = _glob.glob(p) if '*' in p else ([p] if os.path.exists(p) else [])
            if matches:
                found.append((cmd, name)); found_keys.add(cmd); break

    return found


def get_available_apps() -> list[tuple[str, str]]:
    """
    Return list of (exe_path_or_cmd, display_name) from:
    - exe_cache.json (previously found apps)
    - currently running processes (psutil)
    Deduplicated and sorted by name.
    """
    apps: dict[str, str] = {}  # exe → name
    # From exe_cache
    try:
        if os.path.exists(_EXE_CACHE_PATH):
            with open(_EXE_CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            for key, exe_path in cache.items():
                if isinstance(exe_path, str) and exe_path:
                    name = os.path.splitext(os.path.basename(exe_path))[0]
                    apps[exe_path] = name.title()
    except Exception:
        pass
    # From running processes
    try:
        import psutil
        seen_exes = set()
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                exe = proc.info.get('exe') or ''
                name = proc.info.get('name') or ''
                if exe and exe not in seen_exes and name and not name.lower().startswith('svchost'):
                    seen_exes.add(exe)
                    display = os.path.splitext(name)[0].title()
                    apps[exe] = display
            except Exception:
                pass
    except Exception:
        pass
    return sorted(apps.items(), key=lambda x: x[1].lower())


def _load_settings() -> dict:
    try:
        if os.path.exists(_SETTINGS_PATH):
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_settings(data: dict) -> None:
    try:
        with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_projects() -> list[dict]:
    return _load_settings().get('dev_projects', [])


def get_default_editor() -> str:
    return _load_settings().get('dev_default_editor', 'code')


def set_default_editor(editor: str) -> None:
    data = _load_settings()
    data['dev_default_editor'] = editor
    _save_settings(data)


def get_editor_display_names() -> dict:
    """Return the saved display name table: {custom_key: display_name}."""
    return _load_settings().get('dev_editor_names', {})


def save_editor_display_name(key: str, name: str) -> None:
    """Persist a display name for a custom editor key so it survives restarts."""
    data = _load_settings()
    names = data.get('dev_editor_names', {})
    names[key] = name
    data['dev_editor_names'] = names
    _save_settings(data)


def get_custom_editors() -> list:
    """Return the user-curated list of custom editors: [{'key': 'custom:...', 'name': '...'}]"""
    return _load_settings().get('dev_custom_editors', [])


def add_custom_editor(key: str, name: str) -> None:
    """Add or update a custom editor entry (dedup by key)."""
    data = _load_settings()
    editors = [e for e in data.get('dev_custom_editors', []) if e.get('key') != key]
    editors.append({'key': key, 'name': name})
    data['dev_custom_editors'] = editors
    names = data.get('dev_editor_names', {})
    names[key] = name
    data['dev_editor_names'] = names
    _save_settings(data)


def remove_custom_editor(key: str) -> None:
    """Remove a custom editor. If it was the default, fall back to first available."""
    data = _load_settings()
    data['dev_custom_editors'] = [e for e in data.get('dev_custom_editors', []) if e.get('key') != key]
    data.get('dev_editor_names', {}).pop(key, None)
    if data.get('dev_default_editor') == key:
        remaining = data['dev_custom_editors']
        data['dev_default_editor'] = remaining[0]['key'] if remaining else 'code'
    _save_settings(data)


def add_project(name: str, path: str, editor: str = '') -> None:
    data = _load_settings()
    projects = data.get('dev_projects', [])
    projects = [p for p in projects if p.get('name', '').lower() != name.lower()]
    entry: dict = {'name': name.strip(), 'path': path.strip()}
    if editor:
        entry['editor'] = editor.strip()
    projects.append(entry)
    data['dev_projects'] = projects
    _save_settings(data)


def update_project_at(index: int, name: str, path: str, editor: str = '') -> None:
    data = _load_settings()
    projects = data.get('dev_projects', [])
    if 0 <= index < len(projects):
        entry: dict = {'name': name.strip(), 'path': path.strip()}
        if editor:
            entry['editor'] = editor.strip()
        projects[index] = entry
        data['dev_projects'] = projects
        _save_settings(data)


def remove_project(name: str) -> bool:
    data = _load_settings()
    projects = data.get('dev_projects', [])
    new = [p for p in projects if p.get('name', '').lower() != name.lower()]
    if len(new) == len(projects):
        return False
    data['dev_projects'] = new
    _save_settings(data)
    return True


def _resolve_editor_cmd(editor_key: str) -> list[str]:
    """
    Return the best launch command for an editor key.
    For known editors: finds the actual exe path on disk (works even if not in PATH).
    For custom: uses the stored exe path directly.
    """
    if editor_key.startswith('custom:'):
        exe = editor_key[7:].strip()
        return [exe] if exe else []

    import shutil
    import glob as _glob

    user = os.environ.get('USERNAME', '')

    for cmd, _name, exes, paths in _KNOWN_EDITORS:
        if cmd != editor_key:
            continue

        # 1. PATH lookup — covers installers that add a shell entry
        for exe_name in exes:
            found = shutil.which(exe_name)
            if found:
                return [found]

        # 2. Common install directories — handles JetBrains & others not in PATH
        for p in paths:
            p = p.replace('{user}', user)
            matches = sorted(_glob.glob(p) if '*' in p else ([p] if os.path.exists(p) else []),
                             reverse=True)  # newest version first
            for match in matches:
                for exe_name in exes:
                    for sub in ('bin', ''):  # JetBrains store exe in bin/, others at root
                        full = os.path.join(match, sub, exe_name) if sub else os.path.join(match, exe_name)
                        if os.path.isfile(full):
                            return [full]

        # 3. Last resort: cmd name as-is (may work if installer added it to PATH)
        return [exes[0]] if exes else []

    # Unknown key — try as-is
    return [editor_key] if editor_key else []




def open_project(project: dict) -> tuple[bool, str]:
    path = project.get('path', '').strip()
    if not path:
        return False, 'no path'
    if not os.path.exists(path):
        return False, f'path not found: {path}'
    editor_key = project.get('editor') or get_default_editor() or ''
    cmd = _resolve_editor_cmd(editor_key)
    print(f'[work] opening "{project.get("name")}" | editor={editor_key} | cmd={cmd} | path={path}', flush=True)
    if not cmd:
        return False, f'editor not found: {editor_key}'

    exe = cmd[0]
    is_custom = editor_key.startswith('custom:')

    if is_custom:
        # Universal: pass the path as a command-line argument.
        # Works for the vast majority of IDEs (JetBrains, Sublime, Vim, etc.).
        # If the IDE is already running and doesn't handle the path itself — that's
        # the IDE's own behaviour; nothing to do about it universally.
        try:
            subprocess.Popen([exe, path])
            return True, ''
        except Exception as e:
            return False, str(e)
    else:
        # Known editors (code, pycharm, etc.) — standard CLI invocation
        try:
            subprocess.Popen(cmd + [path], shell=False,
                             creationflags=subprocess.CREATE_NO_WINDOW)
            return True, ''
        except Exception as e:
            return False, str(e)


# Digraphs must come before single chars to avoid partial replacement
_TRANSLIT_BASE: list[tuple[str, str]] = [
    ('дж', 'j'), ('дз', 'dz'),
    ('щ', 'sch'), ('ш', 'sh'), ('ч', 'ch'), ('ж', 'zh'),
    ('ю', 'yu'), ('я', 'ya'), ('ё', 'yo'), ('е', 'ye'), ('є', 'ye'),
    ('ї', 'yi'), ('й', 'y'), ('ъ', ''), ('ь', ''),
    ('а', 'a'), ('б', 'b'), ('в', 'v'), ('г', 'g'), ('д', 'd'),
    ('з', 'z'), ('и', 'i'), ('і', 'i'), ('к', 'k'), ('л', 'l'),
    ('м', 'm'), ('н', 'n'), ('о', 'o'), ('п', 'p'), ('р', 'r'),
    ('с', 's'), ('т', 't'), ('у', 'u'), ('ф', 'f'), ('х', 'kh'),
    ('ц', 'ts'), ('ы', 'y'), ('э', 'e'), ('ґ', 'g'),
]

# Ukrainian г is /h/ (Гривня → Hryvnia), not /g/ like Russian
_TRANSLIT_UK_OVERRIDES: dict[str, str] = {'г': 'h'}


def _transliterate(text: str, overrides: 'dict[str, str] | None' = None) -> str:
    t = text.lower()
    for cyr, lat in _TRANSLIT_BASE:
        repl = overrides.get(cyr, lat) if overrides else lat
        t = t.replace(cyr, repl)
    return t

def _search_variants(query: str) -> list[str]:
    """
    Return all meaningful search variants for a query:
    - original (Cyrillic or Latin as typed)
    - Russian transliteration (г→g)
    - Ukrainian transliteration (г→h)
    Deduped, empty strings excluded.
    """
    q = query.lower().strip()
    ru = _transliterate(q)
    uk = _transliterate(q, _TRANSLIT_UK_OVERRIDES)
    seen: set[str] = set()
    result: list[str] = []
    for v in (q, ru, uk):
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result

def search_projects_on_disk(query: str, max_results: int = 20) -> list[str]:
    """
    Fast folder search. Priority:
    1. win32com Windows Search Index — ~50ms, no subprocess overhead
    2. Everything HTTP API          — ~10ms, if running
    3. dir /s /b /ad via cmd        — fallback, native FS enumeration
    """
    variants = _search_variants(query)
    if not any(v for v in variants if v):
        return []

    return (
        _search_win32com(variants, max_results)
        or _search_everything(variants, max_results)
        or _search_bfs(variants, max_results)
    )


def _search_win32com(variants: list[str], max_results: int) -> list[str]:
    """Windows Search Index via win32com — ~50ms when index covers the folder."""
    try:
        import win32com.client
        like_clauses = ' OR '.join(
            f"System.FileName LIKE '%{v}%'" for v in variants if v
        )
        # System.Kind = 'directory' is the correct value (not 'folder')
        sql = (
            f"SELECT TOP {max_results} System.ItemPathDisplay "
            f"FROM SystemIndex "
            f"WHERE System.Kind = 'directory' AND ({like_clauses})"
        )
        conn = win32com.client.Dispatch('ADODB.Connection')
        conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
        rs, _ = conn.Execute(sql)
        found = []
        while not rs.EOF:
            val = rs.Fields['System.ItemPathDisplay'].Value
            if val and os.path.isdir(val):
                found.append(val)
            rs.MoveNext()
        rs.Close(); conn.Close()
        return found
    except Exception:
        return []


def _search_everything(variants: list[str], max_results: int) -> list[str]:
    """Everything tool HTTP API — instant if running on port 80.
    Sends one request per variant (OR semantics) and merges results."""
    try:
        import urllib.request, urllib.parse, json as _j
        found: list[str] = []
        seen: set[str] = set()
        for v in variants:
            if not v:
                continue
            params = urllib.parse.urlencode(
                {'search': f'folder:{v}', 'json': 1, 'count': max_results, 'path_column': 1}
            )
            try:
                with urllib.request.urlopen(f'http://localhost/?{params}', timeout=1) as r:
                    data = _j.loads(r.read())
                for item in data.get('results', []):
                    full = os.path.join(item.get('path', ''), item.get('name', ''))
                    if full and full not in seen and os.path.isdir(full):
                        seen.add(full)
                        found.append(full)
                        if len(found) >= max_results:
                            return found
            except Exception:
                pass
        return found
    except Exception:
        return []


def _get_search_roots() -> list[str]:
    """Return all available drives + home dir as BFS starting points."""
    roots: list[str] = []
    home = os.path.expanduser('~')
    try:
        # Windows API — no alphabet guessing needed
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                roots.append(chr(65 + i) + ':\\')
    except Exception:
        # Fallback: scan existing drives via PATH
        import string
        for letter in string.ascii_uppercase:
            drive = letter + ':\\'
            if os.path.exists(drive):
                roots.append(drive)
    # Put home drive first for faster shallow-project hits
    home_drive = os.path.splitdrive(home)[0].upper() + '\\'
    roots.sort(key=lambda d: (d.upper() != home_drive, d))
    return roots


def _search_bfs(variants: list[str], max_results: int) -> list[str]:
    """
    Breadth-first scan — finds shallow projects (2-4 levels from home) fast.
    Seeds from all available drives; home drive is first.
    Hard 5-second deadline.
    """
    import collections, time

    _SKIP = {
        'node_modules', '__pycache__', '.git', '.svn', '.hg',
        'venv', '.venv', 'env', '.env', 'dist', 'build', 'target',
        'vendor', 'bower_components', '.cache', '.tox',
        'appdata', 'windows', 'program files', 'program files (x86)',
        'programdata', '$recycle.bin', 'system32', 'syswow64',
        'msocache', 'recovery', 'perflogs', 'intel', 'amd',
    }

    def _matches(name: str) -> bool:
        nl = name.lower()
        return any(v and v in nl for v in variants)

    home = os.path.expanduser('~')
    seen: set[str] = {home}
    queue: collections.deque[str] = collections.deque([home])
    found: list[str] = []
    deadline = time.monotonic() + 5.0

    # Seed with all available drives (home drive is already first via _get_search_roots)
    for drive in _get_search_roots():
        if drive not in seen:
            seen.add(drive)
            queue.append(drive)

    while queue and len(found) < max_results and time.monotonic() < deadline:
        path = queue.popleft()
        try:
            for entry in os.scandir(path):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.lower() in _SKIP or entry.name.startswith('.'):
                    continue
                if entry.path in seen:
                    continue
                seen.add(entry.path)
                if _matches(entry.name):
                    found.append(entry.path)
                    if len(found) >= max_results:
                        break
                queue.append(entry.path)
        except (PermissionError, OSError):
            pass

    return found


def _levenshtein(a: str, b: str) -> int:
    """Standard edit distance, O(len(a) × len(b))."""
    if not a: return len(b)
    if not b: return len(a)
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, dp[0] = dp[0], i
        for j, cb in enumerate(b, 1):
            prev, dp[j] = dp[j], prev if ca == cb else 1 + min(prev, dp[j], dp[j - 1])
    return dp[len(b)]


def find_project_by_name(text: str) -> dict | None:
    projects = get_projects()
    if not projects:
        return None
    text_l = text.lower().strip()

    # 1. Exact
    for p in projects:
        if p['name'].lower() == text_l:
            return p

    # 2. Substring (name inside query or query inside name)
    for p in projects:
        nl = p['name'].lower()
        if nl in text_l or text_l in nl:
            return p

    # 3. Cross-script: compare transliteration variants
    tv = _search_variants(text_l)
    for p in projects:
        pv = _search_variants(p['name'].lower())
        for t in tv:
            for q in pv:
                if t and q and (t in q or q in t):
                    return p

    # 4. Any matching word
    text_words = set(text_l.split())
    for p in projects:
        if text_words & set(p['name'].lower().split()):
            return p

    # 5. Fuzzy: Levenshtein ≤ max(1, name_len // 4)
    #    — allows ~1 error per 4 chars (астро→астра, джарвыс→джарвис, etc.)
    best_p, best_dist = None, 999
    for p in projects:
        pname = p['name'].lower()
        # Full-name comparison
        for t in (text_l, *_search_variants(text_l)):
            for q in (pname, *_search_variants(pname)):
                d = _levenshtein(t, q)
                thresh = max(1, len(q) // 4)
                if d <= thresh and d < best_dist:
                    best_p, best_dist = p, d
        # Per-word comparison (for multi-word names)
        for pword in pname.split():
            for tword in text_l.split():
                if len(tword) < 3 or len(pword) < 3:
                    continue
                d = _levenshtein(tword, pword)
                thresh = max(1, len(pword) // 4)
                if d <= thresh and d < best_dist:
                    best_p, best_dist = p, d

    return best_p
