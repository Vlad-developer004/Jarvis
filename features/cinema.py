"""Finding something to watch: "включи фильм X", "найди сериал X сезон 2 серия 3", "где посмотреть X".

Opens the search page of the viewing service the user chose (see actions/cinema_services.py) in the normal browser. Nothing is scraped and nothing is clicked on the screen.
The words are parsed in actions/media_phrases.py.
"""
import webbrowser

from actions import cinema_services as cs
from actions.media_phrases import parse_watch


def parse_cinema_request(text: str) -> dict:
    res = parse_watch(text)
    if res is None:
        return {'type': 'unknown', 'title': (text or '').strip(), 'season': None, 'episode': None, 'hint': text or ''}
    return res


def plan(title: str, is_series: bool = False, season=None, episode=None, hint: str = '') -> dict:
    """What would be opened: {'service': dict|None, 'url': str, 'query': str}. The service is the one named in `hint`, else the user's default, else none (plain web search)."""
    st = cs.load()
    svc = cs.find_service(st['services'], hint) or next((s for s in st['services'] if s['id'] == st['default']), None)
    query = str(title or '').strip()
    if season or episode:
        query += (f' сезон {season}' if season else '') + (f' серия {episode}' if episode else '')
    if svc is None:
        query = f"смотреть {'сериал' if is_series else 'фильм'} {query} онлайн"
    return {'service': svc, 'url': cs.search_url(svc, query), 'query': query}


def watch_media(title: str, is_series: bool = False, season=None, episode=None, hint: str = ''):
    """Opens the search for `title` and returns (True, url)."""
    p = plan(title, is_series, season, episode, hint)
    webbrowser.open(p['url'])
    return (True, p['url'])
