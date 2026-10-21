"""Lock / sleep, any-player track keys and the spoken calculator: phrase matching, the arithmetic parser and the handlers (OS calls mocked)."""
import pytest

import core.handler.commands.info as info_cmd
import core.handler.commands.system as sys_cmd
from core.nlp.calc import evaluate, spoken
from core.nlp.commands import _match_command_inner


class _Handler:
    def __init__(self):
        self.spoken, self.handled, self.responses = [], [], 0

    def speak(self, text, wait=False):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.responses += 1

    def handle(self, cmd, text):
        self.handled.append((cmd, text))


@pytest.mark.parametrize('phrase,cmd', [
    ('заблокируй компьютер', 'lock_pc'), ('заблокируй экран', 'lock_pc'), ('заблокируй клавиатуру', 'keyboard_lock'),
    ('спящий режим', 'sleep_pc'), ('усыпи компьютер', 'sleep_pc'),
    ('следующий трек', 'media_next'), ('предыдущая песня', 'media_prev'), ('следующее видео', 'yt_next'),
    ('сколько будет 15 умножить на 7', 'calc'), ('посчитай 3 плюс 4', 'calc'),
])
def test_phrases_resolve_to_the_right_command(phrase, cmd):
    assert _match_command_inner(phrase, 75) == cmd


@pytest.mark.parametrize('text,result', [
    ('сколько будет 15 умножить на 7', '105'),
    ('сколько будет двадцать пять плюс сорок три', '68'),
    ('посчитай 100 разделить на 8', '12,5'),
    ('сколько будет 20 процентов от 150', '30'),
    ('сколько будет 2 плюс 3 умножить на 4', '14'),
    ('сколько будет (2 плюс 3) умножить на 4', '20'),
    ('скільки буде 12 мінус 5', '7'),
])
def test_calc_evaluates_spoken_arithmetic(text, result):
    assert spoken(evaluate(text)) == result


@pytest.mark.parametrize('text', ['сколько будет лететь до луны', 'сколько будет 5', 'посчитай', '__import__ плюс 1'])
def test_calc_ignores_phrases_without_arithmetic(text):
    assert evaluate(text) is None


def test_calc_division_by_zero_is_reported_not_swallowed():
    with pytest.raises(ZeroDivisionError):
        evaluate('сколько будет 10 разделить на 0')


def test_calc_handler_speaks_the_result_and_guards_the_chat_fallback(monkeypatch):
    h = _Handler()
    info_cmd._calc(h, 'cmd', 'сколько будет 15 умножить на 7')
    assert '105' in h.spoken[-1]

    monkeypatch.setattr(info_cmd, '_calc_fallback', [0.0])
    info_cmd._calc(h, 'cmd', 'сколько будет лететь до луны')
    assert h.handled == [('llm_chat', 'сколько будет лететь до луны')]
    info_cmd._calc(h, 'cmd', 'сколько будет лететь до луны')   # a second miss right away must not loop through chat
    assert len(h.handled) == 1


def test_lock_and_sleep_confirm_first_then_call_the_os(monkeypatch):
    fired = []

    class _Timer:
        def __init__(self, delay, fn): self.fn = fn
        def start(self): fired.append(self.fn.__name__)

    monkeypatch.setattr(sys_cmd.threading, 'Timer', _Timer)
    h = _Handler()
    sys_cmd._sys_lock_pc(h, 'заблокируй компьютер', 0)
    sys_cmd._sys_sleep_pc(h, 'спящий режим', 0)
    assert h.responses == 2 and fired == ['lock_pc', 'sleep_pc']


def test_new_commands_are_registered_in_dispatch_and_catalog():
    from core.handler import dispatch
    from ui_next.bridge import catalog
    for cmd in ('lock_pc', 'sleep_pc', 'calc'):
        assert cmd in dispatch._EXACT
    assert catalog._CAT_OF['lock_pc'] == 'pc' and catalog._CAT_OF['calc'] == 'assistant'


@pytest.mark.parametrize('said,want', [('двести двадцать пять минус сто пятьдесят два', 73), ('сколько будет сто пятьдесят два плюс сто тридцать три', 285),
                                       ('две тысячи пятьсот плюс тысяча', 3500), ('одиннадцать плюс двадцать один', 32), ("скільки буде двісті п'ятдесят мінус сто", 150),
                                       ('сто двадцать пять разделить на пять', 25)])
def test_calc_composes_spoken_numbers(said, want):
    from core.nlp.calc import evaluate
    assert evaluate(said) == want


def test_calc_continues_the_last_answer_and_expires():
    from core.nlp import calc
    calc.forget_result()
    assert calc.route('и плюс сто тридцать три') is None            # nothing to continue
    assert calc.route('двести двадцать пять минус сто пятьдесят два') == ('calc', 'двести двадцать пять минус сто пятьдесят два')
    calc.remember_result(73)
    cmd, phrase = calc.route('и плюс сто тридцать три')
    assert (cmd, calc.evaluate(phrase)) == ('calc', 206)
    calc.remember_result(206)
    assert calc.evaluate(calc.route('умножить на два')[1]) == 412
    assert calc.route('а теперь разделить на ноль')[0] == 'calc'      # the handler reports the division by zero
    calc._last = (73, calc._last[1] - calc.TTL - 1)
    assert calc.route('и плюс сто') is None
    calc.forget_result()


@pytest.mark.parametrize('said', ['13:15', 'громкость плюс десять', 'плюс сто', 'сколько лететь до луны', 'двадцать пять двадцать'])
def test_route_ignores_what_is_not_arithmetic(said):
    from core.nlp import calc
    calc.forget_result()
    assert calc.route(said) is None


def test_calc_handler_remembers_the_result(monkeypatch):
    from core.handler.commands import info
    from core.nlp import calc
    calc.forget_result()
    said = []
    h = type('H', (), {'speak': lambda self, t, **k: said.append(t)})()
    info._calc(h, 'calc', 'сколько будет двести двадцать пять минус сто пятьдесят два')
    assert calc._last[0] == 73
    calc.forget_result()
