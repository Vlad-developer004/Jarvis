"""Tests for core/handler/commands/social.py — small talk, system status,
and the insult-handling persona logic (added this session's llm_chat work
originally targeted, but the pre-existing rule-based insult categorization
here had zero tests of its own despite being what most insults actually hit
before ever reaching the LLM fallback).
"""
import core.handler.commands.social as social_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


# ── handle_social routing ─────────────────────────────────────────────────

def test_handle_social_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'ru')
    monkeypatch.setitem(social_cmd._SOCIAL_ACTIONS, 'thanks', lambda h, t, lang: called.append((t, lang)))
    handler = _FakeHandler()

    social_cmd.handle_social(handler, 'thanks', 'спасибо')

    assert called == [('спасибо', 'ru')]


def test_social_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    from core.nlp.commands_data import CANON_SIMPLE
    # Some commands (e.g. 'thanks') are matched via the CANON_SIMPLE keyword
    # table in commands_data.py rather than the semantic-classifier INTENTS
    # registry — both are legitimate NLU paths.
    known = set(INTENTS.keys()) | set(CANON_SIMPLE.values())
    unknown = set(social_cmd._SOCIAL_ACTIONS.keys()) - known
    assert not unknown, f'_SOCIAL_ACTIONS has non-existent intent keys: {unknown}'


# ── _time_now ─────────────────────────────────────────────────────────────

def test_time_now_russian_uses_seychas_prefix():
    handler = _FakeHandler()
    social_cmd._time_now(handler, 'который час', 'ru')
    assert handler.spoken[0].startswith('Сейчас')


def test_time_now_ukrainian_uses_zaraz_prefix():
    handler = _FakeHandler()
    social_cmd._time_now(handler, 'котра година', 'uk')
    assert handler.spoken[0].startswith('Зараз')


# ── insult categorization ──────────────────────────────────────────────────

def test_insult_dumb_category_russian():
    handler = _FakeHandler()
    social_cmd._system_insult(handler, 'джарвис ты тупой', 'ru')
    assert handler.spoken
    assert 'зеркало' in handler.spoken[0] or 'интеллект' in handler.spoken[0] or 'эго' in handler.spoken[0] or 'умнее' in handler.spoken[0]


def test_insult_silence_category_russian():
    handler = _FakeHandler()
    social_cmd._system_insult(handler, 'джарвис заткнись', 'ru')
    assert handler.spoken
    reply = handler.spoken[0]
    assert 'притих' in reply or 'тишины' in reply or 'Молчание' in reply


def test_insult_goaway_category_russian():
    handler = _FakeHandler()
    social_cmd._system_insult(handler, 'джарвис отвали', 'ru')
    assert handler.spoken
    reply = handler.spoken[0]
    assert 'ушёл' in reply or 'фон' in reply


def test_insult_default_category_for_unrecognized_insult():
    handler = _FakeHandler()
    social_cmd._system_insult(handler, 'джарвис ну ты и тип', 'ru')
    assert handler.spoken
    reply = handler.spoken[0]
    assert 'Принял' in reply or 'лирики' in reply or 'Оскорбления' in reply


def test_insult_never_speaks_the_literal_wake_word_stripped_incorrectly():
    # 'джарвис' must be stripped before category matching, not leaked into
    # the category-detection substring checks in a way that changes result.
    handler_a = _FakeHandler()
    handler_b = _FakeHandler()
    social_cmd._system_insult(handler_a, 'джарвис заткнись', 'ru')
    social_cmd._system_insult(handler_b, 'заткнись', 'ru')
    # Same category regardless of whether the wake word was present
    silence_markers = ('притих', 'тишины', 'Молчание')
    assert any(m in handler_a.spoken[0] for m in silence_markers)
    assert any(m in handler_b.spoken[0] for m in silence_markers)


def test_insult_dumb_category_ukrainian():
    handler = _FakeHandler()
    social_cmd._system_insult(handler, 'джарвіс ти тупий', 'uk')
    assert handler.spoken
    reply = handler.spoken[0]
    assert 'дзеркало' in reply or 'інтелект' in reply or 'его' in reply or 'привід' in reply
