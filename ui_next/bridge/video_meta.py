"""Titles, authors, thumbnails and lengths for the saved YouTube videos (Settings > Tools), the same details the old video manager showed.

The saved list only holds links. The details come from YouTube's public oEmbed endpoint and the watch page (length only), fetched in the background
and cached in memory: `lookup` answers at once with what is known and starts the rest, the screen asks again until nothing is pending. Only
ids matched by _ID_RE are ever requested, so the UI cannot make the bridge fetch an arbitrary address.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_log = logging.getLogger(__name__)
_ID_RE = re.compile(r'^https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])')
_UA = {'User-Agent': 'Mozilla/5.0'}
_RETRY_AFTER = 600.0
_THUMB = (160, 90)
_lock = threading.Lock()
_cache: dict[str, dict] = {}        # video id -> {title, author, thumb, duration, at}
_pending: set[str] = set()
_pool: ThreadPoolExecutor | None = None


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


def _fetch(vid: str) -> None:
    info = {'title': '', 'author': '', 'thumb': '', 'duration': '', 'at': time.time()}
    try:
        req = urllib.request.Request(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json', headers=_UA)
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
        info['title'], info['author'] = str(data.get('title', ''))[:200], str(data.get('author_name', ''))[:100]
        info['thumb'] = _thumb(vid)
        info['duration'] = _duration(vid)
    except Exception:
        _log.debug('video details failed for %s', vid, exc_info=True)
    with _lock:
        _cache[vid] = info
        _pending.discard(vid)


def lookup(urls) -> dict:
    """{'items': {url: {title, author, thumb, duration}}, 'pending': n}: what is known now; the rest is being fetched."""
    global _pool
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
