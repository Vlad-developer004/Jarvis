"""Extension list for the Extensions screen (core.extensions.ExtensionManager) and the install/uninstall that needs no setup."""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# Installing these only flips the installed flag. The rest has a setup step (see _cmd_extension in __init__).
SIMPLE = frozenset({'game_hogwarts', 'game_fs22', 'feature_network_profiles', 'feature_system_health', 'feature_photoshop_voice', 'feature_figma_voice'})
_last: list[dict] | None = None
_mtime = 0.0


def _manager():
    from core.extensions import ExtensionManager
    return ExtensionManager()


def extensions_payload() -> list[dict]:
    from .ext_setup import KINDS
    mgr = _manager()
    out = []
    for e in mgr.list_all():
        eid = e['id']
        out.append({
            'id': eid, 'name': e.get('name', eid), 'desc': e.get('description', ''), 'type': e.get('type', ''),
            'category': e.get('category', ''), 'setup': KINDS.get(eid, ''), 'installed': mgr.is_installed(eid), 'bundled': bool(e.get('bundled')),
            'commands': len(e.get('commands') or []), 'simple': eid in SIMPLE,
        })
    return out


def _installed_file_changed() -> bool:
    """The old dialog (or another process) rewrote the installed list: reload the manager once."""
    global _mtime
    import os
    from core.extensions import _INSTALLED_PATH
    try:
        mt = os.path.getmtime(_INSTALLED_PATH)
    except OSError:
        return False
    if mt == _mtime:
        return False
    first, _mtime = _mtime == 0.0, mt
    return not first


def publish_extensions(publish, only_if_changed: bool = False) -> None:
    global _last
    try:
        if only_if_changed and _installed_file_changed():
            _manager().reload()
        payload = extensions_payload()
    except Exception:
        _log.debug('extension list failed', exc_info=True)
        return
    if only_if_changed and payload == _last:
        return
    _last = payload
    publish('extensions', payload)


def set_installed(ext_id: str, on: bool) -> bool:
    mgr = _manager()
    return mgr.install(ext_id) if on else mgr.uninstall(ext_id)
