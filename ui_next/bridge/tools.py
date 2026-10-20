"""Tools settings of the new UI (the old settings window, tab "Tools"): saved videos, quick links, game-mode keep list, app launch rules, Telegram remote control, updates.

Data lives where the old window keeps it, so both windows and the core see the same values:
  jarvis_settings.json (through core.settings_io): max_saved_videos, meetings, app_launch_rules, auto_update_enabled, feature_modules
  ~/Jarvis_YT_Saved.txt                          : saved videos, one "timestamp - url" per line
  data/game_mode_prefs.json                      : keep_titles (relative to the working directory, as in actions/system_parts/game_mode.py)
  secrets file                                   : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (the token never goes back to the screen)
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

from core import settings_io

_log = logging.getLogger(__name__)
_MAX_ITEMS = 100
_GAME_PREFS = os.path.join('data', 'game_mode_prefs.json')
_TOKEN_RE = re.compile(r'^\d{3,}:[A-Za-z0-9_-]{20,}$')
_CHAT_RE = re.compile(r'^-?\d{3,}$')
_lock = threading.Lock()


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def _clean(s, limit: int) -> str:
    s = str(s or '').strip()
    return '' if len(s) > limit or any(ord(c) < 32 for c in s) else s


def _url_ok(u: str) -> bool:
    return u.lower().startswith(('http://', 'https://')) and len(u) <= 2000 and not any(c in u for c in '\r\n\0 ')


# ---- saved videos ----
def _videos_path() -> str:
    return os.path.join(os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')


def _read_videos() -> list[dict]:
    out = []
    try:
        with open(_videos_path(), 'r', encoding='utf-8') as f:
            for line in f.read().splitlines():
                line = line.strip()
                if line and ' - ' in line:
                    ts, url = line.split(' - ', 1)
                    out.append({'ts': ts.strip(), 'url': url.strip()})
    except OSError:
        pass
    return out


def delete_video(ts: str, url: str) -> dict:
    with _lock:
        items = _read_videos()
        for i, v in enumerate(items):
            if v['ts'] == ts and v['url'] == url:
                del items[i]
                break
        else:
            return _bad('not_found')
        try:
            with open(_videos_path(), 'w', encoding='utf-8') as f:
                for v in items:
                    f.write(f"{v['ts']} - {v['url']}\n")
        except OSError:
            return _bad('write_failed')
    return {'ok': True}


# ---- quick links (voice phrase -> link) ----
def add_meeting(phrase, url, name) -> dict:
    phrase, url, name = _clean(phrase, 60).lower(), _clean(url, 2000), _clean(name, 60)
    if not phrase or not url:
        return _bad('required')
    if not _url_ok(url):
        return _bad('bad_url')
    items = [m for m in settings_io.read().get('meetings', []) if isinstance(m, dict)]
    if any(str(m.get('phrase', '')).lower() == phrase for m in items):
        return _bad('exists')
    if len(items) >= _MAX_ITEMS:
        return _bad('too_many')
    items.append({'name': name or phrase, 'phrase': phrase, 'url': url})
    return {'ok': True} if settings_io.update({'meetings': items}) else _bad('write_failed')


def update_meeting(old, phrase, url, name) -> dict:
    """Change one quick link: found by its current phrase, same checks as a new one (a phrase another link uses is refused)."""
    old, phrase, url, name = str(old or '').lower(), _clean(phrase, 60).lower(), _clean(url, 2000), _clean(name, 60)
    if not phrase or not url:
        return _bad('required')
    if not _url_ok(url):
        return _bad('bad_url')
    items = [m for m in settings_io.read().get('meetings', []) if isinstance(m, dict)]
    at = next((i for i, m in enumerate(items) if str(m.get('phrase', '')).lower() == old), None)
    if at is None:
        return _bad('not_found')
    if phrase != old and any(str(m.get('phrase', '')).lower() == phrase for m in items):
        return _bad('exists')
    items[at] = {'name': name or phrase, 'phrase': phrase, 'url': url}
    return {'ok': True} if settings_io.update({'meetings': items}) else _bad('write_failed')


def delete_meeting(phrase) -> dict:
    items = [m for m in settings_io.read().get('meetings', []) if isinstance(m, dict)]
    left = [m for m in items if str(m.get('phrase', '')).lower() != str(phrase or '').lower()]
    if len(left) == len(items):
        return _bad('not_found')
    return {'ok': True} if settings_io.update({'meetings': left}) else _bad('write_failed')


# ---- apps kept open in game mode ----
def _read_keep() -> list[str]:
    try:
        with open(_GAME_PREFS, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return [str(x) for x in d.get('keep_titles', []) if str(x).strip()] if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def _write_keep(keep: list[str]) -> bool:
    try:
        try:
            with open(_GAME_PREFS, 'r', encoding='utf-8') as f:
                d = json.load(f)
            d = d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            d = {}
        d['keep_titles'] = keep
        os.makedirs(os.path.dirname(_GAME_PREFS), exist_ok=True)
        with open(_GAME_PREFS, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def keep_add(title) -> dict:
    t = _clean(title, 80).lower()
    if not t:
        return _bad('required')
    with _lock:
        keep = _read_keep()
        if t in keep:
            return _bad('exists')
        if len(keep) >= _MAX_ITEMS:
            return _bad('too_many')
        keep.append(t)
        return {'ok': True} if _write_keep(keep) else _bad('write_failed')


def keep_del(title) -> dict:
    t = str(title or '').strip().lower()
    with _lock:
        keep = _read_keep()
        if t not in keep:
            return _bad('not_found')
        keep.remove(t)
        return {'ok': True} if _write_keep(keep) else _bad('write_failed')


# ---- app launch rules: "new" window or "switch" to the open one ----
def _rules() -> dict:
    r = settings_io.read().get('app_launch_rules', {})
    return {str(k): v for k, v in r.items() if v in ('new', 'switch')} if isinstance(r, dict) else {}


def _app_key(name) -> str:
    n = os.path.basename(str(name or '').strip()).lower()
    for ext in ('.exe', '.lnk'):
        if n.endswith(ext):
            n = n[: -len(ext)]
    return _clean(n, 60)


def launch_set(app, mode) -> dict:
    key = _app_key(app)
    if not key:
        return _bad('required')
    if mode not in ('new', 'switch'):
        return _bad('bad_value')
    rules = _rules()
    if key not in rules and len(rules) >= _MAX_ITEMS:
        return _bad('too_many')
    rules[key] = mode
    return {'ok': True} if settings_io.update({'app_launch_rules': rules}) else _bad('write_failed')


def launch_del(app) -> dict:
    rules = _rules()
    key = next((k for k in rules if k.lower() == str(app or '').strip().lower()), None)
    if key is None:
        return _bad('not_found')
    del rules[key]
    return {'ok': True} if settings_io.update({'app_launch_rules': rules}) else _bad('write_failed')


def installed_apps() -> dict:
    """Programs from the Windows uninstall registry, for the picker (same source as the old window)."""
    try:
        from core.system.windows import get_installed_apps
        apps = get_installed_apps()
    except Exception:
        _log.debug('installed apps failed', exc_info=True)
        return _bad('failed')
    rows = [{'name': str(a.get('name', '')), 'exe': str(a.get('exe') or ''), 'ide': bool(a.get('is_ide')), 'noise': bool(a.get('is_noise'))} for a in apps if a.get('name')]
    rows.sort(key=lambda r: (not r['ide'], r['noise'], r['name'].lower()))
    return {'ok': True, 'apps': rows[:1500]}


# ---- Telegram remote control ----
def _remote() -> dict:
    from core.system import module_enabled
    return {'token_set': bool(os.environ.get('TELEGRAM_BOT_TOKEN')), 'chat_id': os.environ.get('TELEGRAM_CHAT_ID', ''), 'enabled': bool(module_enabled('remote_control'))}


def _set_module(name: str, on: bool) -> None:
    mods = settings_io.read().get('feature_modules', {})
    mods = dict(mods) if isinstance(mods, dict) else {}
    mods[name] = bool(on)
    settings_io.update({'feature_modules': mods})
    try:
        from core.system import refresh_module_flags
        refresh_module_flags()
    except Exception:
        _log.debug('refresh_module_flags failed', exc_info=True)


def remote_save(token, chat_id) -> dict:
    token, chat_id = str(token or '').strip(), str(chat_id or '').strip()
    if not token and os.environ.get('TELEGRAM_BOT_TOKEN'):
        token = os.environ['TELEGRAM_BOT_TOKEN']      # only the chat was edited: keep the saved token
    if not token or not chat_id:
        return _bad('required')
    if not _TOKEN_RE.match(token) or not _CHAT_RE.match(chat_id):
        return _bad('bad_value')
    from actions.mail_client import _update_env_var
    _update_env_var('TELEGRAM_BOT_TOKEN', token)
    _update_env_var('TELEGRAM_CHAT_ID', chat_id)
    os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'] = token, chat_id
    _set_module('remote_control', True)
    try:
        from core.engine.jarvis import get_engine
        from features.remote_control import start_remote_control
        engine = get_engine()
        if engine is not None:
            start_remote_control(engine.handler)
    except Exception:
        _log.debug('remote control start failed', exc_info=True)
    return {'ok': True, 'remote': _remote()}


def remote_off() -> dict:
    _set_module('remote_control', False)
    try:
        from features.remote_control.client import stop_remote_control
        stop_remote_control()
    except Exception:
        _log.debug('remote control stop failed', exc_info=True)
    return {'ok': True, 'remote': _remote()}


# ---- updates ----
def _update() -> dict:
    out = {'auto': bool(settings_io.read().get('auto_update_enabled', True)), 'version': '', 'available': '', 'staged': False}
    try:
        from core.system import app_updater
        from core.system.version import APP_VERSION
        out.update(version=APP_VERSION, available=app_updater.get_available_version() or '', staged=bool(app_updater.is_update_staged()))
    except Exception:
        _log.debug('update state failed', exc_info=True)
    return out


def update_check() -> dict:
    try:
        from core.system import app_updater
        threading.Thread(target=app_updater.check_for_update, name='ui-update-check', daemon=True).start()
    except Exception:
        return _bad('failed')
    return {'ok': True}


def update_install() -> dict:
    try:
        from core.system import app_updater
        if not app_updater.is_update_staged():
            return _bad('not_ready')
        if not app_updater.apply_and_restart():
            return _bad('failed')
    except Exception:
        return _bad('failed')
    threading.Timer(0.6, _exit_core).start()    # the installer takes over; the reply goes out first
    return {'ok': True}


def _exit_core() -> None:
    from ui_next import host
    host.exit_now(0)


def _scenario(fn, *args) -> dict:
    from actions import scenarios
    try:
        fn(*args)
    except scenarios.ScenarioError as ex:
        return _bad(ex.code)
    return {'ok': True}


def scenario_save(data: dict) -> dict:
    from actions import scenarios
    return _scenario(scenarios.save, str(data.get('old') or ''), data.get('name'), data.get('phrase'), data.get('steps'))


def scenario_del(name) -> dict:
    from actions import scenarios
    return _scenario(scenarios.delete, str(name or ''))


def set_ip_lookup(on) -> dict:
    return {'ok': True} if settings_io.update({'allow_ip_lookup': bool(on)}) else _bad('write_failed')


def _scenarios() -> list:
    from actions import scenarios
    return scenarios.load()


def get_state() -> dict:
    s = settings_io.read()
    try:
        max_videos = max(1, min(50, int(s.get('max_saved_videos', 10))))
    except (TypeError, ValueError):
        max_videos = 10
    videos = list(reversed(_read_videos()))
    meetings = [{'name': str(m.get('name', '')), 'phrase': str(m.get('phrase', '')), 'url': str(m.get('url', ''))} for m in s.get('meetings', []) if isinstance(m, dict)]
    return {'ok': True, 'max_videos': max_videos, 'videos': videos[:60], 'videos_total': len(videos), 'meetings': meetings, 'keep': sorted(_read_keep()),
            'launch': dict(sorted(_rules().items())), 'remote': _remote(), 'update': _update(),
            'ip_lookup': bool(s.get('allow_ip_lookup', True)), 'scenarios': _scenarios()}


def set_max_videos(n) -> dict:
    try:
        n = int(float(n))
    except (TypeError, ValueError):
        return _bad('bad_value')
    if not 1 <= n <= 50:
        return _bad('bad_value')
    return {'ok': True} if settings_io.update({'max_saved_videos': n}) else _bad('write_failed')


def _meta(urls) -> dict:
    from . import video_meta
    return video_meta.lookup([u for u in urls if isinstance(u, str)] if isinstance(urls, list) else [])


def set_auto_update(on) -> dict:
    return {'ok': True} if settings_io.update({'auto_update_enabled': bool(on)}) else _bad('write_failed')


def run(data: dict) -> dict:
    """Entry of the `tools` bridge command: op `state` | `max_videos` {n} | `video_del` {ts, url} | `meeting_add` {phrase, url, name} | `meeting_del` {phrase} | `meeting_edit` {old, phrase, url, name} | `video_meta` {urls} | `keep_add` {title} | `keep_del` {title}
    | `launch_set` {app, mode} | `launch_del` {app} | `apps` | `remote_save` {token, chat_id} | `remote_off` | `auto_update` {on} | `ip_lookup` {on} | `scenario_save` {old, name, phrase, steps} | `scenario_del` {name} | `update_check` | `update_install`."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return get_state()
    simple = {'max_videos': lambda: set_max_videos(data.get('n')), 'video_del': lambda: delete_video(str(data.get('ts', '')), str(data.get('url', ''))),
              'meeting_add': lambda: add_meeting(data.get('phrase'), data.get('url'), data.get('name')), 'meeting_del': lambda: delete_meeting(data.get('phrase')),
              'meeting_edit': lambda: update_meeting(data.get('old'), data.get('phrase'), data.get('url'), data.get('name')), 'video_meta': lambda: _meta(data.get('urls')),
              'keep_add': lambda: keep_add(data.get('title')), 'keep_del': lambda: keep_del(data.get('title')),
              'launch_set': lambda: launch_set(data.get('app'), data.get('mode')), 'launch_del': lambda: launch_del(data.get('app')), 'apps': installed_apps,
              'remote_save': lambda: remote_save(data.get('token'), data.get('chat_id')), 'remote_off': remote_off,
              'auto_update': lambda: set_auto_update(data.get('on')), 'ip_lookup': lambda: set_ip_lookup(data.get('on')), 'scenario_save': lambda: scenario_save(data), 'scenario_del': lambda: scenario_del(data.get('name')), 'update_check': update_check, 'update_install': update_install}
    fn = simple.get(op)
    if fn is None:
        return _bad('bad_op')
    res = fn()
    if res.get('ok') and op not in ('apps', 'update_check', 'update_install', 'video_meta'):
        res = {**get_state(), **{k: v for k, v in res.items() if k not in ('ok',)}}     # every change returns the fresh state
    return res
