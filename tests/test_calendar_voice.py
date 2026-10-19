"""Voice: "добавь в календарь завтра в 15:00 встреча с Аней" -> recognized, parsed, stored as an own event, confirmed aloud."""
from datetime import date, timedelta

import pytest

import core.handler.commands.integrations as integ
import core.settings_io as sio
from actions import calendar_hub as hub
from actions import calendar_quick as cq


class Handler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = tmp_path / 'settings.json'
    settings.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(settings))
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    return tmp_path


@pytest.mark.parametrize('text', ['добавь в календарь завтра в 15:00 встреча', 'запиши в календарь: в пятницу планёрка', 'запланируй встречу завтра в 10', 'создай событие день рождения мамы 3 мая',
                                  'додай до календаря післязавтра зустріч', 'добавь мне в расписание сегодня ужин'])
def test_add_phrases_are_recognized(text):
    assert cq.is_add_phrase(text)


@pytest.mark.parametrize('text', ['добавь таймер на 5 минут', 'что в календаре', 'добавь в корзину', 'создай папку', 'запиши заметку купить хлеб'])
def test_other_commands_are_not_taken(text):
    assert not cq.is_add_phrase(text)


def test_the_event_noun_stays_in_the_title():
    assert cq.voice_phrase('запланируй встречу завтра в 15:00 с Аней') == 'Встреча завтра в 15:00 с Аней'
    assert cq.voice_phrase('добавь в календарь: стоматолог в пятницу') == 'стоматолог в пятницу'


def test_the_recognizer_routes_it_before_the_ml_model():
    from core.engine import recognition
    assert recognition._is_calendar_add('добавь в календарь завтра встреча')


def test_the_command_stores_the_event_and_says_what_it_did(env):
    h = Handler()
    integ._calendar_add(h, 'добавь в календарь завтра в 15:00 встреча с Аней')
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    got = hub.load_local()
    assert len(got) == 1 and (got[0]['title'], got[0]['date'], got[0]['time'], got[0]['end_time']) == ('Встреча с Аней', tomorrow, '15:00', '16:00')
    assert h.spoken == ['Добавил в календарь: Встреча с Аней, завтра в 15:00.']


def test_an_all_day_repeating_event_by_voice(env):
    h = Handler()
    integ._calendar_add(h, 'добавь в календарь каждый понедельник спортзал')
    e = hub.load_local()[0]
    assert (e['title'], e['all_day'], e['repeat'], e['weekdays']) == ('Спортзал', True, 'weekly', [0]) and 'каждую неделю' in h.spoken[0] and 'на весь день' in h.spoken[0]


def test_missing_title_or_date_is_asked_for_and_nothing_is_stored(env):
    h = Handler()
    integ._calendar_add(h, 'добавь в календарь завтра в 15:00')
    integ._calendar_add(h, 'добавь в календарь позвонить Ане')
    assert hub.load_local() == [] and 'название' in h.spoken[0] and h.spoken[1].startswith('Когда это будет?')


def test_it_is_a_known_intent_with_a_gate_and_a_card():
    from core.nlp.intents import INTENTS
    from ui_next.bridge import commands_meta
    assert 'calendar_add' in INTENTS and 'calendar_add' in integ._INTEGRATIONS_ACTIONS and 'calendar_add' in commands_meta.META
