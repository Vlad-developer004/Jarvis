"""Recognized songs for the Songs screen: the history kept by actions/song_cache.py (Shazam / AudD results).

Covers are small JPEG thumbnails inlined as data URIs (the cover files live in %TEMP% and may be gone: no cover is fine).
Links are resolved here, never taken from the UI: the UI sends a song id and a service name and the bridge opens the URL.
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
from urllib.parse import quote

_log = logging.getLogger(__name__)
_THUMB = 112
_LIST_MAX = 100
_covers: dict[str, str] = {}        # cover_path -> data URI ('' = none)
_last = None
_mtime = -1.0


def song_id(entry: dict) -> str:
    return hashlib.sha1(f"{entry.get('recognized_at', 0)}|{entry.get('title', '')}|{entry.get('artist', '')}".encode('utf-8'), usedforsecurity=False).hexdigest()[:10]


def _query(entry: dict) -> str:
    return ' '.join(x for x in (entry.get('title'), entry.get('artist')) if x)


def link(entry: dict, kind: str) -> str:
    """A browser-openable https URL for the service ('' when the song has none). Stored app-scheme links are turned into web ones."""
    q = quote(_query(entry))
    if kind == 'youtube':
        u = str(entry.get('youtube_url') or '')
        return u if u.startswith(('https://', 'http://')) else ''
    if kind == 'spotify':
        if not entry.get('spotify_url'):
            return ''
        u = str(entry['spotify_url'])
        return u if u.startswith('https://') else f'https://open.spotify.com/search/{q}'
    if kind == 'apple':
        if not entry.get('apple_music_url'):
            return ''
        u = str(entry['apple_music_url'])
        return u if u.startswith('https://') else f'https://music.apple.com/search?term={q}'
    return ''


def _cover_uri(path: str) -> str:
    if not path:
        return ''
    if path in _covers:
        return _covers[path]
    uri = ''
    try:
        if os.path.isfile(path):
            from PIL import Image
            img = Image.open(path).convert('RGB')
            img.thumbnail((_THUMB, _THUMB))
            out = io.BytesIO()
            img.save(out, 'JPEG', quality=82)
            uri = 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
    except Exception:
        _log.debug('cover thumbnail failed', exc_info=True)
    _covers[path] = uri
    return uri


def find(sid: str) -> dict | None:
    from actions import song_cache
    return next((e for e in song_cache.list_recent(300) if song_id(e) == sid), None)


def payload() -> dict:
    from actions import song_cache
    songs = song_cache.list_recent(_LIST_MAX)
    rows = [{
        'id': song_id(e), 'title': e.get('title') or '', 'artist': e.get('artist') or '', 'album': e.get('album') or '',
        'at': int(e.get('recognized_at') or 0), 'source': e.get('source') or '', 'cover': _cover_uri(e.get('cover_thumb') or '') or _cover_uri(e.get('cover_path') or ''),
        'links': [k for k in ('spotify', 'apple', 'youtube') if link(e, k)],
    } for e in songs]
    return {'songs': rows, 'total': song_cache.song_count()}


def publish_songs(publish, only_if_changed: bool = False) -> None:
    """Publishes the `songs` topic; with only_if_changed, only when the history file was rewritten."""
    global _last, _mtime
    try:
        from actions import song_cache
        try:
            mt = os.path.getmtime(song_cache._cache_path())
        except OSError:
            mt = 0.0
        if only_if_changed and mt == _mtime and _last is not None:
            return
        _mtime = mt
        data = payload()
    except Exception:
        _log.debug('songs read failed', exc_info=True)
        return
    if data != _last:
        _last = data
        publish('songs', data)
