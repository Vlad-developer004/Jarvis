"""Regression test for the "silent when confused" gap in
core/engine/recognition.py::handle_recognized_text.

Previously: once Jarvis was active (mid-conversation, within the wake-mode
follow-up window) and heard speech that matched zero commands, the function
simply fell off the end with no feedback at all — indistinguishable from
"didn't hear you" or "ignoring you on purpose". Fixed by speaking a short
'not_understood' response in that specific case (not when ignore_mode is on,
and not more than once per cooldown window to avoid nagging on a run of
fragmentary ASR misses).
"""
import time

import core.engine.recognition as recognition
from core.system import app_state


class _FakeHandler:
    def __init__(self):
        self.interactive_state = None
        self.silent_mode = False
        self.is_speaking = False
        self._last_not_understood_ts = 0.0
        self.play_response_calls = []
        self.handle_calls = []

    def play_response(self, category='confirm', override_silent=False):
        self.play_response_calls.append((category, override_silent))

    def handle(self, cmd, seg):
        self.handle_calls.append((cmd, seg))

    def handle_interactive(self, text):
        pass


def _reset_app_state(monkeypatch):
    monkeypatch.setattr(app_state, 'jarvis_active', True, raising=False)
    monkeypatch.setattr(app_state, 'game_mode', False, raising=False)
    monkeypatch.setattr(app_state, 'dictation_mode', False, raising=False)
    monkeypatch.setattr(app_state, 'ignore_mode', False, raising=False)
    monkeypatch.setattr(app_state, 'detected_game', None, raising=False)
    monkeypatch.setattr(app_state, 'last_command_time', 0.0, raising=False)


def _patch_no_match(monkeypatch):
    monkeypatch.setattr(recognition, '_sem_parse', lambda *a, **k: [])
    monkeypatch.setattr(recognition, 'try_consume_voice_prompt', lambda text: False)
    monkeypatch.setattr(recognition, 'is_speaking', lambda: False)


def test_active_with_no_match_gives_not_understood_feedback(monkeypatch):
    _reset_app_state(monkeypatch)
    _patch_no_match(monkeypatch)
    handler = _FakeHandler()

    recognition.handle_recognized_text('полная бессмыслица непонятная фраза', handler)

    assert handler.play_response_calls == [('not_understood', True)]


def test_not_understood_feedback_is_cooldown_limited(monkeypatch):
    _reset_app_state(monkeypatch)
    _patch_no_match(monkeypatch)
    handler = _FakeHandler()

    recognition.handle_recognized_text('первая бессмыслица', handler)
    recognition.handle_recognized_text('вторая бессмыслица сразу после', handler)

    assert len(handler.play_response_calls) == 1


def test_not_understood_feedback_stays_silent_in_ignore_mode(monkeypatch):
    _reset_app_state(monkeypatch)
    monkeypatch.setattr(app_state, 'ignore_mode', True, raising=False)
    _patch_no_match(monkeypatch)
    handler = _FakeHandler()

    recognition.handle_recognized_text('бессмыслица во время игнор-режима', handler)

    assert handler.play_response_calls == []
