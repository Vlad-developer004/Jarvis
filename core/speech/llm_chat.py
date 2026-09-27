"""Local LLM fallback for free-form voice replies — Jarvis persona chat.

Sits below CANON_SIMPLE and the semantic classifier in the recognition
pipeline (core/engine/recognition.py): only reached when neither the
keyword matcher nor the intent classifier recognised the phrase as a known
command. Runs fully offline via llama-cpp-python (GGUF, CPU), same
lazy-load + unload-timer pattern as core/nlp/semantic.py and TTS.

Model file: models/jarvis_llm/model.gguf — the Jarvis-persona LoRA fine-tune
of Vikhr-Llama-3.2-1B-Instruct, merged and quantized to Q5_K_M. Swap in a
different/updated fine-tune by replacing that file, no code change needed.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core.logging_setup import get_logger as _get_logger

_log = _get_logger('llm_chat')

_SYSTEM_PROMPT = (
    "Ты голосовой ассистент Jarvis. Отвечай кратко, живым разговорным "
    "языком, 1-2 предложения, без списков и заголовков — твой ответ "
    "озвучивается вслух. Если пользователь оскорбляет тебя — не обижайся "
    "всерьёз, отшутись, например намекни, что не стоит ссориться с тем, кто "
    "знает о нём так много."
)
_MAX_TOKENS = 60
# classify_or_chat's prompt is dynamic — system instructions + up to _TOP_K
# retrieved candidate lines (name + anchor phrase each) + the user's text —
# so it needs more headroom than a fixed short chat prompt. 512 was too
# tight and produced an internal llama.cpp logits-buffer index error under
# load; 2048 leaves comfortable margin for candidates + generation.
_N_CTX = 2048
_DEFAULT_UNLOAD_TIMEOUT = 600.0

# ── Conversation context ──────────────────────────────────────────────────
# Follow-ups ("а сделай погромче ещё", "нет, лучше 20") need the model to see
# what was just said. Both generate() and classify_or_chat() include the last
# few turns in the prompt. Bounded and time-boxed on purpose: an unbounded
# history would both blow _N_CTX's budget (already tight with the candidate
# list, see below) and keep long-stale context bleeding into an unrelated
# later conversation after the user walked away and came back.
_HISTORY_MAX_TURNS = 3           # last 3 (user, assistant) pairs = 6 messages
_HISTORY_STALE_SECONDS = 180.0   # gap this long since the last turn clears it

# ── Function-calling fallback ────────────────────────────────────────────
# Reached only after CANON_SIMPLE + the semantic classifier + the rule-based
# matcher all missed. Rather than let the LLM claim "Выполняю X" for a
# phrase nothing actually executes (it was trained on command-confirmation
# text, so it convincingly LIES about acting otherwise), it picks between a
# genuine action call — dispatched through the exact same pipeline as any
# other recognized intent — and a plain chat reply.
#
# Covers the full ~270-intent action space (core/nlp/intents.py) via
# retrieval instead of one flat list: core.nlp.semantic.top_k_candidates()
# reuses the already-loaded centroid embeddings to narrow it down to the
# K most similar intents for THIS phrase (bypassing the normal OOD margin
# gate — we want candidates even when the semantic classifier itself wasn't
# confident enough to commit). Only that short list — with one real anchor
# phrase each, pulled from INTENTS — goes into the prompt and the grammar.
# Pasting all ~270 names into one prompt would both blow the context budget
# and give a 1B model far too many close options to discriminate reliably;
# a handful of pre-filtered, embedding-relevant candidates is a task it can
# actually do.
#
# Empirically chosen (2026-09-22), not a guess: measured retrieval recall
# against ~50 realistic (non-anchor) phrasings across common intents —
# k=6 -> 90.2%, k=8 -> 90.2% (no gain), k=10 -> 94.1% (+4pp for ~70% more
# prompt tokens and more candidates for the small model to discriminate
# between). k=6 is the better cost/benefit point; see
# test_semantic_top_k.py::test_top_k_recall_on_realistic_phrasings for the
# regression guard.
_TOP_K = 6

ACTION_CONFIRM_REQUIRED = frozenset({
    'shutdown', 'shutdown_timer', 'restart', 'restart_jarvis', 'jarvis_exit',
    'empty_trash', 'delete_file', 'delete_folder',
    'system_cleanup', 'system_cleanup_deep',
    'close_all_win', 'close_all_tabs', 'session_delete', 'command_delete',
})
_ACTION_CONFIRM_PROMPTS_OVERRIDE = {
    'shutdown': 'Точно выключить компьютер?',
    'restart': 'Точно перезагрузить компьютер?',
    'restart_jarvis': 'Перезапустить Джарвиса?',
    'jarvis_exit': 'Закрыть Джарвиса?',
    'empty_trash': 'Точно очистить корзину?',
}


def confirm_prompt_for(action: str) -> str:
    """Natural-language confirmation question for an action pending user
    yes/no — a fixed phrase for the common destructive ones, otherwise built
    from that intent's own anchor phrase in INTENTS so it never says a bare
    identifier like 'delete_folder' out loud."""
    if action in _ACTION_CONFIRM_PROMPTS_OVERRIDE:
        return _ACTION_CONFIRM_PROMPTS_OVERRIDE[action]
    try:
        from core.nlp.intents import INTENTS
        anchor = INTENTS[action][0]
        return f'Точно: {anchor}?'
    except Exception:
        return 'Точно выполнить это действие?'


_ACTION_SYSTEM_PROMPT_TMPL = (
    "Ты определяешь намерение пользователя для голосового ассистента Jarvis.\n"
    "Вот список действий, которые могли иметь в виду (имя — пример фразы):\n"
    "{candidates}\n"
    "Если просьба явно соответствует одному из НИХ — ответь СТРОГО в формате "
    "'ACTION: <имя>'.\n"
    "Если просьба не про эти действия, а обычная реплика/вопрос — ответь "
    "'CHAT: <короткий дружелюбный ответ, 1-2 предложения, без списков>'. "
    "Если пользователь оскорбляет тебя — отшутись, намекни, что не стоит "
    "ссориться с тем, кто знает о нём так много.\n"
)


def _candidate_lines(names: list[str]) -> str:
    from core.nlp.intents import INTENTS
    lines = []
    for name in names:
        anchors = INTENTS.get(name) or []
        example = anchors[0] if anchors else name
        lines.append(f'{name} — "{example}"')
    return '\n'.join(lines)


def _build_action_grammar(names: list[str]):
    from llama_cpp import LlamaGrammar
    action_alt = ' | '.join(f'"{n}"' for n in names)
    grammar_text = (
        'root ::= action | chat\n'
        f'action ::= "ACTION: " ({action_alt})\n'
        'chat ::= "CHAT: " [^\\n]+\n'
    )
    return LlamaGrammar.from_string(grammar_text)


# ── Streaming ─────────────────────────────────────────────────────────────
# Same sentence/clause-boundary buffering as features/qa's streaming answer
# window (core/handler/commands/ai.py's qa_search path): flush on sentence
# punctuation, and once the buffer runs long without one, also flush on
# comma/semicolon/dash so a reply with a long clause doesn't sit silent
# until the very end.
_SENTENCE_MARKS = ('.', '!', '?', '\n')
_CLAUSE_MARKS = (',', ';', '—')
_LONG_BUFFER_CHARS = 40


def _flush_ready_sentences(buffer: str, on_chunk: Callable[[str], None]) -> str:
    """Speaks any complete sentence(s) currently in `buffer` and returns
    what's left unflushed."""
    marks = _SENTENCE_MARKS
    if len(buffer) > _LONG_BUFFER_CHARS:
        marks = _SENTENCE_MARKS + _CLAUSE_MARKS
    if not any(m in buffer for m in marks):
        return buffer
    last_pos = max(buffer.rfind(m) for m in marks if m in buffer)
    sentence = buffer[:last_pos + 1].strip()
    rest = buffer[last_pos + 1:]
    if sentence:
        on_chunk(sentence)
    return rest


