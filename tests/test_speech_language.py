"""Regression tests for the UI-language / speech-language split in core/i18n.py.

Until now, i18n.set_language() was a single switch for everything: on-screen
text, the ASR model, the TTS voice, and every RU/UK spoken-phrase picker
across the app. Requested split: switching the interface to Ukrainian must
NOT also switch voice I/O to Ukrainian, because there's no quality Ukrainian
STT/TTS model yet — Jarvis should keep listening and speaking in Russian
regardless of what the on-screen language is set to.

Text-level command *matching* (core/nlp/commands.py's CANON_SIMPLE vs
CANON_SIMPLE_UK) is deliberately NOT part of this split — it interprets
already-transcribed text, which is a linguistic/NLU concern independent of
STT/TTS model quality, so it still follows get_language() like before.
"""
from core import i18n
from core.nlp.commands import match_command


def test_set_language_switches_ui_text_but_not_speech_language():
    i18n.set_language('uk')
    try:
        assert i18n.get_language() == 'uk'
        assert i18n.get_speech_language() == 'ru'
    finally:
        i18n.set_language('ru')


def test_spk_stays_russian_even_when_ui_language_is_ukrainian():
    from core.responses import spk
    i18n.set_language('uk')
    try:
        assert spk('hud.not_running') == 'Интерфейс не запущен.'
    finally:
        i18n.set_language('ru')


def test_tts_voice_language_stays_russian_when_ui_language_is_ukrainian():
    from core.speech.tts import _get_lang
    i18n.set_language('uk')
    try:
        assert _get_lang() == 'ru'
    finally:
        i18n.set_language('ru')


def test_command_matching_still_follows_ui_language_not_speech_language():
    # Regression guard for the opposite mistake: matching must NOT get
    # pinned to speech language, or Ukrainian-phrased command tests (and any
    # future non-voice text input) would silently stop resolving.
    i18n.set_language('uk')
    try:
        assert match_command('заверши роботу') == 'jarvis_exit'
    finally:
        i18n.set_language('ru')
    assert match_command('заверши работу') == 'jarvis_exit'
