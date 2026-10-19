"""Backup of the settings for moving to another PC or reinstalling: one JSON file, saved and restored through native dialogs.

In the file: the settings (jarvis_settings.json) without anything secret and without what belongs to this PC (audio devices, window sizes, last location), the user's own calendar events,
and the appearance choices of the new window (sent by the screen: they live in the browser storage, not in the core). API keys, passwords and tokens are never written: the key detection is by
name (password, token, secret, api key), so a new secret added to the settings later is skipped too. Restoring asks for confirmation first, keeps a copy of the current settings next to them
(`jarvis_settings.before_restore.json`), merges the settings key by key and adds only the calendar events that are not there yet.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime

from core import settings_io
from core.safe import swallow as _swallow

FORMAT = 'jarvis-backup'
VERSION = 1
MAX_BYTES = 5_000_000
MAX_EVENTS = 5000
SECRET_RE = re.compile(r'(pass(word|wd)?|token|secret|api[_-]?key)', re.I)
KEY_RE = re.compile(r'^[A-Za-z0-9_]{1,64}$')
MACHINE_KEYS = frozenset({'audio_input_device_index', 'audio_output_device_name', 'best_sample_rate', 'onnx_threads', 'zoom_factor', 'scrollbar_width', 'sidebar_width_raw', 'sidebar_width_left',
                          'sidebar_width_right', 'start_maximized', 'last_location', 'weather_yesterday', 'dep_sync_target'})
UI_KEYS = ('jarvisTheme', 'jarvisCustom', 'jarvisAuto', 'uiScale', 'jarvisSfx', 'jarvisSfxVol', 'jarvisHide', 'jarvisFx')
_pending: dict[str, dict] = {}
_lock = threading.Lock()


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def _scrub(value):
    """A copy of the value without any secret-looking key at any depth."""
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if not SECRET_RE.search(str(k))}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def portable_settings(settings: dict) -> dict:
    return {k: _scrub(v) for k, v in settings.items() if KEY_RE.match(str(k)) and k not in MACHINE_KEYS and not SECRET_RE.search(str(k))}


def _events() -> list[dict]:
    try:
        from actions import calendar_hub as hub
        return [e for e in hub.load_local() if isinstance(e, dict)][:MAX_EVENTS]
    except Exception:
        return []


def build(ui: dict | None = None) -> dict:
    ui = {k: str(v) for k, v in (ui or {}).items() if k in UI_KEYS and v is not None and len(str(v)) < 5000}
    return {'format': FORMAT, 'version': VERSION, 'created': datetime.now().isoformat(timespec='seconds'), 'settings': portable_settings(settings_io.read()), 'calendar': _events(), 'ui': ui}


def export(ui: dict | None = None, path: str = '') -> dict:
    """Writes the backup file; without `path` a "save as" dialog asks where."""
    if not path:
        from .filepick import save_file
        path = save_file('Сохранить настройки', f"Jarvis_настройки_{datetime.now():%Y-%m-%d}.json")
        if not path:
            return _bad('cancelled')
    data = build(ui)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        return _bad('write_failed')
    return {'ok': True, 'path': path, 'settings': len(data['settings']), 'events': len(data['calendar'])}


def _load(path: str) -> dict | None:
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get('format') != FORMAT or not isinstance(d.get('version'), int) or d['version'] > VERSION or not isinstance(d.get('settings'), dict):
        return None
    return d


def preview(path: str = '') -> dict:
    """Reads a backup file (chosen in a dialog) and remembers it under a token; nothing is changed yet."""
    if not path:
        from .filepick import pick_files, filters
        picked = pick_files('Восстановить настройки', filters(('Резервные копии Jarvis', '*.json')))
        if not picked:
            return _bad('cancelled')
        path = picked[0]
    d = _load(path)
    if d is None:
        return _bad('bad_file')
    settings = portable_settings(d['settings'])
    cal = [e for e in d.get('calendar', []) if isinstance(e, dict)][:MAX_EVENTS] if isinstance(d.get('calendar'), list) else []
    ui = {k: str(v) for k, v in (d.get('ui') or {}).items() if k in UI_KEYS} if isinstance(d.get('ui'), dict) else {}
    token = secrets.token_hex(8)
    with _lock:
        _pending.clear()
        _pending[token] = {'settings': settings, 'calendar': cal, 'ui': ui}
    return {'ok': True, 'token': token, 'created': str(d.get('created') or ''), 'settings': len(settings), 'events': len(cal), 'has_ui': bool(ui)}


def apply(token: str) -> dict:
    with _lock:
        item = _pending.pop(str(token or ''), None)
    if item is None:
        return _bad('expired')
    src = settings_io._path()
    try:
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(os.path.dirname(src), 'jarvis_settings.before_restore.json'))
    except OSError:
        return _bad('write_failed')                      # no copy of the current settings: better to stop than to overwrite them
    cur = settings_io.read()                             # a restored section must not lose the secret the current one holds
    for k, v in item['settings'].items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            v.update({sk: sv for sk, sv in cur[k].items() if SECRET_RE.search(str(sk))})
    if not settings_io.update(item['settings']):
        return _bad('write_failed')
    added = 0
    if item['calendar']:
        try:
            from actions import calendar_hub as hub
            have = {(e.get('title'), e.get('date'), e.get('time')) for e in hub.load_local()}
            for e in item['calendar']:
                if (e.get('title'), e.get('date'), e.get('time')) in have:
                    continue
                try:
                    hub.add_local({k: v for k, v in e.items() if k != 'id'})
                    added += 1
                except hub.CalendarError:
                    continue
        except Exception:
            _swallow()
    return {'ok': True, 'settings': len(item['settings']), 'events_added': added, 'ui': item['ui']}


def run(data: dict) -> dict:
    """Entry of the `backup` bridge command: op `export` {ui?} | `preview` | `apply` {token}. Paths are never taken from the screen: files are picked in native dialogs."""
    op = str(data.get('op', ''))
    if op == 'export':
        return export(data.get('ui') if isinstance(data.get('ui'), dict) else None)
    if op == 'preview':
        return preview()
    if op == 'apply':
        return apply(data.get('token'))
    return _bad('bad_op')
