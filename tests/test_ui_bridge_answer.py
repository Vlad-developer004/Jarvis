"""ui_next/bridge/answer.py: the answer card state, its hide timer, and the hand-off from the old answer window."""
import time

import pytest

from ui_next import bridge
from ui_next.bridge import answer


@pytest.fixture
def card(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(answer, '_publish', lambda topic, payload: sent.append((topic, payload)))
    monkeypatch.setattr(answer, '_state', {'id': 0, 'visible': False, 'subject': '', 'text': '', 'image': '', 'video': False})
    monkeypatch.setattr(answer, '_speech_busy', lambda: False)
    monkeypatch.setattr(answer.time, 'sleep', lambda s: None)
    monkeypatch.setattr(answer, '_find_image', lambda subject, sid: None)
    from PIL import Image
    pic = tmp_path / 'p.png'
    Image.new('RGB', (800, 600), (200, 30, 30)).save(pic)
    return {'sent': sent, 'pic': str(pic)}


def last(card):
    return card['sent'][-1][1]


def wait_hidden(timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if not answer.snapshot()['visible']:
            return True
        time.sleep(0.01)
    return False


def test_an_answer_streams_into_the_card(card):
    answer.show('J.A.R.V.I.S.', False)
    assert last(card)['visible'] and last(card)['id'] == 1
    answer.set_text('Первая часть')
    answer.set_text('Первая часть и вторая')
    assert last(card)['text'] == 'Первая часть и вторая' and card['sent'][0][0] == 'answer'


def test_a_better_title_keeps_the_text_and_a_new_answer_clears_it(card):
    answer.show('J.A.R.V.I.S.', False)
    answer.set_text('текст')
    answer.show('Луна', False)
    assert last(card)['subject'] == 'Луна' and last(card)['text'] == 'текст' and last(card)['id'] == 1
    answer.hide(0)
    assert wait_hidden()
    answer.show('Марс', False)
    assert last(card)['id'] == 2 and last(card)['text'] == ''


def test_text_before_the_card_opens_is_ignored(card):
    answer.set_text('рано')
    assert card['sent'] == []


def test_a_picture_becomes_a_small_jpeg_and_a_late_one_is_dropped(card):
    answer.show('Луна', False)
    answer.set_image(card['pic'])
    assert last(card)['image'].startswith('data:image/jpeg;base64,') and len(last(card)['image']) < 60000
    answer.set_image(card['pic'], sid=99)                      # belongs to a card that is gone
    before = len(card['sent'])
    answer.set_image('C:/no/such/file.png')
    assert len(card['sent']) == before


def test_a_new_subject_drops_the_old_picture(card):
    answer.show('Луна', False)
    answer.set_image(card['pic'])
    answer.show('Марс', True)
    assert last(card)['image'] == ''


def test_a_video_is_announced_without_a_picture(card):
    answer.show('NASA', False)
    answer.set_video('x.mp4')
    assert last(card)['video'] is True and last(card)['image'] == ''


def test_the_card_closes_after_the_speech_and_the_pause(card, monkeypatch):
    answer.show('Луна', False)
    busy = [True, True, False]
    monkeypatch.setattr(answer, '_speech_busy', lambda: busy.pop(0) if busy else False)
    answer.hide(0)
    assert wait_hidden() and last(card)['visible'] is False and busy == []


def test_a_new_answer_cancels_the_pending_hide(card, monkeypatch):
    answer.show('Луна', False)
    monkeypatch.setattr(answer, '_speech_busy', lambda: True)
    answer.hide(0)
    answer.show('Марс', False)
    time.sleep(0.15)
    assert answer.snapshot()['visible'] is True


def test_the_user_can_dismiss_it(card):
    answer.show('Луна', False)
    assert bridge.run_command('answer', {'op': 'close'}) == {'ok': True}
    assert last(card)['visible'] is False and bridge.run_command('answer', {'op': 'x'})['ok'] is False


def test_the_old_window_is_used_unless_the_new_one_is_connected(card, monkeypatch):
    class Hub:
        def __init__(self, on):
            self.on = on

        def has_clients(self):
            return self.on
    monkeypatch.setattr(bridge, '_hub', None)
    assert bridge.answer_event('show', 'x', False) is False
    monkeypatch.setattr(bridge, '_hub', Hub(False))
    assert bridge.answer_event('show', 'x', False) is False
    monkeypatch.setattr(bridge, '_hub', Hub(True))
    assert bridge.answer_event('show', 'x', False) is True and answer.snapshot()['visible']
    assert bridge.answer_event('nope') is False


def test_the_core_functions_reach_the_card(card, monkeypatch):
    from ui_next import host
    taken = []
    monkeypatch.setattr(bridge, 'answer_event', lambda kind, *a: taken.append((kind, a)) or True)
    host.update_ai_window_text('x')
    host.set_ai_window_image('p.png')
    host.set_ai_window_video('v.mp4')
    host.hide_ai_window(0)
    host.cancel_hide_ai_window()
    host.show_ai_window('Марс', False)
    assert [k for k, _a in taken] == ['text', 'image', 'video', 'hide', 'cancel_hide', 'show']
    assert taken[-1][1] == ('Марс', False)


def test_the_card_can_be_switched_off_in_settings(card, monkeypatch):
    from core import settings_io
    from ui_next import host
    taken = []
    monkeypatch.setattr(bridge, 'answer_event', lambda kind, *a: taken.append(kind) or True)
    monkeypatch.setattr(settings_io, 'read', lambda: {'ai_mini_window': False})
    host.show_ai_window('Марс')
    assert taken == []


def test_speech_markup_is_not_shown_on_the_card(card):
    answer.show('Марс', False)
    answer.set_text('Марс — пустыня. <break time="300ms"/> Выживание *крайне* сложно.')
    assert last(card)['text'] == 'Марс — пустыня.  Выживание крайне сложно.'
