"""Where Jarvis looks for a film or a series: the viewing services the user picked (YouTube, Netflix, 1+1 video, ...).

No keys, no accounts, no scraping: a service is a name and a site address. Jarvis opens the service's own search page in the normal browser when its address pattern
is known, and otherwise searches that site through the web search (`site:domain title`). The user can add any site and may give the exact search address with {q}.

Stored in jarvis_settings.json (through core.settings_io) under "cinema": {"services": [{id, name, domain, search}], "default": id}.
"""
from __future__ import annotations

import re
import urllib.parse

from core import settings_io

MAX_SERVICES = 30

# a starting list the user can pick from; `search` is filled only where the service's own search address is well known
PRESETS: list[dict] = [
    {'id': 'youtube', 'name': 'YouTube', 'domain': 'youtube.com', 'search': 'https://www.youtube.com/results?search_query={q}', 'aliases': ['ютуб', 'ютубе', 'youtube', 'ютьюб']},
    {'id': 'netflix', 'name': 'Netflix', 'domain': 'netflix.com', 'search': 'https://www.netflix.com/search?q={q}', 'aliases': ['нетфликс', 'нетфликсе', 'netflix', 'нетфлікс']},
    {'id': '1plus1', 'name': '1+1 video', 'domain': '1plus1.video', 'search': '', 'aliases': ['1+1', 'плюс один', 'один плюс один', 'одинплюсодин']},
    {'id': 'teleportal', 'name': 'Телепортал', 'domain': 'teleportal.ua', 'search': '', 'aliases': ['телепортал', 'телепорталі', 'teleportal']},
    {'id': 'megogo', 'name': 'Megogo', 'domain': 'megogo.net', 'search': '', 'aliases': ['мегого', 'megogo']},
    {'id': 'sweettv', 'name': 'Sweet.tv', 'domain': 'sweet.tv', 'search': '', 'aliases': ['свит', 'sweet', 'світ ти ві']},
    {'id': 'kinopoisk', 'name': 'Кинопоиск', 'domain': 'kinopoisk.ru', 'search': 'https://www.kinopoisk.ru/index.php?kp_query={q}', 'aliases': ['кинопоиск', 'кинопоиске', 'кінопошук']},
    {'id': 'okko', 'name': 'Okko', 'domain': 'okko.tv', 'search': '', 'aliases': ['окко', 'okko']},
    {'id': 'ivi', 'name': 'ivi', 'domain': 'ivi.ru', 'search': '', 'aliases': ['иви', 'ivi']},
    {'id': 'rutube', 'name': 'Rutube', 'domain': 'rutube.ru', 'search': 'https://rutube.ru/search/?query={q}', 'aliases': ['рутуб', 'рутубе', 'rutube']},
    {'id': 'prime', 'name': 'Prime Video', 'domain': 'primevideo.com', 'search': '', 'aliases': ['прайм', 'амазон', 'prime video', 'amazon']},
    {'id': 'disney', 'name': 'Disney+', 'domain': 'disneyplus.com', 'search': '', 'aliases': ['дисней', 'disney']},
    {'id': 'max', 'name': 'Max', 'domain': 'max.com', 'search': '', 'aliases': ['макс', 'hbo']},
    {'id': 'appletv', 'name': 'Apple TV', 'domain': 'tv.apple.com', 'search': '', 'aliases': ['эппл тв', 'apple tv']},
]
_DOMAIN_RE = re.compile(r'^(?=.{4,100}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')


def clean_domain(raw: str) -> str:
    """"https://www.Example.com/path" -> "example.com"; '' when it is not a plausible site name."""
    s = str(raw or '').strip().lower()
    if '://' in s:
        s = urllib.parse.urlsplit(s).netloc
    s = s.split('/')[0].split('?')[0].split(':')[0]
    if s.startswith('www.'):
        s = s[4:]
    try:
        s = s.encode('idna').decode('ascii')
    except UnicodeError:
        return ''
    return s if _DOMAIN_RE.match(s) else ''


def _clean_search(raw: str) -> str:
    s = str(raw or '').strip()
    if not s:
        return ''
    ok = s.lower().startswith(('http://', 'https://')) and '{q}' in s and len(s) <= 400 and not any(c in s for c in '\r\n\0 ')
    return s if ok else ''


