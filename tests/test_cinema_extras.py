"""Cinema mode, the watch-later list and "next episode into the calendar" (brightness and TVmaze are faked)."""
import pytest

import core.settings_io as sio
from actions import cinema_mode as cm
from actions import media_phrases as mp
from actions import tv_info, watch_later
from core.handler.commands import cinema as cin
from ui_next import bridge


class Handler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    screen = {'now': [58, 90], 'fail': False}

    def get():
        return None if screen['fail'] else list(screen['now'])

    def put(v):
        if screen['fail']:
            return False
        screen['now'] = list(v) if isinstance(v, list) else [int(v)] * len(screen['now'])
        return True
    monkeypatch.setattr(cm, '_get_brightness', get)
    monkeypatch.setattr(cm, '_set_brightness', put)
    return screen


@pytest.mark.parametrize('text,mode', [('включи режим кино', 'on'), ('режим кино', 'on'), ('выключи режим кино', 'off'), ('вимкни режим кіно', 'off'), ('включи кино', None)])
def test_parse_mode(text, mode):
    assert mp.parse_mode(text) == mode


def test_mode_dims_and_restores_each_display(env):
    assert cm.enable() == {'ok': True, 'active': True} and env['now'] == [30, 30] and cm.is_active()
    assert cm.enable().get('already') and env['now'] == [30, 30]
    assert cm.disable() == {'ok': True, 'active': False} and env['now'] == [58, 90] and not cm.is_active()
    assert cm.disable().get('already')


def test_mode_reports_a_screen_it_cannot_dim(env):
    env['fail'] = True
    assert cm.enable()['error'] == 'no_brightness' and not cm.is_active()


def test_mode_level_is_validated_and_used(env):
    assert cm.set_level(20)['ok'] and cm.level() == 20 and cm.set_level(200)['error'] == 'bad_value' and cm.set_level('x')['error'] == 'bad_value'
    cm.enable()
    assert env['now'] == [20, 20]


def test_mode_by_voice(env):
    h = Handler()
    cin._handle_mode(h, 'выключи режим кино')
    cin._handle_mode(h, 'включи режим кино')
    cin._handle_mode(h, 'выключи режим кино')
    assert 'и так выключен' in h.spoken[0] and '30 процентов' in h.spoken[1] and 'возвращена' in h.spoken[2] and env['now'] == [58, 90]


@pytest.mark.parametrize('text,want', [('добавь фильм Дюна в список просмотра', ('Дюна', 'movie')), ('посмотрю позже сериал Шерлок', ('Шерлок', 'series')), ('запиши Матрица в список желаемого', ('Матрица', 'movie'))])
def test_parse_later(text, want):
    r = mp.parse_later(text)
    assert (r['title'], r['kind']) == want and mp.route(text) == 'cinema_later'


def test_later_list_roundtrip(env):
    assert watch_later.add('Дюна')['ok'] and watch_later.add('дюна')['error'] == 'exists' and watch_later.add('x')['error'] == 'required'
    assert watch_later.add('Шерлок', 'series')['ok']
    items = watch_later.load()
    assert [i['kind'] for i in items] == ['movie', 'series']
    assert watch_later.remove(items[0]['id'])['ok'] and watch_later.remove('zz')['error'] == 'not_found' and [i['title'] for i in watch_later.load()] == ['Шерлок']


def test_later_by_voice(env):
    h = Handler()
    cin._handle_later(h, 'cinema_later_list', 'что в списке просмотра')
    cin._handle_later(h, 'cinema_later', 'добавь фильм Дюна в список просмотра')
    cin._handle_later(h, 'cinema_later', 'добавь фильм Дюна в список просмотра')
    cin._handle_later(h, 'cinema_later_list', 'что в списке просмотра')
    assert 'пуст' in h.spoken[0] and 'Записал' in h.spoken[1] and 'уже в списке' in h.spoken[2] and 'Дюна' in h.spoken[3]


def test_settings_of_the_cinema_blocks_do_not_overwrite_each_other(env):
    from actions import cinema_services as cs
    watch_later.add('Дюна')
    cm.set_level(25)
    assert cs.add('Мой', 'example.com')['ok'] and watch_later.load() and cm.level() == 25 and sio.read()['keep'] == 1


def test_bridge_state_and_ops(env):
    r = bridge.run_command('cinema', {'op': 'later_add', 'title': 'Дюна', 'kind': 'movie'})
    assert r['ok'] and r['later'][0]['title'] == 'Дюна' and r['mode'] == {'active': False, 'level': 30}
    r = bridge.run_command('cinema', {'op': 'mode', 'on': True})
    assert r['ok'] and r['mode']['active'] and env['now'] == [30, 30]
    assert bridge.run_command('cinema', {'op': 'mode_level', 'value': 1})['error'] == 'bad_value'
    assert not bridge.run_command('cinema', {'op': 'mode', 'on': False})['mode']['active']
    assert bridge.run_command('cinema', {'op': 'later_remove', 'id': r['later'][0]['id']})['later'] == []


def test_next_episode_goes_into_the_calendar_once(env, tmp_path, monkeypatch):
    from actions import calendar_hub as hub
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    info = {'name': 'Show', 'status': 'Running', 'premiered': '', 'url': '', 'prev': None, 'next': {'season': 2, 'number': 3, 'name': 'x', 'airstamp': '2030-05-05T12:00:00+00:00'}}
    monkeypatch.setattr(tv_info, 'lookup', lambda t: info)
    r = bridge.run_command('cinema', {'op': 'info_calendar', 'title': 'Show'})
    assert r['ok'] and r['title'] == 'Show: серия 2x03' and r['date'] == '2030-05-05'
    assert [e['title'] for e in hub.load_local()] == ['Show: серия 2x03']
    assert bridge.run_command('cinema', {'op': 'info_calendar', 'title': 'Show'})['error'] == 'exists'
    info['next'] = None
    assert bridge.run_command('cinema', {'op': 'info_calendar', 'title': 'Show'})['error'] == 'no_next'
