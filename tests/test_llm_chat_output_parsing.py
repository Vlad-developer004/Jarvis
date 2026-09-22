"""Unit tests for core/speech/llm_chat.py's response parsing and
confirmation-prompt logic — deliberately without loading a real GGUF model
(a fake llm.create_chat_completion() stands in), so these run fast and don't
depend on models/jarvis_llm/model.gguf existing on the test machine.
"""
import core.speech.llm_chat as llm_chat


class _FakeLlm:
    """Stands in for llama_cpp.Llama — records reset() calls, returns a
    canned completion regardless of the prompt."""

    def __init__(self, reply: str):
        self.reply = reply
        self.reset_calls = 0
        self.calls = []  # list of the 'messages' kwarg from each call

    def reset(self):
        self.reset_calls += 1

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs.get('messages'))
        return {'choices': [{'message': {'content': self.reply}}]}


def _model_with_fake_llm(monkeypatch, reply: str, candidates=('shutdown', 'vol_down')):
    model = llm_chat.LocalChatModel()
    fake = _FakeLlm(reply)
    model._llm = fake
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)
    # classify_or_chat does `from core.nlp.semantic import top_k_candidates`
    # as a local import, so the module attribute must be patched (patching
    # a name on llm_chat itself would have no effect — it's never imported
    # there at module scope).
    monkeypatch.setattr('core.nlp.semantic.top_k_candidates', lambda text, k: list(candidates))
    return model, fake


class _FakeStreamLlm:
    """Like _FakeLlm, but create_chat_completion(..., stream=True) returns
    an iterator of {'choices': [{'delta': {'content': <piece>}}]} chunks —
    the shape llama_cpp actually yields — splitting `reply` word-by-word so
    tests can observe sentence-boundary flushing across multiple chunks."""

    def __init__(self, reply: str):
        self.reply = reply
        self.reset_calls = 0
        self.calls = []

    def reset(self):
        self.reset_calls += 1

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs.get('messages'))
        if not kwargs.get('stream'):
            return {'choices': [{'message': {'content': self.reply}}]}
        words = self.reply.split(' ')
        def _gen():
            for i, w in enumerate(words):
                piece = w if i == 0 else ' ' + w
                yield {'choices': [{'delta': {'content': piece}}]}
        return _gen()


def _model_with_fake_stream_llm(monkeypatch, reply: str, candidates=('shutdown', 'vol_down')):
    model = llm_chat.LocalChatModel()
    fake = _FakeStreamLlm(reply)
    model._llm = fake
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)
    monkeypatch.setattr('core.nlp.semantic.top_k_candidates', lambda text, k: list(candidates))
    return model, fake


