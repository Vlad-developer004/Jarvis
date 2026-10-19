"""Setup flows of the extensions that need more than an installed flag: the same steps the old extensions dialog ran.

    feature_guard_cam       Telegram chat id (secrets.env TELEGRAM_CHAT_ID)
    feature_mail_client     mail account: address, app password, IMAP/SMTP hosts
    feature_calendar_ics    calendar sources (links or .ics paths)
    game_ets2               telemetry plugin (DLL) install + optional AI narrator
    game_planetbase         telemetry mod install

`get_state` returns what the form needs (never a secret: only "a password is saved"), `save` applies the form, `act` runs a
one-off action. All of them reuse the old dialog's helpers, so both UIs read and write the same files.
"""
from __future__ import annotations

import logging
import os
import threading

from .extensions import set_installed
from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)

KINDS = {
    'feature_guard_cam': 'telegram',
    'feature_mail_client': 'mail',
    'feature_calendar_ics': 'calendar',
    'game_ets2': 'ets2',
    'game_planetbase': 'planetbase',
}


class _Common:
    """The settings file, the secrets file and the module switches, the way the extension setup forms use them."""

    @staticmethod
    def _load_settings() -> dict:
        from core import settings_io
        return settings_io.read()

    @staticmethod
    def _save_settings(s: dict) -> None:
        from core import settings_io
        settings_io.update(s)

    @staticmethod
    def _save_env_key(key: str, value: str) -> None:
        from core.secrets_store import set_secret
        set_secret(key, value)

    @staticmethod
    def _set_feature_module_flag(module_key: str, enabled: bool) -> None:
        from core import settings_io
        mods = settings_io.read().get('feature_modules', {})
        mods = dict(mods) if isinstance(mods, dict) else {}
        mods[module_key] = bool(enabled)
        settings_io.update({'feature_modules': mods})
        try:
            from core.system import refresh_module_flags
            refresh_module_flags()
        except Exception:
            _swallow()


_COMMON = _Common()


def _common() -> _Common:
    return _COMMON


def _calendar_sources() -> list[dict]:
    s = _common()._load_settings().get('calendar_sources')
    return [x for x in s if isinstance(x, dict)] if isinstance(s, list) else []


def _ets2() -> dict:
    out = {'dll': False, 'path': False, 'ai_key': False, 'ai_on': False}
    try:
        from actions.ets2_telemetry_installer import find_ets2_path, is_telemetry_installed
        out['dll'] = bool(is_telemetry_installed())
        out['path'] = bool(find_ets2_path())
    except Exception:
        _log.debug('ets2 state failed', exc_info=True)
    try:
        from features.ets2.llm import has_api_key
        out['ai_key'] = bool(has_api_key())
        out['ai_on'] = bool(_common()._load_settings().get('ets2_llm_enabled', True))
    except Exception:
        _swallow()
    return out


def _planetbase() -> dict:
    out = {'found': False, 'mod': False}
    try:
        from features.planetbase.installer import find_planetbase_path
        p = find_planetbase_path()
        if p:
            managed = p / 'Planetbase_Data' / 'Managed'
            out['found'] = True
            out['mod'] = (managed / 'Assembly-CSharp.bak').exists() and (managed / 'PlanetbaseTelemetry.dll').exists()
    except Exception:
        _log.debug('planetbase state failed', exc_info=True)
    return out


def get_state(ext_id: str) -> dict | None:
    kind = KINDS.get(ext_id)
    if kind is None:
        return None
    from .extensions import _manager
    st = {'kind': kind, 'installed': _manager().is_installed(ext_id)}
    if kind == 'telegram':
        st['chat_id_set'] = bool(os.environ.get('TELEGRAM_CHAT_ID'))
    elif kind == 'mail':
        acct = _common()._load_settings().get('mail_account')
        acct = acct if isinstance(acct, dict) else {}
        try:
            from actions.mail_client import get_resolved_mail_config
            cfg = get_resolved_mail_config()
        except Exception:
            cfg = None
        st.update({'email': str(acct.get('email') or ''), 'imap': str(acct.get('imap_host') or ''), 'smtp': str(acct.get('smtp_host') or ''),
                   'has_password': bool(cfg and cfg.get('password'))})
    elif kind == 'calendar':
        st['sources'] = [str(s.get('url') or s.get('path') or '') for s in _calendar_sources()]
    elif kind == 'ets2':
        st.update(_ets2())
    elif kind == 'planetbase':
        st.update(_planetbase())
    return st


