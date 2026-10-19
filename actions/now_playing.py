"""What is playing on this PC and how to control it, through the Windows media sessions (System Media Transport Controls, Windows 10 1809+).

Any app that shows up in the Windows volume/media flyout has a session: VLC, Spotify, Windows Media Player, and browser tabs with a video (YouTube, a streaming site).
No keys, no accounts, nothing to configure. Needs the `winrt-Windows.Media.Control` packages; without them every call returns "nothing playing".

The WinRT calls run on one background thread with its own event loop, so callers on any thread (UI bridge, voice handler) just call the plain functions below.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from datetime import datetime, timezone
from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)

_STATUS = {0: 'closed', 1: 'opened', 2: 'changing', 3: 'stopped', 4: 'playing', 5: 'paused'}
_TIMEOUT = 4.0
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()
_manager = None
_available: bool | None = None

_APP_NAMES = (('brave', 'Brave'), ('chrome', 'Chrome'), ('msedge', 'Edge'), ('edge', 'Edge'), ('firefox', 'Firefox'), ('opera', 'Opera'), ('yandex', 'Яндекс Браузер'),
              ('vlc', 'VLC'), ('spotify', 'Spotify'), ('zunemusic', 'Медиаплеер'), ('zunevideo', 'Кино и ТВ'), ('mpc', 'MPC'), ('mpv', 'mpv'), ('potplayer', 'PotPlayer'),
              ('telegram', 'Telegram'), ('discord', 'Discord'), ('itunes', 'iTunes'), ('yandexmusic', 'Яндекс Музыка'))


def available() -> bool:
    """True when the WinRT media-control bindings can be imported on this machine."""
    global _available
    if _available is None:
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager  # noqa: F401
            _available = True
        except Exception:
            _available = False
    return _available


def app_label(app_id: str) -> str:
    """A readable app name from the session's AppUserModelId ("Brave._crx_abc" -> "Brave")."""
    low = (app_id or '').lower()
    for key, name in _APP_NAMES:
        if key in low:
            return name
    base = re.split(r'[!_.]', app_id or '', maxsplit=1)[0]
    return base or 'Приложение'


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def _seconds(td) -> float:
    try:
        return float(td.total_seconds())
    except Exception:
        return 0.0


def _position(timeline, status: str, rate: float) -> float:
    """The position Windows reports is the one at `last_updated_time`; while playing it moves on from there."""
    pos = _seconds(timeline.position) - _seconds(timeline.start_time)
    if status == 'playing':
        try:
            upd = timeline.last_updated_time
            if upd is not None and upd.year > 2000:
                pos += max(0.0, (datetime.now(timezone.utc) - upd).total_seconds()) * (rate or 1.0)
        except Exception:
            _swallow()
    return pos


async def _describe(session, index_of: dict, current_id: str) -> dict:
    app = session.source_app_user_model_id or ''
    n = index_of.get(app, 0)
    index_of[app] = n + 1
    pb = session.get_playback_info()
    status = _STATUS.get(int(pb.playback_status), 'unknown')
    title = artist = album = ''
    try:
        props = await session.try_get_media_properties_async()
        title, artist, album = props.title or '', props.artist or '', props.album_title or ''
    except Exception:
        _log.debug('media properties failed', exc_info=True)
    tl = session.get_timeline_properties()
    rate = 1.0
    try:
        rate = float(pb.playback_rate) if pb.playback_rate else 1.0
    except Exception:
        _swallow()
    dur = max(0.0, _seconds(tl.end_time) - _seconds(tl.start_time))
    pos = min(dur, max(0.0, _position(tl, status, rate))) if dur else 0.0
    c = pb.controls
    return {'id': f'{app}#{n}', 'app': app, 'app_name': app_label(app), 'title': title, 'artist': artist, 'album': album, 'status': status, 'pos': round(pos, 1), 'dur': round(dur, 1),
            'current': app == current_id and n == 0,
            'can': {'play': bool(c.is_play_enabled), 'pause': bool(c.is_pause_enabled), 'next': bool(c.is_next_enabled), 'prev': bool(c.is_previous_enabled), 'seek': bool(c.is_playback_position_enabled)}}