def test_classify_or_chat_parses_action_response(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ACTION: shutdown')

    kind, value = model.classify_or_chat('выруби уже этот ноутбук')

    assert (kind, value) == ('action', 'shutdown')
    assert fake.reset_calls == 1  # state-accumulation fix: reset() before every call


def test_classify_or_chat_parses_chat_response(monkeypatch):
    model, _ = _model_with_fake_llm(monkeypatch, 'CHAT: Привет! Всё в порядке.')

    kind, value = model.classify_or_chat('привет как дела')

    assert (kind, value) == ('chat', 'Привет! Всё в порядке.')


def test_classify_or_chat_rejects_action_name_outside_candidates(monkeypatch):
    # Grammar constrains generation to the candidate list already, but a
    # defensive check must still exist — never blindly trust the string.
    model, _ = _model_with_fake_llm(monkeypatch, 'ACTION: some_other_intent',
                                     candidates=('shutdown', 'vol_down'))

    kind, value = model.classify_or_chat('что-то невнятное')

    assert (kind, value) == ('chat', None)


def test_classify_or_chat_handles_malformed_output_without_raising(monkeypatch):
    model, _ = _model_with_fake_llm(monkeypatch, 'this is not a valid grammar output')

    kind, value = model.classify_or_chat('что-то невнятное')

    assert (kind, value) == ('chat', None)


def test_classify_or_chat_falls_back_to_chat_when_no_candidates(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ACTION: shutdown', candidates=())
    monkeypatch.setattr(model, 'generate', lambda text, on_chunk=None: 'какой-то ответ')

    kind, value = model.classify_or_chat('что угодно')

    assert (kind, value) == ('chat', 'какой-то ответ')


def test_confirm_prompt_for_known_action_uses_fixed_phrase():
    assert llm_chat.confirm_prompt_for('shutdown') == 'Точно выключить компьютер?'


def test_confirm_prompt_for_unknown_action_uses_anchor_phrase_not_bare_identifier():
    prompt = llm_chat.confirm_prompt_for('delete_folder')
    assert 'delete_folder' not in prompt  # never speak a raw identifier
    assert prompt.startswith('Точно')


def test_confirm_prompt_for_unmapped_action_has_a_safe_fallback():
    assert llm_chat.confirm_prompt_for('totally_unknown_action_name')


def test_action_confirm_required_only_contains_real_intents():
    from core.nlp.intents import INTENTS
    unknown = llm_chat.ACTION_CONFIRM_REQUIRED - set(INTENTS.keys())
    assert not unknown, f'ACTION_CONFIRM_REQUIRED lists non-existent intents: {unknown}'


def test_action_confirm_required_covers_obviously_destructive_intent_names():
    """Full-registry audit (2026-09-22): every intent whose name reads as
    irreversible/data-destroying must be in ACTION_CONFIRM_REQUIRED before
    the LLM fallback is allowed to fire it on a fuzzy guess. Deliberately
    excludes close_<app>/close_win/close_tab* — closing a single app/tab
    without confirmation is consistent with how CANON_SIMPLE and the
    semantic classifier already handle those same commands elsewhere in
    the app; only gating them for the LLM path would be inconsistent, not
    safer.
    """
    import re
    from core.nlp.intents import INTENTS
    destructive_pattern = re.compile(
        r'^(shutdown|restart|jarvis_exit|empty_trash|delete_|.*_delete$|'
        r'system_cleanup|close_all_)'
    )
    flagged = {name for name in INTENTS if destructive_pattern.match(name)}
    missing = flagged - llm_chat.ACTION_CONFIRM_REQUIRED
    assert not missing, (
        f'intents matching destructive-name patterns are missing from '
        f'ACTION_CONFIRM_REQUIRED: {missing}'
    )


class _MalformedLlm:
    """Simulates a completion response missing the expected shape — e.g. an
    empty choices list or a None content field, which a real llama.cpp
    binding could in principle return on an edge-case failure."""

    def __init__(self, response):
        self.response = response
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1

    def create_chat_completion(self, **kwargs):
        return self.response


def test_generate_does_not_raise_on_empty_choices(monkeypatch):
    model = llm_chat.LocalChatModel()
    model._llm = _MalformedLlm({'choices': []})
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)

    assert model.generate('привет') is None


def test_generate_does_not_raise_on_none_content(monkeypatch):
    model = llm_chat.LocalChatModel()
    model._llm = _MalformedLlm({'choices': [{'message': {'content': None}}]})
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)

    assert model.generate('привет') is None


def test_classify_or_chat_does_not_raise_on_empty_choices(monkeypatch):
    model = llm_chat.LocalChatModel()
    model._llm = _MalformedLlm({'choices': []})
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)
    monkeypatch.setattr('core.nlp.semantic.top_k_candidates', lambda text, k: ['shutdown'])

    kind, value = model.classify_or_chat('что-то')

    assert (kind, value) == ('chat', None)


def test_classify_or_chat_does_not_raise_on_none_content(monkeypatch):
    model = llm_chat.LocalChatModel()
    model._llm = _MalformedLlm({'choices': [{'message': {'content': None}}]})
    monkeypatch.setattr(model, '_ensure_loaded', lambda: None)
    monkeypatch.setattr('core.nlp.semantic.top_k_candidates', lambda text, k: ['shutdown'])

    kind, value = model.classify_or_chat('что-то')

    assert (kind, value) == ('chat', None)


def test_all_intent_names_are_safe_for_gbnf_grammar_literals():
    # _build_action_grammar() splices intent names directly into a GBNF
    # string as bare "literal" tokens (see llm_chat._build_action_grammar).
    # A name containing a quote or backslash would silently corrupt the
    # generated grammar instead of raising — this guards against any future
    # intent name breaking that assumption unnoticed.
    import re
    from core.nlp.intents import INTENTS
    bad = [n for n in INTENTS if not re.fullmatch(r'[A-Za-z0-9_]+', n)]
    assert not bad, f'intent names unsafe for GBNF literals: {bad}'


# ── Conversation context ────────────────────────────────────────────────

