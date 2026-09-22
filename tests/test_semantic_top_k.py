"""Regression tests for SemanticIntentClassifier.top_k_candidates() —
added for the local-LLM function-calling fallback (core/speech/llm_chat.py)
to narrow the ~270-intent action space down to a short, embedding-relevant
list instead of pasting every intent name into one prompt.
"""
from core.nlp.semantic import top_k_candidates


def test_top_k_returns_requested_count():
    result = top_k_candidates('сделай тише', k=5)
    assert len(result) == 5


def test_top_k_never_includes_reported_speech():
    # 'reported_speech' is a real centroid (it's how the OOD filter learns
    # framing like "он сказал выключи компьютер"), but it isn't an
    # executable action and must never be offered to the LLM as one.
    for phrase in ['он сказал выключи компьютер', 'сделай тише', 'открой браузер']:
        result = top_k_candidates(phrase, k=10)
        assert 'reported_speech' not in result


def test_top_k_returns_relevant_candidate_for_a_clear_command():
    # Doesn't need to be the top-1 (that's classify_intent's job), just
    # present somewhere in the short candidate list.
    result = top_k_candidates('создай мне новую папку на рабочем столе', k=6)
    assert 'create_folder' in result


def test_top_k_candidates_are_all_real_intents():
    from core.nlp.intents import INTENTS
    result = top_k_candidates('выключи компьютер', k=8)
    assert all(name in INTENTS for name in result)


def test_top_k_recall_on_realistic_phrasings():
    """Empirical regression guard for llm_chat._TOP_K=6 (see the comment
    there for the full k-sweep this is based on). Uses realistic phrasings,
    not intents.py's own anchors, so it actually measures retrieval quality
    instead of trivially passing. Threshold is set a few points under the
    measured 90.2% baseline so normal anchor-list tweaks don't flake this,
    while a real quality regression still fails it.
    """
    cases = [
        ("перезагрузи комп", "restart"),
        ("убавь звук чутка", "vol_down"),
        ("сделай яркость поменьше", "brightness_down"),
        ("выключи через 20 минут комп", "shutdown_timer"),
        ("напомни через полчаса про звонок", "reminder"),
        ("удали эту папку", "delete_folder"),
        ("сотри этот файл", "delete_file"),
        ("почисти корзину", "empty_trash"),
        ("запусти дискорд", "open_discord"),
        ("открой ворд", "open_word"),
        ("закрой вообще все окна", "close_all_win"),
        ("сверни всё что открыто", "min_all"),
        ("включи вайфай", "wifi_toggle"),
        ("отключи блютуз", "bluetooth_toggle"),
        ("поставь таймер на пять минут", "timer_set"),
        ("отмени таймер", "timer_cancel"),
        ("который час", "time_now"),
        ("как ты себя чувствуешь", "how_are_you"),
        ("ты тупой", "system_insult"),
        ("сделай скриншот экрана", "screenshot"),
        ("запиши эту мысль в заметки", "note_save"),
        ("почисти систему от мусора", "system_cleanup"),
        ("заблокируй клавиатуру", "keyboard_lock"),
        ("проверь скорость интернета", "internet_speed"),
        ("включи охрану", "guard_on"),
        ("поставь громкость на максимум", "vol_max"),
        ("выйди из джарвиса совсем", "jarvis_exit"),
        ("перезапусти джарвиса", "restart_jarvis"),
        ("выведи курс доллара", "currency_rate"),
        ("найди файл с отчётом", "find_file"),
        ("перейди в папку загрузки", "cd_folder"),
        ("проверь есть ли новые письма", "inbox_unread"),
    ]
    hits = sum(1 for phrase, expected in cases if expected in top_k_candidates(phrase, k=6))
    recall = hits / len(cases)
    assert recall >= 0.80, f'top_k(k=6) recall dropped to {recall:.1%} on the realistic-phrasing benchmark'


def test_top_k_surfaces_reminder_for_duration_phrases():
    # Regression: 'reminder' used to have only 2 sparse anchors
    # ('напомни мне'/'нагадай мені'), so a duration-bearing phrase like this
    # never retrieved it even at k=15 — 'timer_add'/'timer_set' (a different
    # feature, actions/game_timer.py) dominated instead. Fixed by adding
    # richer duration-specific anchors in core/nlp/intents.py.
    result = top_k_candidates('напомни через 10 минут выпить воды', k=6)
    assert 'reminder' in result
