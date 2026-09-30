"""Second batch of interactive-state regression tests (see also
test_interactive_states.py and test_llm_action_confirm.py). Covers the
remaining states that had zero coverage: yt_pick ordinal parsing, note/
google/translate/cinema/game confirmation flows, and rest_hours_ask's
duration parsing — plus qa_clarify's synchronous pre-LLM branches (cancel,
wake-word wait, intent reroute, non-question filter); the actual streaming
LLM call inside qa_clarify's background thread is out of scope here, same as
it was already out of scope for the pre-existing QA test suite.
"""
import core.handler.interactive as interactive
from core.handler.interactive import _parse_yt_pick_ordinal


class _FakeHandler:
    def __init__(self, state, data=None):
        self.interactive_state = state
        self.interactive_data = data or {}
        self.handle_calls = []
        self.spoken = []
        self.play_response_calls = []
        self.launched_games = []

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data or {}

    def handle(self, cmd, text):
        self.handle_calls.append((cmd, text))

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))

    def _launch_game_engine(self, game_info):
        self.launched_games.append(game_info)


class _ImmediateThread:
    """Runs the target synchronously instead of on a real thread, so tests
    can assert on side effects deterministically without sleeps/races."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _no_semantic(monkeypatch, global_cmd=''):
    monkeypatch.setattr(interactive, '_sem_cmd', lambda *a, **k: global_cmd)


def _immediate_threads(monkeypatch):
    monkeypatch.setattr(interactive.threading, 'Thread', _ImmediateThread)


# ── _parse_yt_pick_ordinal (pure function) ───────────────────────────────

def test_yt_pick_ordinal_exact_word_match():
    assert _parse_yt_pick_ordinal(['открой', 'первое']) == 0


def test_yt_pick_ordinal_exact_digit_match():
    assert _parse_yt_pick_ordinal(['3']) == 2


def test_yt_pick_ordinal_ukrainian_word():
    assert _parse_yt_pick_ordinal(['друге']) == 1


def test_yt_pick_ordinal_fuzzy_fallback_for_misheard_word():
    # 'третье' slightly mangled by STT
    assert _parse_yt_pick_ordinal(['третьи']) == 2


def test_yt_pick_ordinal_returns_none_for_unrelated_words():
    assert _parse_yt_pick_ordinal(['включи', 'музыку']) is None


def test_yt_pick_ordinal_ignores_short_words_in_fuzzy_pass():
    # No exact match and every word is under the length-3 fuzzy floor
    assert _parse_yt_pick_ordinal(['ну', 'то']) is None


# ── note_ask ──────────────────────────────────────────────────────────────

def test_note_ask_saves_note_on_valid_text(monkeypatch):
    _no_semantic(monkeypatch)
    saved = []
    monkeypatch.setattr('actions.notes.save_note', lambda note: saved.append(note) or True)
    handler = _FakeHandler('note_ask', {})

    interactive.handle_interactive(handler, 'купить молоко')

    assert saved == ['купить молоко']
    assert handler.play_response_calls
    assert handler.interactive_state is None


def test_note_ask_empty_text_keeps_waiting(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('note_ask', {})

    interactive.handle_interactive(handler, '   ')

    assert handler.interactive_state == 'note_ask'


# ── google_ask ────────────────────────────────────────────────────────────

def test_google_ask_opens_encoded_search_url(monkeypatch):
    _no_semantic(monkeypatch)
    opened = []
    monkeypatch.setattr('webbrowser.open', lambda url: opened.append(url))
    handler = _FakeHandler('google_ask', {})

    interactive.handle_interactive(handler, 'погода в берлине')

    assert len(opened) == 1
    assert 'google.com/search?q=' in opened[0]
    assert '%D0%BF%D0%BE%D0%B3%D0%BE%D0%B4%D0%B0' in opened[0]  # 'погода' percent-encoded
    assert handler.interactive_state is None


def test_google_ask_cancel_word_does_not_open_browser(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('webbrowser.open',
                         lambda url: (_ for _ in ()).throw(AssertionError('must not open')))
    handler = _FakeHandler('google_ask', {})

    interactive.handle_interactive(handler, 'отмена')

    assert handler.interactive_state is None


# ── translate_ask ─────────────────────────────────────────────────────────

def test_translate_ask_parses_query_and_target_language(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)

    class _Resp:
        def json(self):
            return {'responseData': {'translatedText': 'hello'}}

    monkeypatch.setattr('requests.get', lambda url, timeout=5: _Resp())
    handler = _FakeHandler('translate_ask', {})

    interactive.handle_interactive(handler, 'привет как дела на английский')

    assert handler.spoken and 'hello' in handler.spoken[0]
    assert handler.interactive_state is None


def test_translate_ask_defaults_to_english_without_na_clause(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)
    captured_urls = []

    class _Resp:
        def json(self):
            return {'responseData': {'translatedText': 'ok'}}

    def _get(url, timeout=5):
        captured_urls.append(url)
        return _Resp()

    monkeypatch.setattr('requests.get', _get)
    handler = _FakeHandler('translate_ask', {})

    interactive.handle_interactive(handler, 'привет')

    assert captured_urls and 'langpair=ru|en' in captured_urls[0]


# ── cinema_ask ────────────────────────────────────────────────────────────

def test_cinema_ask_searches_for_title(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)
    searched = []
    monkeypatch.setattr('features.cinema.watch_media',
                         lambda t, s, sn, ep: searched.append((t, s, sn, ep)) or (True, 'http://x'))
    handler = _FakeHandler('cinema_ask', {'is_series': False})

    interactive.handle_interactive(handler, 'интерстеллар')

    assert searched == [('интерстеллар', False, 1, 1)]
    assert handler.interactive_state is None


# ── game_watcher_suggest ──────────────────────────────────────────────────

def test_game_watcher_suggest_yes_applies_profile(monkeypatch):
    _no_semantic(monkeypatch)
    applied = []
    monkeypatch.setattr('core.handler.commands.game.apply_game_profile',
                         lambda handler, profile, name: applied.append((profile, name)))
    handler = _FakeHandler('game_watcher_suggest', {'profile': 'ets2', 'name': 'Euro Truck Simulator 2'})

    interactive.handle_interactive(handler, 'да')

    assert applied == [('ets2', 'Euro Truck Simulator 2')]
    assert handler.interactive_state is None


def test_game_watcher_suggest_no_declines_without_applying(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('core.handler.commands.game.apply_game_profile',
                         lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not apply')))
    handler = _FakeHandler('game_watcher_suggest', {'profile': 'ets2', 'name': 'ETS2'})

    interactive.handle_interactive(handler, 'нет')

    assert handler.interactive_state is None


def test_game_watcher_suggest_ambiguous_reply_keeps_waiting(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('game_watcher_suggest', {'profile': 'ets2', 'name': 'ETS2'})

    # Deliberately avoids any token in yes_words/no_words (including 'не').
    interactive.handle_interactive(handler, 'что-то совсем другое сейчас')

    assert handler.interactive_state == 'game_watcher_suggest'


# ── game_confirm ──────────────────────────────────────────────────────────

def test_game_confirm_yes_launches_pending_game(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('game_confirm', {'game_name': 'ETS2', 'game_uri': 'steam://x', 'install_dir': 'C:/x'})

    interactive.handle_interactive(handler, 'да')

    assert len(handler.launched_games) == 1
    assert handler.launched_games[0].name == 'ETS2'
    assert handler.interactive_state is None


def test_game_confirm_no_asks_which_game_instead(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('game_confirm', {'games': ['ETS2', 'ATS']})

    interactive.handle_interactive(handler, 'нет')

    assert handler.launched_games == []
    assert handler.interactive_state == 'game_specific'


def test_game_confirm_fuzzy_matches_a_different_named_game(monkeypatch):
    from features.gaming import GameInfo
    _no_semantic(monkeypatch)
    found_game = GameInfo(name='Planetbase', launcher='', launch_uri='', install_dir='')
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: found_game)
    handler = _FakeHandler('game_confirm', {'games': ['Planetbase']})

    interactive.handle_interactive(handler, 'планетбейс')

    assert len(handler.launched_games) == 1
    assert handler.launched_games[0].name == 'Planetbase'


def test_game_confirm_no_match_apologizes_and_clears_state(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: None)
    handler = _FakeHandler('game_confirm', {'games': ['ETS2']})

    interactive.handle_interactive(handler, 'что-то совсем другое')

    assert handler.launched_games == []
    assert handler.interactive_state is None


# ── rest_hours_ask ────────────────────────────────────────────────────────

def test_rest_hours_ask_parses_number_from_text(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)
    called = []
    monkeypatch.setattr('core.engine.ets2_commands._confirm_rest_duration',
                         lambda hours: called.append(hours))
    handler = _FakeHandler('rest_hours_ask', {})

    interactive.handle_interactive(handler, '7 часов')

    assert called == [7]


def test_rest_hours_ask_clamps_out_of_range_number(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)
    called = []
    monkeypatch.setattr('core.engine.ets2_commands._confirm_rest_duration',
                         lambda hours: called.append(hours))
    handler = _FakeHandler('rest_hours_ask', {})

    interactive.handle_interactive(handler, '99 часов')

    assert called == [24]  # clamped to the 1-24 valid range


def test_rest_hours_ask_defaults_to_nine_when_unparseable(monkeypatch):
    _no_semantic(monkeypatch)
    _immediate_threads(monkeypatch)
    called = []
    monkeypatch.setattr('core.engine.ets2_commands._confirm_rest_duration',
                         lambda hours: called.append(hours))
    handler = _FakeHandler('rest_hours_ask', {})

    interactive.handle_interactive(handler, 'не знаю сколько')

    assert called == [9]


# ── qa_clarify (synchronous pre-LLM branches only) ───────────────────────

def test_qa_clarify_cancel_word_clears_state(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('qa_clarify', {})

    interactive.handle_interactive(handler, 'спасибо')

    assert handler.interactive_state is None
    assert handler.play_response_calls


def test_qa_clarify_reroutes_to_a_different_recognized_intent(monkeypatch):
    # If the follow-up text actually matches a different real command,
    # qa_clarify must hand off to it instead of treating it as a question.
    _no_semantic(monkeypatch, global_cmd='open_browser')
    handler = _FakeHandler('qa_clarify', {})

    interactive.handle_interactive(handler, 'открой браузер')

    assert handler.handle_calls == [('open_browser', 'открой браузер')]
    assert handler.interactive_state is None


def test_qa_clarify_non_question_keeps_waiting_without_calling_llm(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('features.qa.is_real_question', lambda text: False)
    handler = _FakeHandler('qa_clarify', {})

    interactive.handle_interactive(handler, 'угу ладно')

    assert handler.interactive_state == 'qa_clarify'


# ── game_launcher_choice / game_specific ──────────────────────────────────

_LAUNCHERS = {'Steam': 'C:/steam.exe', 'Epic Games': 'C:/epic.exe'}


def _spy_open_launcher(monkeypatch):
    opened = []
    monkeypatch.setattr('core.handler.commands.game.open_launcher_and_suggest',
                        lambda handler, name, path: opened.append((name, path)))
    return opened


def test_launcher_choice_recognizes_steam_from_stt_spelling(monkeypatch):
    _no_semantic(monkeypatch)
    opened = _spy_open_launcher(monkeypatch)
    handler = _FakeHandler('game_launcher_choice', {'launchers': _LAUNCHERS})

    interactive.handle_interactive(handler, 'стим')

    assert opened == [('Steam', 'C:/steam.exe')]
    assert handler.interactive_state is None


def test_launcher_choice_recognizes_epic(monkeypatch):
    _no_semantic(monkeypatch)
    opened = _spy_open_launcher(monkeypatch)
    handler = _FakeHandler('game_launcher_choice', {'launchers': _LAUNCHERS})

    interactive.handle_interactive(handler, 'эпик геймс')

    assert opened == [('Epic Games', 'C:/epic.exe')]


def test_launcher_choice_accepts_a_game_name_instead(monkeypatch):
    from features.gaming import GameInfo
    _no_semantic(monkeypatch)
    opened = _spy_open_launcher(monkeypatch)
    game = GameInfo(name='Planetbase', launcher='', launch_uri='', install_dir='')
    monkeypatch.setattr('features.gaming.scan_all_games', lambda: [game])
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: game)
    handler = _FakeHandler('game_launcher_choice', {'launchers': _LAUNCHERS})

    interactive.handle_interactive(handler, 'планетбейс')

    assert opened == []
    assert [g.name for g in handler.launched_games] == ['Planetbase']


def test_launcher_choice_unrecognized_keeps_waiting(monkeypatch):
    _no_semantic(monkeypatch)
    opened = _spy_open_launcher(monkeypatch)
    monkeypatch.setattr('features.gaming.scan_all_games', lambda: [])
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: None)
    spoken = []
    monkeypatch.setattr(interactive, 'speak', spoken.append)
    handler = _FakeHandler('game_launcher_choice', {'launchers': _LAUNCHERS})

    interactive.handle_interactive(handler, 'бла бла')

    assert opened == [] and handler.launched_games == []
    assert handler.interactive_state == 'game_launcher_choice'
    assert spoken and 'платформ' in spoken[0]


def test_launcher_choice_cancel_clears_state(monkeypatch):
    _no_semantic(monkeypatch)
    opened = _spy_open_launcher(monkeypatch)
    handler = _FakeHandler('game_launcher_choice', {'launchers': _LAUNCHERS})

    interactive.handle_interactive(handler, 'отмена')

    assert opened == [] and handler.interactive_state is None


def test_game_specific_launches_named_game(monkeypatch):
    from features.gaming import GameInfo
    _no_semantic(monkeypatch)
    game = GameInfo(name='Planetbase', launcher='', launch_uri='', install_dir='')
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: game)
    handler = _FakeHandler('game_specific', {'games': [game]})

    interactive.handle_interactive(handler, 'планетбейс')

    assert [g.name for g in handler.launched_games] == ['Planetbase']
    assert handler.interactive_state is None


def test_game_specific_unknown_game_clears_state(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('features.gaming.fuzzy_find_game', lambda games, text: None)
    handler = _FakeHandler('game_specific', {'games': []})

    interactive.handle_interactive(handler, 'что-то другое')

    assert handler.launched_games == [] and handler.interactive_state is None
