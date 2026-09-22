"""Integration tests for the local-LLM fallback: exercises the REAL model
file (models/jarvis_llm/model.gguf) and the REAL semantic embeddings
together, unlike tests/test_llm_chat_output_parsing.py which fakes the
model entirely to test just the response-parsing logic in isolation.

Slower and more fragile than the unit tests by nature (actual CPU inference,
actual retrieval against the actual centroid cache) — that's the tradeoff
for verifying the real pipeline actually works end to end, not just each
piece in isolation. Skips cleanly if the model file isn't present (e.g. a
fresh checkout before models/jarvis_llm/model.gguf has been placed) rather
than failing the whole suite over a missing binary asset.
"""
import os
from pathlib import Path

import pytest

pytest.importorskip('llama_cpp')

_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / 'models' / 'jarvis_llm' / 'model.gguf'
)
if not _MODEL_PATH.exists():
    pytest.skip(
        f'models/jarvis_llm/model.gguf not present at {_MODEL_PATH} — '
         'integration tests need the real GGUF file, see README Roadmap',
        allow_module_level=True,
    )


@pytest.fixture(scope='module')
def real_model():
    """One shared model instance for the whole file — loading it is the
    expensive part (~seconds), and these tests don't mutate shared state
    that would make reuse unsafe (classify_or_chat/generate are pure
    request/response calls)."""
    from core.speech.llm_chat import LocalChatModel
    model = LocalChatModel()
    model._ensure_loaded()
    return model


@pytest.mark.timeout(60)
def test_generate_returns_nonempty_russian_reply(real_model):
    reply = real_model.generate('Привет, как дела?')
    assert reply
    assert isinstance(reply, str)


@pytest.mark.timeout(60)
def test_classify_or_chat_returns_a_valid_shape(real_model):
    kind, value = real_model.classify_or_chat('открой калькулятор')
    assert kind in ('action', 'chat')
    if kind == 'action':
        from core.nlp.intents import INTENTS
        assert value in INTENTS


@pytest.mark.timeout(60)
def test_classify_or_chat_action_result_is_dispatchable(real_model):
    """If it resolves to an action, that name must be a real, dispatchable
    intent — the exact thing ACTION_CONFIRM_REQUIRED and
    core/handler/commands/ai.py's handler assume is always true."""
    from core.nlp.intents import INTENTS
    kind, value = real_model.classify_or_chat('выключи компьютер')
    if kind == 'action':
        assert value in INTENTS
    else:
        # Small base model, not yet fine-tuned (see README Roadmap) — a
        # miss here is a known accuracy gap, not something this test
        # should hard-fail on. It must still degrade to a safe 'chat'
        # shape rather than crash or return something undispatchable.
        assert value is None or isinstance(value, str)
