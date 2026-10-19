"""actions/cinema_services.py, the watch phrases and features/cinema.py: where Jarvis looks for a film (no keys, no scraping)."""
import pytest

import core.settings_io as sio
from actions import cinema_services as cs
from actions import media_phrases as mp
from features import cinema


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    return path


@pytest.mark.parametrize('raw,dom', [('https://www.Example.com/path?q=1', 'example.com'), ('1plus1.video', '1plus1.video'), ('  Netflix.com ', 'netflix.com'), ('sweet.tv:443/x', 'sweet.tv'),
                                      ('nodomain', ''), ('', ''), ('http://', ''), ('a b.com', ''), ('javascript:alert(1)', '')])
def test_clean_domain(raw, dom):
    assert cs.clean_domain(raw) == dom


def test_default_is_youtube_until_the_user_chooses(env):
    st = cs.load()
    assert [s['id'] for s in st['services']] == ['youtube'] and st['default'] == 'youtube'


def test_add_remove_and_default(env):
    assert cs.add('1+1 video', '1plus1.video')['ok'] and cs.add('Свой сайт', 'https://kino.example.org/', 'https://kino.example.org/s?q={q}')['ok']
    st = cs.load()
    assert [s['domain'] for s in st['services']] == ['youtube.com', '1plus1.video', 'kino.example.org'] and st['services'][2]['search'].endswith('{q}')
    assert cs.add('Дубль', 'www.1plus1.video')['error'] == 'exists' and cs.add('', 'x.com')['error'] == 'required' and cs.add('X', 'not a site')['error'] == 'bad_domain'
    assert cs.set_default('1plus1')['ok'] and cs.load()['default'] == '1plus1' and cs.set_default('zzz')['error'] == 'not_found'
    assert cs.remove('1plus1')['ok'] and cs.load()['default'] == 'youtube' and cs.remove('1plus1')['error'] == 'not_found'
    assert sio.read()['keep'] == 1


def test_an_unsafe_search_address_is_dropped(env):
    cs.add('X', 'x.com', 'javascript:alert({q})')
    cs.add('Y', 'y.com', 'https://y.com/s?q={q} evil')
    assert [s['search'] for s in cs.load()['services'][1:]] == ['', '']


def test_search_url(env):
    yt = {'domain': 'youtube.com', 'search': 'https://www.youtube.com/results?search_query={q}'}
    assert cs.search_url(yt, 'Шерлок сезон 2') == 'https://www.youtube.com/results?search_query=%D0%A8%D0%B5%D1%80%D0%BB%D0%BE%D0%BA+%D1%81%D0%B5%D0%B7%D0%BE%D0%BD+2'
    assert cs.search_url({'domain': '1plus1.video', 'search': ''}, 'дюна') == 'https://www.google.com/search?q=site%3A1plus1.video+%D0%B4%D1%8E%D0%BD%D0%B0'
    assert cs.search_url(None, 'дюна').startswith('https://www.google.com/search?q=')


def test_find_service_by_spoken_name(env):
    cs.add('1+1 video', '1plus1.video')
    cs.add('Netflix', 'netflix.com')
    sv = cs.load()['services']
    assert cs.find_service(sv, 'интерстеллар на нетфликсе')['id'] == 'netflix' and cs.find_service(sv, 'дюна в ютубе')['id'] == 'youtube'
    assert cs.find_service(sv, 'сериал на 1+1')['id'] == '1plus1' and cs.find_service(sv, 'просто дюна') is None


@pytest.mark.parametrize('text,kind,title,season,episode', [
    ('включи фильм Матрица', 'movie', 'матрица', None, None), ('найди сериал Шерлок сезон 2 серия 3', 'series', 'шерлок', 2, 3), ('где посмотреть Дюна', 'unknown', 'дюна', None, None),
    ('включи сериал Ивановы-Ивановы на мегого', 'series', 'ивановы-ивановы', None, None), ('увімкни фільм Земля кочівників', 'movie', 'земля кочівників', None, None),
    ('включи фильм интерстеллар на netflix', 'movie', 'интерстеллар', None, None), ('запусти сериал Фоллаут 2 сезон', 'series', 'фоллаут', 2, None), ('покажи фильм', 'movie', '', None, None),
])
def test_watch_phrases(text, kind, title, season, episode):
    r = mp.parse_watch(text)
    assert (r['type'], r['title'], r['season'], r['episode']) == (kind, title, season, episode)
    assert mp.route(text) == 'cinema_watch'


@pytest.mark.parametrize('text', ['включи музыку', 'включи видео про котиков', 'поставь таймер на 5 минут', 'найди файл отчёт', 'открой браузер', 'покажи погоду'])
def test_other_commands_are_not_watch_requests(text):
    assert mp.parse_watch(text) is None


def test_plan_uses_the_named_service_then_the_default_then_a_plain_search(env):
    cs.add('Netflix', 'netflix.com')
    p = cinema.plan('интерстеллар', False, hint='интерстеллар на нетфликсе')
    assert p['service']['id'] == 'netflix' and p['url'] == 'https://www.netflix.com/search?q=%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D1%81%D1%82%D0%B5%D0%BB%D0%BB%D0%B0%D1%80'
    p = cinema.plan('шерлок', True, 2, 3)
    assert p['service']['id'] == 'youtube' and 'search_query=' in p['url'] and '%D1%81%D0%B5%D0%B7%D0%BE%D0%BD+2' in p['url']
    for s in list(cs.load()['services']):
        cs.remove(s['id'])
    p = cinema.plan('дюна', False)
    assert p['service'] is None and 'google.com/search' in p['url'] and '%D1%81%D0%BC%D0%BE%D1%82%D1%80%D0%B5%D1%82%D1%8C+%D1%84%D0%B8%D0%BB%D1%8C%D0%BC' in p['url']


def test_watch_media_opens_the_page_in_the_browser(env, monkeypatch):
    opened = []
    monkeypatch.setattr(cinema.webbrowser, 'open', lambda u: opened.append(u) or True)
    ok, url = cinema.watch_media('матрица')
    assert ok and opened == [url] and url.startswith('https://www.youtube.com/results?search_query=')
