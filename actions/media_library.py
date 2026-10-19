"""The user's own films and series on disk: folders to look in, season/episode read from file names, "continue the series" and the last watched episode.

Nothing is downloaded or uploaded; files are opened in the program Windows has set for them. Stored in jarvis_settings.json under "cinema":
{"library": {"folders": [path], "progress": {series key: {"path", "at"}}, "last": series key}}.
"""
from __future__ import annotations

import difflib
import os
import re
import threading
import time

from core import settings_io

VIDEO_EXT = frozenset({'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.webm', '.ts', '.mpg', '.mpeg', '.flv'})
MAX_FOLDERS = 12
MAX_FILES = 20000
MAX_DEPTH = 6
_CACHE_TTL = 120.0

_SXE = re.compile(r'(?<![a-z0-9])s(\d{1,2})[ ._-]?e(\d{1,3})(?:[ ._-]?e?(\d{1,3}))?(?![0-9])', re.I)
_NXN = re.compile(r'(?<![a-z0-9])(\d{1,2})x(\d{2,3})(?![0-9a-z])', re.I)
_WORDS = re.compile(r'(?:сезон|season)[ ._-]*(\d{1,2}).{0,12}?(?:серия|серія|эпизод|епізод|episode|ep)[ ._-]*(\d{1,3})', re.I)
_EP_ONLY = re.compile(r'(?:серия|серія|эпизод|епізод|episode|ep)[ ._-]*(\d{1,3})', re.I)
_SEASON_DIR = re.compile(r'^(?:сезон|season|s)[ ._-]*(\d{1,2})$', re.I)
_JUNK = re.compile(r'\b(?:1080p|720p|480p|2160p|4k|uhd|hdr|x264|x265|h264|h265|hevc|bluray|bdrip|brrip|web-?dl|webrip|hdtv|dvdrip|avc|aac|ac3|dts|rus|ukr|eng|multi)\b.*$', re.I)
_YEAR = re.compile(r'[\s._(\[-]+((?:19|20)\d{2})[\s._)\]-]*$')
_SEP = re.compile(r'[._]+')

_lock = threading.Lock()
_cache: dict = {'folders': None, 'at': 0.0, 'items': []}


def _clean_title(raw: str) -> str:
    s = _SEP.sub(' ', raw)
    s = _JUNK.sub('', s)
    s = re.sub(r'[\[(].*?[\])]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip(' -–—,.')


def key_of(title: str) -> str:
    """"Ивановы-Ивановы" and "ивановы ивановы" are the same series."""
    return re.sub(r'[^0-9a-zа-яіїєґ]+', '', str(title or '').lower().replace('ё', 'е'))


def parse_name(path: str) -> dict:
    """{'title', 'season', 'episode', 'year'} from a file path; a file without an episode mark is a movie (season/episode None).
    A season folder ("Season 2") and the series folder above it fill in what the file name lacks."""
    base = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path))
    grand = os.path.basename(os.path.dirname(os.path.dirname(path)))
    season = episode = None
    title = ''
    for rx in (_SXE, _NXN, _WORDS):
        m = rx.search(base)
        if m:
            season, episode = int(m.group(1)), int(m.group(2))
            title = _clean_title(base[:m.start()])
            break
    if episode is None:
        m = _EP_ONLY.search(base)
        if m:
            episode = int(m.group(1))
            title = _clean_title(base[:m.start()])
    sd = _SEASON_DIR.match(parent.strip())
    if sd:
        if season is None and episode is not None:
            season = int(sd.group(1))
        if not title:
            title = _clean_title(grand)
    elif episode is not None and not title:
        title = _clean_title(parent)
    if episode is not None and season is None:
        season = 1
    year = None
    if episode is None:
        base_t = _SEP.sub(' ', base)
        ym = _YEAR.search(_JUNK.sub('', base_t).rstrip()) or _YEAR.search(re.sub(r'[\[(].*', '', base_t).rstrip())
        year = int(ym.group(1)) if ym else None
        title = _clean_title(re.sub(r'[\s(\[-]*(?:19|20)\d{2}\b.*$', '', base_t) if year else base_t)
    return {'title': title or _clean_title(base), 'season': season, 'episode': episode, 'year': year}