def _slug(name: str, taken: set) -> str:
    base = re.sub(r'[^a-z0-9]+', '', name.lower()) or 'site'
    sid, n = base, 2
    while sid in taken:
        sid, n = f'{base}{n}', n + 1
    return sid


def load() -> dict:
    """{'services': [...], 'default': id}. Without a saved choice there is one service, YouTube."""
    raw = settings_io.read().get('cinema', {})
    raw = raw if isinstance(raw, dict) else {}
    items = []
    for s in raw.get('services', []) if isinstance(raw.get('services'), list) else []:
        if isinstance(s, dict) and clean_domain(s.get('domain')) and str(s.get('name', '')).strip():
            items.append({'id': str(s.get('id') or ''), 'name': str(s['name']).strip()[:40], 'domain': clean_domain(s['domain']), 'search': _clean_search(s.get('search'))})
    if not items and 'services' not in raw:
        items = [{k: p[k] for k in ('id', 'name', 'domain', 'search')} for p in PRESETS[:1]]
    ids = [s['id'] for s in items]
    default = raw.get('default') if raw.get('default') in ids else (ids[0] if ids else '')
    return {'services': items, 'default': default}


def _save(services: list, default: str) -> bool:
    cur = settings_io.read().get('cinema', {})
    cur = dict(cur) if isinstance(cur, dict) else {}
    cur.update(services=services, default=default if any(s['id'] == default for s in services) else (services[0]['id'] if services else ''))
    return settings_io.update({'cinema': cur})


def add(name: str, domain: str, search: str = '') -> dict:
    name, dom = str(name or '').strip()[:40], clean_domain(domain)
    if not name or not dom:
        return {'ok': False, 'error': 'required' if not (name and str(domain or '').strip()) else 'bad_domain'}
    st = load()
    if len(st['services']) >= MAX_SERVICES:
        return {'ok': False, 'error': 'too_many'}
    if any(s['domain'] == dom for s in st['services']):
        return {'ok': False, 'error': 'exists'}
    preset = next((p for p in PRESETS if p['domain'] == dom), None)
    sid = preset['id'] if preset and not any(s['id'] == preset['id'] for s in st['services']) else _slug(name, {s['id'] for s in st['services']})
    sv = {'id': sid, 'name': name, 'domain': dom, 'search': _clean_search(search) or (preset['search'] if preset else '')}
    return {'ok': True} if _save(st['services'] + [sv], st['default'] or sid) else {'ok': False, 'error': 'write_failed'}


def remove(sid: str) -> dict:
    st = load()
    left = [s for s in st['services'] if s['id'] != sid]
    if len(left) == len(st['services']):
        return {'ok': False, 'error': 'not_found'}
    return {'ok': True} if _save(left, st['default']) else {'ok': False, 'error': 'write_failed'}


def set_default(sid: str) -> dict:
    st = load()
    if not any(s['id'] == sid for s in st['services']):
        return {'ok': False, 'error': 'not_found'}
    return {'ok': True} if _save(st['services'], sid) else {'ok': False, 'error': 'write_failed'}


def search_url(service: dict | None, query: str) -> str:
    """The page to open: the service's own search when its address is known, else a web search limited to the service's site, else a plain web search."""
    q = urllib.parse.quote_plus(str(query or '').strip())
    if service and service.get('search'):
        return service['search'].replace('{q}', q)
    if service and service.get('domain'):
        return 'https://www.google.com/search?q=' + urllib.parse.quote_plus(f"site:{service['domain']} ") + q
    return 'https://www.google.com/search?q=' + q


def find_service(services: list[dict], text: str) -> dict | None:
    """The service named in a phrase ("... на Netflix", "в ютубе"), by its name, its domain or a known spoken alias."""
    t = (text or '').lower()
    for s in services:
        p = next((p for p in PRESETS if p['id'] == s['id'] or p['domain'] == s['domain']), None)
        names = {s['name'].lower(), s['domain'].split('.')[0]} | set(p['aliases'] if p else [])
        for n in names:
            if n and re.search(r'(?<![\wа-яёіїє])' + re.escape(n) + r'(?![\wа-яёіїє])', t):
                return s
    return None
