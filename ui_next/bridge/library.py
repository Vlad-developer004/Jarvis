"""Installed games for the Games screen: the same scan the voice command "запусти игру" uses (features.gaming.scanner).

The UI never sends a path or a name to launch: it sends the id of a game from the published list, and the
launch goes through the handler exactly like the voice flow does (game mode on, profile applied).
"""
from __future__ import annotations

import hashlib
import logging
import threading

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_games: dict[str, object] = {}      # id -> GameInfo of the last scan
_scanning = False
_icons: dict[str, str] = {}         # id -> data URI ('' = none), kept across rescans


def game_id(launcher: str, name: str) -> str:
    return hashlib.sha1(f'{launcher}|{name}'.encode('utf-8'), usedforsecurity=False).hexdigest()[:10]


def scan(force: bool = False) -> list[dict]:
    """Blocking scan (a few seconds: registry, Steam manifests). Returns the payload list, most recently played first."""
    from features.gaming.scanner import scan_all_games
    found = scan_all_games(force=force)
    by_id = {}
    for g in found:
        by_id.setdefault(game_id(g.launcher, g.name), g)
    with _lock:
        _games.clear()
        _games.update(by_id)
    from .gameicons import icon_uri
    for gid, g in by_id.items():
        if gid not in _icons:
            _icons[gid] = icon_uri(getattr(g, 'install_dir', ''))
    rows = [{'id': gid, 'name': g.name, 'launcher': g.launcher, 'last': int(g.last_played or 0), 'icon': _icons.get(gid, '')} for gid, g in by_id.items()]
    rows.sort(key=lambda r: (-r['last'], r['name'].lower()))
    return rows


def find(gid: str):
    with _lock:
        return _games.get(gid)


def scan_async(publish, force: bool = False) -> bool:
    """Scans in a thread and publishes the `library` topic. False when a scan is already running."""
    global _scanning
    with _lock:
        if _scanning:
            return False
        _scanning = True

    def _run():
        global _scanning
        try:
            publish('library', {'games': scan(force), 'scanning': False})
        except Exception:
            _log.exception('game scan failed')
            publish('library', {'games': [], 'scanning': False, 'error': True})
        finally:
            with _lock:
                _scanning = False

    threading.Thread(target=_run, name='ui-bridge-games', daemon=True).start()
    return True
