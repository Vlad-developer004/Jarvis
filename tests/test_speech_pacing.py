"""Tests for core/speech/pacing.py — automatic pause/emphasis markup for game speech."""
import re

from core.speech.pacing import add_pauses
from core.speech.tts import _chunk_text, strip_speech_markup


def _breaks(text):
    return re.findall(r'<break time="(\d+)ms"/>', text)


def test_sentence_pause_is_longer_than_silero_natural_pause():
    out = add_pauses("Энергия на пределе. Осталось десять процентов заряда.")
    assert _breaks(out) == ["620"]  # natural Silero pause is ~400-560 ms; shorter would rush
    assert out.startswith("Энергия на пределе.") and out.endswith("Осталось десять процентов заряда.")


def test_short_single_phrase_is_untouched():
    assert add_pauses("Пауза.") == "Пауза."
    assert add_pauses("") == ""
    assert add_pauses("Сэр, всё спокойно.") == "Сэр, всё спокойно."


def test_commas_get_a_breath_only_in_long_sentences():
    long_text = "Топлива в баке хватит на дорогу, но через час стоит заправиться, чтобы не рисковать."
    assert _breaks(add_pauses(long_text)) == ["180", "180"]
    # comma directly after a short lead-in is left alone
    assert _breaks(add_pauses("Сэр, топлива в баке хватит на всю дорогу до самого пункта назначения.")) == []
    # short text: no comma breaks at all
    assert _breaks(add_pauses("Да, конечно, сделаю прямо сейчас.")) == []


def test_dash_gets_a_pause():
    out = add_pauses("Запас хода — триста километров, этого хватит доехать спокойно.")
    assert "320" in _breaks(out)


def test_decimals_and_units_are_not_split():
    text = "Скорость 62.5 км/ч и лимит 50 сейчас, превышение на 12.5 процента."
    assert "620" not in _breaks(add_pauses(text))


def test_idempotent_and_respects_existing_markup():
    marked = 'Первое предложение. <break time="250ms"/> Второе предложение здесь.'
    assert add_pauses(marked) == marked
    once = add_pauses("Первое предложение здесь. Второе предложение тоже.")
    assert add_pauses(once) == once


def test_existing_emphasis_is_left_alone():
    text = "Это *очень* важно. Внимание к деталям обязательно."
    assert add_pauses(text) == text


def test_one_emphasis_on_urgent_word_only():
    out = add_pauses("Внимание! Критическая нехватка энергии. Срочно постройте панель.")
    assert out.count("*") == 2 and "*Внимание*" in out
    calm = add_pauses("Зелёный код. Тревога снята, можно выдохнуть спокойно.")
    assert "*" not in calm


def test_break_budgets_are_capped():
    text = " ".join(f"Предложение номер {i} достаточно длинное, и в нём есть запятая для теста." for i in range(12))
    out = add_pauses(text)
    assert _breaks(out).count("620") == 5
    assert _breaks(out).count("180") <= 4


def test_stress_marks_and_plus_markers_survive():
    text = "Зап+ас х+ода — 300 килом+етров. Топливо ещё есть, мы не спеша доедем."
    out = add_pauses(text)
    assert "зап+ас" in out.lower() and "килом+етров" in out
    assert strip_speech_markup(out).count("+") == text.count("+")


def test_marked_text_survives_chunking_and_strips_cleanly():
    out = add_pauses("Внимание! Критическая нехватка энергии. Срочно постройте панель сейчас же.")
    chunks = _chunk_text(out)
    assert chunks and all(c.strip() for c in chunks)
    plain = strip_speech_markup(out)
    assert "<" not in plain and "*" not in plain
    assert "Критическая нехватка энергии." in plain


def test_no_double_spaces_around_breaks():
    out = add_pauses("Заряд накопителей просел до восьми процентов, стоит отключить лишнее прямо сейчас.")
    assert "  " not in out
