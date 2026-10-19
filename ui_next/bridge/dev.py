"""Developer settings of the new UI (the old settings window, tab "Developer"): the IDE context apps, folder search, extensions for new files, editors and the "get to work" projects.

Data lives where the old window keeps it (jarvis_settings.json, written through core.settings_io so the old HUD's copy follows):
  context_apps, allow_parent_search, folder_search_depth, programming_file_extensions, dev_projects, dev_default_editor, dev_custom_editors, dev_editor_names
Finding editors, searching folders and starting a project reuse actions/dev_projects.py.
"""
from __future__ import annotations

import os
import re
import threading

from core import settings_io

DEFAULT_CONTEXT_APPS = ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe']
MAX_ITEMS = 100
_APP_RE = re.compile(r'^[\w.+\- ]{1,60}$')
_lock = threading.Lock()
_detected: list[tuple[str, str]] | None = None


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def _s(key: str, default=None):
    return settings_io.read().get(key, default)


def _list(key: str, default=None) -> list:
    v = _s(key, default if default is not None else [])
    return list(v) if isinstance(v, list) else list(default or [])


def _put(**changes) -> bool:
    return settings_io.update(changes)


def get_state() -> dict:
    from actions.dev_projects import get_default_editor
    from actions.programming_extensions import normalize_extension
    exts = []
    for x in _list('programming_file_extensions'):
        n = normalize_extension(str(x))
        if n and n not in exts:
            exts.append(n)
    projects = [{'name': str(p.get('name', '')), 'path': str(p.get('path', '')), 'editor': str(p.get('editor', '')), 'exists': os.path.exists(str(p.get('path', '')))}
                for p in _list('dev_projects') if isinstance(p, dict) and p.get('name')]
    try:
        depth = max(1, min(10, int(_s('folder_search_depth', 4))))
    except (TypeError, ValueError):
        depth = 4
    return {'ok': True, 'context_apps': [str(a) for a in _list('context_apps', DEFAULT_CONTEXT_APPS)], 'allow_parent': bool(_s('allow_parent_search', False)), 'depth': depth,
            'extensions': exts, 'projects': projects, 'default_editor': get_default_editor()}


# ---- IDE context apps and folder search ----
def ctx_add(app: str) -> dict:
    app = str(app or '').strip().lower()
    if not _APP_RE.match(app):
        return _bad('bad_value')
    cur = [str(a) for a in _list('context_apps', DEFAULT_CONTEXT_APPS)]
    if app in [a.lower() for a in cur]:
        return _bad('exists')
    if len(cur) >= MAX_ITEMS:
        return _bad('too_many')
    return {'ok': True} if _put(context_apps=cur + [app]) else _bad('write_failed')


def ctx_remove(app: str) -> dict:
    cur = [str(a) for a in _list('context_apps', DEFAULT_CONTEXT_APPS)]
    left = [a for a in cur if a.lower() != str(app or '').lower()]
    if len(left) == len(cur):
        return _bad('not_found')
    return {'ok': True} if _put(context_apps=left) else _bad('write_failed')


def set_parent_search(on) -> dict:
    return {'ok': True} if _put(allow_parent_search=bool(on)) else _bad('write_failed')


def set_depth(value) -> dict:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return _bad('bad_value')
    if not 1 <= n <= 10:
        return _bad('bad_value')
    return {'ok': True} if _put(folder_search_depth=n) else _bad('write_failed')


# ---- extensions of new files ----
def ext_add(ext: str) -> dict:
    from actions.programming_extensions import normalize_extension
    n = normalize_extension(str(ext or ''))
    if not n:
        return _bad('bad_value')
    cur = get_state()['extensions']
    if n in cur:
        return _bad('exists')
    if len(cur) >= MAX_ITEMS:
        return _bad('too_many')
    return {'ok': True} if _put(programming_file_extensions=cur + [n]) else _bad('write_failed')