def _cfg() -> dict:
    raw = settings_io.read().get('cinema', {})
    lib = raw.get('library', {}) if isinstance(raw, dict) else {}
    lib = lib if isinstance(lib, dict) else {}
    folders = [str(f) for f in lib.get('folders', []) if isinstance(f, str) and f.strip()] if isinstance(lib.get('folders'), list) else []
    progress = lib.get('progress') if isinstance(lib.get('progress'), dict) else {}
    last = lib.get('last') if isinstance(lib.get('last'), str) else ''
    return {'folders': folders, 'progress': progress, 'last': last}


def _save(cfg: dict) -> bool:
    cur = settings_io.read().get('cinema', {})
    cur = dict(cur) if isinstance(cur, dict) else {}
    cur['library'] = {'folders': cfg['folders'], 'progress': cfg['progress'], 'last': cfg['last']}
    return settings_io.update({'cinema': cur})


def folders() -> list[str]:
    return _cfg()['folders']


def add_folder(path: str) -> dict:
    p = os.path.normpath(str(path or '').strip().strip('"'))
    if not p or not os.path.isdir(p):
        return {'ok': False, 'error': 'not_a_folder'}
    cfg = _cfg()
    if any(os.path.normcase(p) == os.path.normcase(f) for f in cfg['folders']):
        return {'ok': False, 'error': 'exists'}
    if len(cfg['folders']) >= MAX_FOLDERS:
        return {'ok': False, 'error': 'too_many'}
    cfg['folders'].append(p)
    _drop_cache()
    return {'ok': True} if _save(cfg) else {'ok': False, 'error': 'write_failed'}


def remove_folder(path: str) -> dict:
    cfg = _cfg()
    left = [f for f in cfg['folders'] if os.path.normcase(f) != os.path.normcase(str(path or ''))]
    if len(left) == len(cfg['folders']):
        return {'ok': False, 'error': 'not_found'}
    cfg['folders'] = left
    _drop_cache()
    return {'ok': True} if _save(cfg) else {'ok': False, 'error': 'write_failed'}


def _drop_cache() -> None:
    with _lock:
        _cache.update(folders=None, at=0.0, items=[])


def scan(folder_list: list[str] | None = None, force: bool = False) -> list[dict]:
    """Every video file in the folders: [{'path', 'title', 'season', 'episode', 'year', 'key', 'size'}], cached for two minutes."""
    fl = list(folder_list if folder_list is not None else folders())
    with _lock:
        if not force and _cache['folders'] == fl and time.time() - _cache['at'] < _CACHE_TTL:
            return list(_cache['items'])
    items: list[dict] = []
    for root in fl:
        base_depth = root.rstrip('\\/').count(os.sep)
        for dirpath, dirs, files in os.walk(root):
            if dirpath.count(os.sep) - base_depth >= MAX_DEPTH:
                dirs[:] = []
            for name in files:
                if os.path.splitext(name)[1].lower() not in VIDEO_EXT:
                    continue
                full = os.path.join(dirpath, name)
                info = parse_name(full)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                items.append({'path': full, **info, 'key': key_of(info['title']), 'size': size})
                if len(items) >= MAX_FILES:
                    break
            if len(items) >= MAX_FILES:
                break
    with _lock:
        _cache.update(folders=fl, at=time.time(), items=items)
    return list(items)


