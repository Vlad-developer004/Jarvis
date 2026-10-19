"""The "watch later" list of the Cinema screen: titles the user wants to see, kept in jarvis_settings.json under "cinema": {"later": [{id, title, kind}]}."""
from __future__ import annotations

import uuid

from core import settings_io

MAX_ITEMS = 60


def _cinema() -> dict:
    raw = settings_io.read().get('cinema', {})
    return dict(raw) if isinstance(raw, dict) else {}


def load() -> list[dict]:
    raw = _cinema().get('later')
    out = []
    for x in raw if isinstance(raw, list) else []:
        if isinstance(x, dict) and str(x.get('title', '')).strip():
            out.append({'id': str(x.get('id') or uuid.uuid4().hex[:8]), 'title': str(x['title']).strip()[:120], 'kind': 'series' if x.get('kind') == 'series' else 'movie'})
    return out


def _save(items: list[dict]) -> bool:
    cur = _cinema()
    cur['later'] = items
    return settings_io.update({'cinema': cur})


def add(title: str, kind: str = 'movie') -> dict:
    title = ' '.join(str(title or '').split())[:120]
    if len(title) < 2:
        return {'ok': False, 'error': 'required'}
    items = load()
    if any(i['title'].lower() == title.lower() for i in items):
        return {'ok': False, 'error': 'exists'}
    if len(items) >= MAX_ITEMS:
        return {'ok': False, 'error': 'too_many'}
    items.append({'id': uuid.uuid4().hex[:8], 'title': title, 'kind': 'series' if kind == 'series' else 'movie'})
    return {'ok': True} if _save(items) else {'ok': False, 'error': 'write_failed'}


def remove(item_id: str) -> dict:
    items = load()
    left = [i for i in items if i['id'] != item_id]
    if len(left) == len(items):
        return {'ok': False, 'error': 'not_found'}
    return {'ok': True} if _save(left) else {'ok': False, 'error': 'write_failed'}