def ext_remove(ext: str) -> dict:
    cur = get_state()['extensions']
    left = [e for e in cur if e != str(ext or '').strip().lower().lstrip('.')]
    if len(left) == len(cur):
        return _bad('not_found')
    return {'ok': True} if _put(programming_file_extensions=left) else _bad('write_failed')


# ---- editors ----
def editors(refresh: bool = False) -> dict:
    """Editors found on this PC plus the ones the user added by hand: {editors: [{key, name, custom}], default}."""
    global _detected
    from actions.dev_projects import detect_installed_editors, get_default_editor
    with _lock:
        if _detected is None or refresh:
            _detected = detect_installed_editors()
        found = list(_detected)
    rows = [{'key': k, 'name': n, 'custom': False} for k, n in found]
    seen = {r['key'] for r in rows}
    for c in _list('dev_custom_editors'):
        if isinstance(c, dict) and c.get('key') and c['key'] not in seen:
            rows.append({'key': str(c['key']), 'name': str(c.get('name') or c['key']), 'custom': True})
    return {'ok': True, 'editors': rows, 'default': get_default_editor()}


def _known_editor_keys() -> set[str]:
    return {r['key'] for r in editors()['editors']}


def editor_default(key: str) -> dict:
    key = str(key or '')
    if key not in _known_editor_keys():
        return _bad('not_found')
    return {'ok': True} if _put(dev_default_editor=key) else _bad('write_failed')


def editor_add(path: str = '', name: str = '') -> dict:
    """Adds a program as an editor (`custom:<exe path>`) and makes it the default one. Without a path a native file dialog opens."""
    path = str(path or '').strip().strip('"')
    if not path:
        from .filepick import filters, pick_files
        picked = pick_files('Редактор кода', filters(('Программы', '*.exe')))
        if not picked:
            return _bad('cancelled')
        path = picked[0]
    if not path.lower().endswith('.exe') or not os.path.isfile(path):
        return _bad('bad_value')
    key = 'custom:' + path
    title = ' '.join(str(name or '').split())[:40] or os.path.splitext(os.path.basename(path))[0]
    custom = [c for c in _list('dev_custom_editors') if isinstance(c, dict) and c.get('key') != key]
    if len(custom) >= MAX_ITEMS:
        return _bad('too_many')
    names = dict(_s('dev_editor_names', {}) if isinstance(_s('dev_editor_names', {}), dict) else {})
    names[key] = title
    ok = _put(dev_custom_editors=custom + [{'key': key, 'name': title}], dev_editor_names=names, dev_default_editor=key)
    return {'ok': True, 'key': key} if ok else _bad('write_failed')


def editor_remove(key: str) -> dict:
    key = str(key or '')
    custom = [c for c in _list('dev_custom_editors') if isinstance(c, dict)]
    left = [c for c in custom if c.get('key') != key]
    if not key.startswith('custom:') or len(left) == len(custom):
        return _bad('not_found')
    names = dict(_s('dev_editor_names', {}) if isinstance(_s('dev_editor_names', {}), dict) else {})
    names.pop(key, None)
    changes = {'dev_custom_editors': left, 'dev_editor_names': names}
    if _s('dev_default_editor') == key:
        changes['dev_default_editor'] = left[0]['key'] if left else 'code'
    return {'ok': True} if _put(**changes) else _bad('write_failed')


# ---- "get to work" projects ----
def project_save(name: str, path: str, editor: str = '', old_name: str = '') -> dict:
    name = ' '.join(str(name or '').split())[:60]
    path = str(path or '').strip().strip('"')
    editor = str(editor or '').strip()
    if not name or not path:
        return _bad('required')
    if not os.path.exists(path):
        return _bad('path_missing')
    if editor and editor not in _known_editor_keys():
        return _bad('not_found')
    projects = [p for p in _list('dev_projects') if isinstance(p, dict)]
    old = str(old_name or '').lower()
    entry = {'name': name, 'path': path, **({'editor': editor} if editor else {})}
    idx = next((i for i, p in enumerate(projects) if old and str(p.get('name', '')).lower() == old), None)
    clash = next((i for i, p in enumerate(projects) if str(p.get('name', '')).lower() == name.lower() and i != idx), None)
    if clash is not None:
        return _bad('exists')
    if idx is None:
        if len(projects) >= MAX_ITEMS:
            return _bad('too_many')
        projects.append(entry)
    else:
        projects[idx] = entry
    return {'ok': True} if _put(dev_projects=projects) else _bad('write_failed')


