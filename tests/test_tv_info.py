"""actions/tv_info.py (TVmaze, faked), "когда выйдет следующая серия X" and the `info` bridge op."""
import pytest

from actions import media_phrases as mp
from actions import tv_info
from core.handler.commands import cinema as cin
from ui_next import bridge


class Handler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


def ep(s, n, stamp):
    return {'season': s, 'number': n, 'name': 'x', 'airstamp': stamp}


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    tv_info._cache.clear()
    calls = []
    data = {'name': 'Show', 'status': 'Running', 'premiered': '2020-01-01', 'url': 'u', 'prev': ep(1, 1, '2026-08-10T12:00:00+00:00'), 'next': ep(1, 2, '2026-12-05T12:00:00+00:00')}
    monkeypatch.setattr(tv_info, '_fetch', lambda t: calls.append(t) or data)
    return {'calls': calls, 'data': data}


@pytest.mark.parametrize('text,title', [('когда выйдет следующая серия Шерлока', 'шерлока'), ('коли вийде наступна серія Шерлока', 'шерлока'), ('когда выйдет новая серия', ''), ('когда будет следующая серия сериала Дом', 'дом')])
def test_parse_when(text, title):
    assert mp.parse_when(text) == {'title': title} and mp.route(text) == 'cinema_when'


def test_lookup_is_cached_and_a_failed_fetch_is_not(fresh, monkeypatch):
    assert tv_info.lookup('Show') and tv_info.lookup('  show ') and len(fresh['calls']) == 1
    tv_info._cache.clear()
    monkeypatch.setattr(tv_info, '_fetch', lambda t: None)
    assert tv_info.lookup('x show') is None and not tv_info._cache


def test_spoken_date_uses_month_names():
    assert tv_info.spoken_date('2026-12-05T12:00:00+00:00', 'ru') == '5 декабря' and tv_info.spoken_date('2026-12-05T12:00:00+00:00', 'uk') == '5 грудня' and tv_info.spoken_date('bad') == ''


def test_describe_when_cases(fresh):
    d = fresh['data']
    assert 'сезон 1, серия 2, выйдет 5 декабря' in cin.describe_when(d, 'show', 'ru')
    assert 'не объявлена' in cin.describe_when({**d, 'next': None}, 'show', 'ru')
    assert 'завершён' in cin.describe_when({**d, 'next': None, 'status': 'Ended'}, 'show', 'ru')
    assert 'Не нашёл' in cin.describe_when(None, 'show', 'ru')


def test_handler_asks_for_a_title_when_there_is_none(tmp_path, monkeypatch):
    import core.settings_io as sio
    path = tmp_path / 's.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    h = Handler()
    cin._handle_when(h, 'когда выйдет новая серия')
    assert 'Назовите сериал' in h.spoken[0]
    cin._handle_when(h, 'когда выйдет следующая серия show')
    assert 'Следующая серия' in h.spoken[1]


def test_bridge_info(fresh):
    r = bridge.run_command('cinema', {'op': 'info', 'title': 'Show'})
    assert r['ok'] and r['next']['number'] == 2
    assert bridge.run_command('cinema', {'op': 'info', 'title': ''})['error'] == 'required'
    fresh['data'] = None