def _save_telegram(data: dict) -> dict:
    cid = str(data.get('chat_id') or '').strip()
    if not cid and os.environ.get('TELEGRAM_CHAT_ID'):
        return {'ok': True}                              # keep the saved one
    if not cid.lstrip('-').isdigit():
        return {'ok': False, 'error': 'bad_chat_id'}
    _common()._save_env_key('TELEGRAM_CHAT_ID', cid)
    os.environ['TELEGRAM_CHAT_ID'] = cid
    return {'ok': True}


def _save_mail(data: dict) -> dict:
    from actions.mail_client import get_resolved_mail_config, save_mail_account
    email = str(data.get('email') or '').strip()
    password = str(data.get('password') or '').strip()
    imap, smtp = str(data.get('imap') or '').strip()[:120], str(data.get('smtp') or '').strip()[:120]
    if not email or '@' not in email or len(email) > 200:
        return {'ok': False, 'error': 'bad_email'}
    if not password:
        cfg = get_resolved_mail_config()
        if not (cfg and cfg.get('password')):
            return {'ok': False, 'error': 'no_password'}
        password = ''                                    # keep the saved one; save_mail_account leaves it alone when empty
    save_mail_account(email, password, imap, smtp, 993, 587)
    _common()._set_feature_module_flag('inbox_digest', True)
    return {'ok': True}


def _save_calendar(data: dict) -> dict:
    raw = data.get('sources')
    if not isinstance(raw, list) or len(raw) > 30:
        return {'ok': False, 'error': 'bad_sources'}
    sources = []
    for item in raw:
        v = str(item or '').strip()
        if not v or len(v) > 500:
            continue
        sources.append({'url': v} if v.lower().startswith(('http://', 'https://', 'webcal://')) else {'path': v})
    c = _common()
    s = c._load_settings()
    s['calendar_sources'] = sources
    c._save_settings(s)
    c._set_feature_module_flag('calendar_ics', True)
    return {'ok': True}


_SAVERS = {'telegram': _save_telegram, 'mail': _save_mail, 'calendar': _save_calendar}


def save(ext_id: str, data: dict) -> dict:
    """Applies the form and marks the extension installed."""
    kind = KINDS.get(ext_id)
    saver = _SAVERS.get(kind)
    if saver is None:
        return {'ok': False, 'error': 'no_form'}
    res = saver(data)
    if res.get('ok'):
        set_installed(ext_id, True)
    return res


def _background(fn, name: str) -> None:
    def run():
        try:
            fn()
        except Exception:
            _log.exception('%s failed', name)
    threading.Thread(target=run, name='ui-bridge-' + name, daemon=True).start()


def act(ext_id: str, data: dict) -> dict:
    kind, name = KINDS.get(ext_id), str(data.get('action') or '')
    if kind is None:
        return {'ok': False, 'error': 'unknown_extension'}
    if name == 'uninstall':
        return {'ok': set_installed(ext_id, False)}
    if kind == 'mail' and name == 'app_password_page':
        import webbrowser
        from actions.mail_client import app_password_url_for_email
        return {'ok': bool(webbrowser.open(app_password_url_for_email(str(data.get('email') or ''))))}
    if kind == 'ets2':
        if name == 'ai':
            c = _common()
            s = c._load_settings()
            s['ets2_llm_enabled'] = bool(data.get('on'))
            c._save_settings(s)
            return {'ok': True}
        if name == 'install':
            set_installed(ext_id, True)
            from actions.ets2_telemetry_installer import find_ets2_path, install, validate_ets2_path
            path = find_ets2_path()
            if not (path and validate_ets2_path(path)):
                from actions.ets2_telemetry_installer import run_installer
                run_installer()                               # asks for the game folder in the native dialog, then installs
                return {'ok': True, 'needs_path': True}
            _background(lambda: install(path), 'ets2-plugin')
            return {'ok': True, 'started': True}
    if kind == 'planetbase' and name == 'install':
        set_installed(ext_id, True)
        from features.planetbase.installer import ensure_installed, find_planetbase_path
        if not find_planetbase_path():
            return {'ok': True, 'not_found': True}
        _background(ensure_installed, 'planetbase-mod')
        return {'ok': True, 'started': True}
    return {'ok': False, 'error': 'bad_action'}