def test_generate_includes_prior_turn_in_next_prompt(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ответ раз')
    model.generate('привет')

    fake.reply = 'ответ два'
    model.generate('как дела')

    second_call_messages = fake.calls[1]
    contents = [m['content'] for m in second_call_messages]
    assert 'привет' in contents
    assert 'ответ раз' in contents
    assert contents[-1] == 'как дела'  # current turn always comes last


def test_generate_first_call_has_no_history(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ответ')
    model.generate('привет')

    first_call_messages = fake.calls[0]
    # Only the system prompt + the current user turn — no history yet
    assert len(first_call_messages) == 2


def test_history_capped_at_max_turns(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ok')
    for i in range(llm_chat._HISTORY_MAX_TURNS + 3):
        model.generate(f'turn {i}')

    assert len(model._history) == llm_chat._HISTORY_MAX_TURNS * 2
    # oldest turns evicted, most recent kept
    contents = [m['content'] for m in model._history]
    assert 'turn 0' not in contents


def test_stale_history_is_cleared(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ответ раз')
    model.generate('привет')
    assert model._history  # populated after first turn

    # Simulate a long gap since the last turn
    model._last_turn_ts -= (llm_chat._HISTORY_STALE_SECONDS + 10)

    fake.reply = 'ответ два'
    model.generate('другая тема')

    second_call_messages = fake.calls[1]
    # No stale 'привет'/'ответ раз' carried into this unrelated later turn
    contents = [m['content'] for m in second_call_messages]
    assert 'привет' not in contents
    assert len(second_call_messages) == 2  # system + current turn only


def test_reset_conversation_clears_history(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'ответ')
    model.generate('привет')
    assert model._history

    model.reset_conversation()

    assert model._history == []


def test_classify_or_chat_action_result_clears_conversation_history(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'CHAT: болтаем')
    model.classify_or_chat('привет')
    assert model._history  # chat turn recorded

    fake.reply = 'ACTION: shutdown'
    model.classify_or_chat('выключи компьютер')

    assert model._history == []  # action execution wipes prior small talk


def test_classify_or_chat_chat_result_appends_to_history(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'CHAT: привет тебе тоже')
    model.classify_or_chat('привет')

    assert len(model._history) == 2
    assert model._history[0]['content'] == 'привет'
    assert model._history[1]['content'] == 'привет тебе тоже'


def test_classify_or_chat_includes_history_in_prompt(monkeypatch):
    model, fake = _model_with_fake_llm(monkeypatch, 'CHAT: первый ответ')
    model.classify_or_chat('первый вопрос')

    fake.reply = 'CHAT: второй ответ'
    model.classify_or_chat('второй вопрос')

    second_call_messages = fake.calls[1]
    contents = [m['content'] for m in second_call_messages]
    assert 'первый вопрос' in contents
    assert 'первый ответ' in contents


# ── Streaming ───────────────────────────────────────────────────────────

def test_generate_streams_sentences_via_on_chunk(monkeypatch):
    model, fake = _model_with_fake_stream_llm(monkeypatch, 'Привет там. Как дела у тебя?')
    chunks = []

    reply = model.generate('привет', on_chunk=chunks.append)

    assert chunks == ['Привет там.', 'Как дела у тебя?']
    assert reply == 'Привет там. Как дела у тебя?'


def test_generate_without_on_chunk_does_not_stream(monkeypatch):
    # stream=False path must still work — existing non-streaming callers
    # (nothing in this file passes on_chunk) are unaffected by its addition.
    model, fake = _model_with_fake_stream_llm(monkeypatch, 'Обычный ответ.')

    reply = model.generate('привет')

    assert reply == 'Обычный ответ.'
    assert fake.calls  # non-stream branch was still invoked


def test_classify_or_chat_streams_chat_reply_sentence_by_sentence(monkeypatch):
    model, fake = _model_with_fake_stream_llm(monkeypatch, 'CHAT: Привет. Как сам?')
    chunks = []

    kind, value = model.classify_or_chat('привет', on_chat_chunk=chunks.append)

    assert kind == 'chat'
    assert value == 'Привет. Как сам?'
    assert chunks == ['Привет.', 'Как сам?']


def test_classify_or_chat_action_result_never_calls_on_chat_chunk(monkeypatch):
    model, fake = _model_with_fake_stream_llm(monkeypatch, 'ACTION: shutdown')
    chunks = []

    kind, value = model.classify_or_chat('выключи компьютер', on_chat_chunk=chunks.append)

    assert (kind, value) == ('action', 'shutdown')
    assert chunks == []  # action names are never streamed as speech


def test_classify_or_chat_stream_rejects_unknown_action_name(monkeypatch):
    model, fake = _model_with_fake_stream_llm(
        monkeypatch, 'ACTION: some_other_intent', candidates=('shutdown', 'vol_down'))

    kind, value = model.classify_or_chat('что-то', on_chat_chunk=lambda s: None)

    assert (kind, value) == ('chat', None)


def test_classify_or_chat_stream_appends_chat_reply_to_history(monkeypatch):
    model, fake = _model_with_fake_stream_llm(monkeypatch, 'CHAT: Привет тебе')
    model.classify_or_chat('привет', on_chat_chunk=lambda s: None)

    assert len(model._history) == 2
    assert model._history[1]['content'] == 'Привет тебе'
