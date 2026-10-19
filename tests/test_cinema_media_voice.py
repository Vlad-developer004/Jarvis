"""Voice: rewind, "what is playing", "how long is left" (the Windows media sessions are faked)."""
import pytest

from actions import now_playing as np
from core.handler.commands import cinema as cin


class Handler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


def row(**kw):
    base = {'id': 'VLC.exe#0', 'app': 'VLC.exe', 'app_name': 'VLC', 'title': 'Ивановы', 'artist': '', 'status': 'playing', 'pos': 600.0, 'dur': 3600.0, 'current': True,
            'can': {'play': False, 'pause': True, 'next': False, 'prev': False, 'seek': True}}
    base.update(kw)
    return base


@pytest.fixture
def player(monkeypatch):
    state = {'rows': [row()], 'sent': []}
    monkeypatch.setattr(np, 'snapshot', lambda: state['rows'])

    def control(action, sid='', arg=0.0):
        state['sent'].append((action, sid, arg))
        return state.get('reply', {'ok': True})
    monkeypatch.setattr(np, 'control', control)
    return state


def test_the_recognizer_routes_media_phrases_before_the_timer_rules():
    from core.engine import recognition
    assert recognition._cinema_route('перемотай на 5 минут назад') == 'cinema_seek'
    assert recognition._cinema_route('сколько осталось до конца') == 'cinema_left' and recognition._cinema_route('сколько осталось') is None


def test_now_playing_names_the_title_and_the_app(player):
    h = Handler()
    cin.handle_cinema(h, 'cinema_now', 'что сейчас играет')
    assert h.spoken == ['Сейчас играет Ивановы, в VLC.']
    player['rows'] = [row(status='paused')]
    cin.handle_cinema(h, 'cinema_now', 'что сейчас играет')
    assert h.spoken[-1] == 'На паузе Ивановы.'


def test_nothing_playing(player):
    player['rows'] = []
    h = Handler()
    for cmd in ('cinema_now', 'cinema_left', 'cinema_seek'):
        cin.handle_cinema(h, cmd, 'перемотай на 5 минут')
    assert all('ничего не играет' in s for s in h.spoken) and player['sent'] == []


def test_time_left(player):
    h = Handler()
    cin.handle_cinema(h, 'cinema_left', 'сколько осталось до конца')
    assert h.spoken == ['До конца осталось 50 минут.']
    player['rows'] = [row(dur=0.0)]
    cin.handle_cinema(h, 'cinema_left', 'сколько осталось до конца')
    assert 'не сообщает длительность' in h.spoken[-1]


def test_rewind_sends_the_right_request_and_confirms(player):
    h = Handler()
    cin.handle_cinema(h, 'cinema_seek', 'перемотай на 5 минут назад')
    cin.handle_cinema(h, 'cinema_seek', 'перемотай на 1 час 20 минут вперёд')
    cin.handle_cinema(h, 'cinema_seek', 'перемотай на отметку 20:00')
    assert player['sent'] == [('seek_by', 'VLC.exe#0', -300.0), ('seek_by', 'VLC.exe#0', 4800.0), ('seek_to', 'VLC.exe#0', 1200.0)]
    assert h.spoken == ['Перемотал на 5 минут назад.', 'Перемотал на 1 час 20 минут вперёд.', 'Перемотал на 20 минут от начала.']


def test_a_player_that_refuses_rewinding_is_explained(player):
    player['reply'] = {'ok': False, 'error': 'cannot_seek'}
    h = Handler()
    cin.handle_cinema(h, 'cinema_seek', 'перемотай на 5 минут назад')
    assert 'не даёт перематывать' in h.spoken[0]
