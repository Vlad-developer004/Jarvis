"""Regression tests for the local-LLM fallback hook in
core/engine/recognition.py::_sem_parse.

Covers two things that broke informally during manual testing this session:
  - the 'llm_chat_fallback' module toggle must be checked at the SOURCE
    (inside _sem_parse), not via dispatch._MODULE_GATES — gating it the
    normal way would announce "AI disabled" out loud on every single
    unrecognized utterance instead of just staying silent like before this
    fallback existed.
  - ASR noise (too short, or no Cyrillic vowel) must never reach the LLM,
    same guard as core/nlp/semantic.py's Layer 0.
"""
import core.engine.recognition as recognition
from core.system import modules as system_modules


def _set_toggle(monkeypatch, enabled: bool):
    monkeypatch.setattr(
        system_modules, '_read_settings',
        lambda: {'feature_modules': {'llm_chat_fallback': enabled}},
    )
    system_modules.refresh_module_flags()


def _patch_no_match(monkeypatch):
    monkeypatch.setattr(recognition, 'classify_intent', lambda *a, **k: None)
    monkeypatch.setattr(recognition, 'extract_all_commands', lambda text: [])


def test_llm_chat_fires_when_toggle_enabled_and_nothing_else_matched(monkeypatch):
    _set_toggle(monkeypatch, True)
    _patch_no_match(monkeypatch)

    result = recognition._sem_parse('мне сегодня очень скучно совсем')

    assert result == [('llm_chat', 'мне сегодня очень скучно совсем')]


def test_llm_chat_stays_silent_when_toggle_disabled(monkeypatch):
    _set_toggle(monkeypatch, False)
    _patch_no_match(monkeypatch)

    result = recognition._sem_parse('мне сегодня очень скучно совсем')

    assert result == []


def test_llm_chat_never_fires_on_single_word(monkeypatch):
    _set_toggle(monkeypatch, True)
    _patch_no_match(monkeypatch)

    assert recognition._sem_parse('скучно') == []


def test_llm_chat_never_fires_on_vowelless_asr_noise(monkeypatch):
    _set_toggle(monkeypatch, True)
    _patch_no_match(monkeypatch)

    # No Cyrillic vowel at all — classic Vosk/GigaAM hallucination artefact.
    assert recognition._sem_parse('мм тс кх') == []


def test_llm_chat_does_not_override_a_real_match(monkeypatch):
    _set_toggle(monkeypatch, True)
    monkeypatch.setattr(recognition, 'classify_intent', lambda *a, **k: None)
    # Phrase deliberately avoids CANON_SIMPLE/regex shortcuts earlier in
    # _sem_parse — the point is testing that a rule-based match wins over
    # the llm_chat fallback, not exercising those unrelated code paths.
    monkeypatch.setattr(
        recognition, 'extract_all_commands',
        lambda text: [('some_test_intent', text)],
    )

    result = recognition._sem_parse('совершенно случайная тестовая фраза')

    assert result == [('some_test_intent', 'совершенно случайная тестовая фраза')]
