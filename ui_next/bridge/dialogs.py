"""The core's dialogs, built for the new window (see prompts.py for how they are shown and answered).

Each function takes what the old Tk dialog took and returns what it returned, or `prompts.NOT_HANDLED` when no new window is connected (the old dialog is then used). The old dialog modules call these
first: ui/dialogs/name_dlg.py (`ask_text`), git_stage_dlg.py (`ask_git_stage`), yt_picker_dlg.py (the picker and its voice helpers), core/handler/commands/system.py (the cleanup review) and features/guard.py (the alert).
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import tempfile
import threading
from pathlib import Path

from . import prompts
from core.safe import swallow as _swallow

NOT_HANDLED = prompts.NOT_HANDLED
_NAME_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_BRANCH_RE = re.compile(r'^(?!-)(?!.*\.\.)[\w./-]{1,100}$')
_EXT_RE = re.compile(r'^[a-z0-9]{1,16}$')
_CORE_EXT = ('docx', 'xlsx', 'pptx', 'txt')
_DESC = {'ru': {'docx': 'Word Документ', 'xlsx': 'Excel Таблица', 'pptx': 'PowerPoint Презентация', 'txt': 'Текстовый файл', 'tsx': 'TypeScript JSX', 'ts': 'TypeScript файл', 'py': 'Python Скрипт', 'js': 'JavaScript Файл',
               'html': 'Веб-страница', 'md': 'Markdown Документ'},
         'uk': {'docx': 'Word Документ', 'xlsx': 'Excel Таблиця', 'pptx': 'PowerPoint Презентація', 'txt': 'Текстовий файл', 'tsx': 'TypeScript JSX', 'ts': 'TypeScript файл', 'py': 'Python Скрипт', 'js': 'JavaScript Файл',
               'html': 'Веб-сторінка', 'md': 'Markdown Документ'}}


def _lang() -> str:
    try:
        from core.i18n import get_language
        return 'uk' if get_language() == 'uk' else 'ru'
    except Exception:
        return 'ru'


def _s(v, limit: int) -> str:
    return str(v or '')[:limit]


def _ext_options(lang: str) -> list[dict]:
    exts = list(_CORE_EXT)
    try:
        from actions.programming_extensions import get_programming_extensions
        exts += [e.lstrip('.') for e in get_programming_extensions() if e.lstrip('.') not in _CORE_EXT]
    except Exception:
        _swallow()
    desc = _DESC.get(lang, _DESC['ru'])
    return [{'ext': e, 'label': f"{desc.get(e, 'Файл')}  (.{e})"} for e in exts]


def _quick_paths() -> list[dict]:
    home = Path.home()
    cand = [('Рабочий стол', home / 'Desktop'), ('Документы', home / 'Documents'), ('Загрузки', home / 'Downloads'), ('Проект', Path.cwd())]
    return [{'label': n, 'path': str(p)} for n, p in cand if p.exists()]


# ---- a line of text, optionally with a folder and a file type ----
def ask_text(*, title, header, ok_text, cancel_text, placeholder='', hint_voice='', voice_confirm=(), voice_cancel=(), require_message_to_confirm=False,
             initial_path=None, show_extension_field=False, default_extension=None, initial_value=None):
    """Returns the text, or (folder, text), or (folder, name, extension), or None when cancelled; NOT_HANDLED without a new window."""
    with_path = initial_path is not None
    with_ext = bool(with_path and show_extension_field)
    lang = _lang()
    exts = _ext_options(lang) if with_ext else []
    data = {'title': _s(title, 120), 'header': _s(header, 160), 'ok': _s(ok_text, 40), 'cancel': _s(cancel_text, 40), 'placeholder': _s(placeholder, 120), 'hint': _s(hint_voice, 200),
            'require': bool(require_message_to_confirm), 'path': _s(initial_path, 600) if with_path else None, 'value': _s(initial_value, 300), 'with_ext': with_ext, 'exts': exts,
            'ext': (default_extension or 'txt').strip().lower().lstrip('.') or 'txt', 'quick': _quick_paths() if with_path else []}
    allowed = {e['ext'] for e in exts}

    def validate(v):
        v = v if isinstance(v, dict) else {}
        text = str(v.get('text', '')).strip()[:300]
        path = str(v.get('path', '')).strip()[:600]
        if with_ext:
            ext = str(v.get('ext', '')).strip().lower().lstrip('.')
            if not text or _NAME_BAD.search(text) or not _EXT_RE.match(ext) or (allowed and ext not in allowed and ext not in {e['ext'] for e in _ext_options(lang)}):
                raise ValueError('bad name or type')
            return (path, text, ext)
        if with_path:
            if _NAME_BAD.search(text) or (require_message_to_confirm and not text):
                raise ValueError('bad name')
            return (path, text)
        if require_message_to_confirm and not text:
            raise ValueError('empty')
        return text
    res = prompts.ask('text', data, {'validate': validate}, voice=(tuple(voice_confirm), tuple(voice_cancel)))
    if res is NOT_HANDLED:
        return NOT_HANDLED
    return res[1] if res[0] == 'ok' else None


# ---- the files and options of a git commit ----
def ask_git_stage(repo_path, files):
    """Returns the old dialog's dict (files, message, branch, push, force, upstream, open_pr, pr_title) or None; NOT_HANDLED without a new window."""
    try:
        from actions.git_commit import get_branches, get_current_branch
        branches, current = list(get_branches(repo_path)), get_current_branch(repo_path)
    except Exception:
        branches, current = [], ''
    rows = [{'file': _s(f.get('file'), 400), 'status': _s(f.get('status'), 20)} for f in files][:3000]
    names = {r['file'] for r in rows}
    data = {'repo': _s(repo_path, 400), 'files': rows, 'branches': [_s(b, 120) for b in branches][:300], 'current': _s(current, 120)}

    def validate(v):
        v = v if isinstance(v, dict) else {}
        sel = [str(x) for x in v.get('files', [])]
        if any(x not in names for x in sel):
            raise ValueError('unknown file')
        branch = str(v.get('branch', '')).strip()
        if not _BRANCH_RE.match(branch):
            raise ValueError('bad branch')
        push = bool(v.get('push'))
        pr = str(v.get('pr_title', '')).strip()[:200] if push else ''
        return {'files': sel, 'message': str(v.get('message', '')).strip()[:2000], 'branch': branch, 'push': push, 'force': bool(v.get('force')) and push, 'upstream': bool(v.get('upstream')) and push,
                'open_pr': bool(pr), 'pr_title': pr}
    from ui_next import host
    voice = (host.VOICE_COMMIT_CONFIRM, host.VOICE_CANCEL)
    res = prompts.ask('git', data, {'validate': validate}, voice=voice)
    if res is NOT_HANDLED:
        return NOT_HANDLED
    return res[1] if res[0] == 'ok' else None


