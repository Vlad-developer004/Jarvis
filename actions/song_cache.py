"""Local cache of already-recognized songs, stored as plain JSON
(get_data_path('song_cache.json')) — not a general music-library index.

Every time actions/song_id.py successfully identifies a song (via Shazam or
AudD), it stores the result here together with the fingerprint hashes of
that recording. Next time the same song is heard again, recognize_song()
checks this cache first and, on a confident match, returns instantly with
no network call at all.

Matching reuses the same constellation-hash voting approach as a real
audio-fingerprint match: a genuine repeat produces a sharp spike of votes at
one constant time offset, so a match also has to clearly outscore that
song's own average vote level (see min_peak_ratio) — not just win by raw
count — to rule out coincidental hash collisions.

Like every fingerprinting system in this family (Shazam included), this is
much more reliable on harmonically/rhythmically rich audio (real songs —
vocals, drums, chord changes) than on sustained pure tones or drones, whose
own periodicity can produce misleadingly high vote counts against unrelated
audio. min_votes is set on the conservative side for exactly this reason —
a missed cache hit just falls through to the network path in song_id.py, a
false one wouldn't.
"""
import json
import threading
from collections import defaultdict

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


def remember(result: dict, hashes: list[tuple[int, int]]) -> None:
    """result: the same dict recognize_song() returns on success (must have
    at least 'title'/'artist'). hashes: fingerprint_pcm() output for the
    clip that was just recognized."""
    if not hashes:
        return
    with _lock:
        data = _load()
        entry = dict(result)
        entry.pop('ok', None)
        entry.pop('source', None)
        entry['hashes'] = [[h, t] for h, t in hashes]
        data['songs'].append(entry)
        if len(data['songs']) > _MAX_SONGS:
            data['songs'] = data['songs'][-_MAX_SONGS:]
        _save(data)


def match(query_hashes: list[tuple[int, int]], min_votes: int = 20, min_peak_ratio: float = 3.0) -> dict | None:
    if not query_hashes:
        return None
    with _lock:
        data = _load()
    if not data['songs']:
        return None

    by_hash: dict[int, int] = dict(query_hashes)  # hash -> query time frame
    best_entry = None
    best_count = 0

    for entry in data['songs']:
        votes: dict[int, int] = defaultdict(int)
        for h, db_offset in entry.get('hashes', ()):
            q_offset = by_hash.get(h)
            if q_offset is not None:
                votes[db_offset - q_offset] += 1
        if not votes:
            continue
        top_delta_count = max(votes.values())
        if top_delta_count < min_votes:
            continue
        total = sum(votes.values())
        avg = total / len(votes)
        if avg > 0 and top_delta_count < avg * min_peak_ratio:
            continue
        if top_delta_count > best_count:
            best_count = top_delta_count
            best_entry = entry

    if best_entry is None:
        return None
    res = {k: v for k, v in best_entry.items() if k != 'hashes'}
    res['ok'] = True
    res['source'] = 'cache'
    return res


def song_count() -> int:
    with _lock:
        return len(_load()['songs'])