def pick(sessions: list[dict], sid: str = '') -> dict | None:
    """The session a command is meant for: the one asked for, else the one playing right now, else the one Windows calls current, else the first."""
    if not sessions:
        return None
    if sid:
        return next((s for s in sessions if s['id'] == sid), None)
    return next((s for s in sessions if s['status'] == 'playing'), None) or next((s for s in sessions if s['current']), None) or sessions[0]


# ---- the event loop thread ----
def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None or not _loop.is_running():
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, name='now-playing-loop', daemon=True).start()
            _loop = loop
        return _loop


def _run(coro, default=None, timeout: float = _TIMEOUT):
    try:
        return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result(timeout)
    except Exception:
        _log.debug('now playing call failed', exc_info=True)
        return default


async def _mgr():
    global _manager
    if _manager is None:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        _manager = await M.request_async()
    return _manager


async def _snapshot() -> list[dict]:
    mgr = await _mgr()
    cur = mgr.get_current_session()
    cur_id = cur.source_app_user_model_id if cur else ''
    index_of: dict = {}
    return [await _describe(s, index_of, cur_id) for s in mgr.get_sessions()]


def snapshot() -> list[dict]:
    """Every media session right now (playing and paused), newest state; [] when nothing is open or the bindings are missing."""
    if not available():
        return []
    return _run(_snapshot(), []) or []


def current() -> dict | None:
    return pick(snapshot())


async def _session_by_id(sid: str):
    mgr = await _mgr()
    index_of: dict = {}
    sessions = list(mgr.get_sessions())
    infos = []
    for s in sessions:
        app = s.source_app_user_model_id or ''
        n = index_of.get(app, 0)
        index_of[app] = n + 1
        infos.append((f'{app}#{n}', s))
    return infos


async def _control(action: str, sid: str, arg: float) -> dict:
    infos = await _session_by_id(sid or '')
    snap = await _snapshot()
    target = pick(snap, sid)
    if target is None:
        return {'ok': False, 'error': 'nothing_playing'}
    session = next(s for i, s in infos if i == target['id'])
    ok = False
    if action == 'toggle':
        ok = await session.try_toggle_play_pause_async()
    elif action == 'play':
        ok = await session.try_play_async()
    elif action == 'pause':
        ok = await session.try_pause_async()
    elif action == 'stop':
        ok = await session.try_stop_async()
    elif action == 'next':
        ok = await session.try_skip_next_async()
    elif action == 'prev':
        ok = await session.try_skip_previous_async()
    elif action in ('seek_to', 'seek_by'):
        if not target['can']['seek'] or not target['dur']:
            return {'ok': False, 'error': 'cannot_seek', 'session': target}
        goal = arg if action == 'seek_to' else target['pos'] + arg
        goal = max(0.0, min(target['dur'] - 1.0, goal))
        ok = await session.try_change_playback_position_async(int(goal * 10_000_000))
        target = {**target, 'pos': goal}
    else:
        return {'ok': False, 'error': 'bad_action'}
    return {'ok': bool(ok), 'session': target} if ok else {'ok': False, 'error': 'refused', 'session': target}


ACTIONS = ('toggle', 'play', 'pause', 'stop', 'next', 'prev', 'seek_to', 'seek_by')


def control(action: str, sid: str = '', arg: float = 0.0) -> dict:
    """Sends `action` to a session (see ACTIONS; `arg` is seconds for seek_to/seek_by). The answer carries the session it went to."""
    if action not in ACTIONS:
        return {'ok': False, 'error': 'bad_action'}
    if not available():
        return {'ok': False, 'error': 'unavailable'}
    return _run(_control(action, sid, float(arg)), {'ok': False, 'error': 'failed'})
