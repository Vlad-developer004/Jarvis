"""Regression test for normalize_for_tts()'s number-to-word conversion not
applying the case a preposition governs.

Before this fix, "до 19 градусов" ('up to 19 degrees') was spoken as "до
девятнадцать градусов" — bare nominative "девятнадцать" instead of the
genitive "девятнадцати" that "до" requires. The noun ("градусов") was
already correct (Russian's quantifier-agreement rule happens to produce the
same genitive-plural form there regardless of the governing case), so only
the cardinal number word itself needed the fix.
"""
from core.speech.tts import normalize_for_tts


def test_do_preposition_inflects_number_to_genitive():
    result = normalize_for_tts('днем поднимается температура до 19 градусов')
    assert 'до девятнадцати градусов' in result
    assert 'до девятнадцать' not in result


def test_ot_and_do_both_inflect_in_a_range():
    result = normalize_for_tts('от 10 до 15 градусов')
    assert result == 'от десяти до пятнадцати градусов'


def test_okolo_preposition_inflects_to_genitive():
    result = normalize_for_tts('температура около 5 градусов')
    assert 'около пяти градусов' in result


def test_number_without_governing_preposition_stays_nominative():
    # No preposition present — quantifier-agreement nominative is correct
    # here, must not be touched by the genitive-inflection logic.
    result = normalize_for_tts('осталось 3 задачи')
    assert result == 'осталось три задачи'


def test_unrelated_preposition_does_not_trigger_inflection():
    # 'через' isn't a genitive-governing preposition in this set — must not
    # be affected by the fix.
    result = normalize_for_tts('выключу компьютер через 10 минут')
    assert result == 'выключу компьютер через десять минут'


def test_okolo_with_hundred_inflects_to_genitive():
    # Regression: pymorphy3 returns "сто" as an indeclinable abbreviation
    # noun homonym (score-tied with its real NUMR reading) before the
    # actual numeral reading — an unfiltered first match "successfully"
    # inflects it to itself, so this used to come out as "около сто" instead
    # of the genitive "около ста". See _inflect_last's prefer_pos.
    result = normalize_for_tts('около 100 человек пришло')
    assert 'около ста' in result
    assert 'около сто ' not in result


def test_chelovek_stays_invariant_after_cardinal():
    # "человек" doesn't take its regular (suppletive) genitive plural
    # "людей" after a cardinal number — Russian keeps the invariant
    # counting form ("сто человек", never "сто людей").
    result = normalize_for_tts('пришло 100 человек')
    assert 'человек' in result
    assert 'людей' not in result