def _consume_plain_stream(stream, on_chunk: Callable[[str], None]) -> str:
    """Consumes an unconstrained (no grammar) streaming completion, calling
    on_chunk() per completed sentence/clause as they arrive. Returns the
    full accumulated reply text."""
    full = []
    buffer = ''
    for chunk in stream:
        delta = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
        if not delta:
            continue
        full.append(delta)
        buffer += delta
        buffer = _flush_ready_sentences(buffer, on_chunk)
    if buffer.strip():
        on_chunk(buffer.strip())
    return ''.join(full).strip()


def _consume_classify_stream(stream, on_chat_chunk: Callable[[str], None]) -> tuple[Optional[str], str]:
    """Consumes a grammar-constrained ACTION:/CHAT: streaming completion.
    Streams sentence-by-sentence via on_chat_chunk() only once the CHAT:
    prefix is confirmed (action names are never streamed — they're short
    identifiers spoken as a single confirm-prompt elsewhere, not raw TTS
    text). Returns (kind, content) where kind is 'action'/'chat'/None (None
    means the grammar's output didn't match either expected prefix, which
    shouldn't happen given the grammar constraint, but a stream can still
    end with zero tokens produced)."""
    raw = ''
    resolved: Optional[str] = None
    content = ''
    buffer = ''
    for chunk in stream:
        delta = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
        if not delta:
            continue
        raw += delta
        if resolved is None:
            if raw.startswith('ACTION: '):
                resolved = 'action'
                content = raw[len('ACTION: '):]
            elif raw.startswith('CHAT: '):
                resolved = 'chat'
                content = raw[len('CHAT: '):]
                buffer = content
            continue
        content += delta
        if resolved == 'chat':
            buffer += delta
            buffer = _flush_ready_sentences(buffer, on_chat_chunk)
    if resolved == 'chat' and buffer.strip():
        on_chat_chunk(buffer.strip())
    return resolved, content.strip()


