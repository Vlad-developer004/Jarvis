"""Local history of songs recognized via actions/song_id.py, stored as plain
JSON (get_data_path('song_cache.json')).

Every successful recognition (Shazam or AudD) is appended here for the
"Recognized songs" HUD panel — title/artist/links/cover/timestamp. This is a
display log, not a matching cache: it used to also try to answer "have I
heard this exact clip before" via audio-fingerprint voting to skip the
network call on a repeat, but that produced confusing false positives (a
new, unrelated recording occasionally out-scored the vote threshold against
an old entry and got silently misreported as that old song) — recognize_song()
now always asks Shazam/AudD, and this file is purely a record of the results
for the user to browse, per the user's actual request for it.
"""
import json
import threading
import time

from core.logging_setup import get_logger

_log = get_logger('song_cache')
_lock = threading.Lock()
_MAX_SONGS = 300  # oldest entries are dropped past this so the JSON file stays bounded


def _cache_path() -> str:
    from config_pack.config import get_data_path
    return get_data_path('song_cache.json')


def _load() -> dict:
    try:
        with open(_cache_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get('songs'), list):
                return data
    except Exception:
        pass
    return {'songs': []}


def _save(data: dict) -> None:
    try:
        with open(_cache_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        _log.error('failed saving song cache: %s', e, exc_info=True)


def remember(result: dict) -> None:
    """result: the same dict recognize_song() returns on success (must have
    at least 'title'/'artist')."""
    with _lock:
        data = _load()
        entry = dict(result)
        entry.pop('ok', None)
        entry['recognized_at'] = time.time()
        data['songs'].append(entry)
        if len(data['songs']) > _MAX_SONGS:
            data['songs'] = data['songs'][-_MAX_SONGS:]
        _save(data)


def list_recent(limit: int = 100) -> list[dict]:
    """Newest first, for the "Recognized songs" HUD panel."""
    with _lock:
        songs = list(_load()['songs'])
    songs.sort(key=lambda e: e.get('recognized_at', 0), reverse=True)
    return songs[:limit]


def clear() -> None:
    with _lock:
        _save({'songs': []})


def song_count() -> int:
    with _lock:
        return len(_load()['songs'])