def library(items: list[dict] | None = None) -> dict:
    """{'series': [{key, title, episodes, seasons, last_path, ...}], 'movies': [{key, title, year, path}]}, sorted by title."""
    items = scan() if items is None else items
    cfg = _cfg()
    series: dict[str, dict] = {}
    movies: list[dict] = []
    for it in items:
        if it['episode'] is None:
            movies.append({'key': it['key'], 'title': it['title'], 'year': it['year'], 'path': it['path']})
            continue
        s = series.setdefault(it['key'], {'key': it['key'], 'title': it['title'], 'episodes': 0, 'seasons': set()})
        s['episodes'] += 1
        s['seasons'].add(it['season'])
    out = []
    for k, s in series.items():
        prog = cfg['progress'].get(k) or {}
        out.append({'key': k, 'title': s['title'], 'episodes': s['episodes'], 'seasons': len(s['seasons']), 'last': _label_for(prog.get('path'), items), 'at': prog.get('at', 0)})
    out.sort(key=lambda x: x['title'].lower())
    movies.sort(key=lambda x: x['title'].lower())
    return {'series': out, 'movies': movies}


def _label_for(path, items) -> str:
    it = next((i for i in items if i['path'] == path), None)
    return f"{it['season']}x{it['episode']:02d}" if it and it['episode'] is not None else ''


def _episodes(key: str, items: list[dict]) -> list[dict]:
    return sorted((i for i in items if i['key'] == key and i['episode'] is not None), key=lambda i: (i['season'] or 0, i['episode'] or 0, i['path']))


def find(query: str, items: list[dict] | None = None) -> str:
    """The series or movie key best matching a spoken title, '' when nothing fits well enough."""
    items = scan() if items is None else items
    q = key_of(query)
    if len(q) < 2:
        return ''
    keys = {i['key'] for i in items if i['key']}
    if q in keys:
        return q
    inside = sorted((k for k in keys if q in k or (len(k) >= 4 and k in q)), key=len)
    if inside:
        return inside[0]
    best = difflib.get_close_matches(q, list(keys), n=1, cutoff=0.82)
    return best[0] if best else ''


def next_episode(key: str, items: list[dict] | None = None) -> dict | None:
    """The episode after the last watched one (the first one when nothing was watched or the series is finished), or None for an unknown series."""
    items = scan() if items is None else items
    eps = _episodes(key, items)
    if not eps:
        return None
    done = (_cfg()['progress'].get(key) or {}).get('path')
    idx = next((n for n, e in enumerate(eps) if e['path'] == done), -1)
    return eps[idx + 1] if 0 <= idx + 1 < len(eps) else eps[0]


def pick_episode(key: str, season=None, episode=None, items: list[dict] | None = None) -> dict | None:
    """A named episode ("season 2 episode 3"; a bare episode number means season 1 or the only season), else None."""
    items = scan() if items is None else items
    eps = _episodes(key, items)
    if season is None and episode is not None:
        seasons = sorted({e['season'] for e in eps})
        season = seasons[0] if len(seasons) == 1 else (1 if 1 in seasons else None)
    return next((e for e in eps if e['season'] == season and e['episode'] == episode), None) if season is not None and episode is not None else None


def movie_for(key: str, items: list[dict] | None = None) -> dict | None:
    items = scan() if items is None else items
    return next((i for i in items if i['key'] == key and i['episode'] is None), None)


def last_series_key() -> str:
    return _cfg()['last']


def mark_watched(item: dict) -> None:
    """Remembers the episode as the last watched one of its series."""
    if item.get('episode') is None or not item.get('key'):
        return
    cfg = _cfg()
    cfg['progress'][item['key']] = {'path': item['path'], 'at': int(time.time())}
    cfg['last'] = item['key']
    _save(cfg)


def play(item: dict) -> bool:
    """Opens the file in the default player and remembers it. False when the file is gone or cannot be started."""
    path = item.get('path', '')
    if not path or not os.path.isfile(path):
        return False
    try:
        from core.safe_open import open_user_file
        open_user_file(path)                          # the program Windows has set for this file type; never one that runs code
    except (OSError, AttributeError, PermissionError):
        return False
    mark_watched(item)
    return True


def item_for_path(path: str) -> dict | None:
    """The scanned entry for a path from the library (so a path sent by the screen is never opened unless it is a known video file)."""
    return next((i for i in scan() if i['path'] == path), None)