# ---- what the deep cleanup found ----
def open_cleanup(candidates, on_confirm) -> bool:
    """candidates: [{'path','name','size_bytes','age_days'}]. on_confirm(paths) runs with the checked ones (only paths that were listed). False without a new window."""
    items = [{'path': _s(c.get('path'), 500), 'name': _s(c.get('name'), 200), 'size': int(c.get('size_bytes') or 0), 'age': int(c.get('age_days') or 0)} for c in candidates]
    listed = {i['path'] for i in items}

    def validate(v):
        paths = [str(p) for p in (v if isinstance(v, list) else [])]
        if any(p not in listed for p in paths):
            raise ValueError('unlisted path')
        return list(dict.fromkeys(paths))

    def done(status, value):
        if status == 'ok' and value:
            on_confirm(value)
    return prompts.open_prompt('cleanup', {'items': items}, {'validate': validate}, done)


# ---- which video to play ----
def _thumb_uri(url: str) -> str:
    try:
        import requests
        from PIL import Image
        cache = os.path.join(tempfile.gettempdir(), 'jarvis_ytpick')
        os.makedirs(cache, exist_ok=True)
        path = os.path.join(cache, hashlib.md5(url.encode('utf-8'), usedforsecurity=False).hexdigest() + '.jpg')
        if not os.path.exists(path):
            r = requests.get(url, timeout=6.0, headers={'User-Agent': 'JarvisOS'})
            if r.status_code != 200:
                return ''
            with open(path, 'wb') as f:
                f.write(r.content)
        with Image.open(path) as img:
            img = img.convert('RGB')
            img.thumbnail((240, 160))
            buf = io.BytesIO()
            img.save(buf, 'JPEG', quality=80)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


def open_yt_picker(candidates, on_select, on_timeout=None, on_cancel=None, timeout_sec: float = 20.0) -> bool:
    """False without a new window. Thumbnails arrive a little later, the list is shown at once."""
    items = [{'title': _s(c.get('title'), 200), 'thumb': ''} for c in candidates]

    def validate(v):
        i = int(v)
        if not 0 <= i < len(candidates):
            raise ValueError('index')
        return i

    def done(status, value):
        if status == 'ok':
            on_select(candidates[value], value)
        elif status == 'timeout':
            if on_timeout:
                on_timeout()
        elif on_cancel:
            on_cancel()
    if not prompts.open_prompt('yt', {'items': items}, {'validate': validate}, done, timeout=timeout_sec):
        return False
    pid = prompts.current_id()

    def fetch():
        got = list(items)
        for n, c in enumerate(candidates):
            if c.get('thumbnail'):
                got[n] = {**got[n], 'thumb': _thumb_uri(c['thumbnail'])}
                prompts.update(pid, {'items': list(got)})
    threading.Thread(target=fetch, daemon=True, name='YtPickThumbs').start()
    return True


def yt_open() -> bool:
    return prompts.is_open('yt')


def yt_select(i: int) -> bool:
    return prompts.finish_kind('yt', 'ok', i)


def yt_cancel() -> bool:
    return prompts.finish_kind('yt', 'cancel')


# ---- the stranger alert of the camera guard ----
def show_guard_alert(image_path) -> bool:
    """A notice with the camera picture; False without a new window."""
    uri = ''
    try:
        if image_path and os.path.exists(image_path):
            from PIL import Image
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                img.thumbnail((480, 360))
                buf = io.BytesIO()
                img.save(buf, 'JPEG', quality=82)
            uri = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        uri = ''
    return prompts.open_prompt('notice', {'tone': 'alert', 'title': 'Обнаружен посторонний', 'text': 'Камера охраны увидела незнакомого человека. Снимок отправлен владельцу, если подключён Telegram.', 'image': uri},
                               {'validate': lambda v: None}, lambda s, v: None)