def project_remove(name: str) -> dict:
    projects = [p for p in _list('dev_projects') if isinstance(p, dict)]
    left = [p for p in projects if str(p.get('name', '')).lower() != str(name or '').lower()]
    if len(left) == len(projects):
        return _bad('not_found')
    return {'ok': True} if _put(dev_projects=left) else _bad('write_failed')


def project_open(name: str) -> dict:
    """Starts the project in its editor, like the voice command "за работу"."""
    from actions.dev_projects import open_project
    p = next((p for p in _list('dev_projects') if isinstance(p, dict) and str(p.get('name', '')).lower() == str(name or '').lower()), None)
    if p is None:
        return _bad('not_found')
    ok, msg = open_project(p)
    if ok:
        return {'ok': True}
    return _bad('path_missing' if str(msg).startswith('path not found') else 'no_editor' if str(msg).startswith('editor not found') else 'failed')


def pick_folder() -> dict:
    from .filepick import pick_folder as pick
    path = pick('Папка проекта')
    return {'ok': True, 'path': path} if path else _bad('cancelled')


def find_folders(query: str) -> dict:
    """Folders on the disk whose name matches the words ("джарвис" also finds "Jarvis")."""
    from actions.dev_projects import search_projects_on_disk
    q = str(query or '').strip()
    if len(q) < 2 or len(q) > 80:
        return _bad('required')
    try:
        return {'ok': True, 'results': [str(x) for x in search_projects_on_disk(q, 20)]}
    except Exception:
        return _bad('failed')


def run(data: dict) -> dict:
    """Entry of the `dev` bridge command. op `state` | `editors` {refresh?} | `ctx_add` {app} | `ctx_remove` {app} | `parent_search` {on} | `depth` {value} | `ext_add` {ext} | `ext_remove` {ext}
    | `editor_default` {key} | `editor_add` {path?, name?} | `editor_remove` {key} | `project_save` {name, path, editor?, old_name?} | `project_remove` {name} | `project_open` {name} | `pick_folder` | `find` {query}.
    A change answers with the fresh state (editor ops also with `editors`)."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return get_state()
    if op == 'editors':
        return editors(bool(data.get('refresh')))
    if op == 'pick_folder':
        return pick_folder()
    if op == 'find':
        return find_folders(data.get('query'))
    if op == 'project_open':
        return project_open(data.get('name'))
    table = {'ctx_add': lambda: ctx_add(data.get('app')), 'ctx_remove': lambda: ctx_remove(data.get('app')), 'parent_search': lambda: set_parent_search(data.get('on')), 'depth': lambda: set_depth(data.get('value')),
             'ext_add': lambda: ext_add(data.get('ext')), 'ext_remove': lambda: ext_remove(data.get('ext')), 'editor_default': lambda: editor_default(data.get('key')),
             'editor_add': lambda: editor_add(data.get('path', ''), data.get('name', '')), 'editor_remove': lambda: editor_remove(data.get('key')),
             'project_save': lambda: project_save(data.get('name'), data.get('path'), data.get('editor', ''), data.get('old_name', '')), 'project_remove': lambda: project_remove(data.get('name'))}
    fn = table.get(op)
    if fn is None:
        return _bad('bad_op')
    res = fn()
    if not res.get('ok'):
        return res
    out = {**get_state(), 'ok': True}
    if op.startswith('editor'):
        out['editors'] = editors()['editors']
    return out
