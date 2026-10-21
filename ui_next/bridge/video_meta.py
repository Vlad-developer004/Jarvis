"""Titles, authors, thumbnails and lengths for the saved YouTube videos (Settings > Tools), the same details the old video manager showed.

The saved list only holds links. The details come from YouTube's public oEmbed endpoint, the thumbnail server and the watch page (length only), fetched
in the background: the three requests of a video run side by side and each result is stored as soon as it arrives. The details are kept in memory and in
a small file (video_meta.json), and `warm` loads them when the bridge starts, so the screen opens with titles and pictures instead of waiting for the
network. `lookup` answers at once with what is known and starts the rest, the screen asks again until nothing is pending. Only ids matched by _ID_RE
are ever requested, so the UI cannot make the bridge fetch an arbitrary address.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_log = logging.getLogger(__name__)
_ID_RE = re.compile(r'^https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])')
_UA = {'User-Agent': 'Mozilla/5.0'}
_RETRY_AFTER = 600.0
_DISK_MAX = 200
_THUMB = (160, 90)
_lock = threading.Lock()
_cache: dict[str, dict] = {}        # video id -> {title, author, thumb, duration, at}
_pending: set[str] = set()
_pool: ThreadPoolExecutor | None = None
_loaded = False


def video_id(url: str) -> str | None:
    m = _ID_RE.search(str(url or ''))
    return m.group(1) if m else None


def _duration(vid: str) -> str:
    """Length as m:ss or h:mm:ss, read from the start of the watch page (the field sits early in it)."""
    try:
        req = urllib.request.Request(f'https://www.youtube.com/watch?v={vid}', headers={**_UA, 'Accept-Language': 'en'})
        buf = b''
        with urllib.request.urlopen(req, timeout=8) as r:
            while len(buf) < 800_000:
                chunk = r.read(32_768)
                if not chunk:
                    break
                buf += chunk
                m = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', buf.decode('utf-8', errors='ignore'))
                if m:
                    h, rem = divmod(int(m.group(1)), 3600)
                    mi, s = divmod(rem, 60)
                    return f'{h}:{mi:02d}:{s:02d}' if h else f'{mi}:{s:02d}'
    except Exception:
        _log.debug('duration lookup failed for %s', vid, exc_info=True)
    return ''


def _thumb(vid: str) -> str:
    try:
        from PIL import Image
        req = urllib.request.Request(f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg', headers=_UA)
        with urllib.request.urlopen(req, timeout=6) as r:
            img = Image.open(io.BytesIO(r.read())).convert('RGB').resize(_THUMB)
        out = io.BytesIO()
        img.save(out, 'JPEG', quality=70)
        return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
    except Exception:
        return ''


def _oembed(vid: str) -> dict:
    req = urllib.request.Request(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json', headers=_UA)
    with urllib.request.urlopen(req, timeout=6) as r:
        data = json.loads(r.read())
    return {'title': str(data.get('title', ''))[:200], 'author': str(data.get('author_name', ''))[:100]}


def _disk_path() -> str:
    from config_pack.config import get_data_path
    return get_data_path('video_meta.json')


def _load_disk() -> None:
    """Fills the memory cache from the file once; what was found earlier is shown at once and is not asked for again."""
    global _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
    try:
        with open(_disk_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _lock:
            for vid, c in data.items():
                if isinstance(c, dict) and c.get('title') and re.fullmatch(r'[A-Za-z0-9_-]{11}', vid) and vid not in _cache:
                    _cache[vid] = {'title': str(c['title'])[:200], 'author': str(c.get('author', ''))[:100], 'thumb': str(c.get('thumb', '')),
                                   'duration': str(c.get('duration', ''))[:12], 'at': time.time()}
    except (OSError, ValueError, AttributeError):
        pass


def _save_disk() -> None:
    with _lock:
        keep = {v: {k: c[k] for k in ('title', 'author', 'thumb', 'duration')} for v, c in _cache.items() if c['title']}
    if len(keep) > _DISK_MAX:
        keep = dict(list(keep.items())[-_DISK_MAX:])
    try:
        path = _disk_path()
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(keep, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        _log.debug('video details not saved', exc_info=True)


def _fetch(vid: str) -> None:
    info = {'title': '', 'author': '', 'thumb': '', 'duration': '', 'at': time.time()}
    with _lock:
        _cache[vid] = info          # lookups see what has arrived so far

    def part(fn, apply):
        try:
            got = fn(vid)
            with _lock:
                apply(got)
        except Exception:
            _log.debug('video detail failed for %s', vid, exc_info=True)
    try:
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix='ui-bridge-video-part') as ex:
            ex.submit(part, _oembed, lambda d: info.update(d))
            ex.submit(part, _thumb, lambda t: info.update(thumb=t))
            ex.submit(part, _duration, lambda t: info.update(duration=t))
    finally:
        with _lock:
            _pending.discard(vid)
        if info['title']:
            _save_disk()


def warm() -> None:
    """Loads the saved details and fetches what is missing for the saved videos, so the Videos screen is ready when it is opened."""
    try:
        from . import tools
        lookup([v['url'] for v in tools.get_state().get('videos', [])])
    except Exception:
        _log.debug('video details warm-up failed', exc_info=True)


def lookup(urls) -> dict:
    """{'items': {url: {title, author, thumb, duration}}, 'pending': n}: what is known now; the rest is being fetched."""
    global _pool
    _load_disk()
    items, todo = {}, []
    now = time.time()
    with _lock:
        for url in list(urls)[:60]:
            vid = video_id(url)
            if not vid:
                continue
            c = _cache.get(vid)
            if c and (c['title'] or now - c['at'] < _RETRY_AFTER):
                items[str(url)] = {k: c[k] for k in ('title', 'author', 'thumb', 'duration')}
            elif vid not in _pending:
                _pending.add(vid)
                todo.append(vid)
        pending = len(_pending)
        if todo and _pool is None:
            _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='ui-bridge-video')
    for vid in todo:
        _pool.submit(_fetch, vid)
    return {'ok': True, 'items': items, 'pending': pending}
