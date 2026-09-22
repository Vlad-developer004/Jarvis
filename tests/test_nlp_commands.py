"""Unit tests for the keyword/fuzzy intent matcher in core/nlp/commands.py.

Several of these are regression tests for bugs found and fixed in this
project's 2026-09 file-split pass, where a name got left behind in the
module it moved out of:
  - _INSULT (moved to commands_data.py, commands.py forgot to import it)
  - reactor_color_* all collapsing onto reactor_color_red (an OR-based
    'keywords' match instead of an AND-gated 'require_words' match)
"""
from core.nlp.commands import (
    match_command,
    normalize_numbers,
    extract_amount,
    extract_duration_seconds,
)
from core.i18n import set_language


def test_reminder_matches_with_text_between_napomni_and_cherez():
    # Regression: 'reminder' only had a multi-word extra ('напомни через'),
    # so real phrasing like "напомни ВЫПИТЬ ТАБЛЕТКИ через 5 минут" broke the
    # keyword/extras match (extras require the literal phrase as a substring)
    # and fell through to fuzzy matching, which also missed the min_score.
    assert match_command('напомни выпить таблетки через пять минут') == 'reminder'
    assert match_command('напомни через 10 минут') == 'reminder'


def test_reminder_fix_does_not_hijack_shutdown_timer():
    # 'через' alone as an extra must not make unrelated 'X через N минут'
    # phrases resolve to reminder just because they share that one word.
    assert match_command('выключи через 10 минут') == 'shutdown_timer'


def test_insult_detection_returns_system_insult():
    # 'тормоз' is not a CANON_SIMPLE exact key, so this only resolves
    # correctly if the insult-detection branch's `_INSULT` name is bound.
    assert match_command('джарвис ты тормоз') == 'system_insult'


def test_insult_requires_being_directed_at_jarvis():
    # No wake word, doesn't start with 'ты ' either -> not directed.
    assert match_command('какой сегодня тормоз в пробке') != 'system_insult'


def test_reactor_colors_are_distinct_not_all_red():
    cases = {
        'сделай реактор красным': 'reactor_color_red',
        'сделай реактор синим': 'reactor_color_cyan',
        'сделай реактор зелёным': 'reactor_color_green',
        'сделай реактор жёлтым': 'reactor_color_amber',
        'сделай реактор фиолетовым': 'reactor_color_magenta',
        'сделай реактор белым': 'reactor_color_white',
    }
    for phrase, expected in cases.items():
        assert match_command(phrase) == expected, phrase


def test_reactor_effects_require_the_word_reactor():
    # 'require_words' is an AND-gate distinct from the OR-based 'keywords' —
    # the bare color word alone must not fire the reactor command.
    assert match_command('сделай красным') != 'reactor_color_red'


def test_reactor_pulse_and_glitch():
    assert match_command('пульс реактора') == 'reactor_pulse'
    assert match_command('тряхни реактор') == 'reactor_glitch'


def test_normalize_numbers_word_to_digit():
    assert normalize_numbers('поставь таймер на пять минут') == 'поставь таймер на 5 минут'


def test_normalize_numbers_compound_tens():
    # 'двадцать один' -> '21' (tens + units combined into one token)
    assert normalize_numbers('двадцать один') == '21'


def test_normalize_numbers_leaves_plain_digits_alone():
    assert normalize_numbers('открой файл номер 3') == 'открой файл номер 3'


def test_extract_amount_defaults_to_five_without_digits():
    assert extract_amount('открой недавние файлы') == 5


def test_extract_amount_sums_digits_found():
    assert extract_amount('покажи 3 файла') == 3


def test_extract_duration_seconds_half_hour():
    assert extract_duration_seconds('поставь таймер на полчаса') == 1800


def test_extract_duration_seconds_half_minute():
    assert extract_duration_seconds('подожди полминуты') == 30


def test_wake_word_variants_all_resolve_to_wake():
    # 'бобик' was removed as a wake word by explicit request — only 'джарвис'
    # itself is a real wake word now. Near-misspellings like 'джервис' still
    # resolve via the fuzzy fallback (Levenshtein distance to the 'джарвис'
    # CANON_SIMPLE key), which is separate from having their own dict entry.
    for phrase in ('джарвис', 'джервис', 'дарвис'):
        assert match_command(phrase) == 'wake', phrase
    assert match_command('бобик') != 'wake'


def test_finish_work_exits_jarvis_not_starts_a_work_session():
    # Regression: "заверши работу" used to fuzzy-match 'work_session'
    # ('за работу'/'начнём работу') over the longer, correct
    # 'завершить работу джарвиса' -> jarvis_exit key, because an exact
    # word match on a 2-word CANON key scored higher than a 3-word one
    # missing 'джарвиса'. Now an explicit CANON_SIMPLE entry.
    for phrase in ('заверши работу', 'закончи работу', 'закончил работу', 'завершил работу'):
        assert match_command(phrase) == 'jarvis_exit', phrase
    # Starting a work session must still work exactly as before.
    for phrase in ('начнём работу', 'за работу', 'открой проект'):
        assert match_command(phrase) == 'work_session', phrase