def _get_project_root() -> str:
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_MODEL_PATH = os.path.join(_get_project_root(), 'models', 'jarvis_llm', 'model.gguf')


def get_default_model_path() -> str:
    """Where the default (non-custom) chat model lives on disk — used by
    llm_downloader to know where to save it, without that module reaching
    into this one's private _MODEL_PATH."""
    return _MODEL_PATH


def _get_model_path() -> str:
    """Bundled Jarvis-persona model, unless the user picked their own GGUF in
    Settings (voice tab) and it actually still exists on disk — a moved/
    deleted custom file silently falls back to the bundled one rather than
    erroring on every fallback chat turn."""
    try:
        from config_pack.config import get_settings_path
        import json as _json
        with open(get_settings_path(), encoding='utf-8') as f:
            custom = str(_json.load(f).get('llm_chat_model_path') or '').strip()
        if custom and os.path.isfile(custom):
            return custom
    except Exception:
        pass
    return _MODEL_PATH


def validate_gguf_model(path: str, timeout: float = 90.0) -> tuple[bool, str]:
    """Test-loads a candidate GGUF file in a throwaway subprocess before it's
    ever trusted in the real Jarvis process.

    llama.cpp loading an incompatible/corrupt/wrong-format file doesn't
    reliably raise a catchable Python exception — it can hard-crash the
    interpreter natively (the same class of access violation _infer_lock
    guards against for concurrent decode calls, see LocalChatModel's
    docstring). A user picking an arbitrary .gguf file from disk is exactly
    the situation where that risk is real, so the load is attempted in a
    disposable child process first: if IT crashes, only that child dies and
    this function just reports failure — Jarvis itself never touched the
    file in-process. Only a clean, verified load gets saved to settings.
    """
    if not path or not os.path.isfile(path):
        return False, 'Файл не найден.'
    if not path.lower().endswith('.gguf'):
        return False, 'Ожидается файл формата .gguf.'
    import subprocess
    import sys
    script = (
        'import sys\n'
        'from llama_cpp import Llama\n'
        'Llama(model_path=sys.argv[1], n_ctx=256, n_threads=1, verbose=False)\n'
        'print("JARVIS_GGUF_OK")\n'
    )
    try:
        proc = subprocess.run(
            [sys.executable, '-c', script, path],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f'Загрузка не завершилась за {int(timeout)} с — файл, вероятно, не подходит.'
    except Exception as e:
        return False, f'Не удалось запустить проверку: {e}'
    if proc.returncode == 0 and 'JARVIS_GGUF_OK' in proc.stdout:
        return True, 'Модель успешно загружена и проверена.'
    if proc.returncode < 0:
        return False, f'Проверка аварийно завершилась (сигнал {-proc.returncode}) — файл несовместим.'
    detail = (proc.stderr or proc.stdout or '').strip().splitlines()
    return False, f'Ошибка загрузки: {detail[-1] if detail else f"код {proc.returncode}"}'


class LocalChatModel:
    """Lazy-loaded llama.cpp wrapper with an inactivity unload timer."""

    def __init__(self) -> None:
        self._llm = None
        self._loaded_path: Optional[str] = None
        self._load_lock = threading.Lock()
        self._async_mode = False
        self._unload_timer: Optional[threading.Timer] = None
        self._unload_lock = threading.Lock()
        self._unload_timeout: Optional[float] = None
        # ── Conversation context (see module-level _HISTORY_* constants) ────
        self._history: list[dict] = []
        self._history_lock = threading.Lock()
        self._last_turn_ts: float = 0.0
        # Serializes every actual llama.cpp call (generate/classify_or_chat)
        # against this single shared Llama() instance. handle_ai() in
        # core/handler/commands/ai.py spawns a new thread per llm_chat
        # invocation with no queueing, so two unmatched utterances arriving
        # close together (e.g. an acoustic echo loop on a speaker setup
        # without headphones/AEC, where Jarvis's own TTS gets picked back up
        # by the mic as a "new" command) used to call llm.create_chat_completion()
        # from two threads at once — llama.cpp's decode() is not reentrant on
        # one context, and that produced a hard Windows access-violation
        # crash (see logs/crash_dump.log), not a Python exception this file
        # could catch.
        self._infer_lock = threading.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        model_path = _get_model_path()
        if self._llm is not None and self._loaded_path == model_path:
            return
        with self._load_lock:
            if self._llm is not None and self._loaded_path == model_path:
                return
            if self._llm is not None:
                # Path changed under us (user picked a different model) —
                # drop the old instance before loading the new one instead
                # of leaking it.
                self._llm = None
            if not Path(model_path).exists():
                raise RuntimeError(f'[LLM_CHAT] Model file not found: {model_path}')
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=model_path,
                n_ctx=_N_CTX,
                n_threads=max(1, (os.cpu_count() or 4) - 1),
                verbose=False,
            )
            self._loaded_path = model_path
            _log.info('Local chat model loaded from %s', model_path)
            self._reset_unload_timer()

    def _unload(self) -> None:
        with self._load_lock:
            if self._llm is None:
                return
            self._llm = None
            self._loaded_path = None
        import gc
        gc.collect()
        _log.info('Local chat model unloaded to free RAM.')

    def _reset_unload_timer(self) -> None:
        if self._unload_timeout is None:
            try:
                from config_pack.config import get_settings_path
                import json as _json
                with open(get_settings_path(), encoding='utf-8') as f:
                    self._unload_timeout = float(_json.load(f).get('llm_chat_unload_timeout', _DEFAULT_UNLOAD_TIMEOUT))
            except Exception:
                self._unload_timeout = _DEFAULT_UNLOAD_TIMEOUT
        timeout = self._unload_timeout
        if timeout <= 0:
            return
        with self._unload_lock:
            if self._unload_timer is not None:
                self._unload_timer.cancel()
            self._unload_timer = threading.Timer(timeout, self._unload)
            self._unload_timer.daemon = True
            self._unload_timer.start()

    def warmup_async(self, on_done=None) -> None:
        """Start background model loading; generate() returns None until ready."""
        if self._llm is not None:
            if on_done:
                on_done()
            return
        self._async_mode = True
        def _bg():
            try:
                self._ensure_loaded()
            except Exception as e:
                _log.error('Warmup failed: %s', e, exc_info=True)
            self._async_mode = False
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True, name='LlmChatWarmup').start()

    # ── Conversation context ─────────────────────────────────────────────

    def _get_history_messages(self) -> list[dict]:
        """Returns the recent-turns context, or [] if it's gone stale (the
        user walked away and came back later, or this is a fresh session)."""
        with self._history_lock:
            if not self._history:
                return []
            if time.time() - self._last_turn_ts > _HISTORY_STALE_SECONDS:
                self._history = []
                return []
            return list(self._history)

    def _append_turn(self, user_text: str, assistant_text: str) -> None:
        with self._history_lock:
            self._history.append({'role': 'user', 'content': user_text})
            self._history.append({'role': 'assistant', 'content': assistant_text})
            max_messages = _HISTORY_MAX_TURNS * 2
            if len(self._history) > max_messages:
                self._history = self._history[-max_messages:]
            self._last_turn_ts = time.time()

    def reset_conversation(self) -> None:
        """Explicitly drop conversation context — e.g. after a real action
        executes, so its confirmation exchange doesn't bleed into unrelated
        small talk right after."""
        with self._history_lock:
            self._history = []

    # ── Generation ────────────────────────────────────────────────────────

    def generate(self, text: str, on_chunk: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """Generate a short spoken-style reply to free-form text, or None if
        the model isn't ready yet (async warmup still in progress) or the
        call failed — callers should treat None as "say nothing", same as a
        rejected semantic classification.

        With on_chunk given, streams the reply and calls on_chunk(sentence)
        as each sentence/clause completes (see _consume_plain_stream) instead
        of the caller waiting for the whole reply — the same pattern
        core/handler/commands/ai.py's qa_search path already uses for QA
        answers. The full reply is still returned at the end either way, for
        history/logging. Without on_chunk, behaves exactly as before
        (single non-streamed call) — existing callers are unaffected."""
        if self._async_mode and self._llm is None:
            return None
        try:
            self._ensure_loaded()
        except Exception as e:
            _log.error('Model unavailable: %s', e)
            return None

        with self._load_lock:
            llm = self._llm
        if llm is None:
            return None

        messages = [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            *self._get_history_messages(),
            {'role': 'user', 'content': text},
        ]
        try:
            # This instance is a long-lived singleton reused across many
            # unrelated calls — reset its internal kv-cache/token state each
            # time instead of letting it silently accumulate across calls,
            # which previously produced a llama.cpp logits-buffer index
            # error ("index N out of bounds for axis 0") under load.
            # The whole reset+decode span is serialized via _infer_lock —
            # llama.cpp's decode() is not reentrant on one context, and two
            # threads calling in concurrently (e.g. an acoustic echo loop
            # re-triggering llm_chat while the previous call is still
            # generating) crashes the process with a Windows access
            # violation instead of raising a catchable Python exception.
            with self._infer_lock:
                llm.reset()
                if on_chunk is not None:
                    stream = llm.create_chat_completion(
                        messages=messages, max_tokens=_MAX_TOKENS, temperature=0.3, stream=True,
                    )
                    reply = _consume_plain_stream(stream, on_chunk)
                else:
                    out = llm.create_chat_completion(
                        messages=messages,
                        max_tokens=_MAX_TOKENS,
                        temperature=0.3,
                    )
            if on_chunk is not None:
                self._reset_unload_timer()
                if reply:
                    self._append_turn(text, reply)
                return reply or None
        except Exception as e:
            _log.error('Generation failed: %s', e, exc_info=True)
            return None

        self._reset_unload_timer()
        try:
            reply = out['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, AttributeError, TypeError) as e:
            _log.error('Unexpected completion shape: %r (%s)', out, e)
            return None
        if reply:
            self._append_turn(text, reply)
        return reply or None

    def classify_or_chat(
        self, text: str, on_chat_chunk: Optional[Callable[[str], None]] = None
    ) -> tuple[str, str]:
        """Returns ('action', intent_name) if the phrase resolves to one of
        the embedding-retrieved candidates (see module docstring), else
        ('chat', reply_text). On any failure, falls back to ('chat', None) —
        caller treats a None reply as "say nothing", same convention as
        generate().

        With on_chat_chunk given, a CHAT result is streamed sentence-by-
        sentence via that callback as it's generated (see
        _consume_classify_stream) instead of the caller waiting for the full
        reply — action names are never streamed this way since they're a
        short identifier spoken as one confirm-prompt, not raw reply text.
        The full text is still returned in `value` either way. Without
        on_chat_chunk, behaves exactly as before — existing callers are
        unaffected."""
        if self._async_mode and self._llm is None:
            return ('chat', None)
        try:
            self._ensure_loaded()
        except Exception as e:
            _log.error('Model unavailable: %s', e)
            return ('chat', None)

        with self._load_lock:
            llm = self._llm
        if llm is None:
            return ('chat', None)

        try:
            from core.nlp.semantic import top_k_candidates
            candidates = top_k_candidates(text, k=_TOP_K)
        except Exception as e:
            _log.error('top_k_candidates failed: %s', e, exc_info=True)
            candidates = []

        if not candidates:
            # No usable centroids (e.g. cache still rebuilding) — chat only,
            # no action grammar to constrain against.
            return ('chat', self.generate(text, on_chunk=on_chat_chunk))

        messages = [
            {'role': 'system', 'content': _ACTION_SYSTEM_PROMPT_TMPL.format(
                candidates=_candidate_lines(candidates)
            )},
            *self._get_history_messages(),
            {'role': 'user', 'content': text},
        ]
        try:
            grammar = _build_action_grammar(candidates)
            # See generate()'s _infer_lock comment — the whole reset+decode
            # span (including consuming a streamed generator, which drives
            # further decode() calls under the hood) must be serialized
            # against this shared Llama() instance, not just the call that
            # kicks generation off.
            with self._infer_lock:
                llm.reset()  # avoid state accumulating across calls
                if on_chat_chunk is not None:
                    stream = llm.create_chat_completion(
                        messages=messages, max_tokens=_MAX_TOKENS, temperature=0.35,
                        grammar=grammar, stream=True,
                    )
                    resolved, content = _consume_classify_stream(stream, on_chat_chunk)
                else:
                    out = llm.create_chat_completion(
                        messages=messages,
                        max_tokens=_MAX_TOKENS,
                        # Low enough to keep ACTION-name selection stable, high enough
                        # that CHAT replies don't just parrot the closest few-shot
                        # example verbatim (observed at temperature=0.1).
                        temperature=0.35,
                        grammar=grammar,
                    )
            if on_chat_chunk is not None:
                self._reset_unload_timer()
                if resolved == 'action':
                    name = content
                    if name in candidates:
                        self.reset_conversation()
                        return ('action', name)
                    _log.warning('Grammar produced unknown action name: %r', name)
                    return ('chat', None)
                if resolved == 'chat':
                    if content:
                        self._append_turn(text, content)
                    return ('chat', content or None)
                _log.warning('Unexpected grammar stream output (resolved=%r): %r', resolved, content)
                return ('chat', None)
        except Exception as e:
            _log.error('classify_or_chat generation failed: %s', e, exc_info=True)
            return ('chat', None)

        self._reset_unload_timer()
        try:
            raw = out['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, AttributeError, TypeError) as e:
            _log.error('Unexpected completion shape: %r (%s)', out, e)
            return ('chat', None)
        if raw.startswith('ACTION: '):
            name = raw[len('ACTION: '):].strip()
            if name in candidates:
                # Drop context on a real action — its confirm/execute exchange
                # is not useful (and could be actively confusing) as
                # background for the next, likely-unrelated turn of chat.
                self.reset_conversation()
                return ('action', name)
            _log.warning('Grammar produced unknown action name: %r', name)
            return ('chat', None)
        if raw.startswith('CHAT: '):
            reply = raw[len('CHAT: '):].strip()
            if reply:
                self._append_turn(text, reply)
            return ('chat', reply or None)
        _log.warning('Unexpected grammar output: %r', raw)
        return ('chat', None)


_model: Optional[LocalChatModel] = None


def _get_model() -> LocalChatModel:
    global _model  # noqa: PLW0603 — module-level singleton is intentional
    if _model is None:
        _model = LocalChatModel()
    return _model


def generate(text: str, on_chunk: Optional[Callable[[str], None]] = None) -> Optional[str]:
    return _get_model().generate(text, on_chunk=on_chunk)


def classify_or_chat(
    text: str, on_chat_chunk: Optional[Callable[[str], None]] = None
) -> tuple[str, str]:
    return _get_model().classify_or_chat(text, on_chat_chunk=on_chat_chunk)


def warmup_async(on_done=None) -> None:
    _get_model().warmup_async(on_done)


def invalidate_model() -> None:
    """Drop the currently loaded model so the next call picks up a changed
    'llm_chat_model_path' setting immediately, instead of waiting for
    whichever model is already resident to naturally hit its unload timer
    (or never unload, if the user set it to "always resident")."""
    if _model is not None:
        _model._unload()
