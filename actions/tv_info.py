"""Series facts from TVmaze (https://www.tvmaze.com, free, no key, no account): status and the dates of the previous and the next episode.

Used by "когда выйдет следующая серия X" and the Cinema screen. The data is credited to TVmaze in the UI (CC BY-SA). One request per title, cached for six hours.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

_URL = 'https://api.tvmaze.com/singlesearch/shows?q={q}&embed[]=nextepisode&embed[]=previousepisode'
_TTL = 6 * 3600.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, dict | None]] = {}

_MONTHS = {
    'ru': ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    'uk': ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'],
}


def _episode(e: dict | None) -> dict | None:
    if not isinstance(e, dict) or not e.get('airstamp'):
        return None
    return {'season': e.get('season'), 'number': e.get('number'), 'name': str(e.get('name') or ''), 'airstamp': e['airstamp']}


def _fetch(title: str) -> dict | None:
    req = urllib.request.Request(_URL.format(q=urllib.parse.quote(title)), headers={'User-Agent': 'Jarvis-assistant'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode('utf-8'))
    except Exception:
        return None
    emb = d.get('_embedded') or {}
    return {'name': str(d.get('name') or title), 'status': str(d.get('status') or ''), 'premiered': str(d.get('premiered') or ''), 'url': str(d.get('url') or ''),
            'prev': _episode(emb.get('previousepisode')), 'next': _episode(emb.get('nextepisode'))}


def lookup(title: str) -> dict | None:
    """{'name', 'status', 'premiered', 'url', 'prev', 'next'} (prev/next: {'season', 'number', 'name', 'airstamp'} or None), None when the show is unknown or there is no network."""
    key = ' '.join(str(title or '').lower().split())
    if len(key) < 2:
        return None
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    data = _fetch(key)
    if data is not None:                                  # a network error is not cached, so the next ask retries
        with _lock:
            _cache[key] = (time.time(), data)
    return data


def spoken_date(airstamp: str, lang: str = 'ru') -> str:
    """"10 августа" in the local time zone (the day the episode is on for the user), "" when the stamp is unreadable."""
    try:
        dt = datetime.fromisoformat(airstamp).astimezone()
    except (ValueError, TypeError):
        return ''
    return f"{dt.day} {_MONTHS.get(lang, _MONTHS['ru'])[dt.month - 1]}"