def test_finish_work_ukrainian():
    set_language('uk')
    try:
        for phrase in ('заверши роботу', 'закінчи роботу'):
            assert match_command(phrase) == 'jarvis_exit', phrase
        assert match_command('до роботи') == 'work_session'
    finally:
        set_language('ru')


def test_media_pause_ukrainian_language_switch():
    # CANON_SIMPLE vs CANON_SIMPLE_UK is selected via core.i18n.get_language();
    # sanity-check both tables actually resolve independently.
    set_language('ru')
    assert match_command('стоп') == 'media_pause'
    set_language('uk')
    assert match_command('стоп') == 'media_pause'


def test_nasa_apod_requires_nasa_keyword():
    assert match_command('покажи картинку дня от наса') == 'nasa_apod'
    assert match_command('снимок дня наса') == 'nasa_apod'
    # require_words gate: no 'наса'/'nasa' in the phrase -> must not fire.
    assert match_command('что сегодня в космосе') != 'nasa_apod'


def test_unrecognized_gibberish_returns_empty_string():
    assert match_command('фыв ыпаолдж ячсимть') == ''


def test_open_deck_command_base_discoverable_by_voice():
    # The command database ("Колода"/deck.py, opened only via a HUD button
    # until now) needs a voice trigger distinct from 'что ты умеешь', which
    # was already claimed by show_help (the welcome/intro dialog) — the two
    # phrases must resolve to different destinations.
    assert match_command('покажи все команды') == 'open_deck'
    assert match_command('база команд') == 'open_deck'
    assert match_command('что ты умеешь') == 'show_help'


def test_open_deck_command_base_discoverable_by_voice_ukrainian():
    set_language('uk')
    try:
        assert match_command('покажи всі команди') == 'open_deck'
        assert match_command('база команд') == 'open_deck'
        assert match_command('що ти вмієш') == 'show_help'
    finally:
        set_language('ru')


def test_empty_text_returns_empty_string():
    assert match_command('') == ''


def test_youtube_candidates_ambiguous_when_titles_match():
    from actions.youtube import candidates_are_ambiguous
    candidates = [
        {'title': 'Imagine Dragons - Believer (Official Music Video)'},
        {'title': 'Imagine Dragons - Believer (Lyrics)'},
        {'title': "Imagine Dragons - Believer | One Voice Children's Choir | Kids Cover"},
    ]
    assert candidates_are_ambiguous(candidates) is True


def test_youtube_candidates_not_ambiguous_when_top_result_is_distinct():
    from actions.youtube import candidates_are_ambiguous
    candidates = [
        {'title': 'How to bake bread'},
        {'title': 'Cat compilation 2024'},
        {'title': 'Learn guitar in 10 minutes'},
    ]
    assert candidates_are_ambiguous(candidates) is False


def test_youtube_candidates_ambiguous_false_for_single_result():
    from actions.youtube import candidates_are_ambiguous
    assert candidates_are_ambiguous([{'title': 'Only One'}]) is False
    assert candidates_are_ambiguous([]) is False


def test_yt_pick_ordinals_cover_ru_and_uk_first_five():
    from core.handler.interactive import _YT_PICK_ORDINALS
    for word, idx in [('первое', 0), ('второе', 1), ('третье', 2), ('четвертое', 3), ('пятое', 4),
                       ('перше', 0), ('друге', 1), ('третє', 2)]:
        assert _YT_PICK_ORDINALS[word] == idx


def test_long_unrelated_phrase_not_fuzzy_matched_to_short_app_command():
    """Regression (found 2026-09-22 during manual testing): "открой автор
    эффектс" (After Effects — not a registered app) was misrecognized as
    'open_obs' because the final token_set_ratio fallback scored purely off
    the shared verb 'открой', even though 'обс' never appears in the phrase
    at all. An unregistered app must not silently launch something else.
    """
    assert match_command('открой автор эффектс') == ''
    assert match_command('открой афтер эффектс') == ''
    # Real short-key app commands must still resolve correctly
    assert match_command('открой обс') == 'open_obs'
    assert match_command('запусти обс') == 'open_obs'
    assert match_command('открой ворд') == 'open_word'
    assert match_command('открой дискорд') == 'open_discord'


def test_reminder_not_confused_with_note_save():
    """Regression (found 2026-09-22): 'напомни мне' resolved to 'note_save'
    instead of 'reminder'. Two independent causes, both fixed:
      1. 'мне' is a stripped filler word, so "напомни мне" collapsed to
         "напомни" (7 chars) — Levenshtein-distance 1 from 'запомни'
         (note_save's canon key), well inside the 20% typo-correction
         threshold despite being a different real word, not a misspelling.
      2. Russian CANON_SIMPLE had no bare 'напомни'/'напомни мне' key at
         all (only the Ukrainian dict had 'нагадай': 'reminder'), so even
         past the Levenshtein guard, fuzzy token_set_ratio fell back to
         'запомни' as the closest candidate.
    """
    assert match_command('напомни мне') == 'reminder'
    assert match_command('напомни') == 'reminder'
    assert match_command('напомни через 10 минут выпить воды') == 'reminder'
    # note_save itself must still resolve correctly — not collateral damage
    assert match_command('запомни это') == 'note_save'
    assert match_command('запиши идею') == 'note_save'
