"""The "Кино" screen of the new UI: viewing services and "find something to watch" (the voice command does the same, see features/cinema.py).

What is playing is not here: it comes through the `nowplaying` topic and the `media` command (actions/now_playing.py).
"""
from __future__ import annotations

import webbrowser

from actions import cinema_services as cs
from actions import media_library as ml
from actions import watch_later, cinema_mode


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def get_state() -> dict:
    st = cs.load()
    have = {s['domain'] for s in st['services']}
    presets = [{'id': p['id'], 'name': p['name'], 'domain': p['domain'], 'own_search': bool(p['search'])} for p in cs.PRESETS if p['domain'] not in have]
    services = [{**s, 'own_search': bool(s['search'])} for s in st['services']]
    return {'ok': True, 'services': services, 'default': st['default'], 'presets': presets, 'later': watch_later.load(), 'mode': {'active': cinema_mode.is_active(), 'level': cinema_mode.level()}}


def watch(title, service_id, kind, season, episode) -> dict:
    """Opens the search page for `title` in the browser (the service the screen picked, else the default one)."""
    title = str(title or '').strip()
    if len(title) < 2 or len(title) > 200:
        return _bad('required')
    st = cs.load()
    svc = next((s for s in st['services'] if s['id'] == service_id), None) or next((s for s in st['services'] if s['id'] == st['default']), None)
    is_series = kind == 'series'

    def num(v):
        try:
            n = int(v)
            return n if 0 < n < 1000 else None
        except (TypeError, ValueError):
            return None
    query = title + (f' сезон {num(season)}' if num(season) else '') + (f' серия {num(episode)}' if num(episode) else '')
    if svc is None:
        query = f"смотреть {'сериал' if is_series else 'фильм'} {query} онлайн"
    url = cs.search_url(svc, query)
    return {'ok': bool(webbrowser.open(url)), 'url': url, 'service': svc['name'] if svc else ''}


def lib_state(force: bool = False) -> dict:
    """The user's own films and series: folders plus what was found in them."""
    items = ml.scan(force=force)
    lib = ml.library(items)
    return {'ok': True, 'folders': ml.folders(), 'series': lib['series'], 'movies': lib['movies'][:400], 'movies_total': len(lib['movies']), 'files': len(items), 'last': ml.last_series_key()}


def lib_play(data: dict) -> dict:
    """Opens an episode or a movie: {path} for a file the scan knows, or {key} for the next unwatched episode of a series."""
    items = ml.scan()
    if data.get('path'):
        item = next((i for i in items if i['path'] == str(data['path'])), None)
    else:
        item = ml.next_episode(str(data.get('key', '')), items)
    if item is None:
        return _bad('not_found')
    ok = ml.play(item)
    return {**lib_state(), 'ok': ok, 'played': item['path']} if ok else _bad('open_failed')


def lib_run(op: str, data: dict) -> dict:
    if op == 'lib':
        return lib_state(bool(data.get('force')))
    if op == 'lib_add':
        path = str(data.get('path') or '')
        if not path:
            from .filepick import pick_folder
            path = pick_folder('Папка с фильмами и сериалами')
            if not path:
                return _bad('cancelled')
        res = ml.add_folder(path)
    elif op == 'lib_remove':
        res = ml.remove_folder(str(data.get('path', '')))
    elif op == 'lib_play':
        return lib_play(data)
    else:
        return _bad('bad_op')
    return lib_state(True) if res.get('ok') else res


def info(title) -> dict:
    """Series facts from TVmaze for the Cinema screen: {ok, name, status, premiered, url, prev, next}."""
    from actions import tv_info
    title = str(title or '').strip()
    if len(title) < 2 or len(title) > 200:
        return _bad('required')
    d = tv_info.lookup(title)
    return {'ok': True, **d} if d else _bad('no_data')


def info_calendar(title) -> dict:
    """Puts the date of the next episode (TVmaze) into the user's own calendar as an all-day event."""
    from datetime import datetime
    from actions import calendar_hub as hub, tv_info
    d = tv_info.lookup(str(title or '').strip())
    if not d or not d.get('next'):
        return _bad('no_next')
    n = d['next']
    try:
        day = datetime.fromisoformat(n['airstamp']).astimezone().date().isoformat()
    except ValueError:
        return _bad('no_next')
    name = f"{d['name']}: серия {n['season']}x{int(n['number']):02d}"
    if any(e.get('title') == name and e.get('date') == day for e in hub.load_local()):
        return _bad('exists')
    try:
        hub.add_local({'title': name, 'date': day, 'all_day': True, 'notes': 'Дата по данным TVmaze'})
    except hub.CalendarError:
        return _bad('write_failed')
    from . import calendar as bcal
    bcal._enable_module()
    return {'ok': True, 'title': name, 'date': day}


def run(data: dict) -> dict:
    """Entry of the `cinema` bridge command: op `state` | `add` {name, domain, search?} | `remove` {id} | `default` {id} | `watch` {title, id?, kind?, season?, episode?}."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return get_state()
    if op == 'info_calendar':
        return info_calendar(data.get('title'))
    if op == 'mode':
        res = cinema_mode.enable() if data.get('on') else cinema_mode.disable()
        return {**get_state(), 'ok': True} if res.get('ok') else res
    if op == 'mode_level':
        res = cinema_mode.set_level(data.get('value'))
        return {**get_state(), 'ok': True} if res.get('ok') else res
    if op == 'info':
        return info(data.get('title'))
    if op.startswith('lib'):
        return lib_run(op, data)
    if op == 'watch':
        return watch(data.get('title'), str(data.get('id', '')), str(data.get('kind', '')), data.get('season'), data.get('episode'))
    fn = {'later_add': lambda: watch_later.add(data.get('title'), str(data.get('kind', 'movie'))), 'later_remove': lambda: watch_later.remove(str(data.get('id', ''))),
          'add': lambda: cs.add(data.get('name'), data.get('domain'), data.get('search', '')), 'remove': lambda: cs.remove(str(data.get('id', ''))), 'default': lambda: cs.set_default(str(data.get('id', '')))}.get(op)
    if fn is None:
        return _bad('bad_op')
    res = fn()
    return {**get_state(), 'ok': True} if res.get('ok') else res

