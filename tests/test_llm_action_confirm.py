"""Regression tests for the 'llm_action_confirm' interactive state in
core/handler/interactive.py.

This gates any action the local LLM fallback (core/speech/llm_chat.py)
resolves via classify_or_chat() when that action is in ACTION_CONFIRM_REQUIRED
(shutdown, restart, delete_*, ...). Classification there is fuzzier than
CANON_SIMPLE/semantic (see llm_chat.py's module docstring), so the action
must only actually run — via handler.handle(), the same dispatch path as any
other recognized intent — after an explicit spoken "yes".
"""
import core.handler.interactive as interactive


class _FakeHandler:
    def __init__(self, state, data):
        self.interactive_state = state
        self.interactive_data = data
        self.handle_calls = []
        self.spoken = []

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data or {}

    def handle(self, cmd, text):
        self.handle_calls.append((cmd, text))


def _no_semantic_confirm(monkeypatch):
    # Keep this test isolated from the semantic model — yes/no falls back to
    # the plain word lists in _state_llm_action_confirm.
    monkeypatch.setattr(interactive, '_sem_cmd', lambda *a, **k: '')
    monkeypatch.setattr(interactive, 'speak', lambda *a, **k: None)


def test_yes_dispatches_the_pending_action(monkeypatch):
    _no_semantic_confirm(monkeypatch)
    handler = _FakeHandler('llm_action_confirm', {'action': 'shutdown'})

    interactive.handle_interactive(handler, 'да')

    assert handler.handle_calls == [('shutdown', 'да')]
    assert handler.interactive_state is None


def test_no_cancels_without_dispatching(monkeypatch):
    _no_semantic_confirm(monkeypatch)
    handler = _FakeHandler('llm_action_confirm', {'action': 'shutdown'})

    interactive.handle_interactive(handler, 'нет')

    assert handler.handle_calls == []
    assert handler.interactive_state is None


def test_unrelated_reply_cancels_rather_than_defaulting_to_yes(monkeypatch):
    # Deliberately fail closed: anything that isn't a recognized "yes" must
    # NOT execute a destructive action (shutdown/restart/delete/...).
    _no_semantic_confirm(monkeypatch)
    handler = _FakeHandler('llm_action_confirm', {'action': 'delete_folder'})

    interactive.handle_interactive(handler, 'какая сегодня погода')

    assert handler.handle_calls == []


def test_missing_action_in_state_data_never_dispatches(monkeypatch):
    _no_semantic_confirm(monkeypatch)
    handler = _FakeHandler('llm_action_confirm', {})

    interactive.handle_interactive(handler, 'да')

    assert handler.handle_calls == []
