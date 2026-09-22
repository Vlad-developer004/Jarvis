"""
SemanticIntentClassifier — ONNX-only multilingual intent classifier.

Architecture overview
─────────────────────
Inference is a four-layer pipeline:

  Layer 0 — Pre-filter / State Machine
      • Rejects hallucination-noise from Vosk/GigaAM (no Cyrillic vowel).
      • If the system is waiting for a yes/no answer, short confirmation words
        are intercepted by a plain dictionary lookup — bypassing the neural path.
      • In IDLE state, isolated short words are blocked before they reach the
        encoder (too ambiguous to classify reliably).

  Layer 1 — Optional Sparse Keyword Gate
      • Cheap substring/root check for a small set of high-stakes intents.
      • Used as a confidence booster: if the dense path is uncertain and a
        known keyword root is present, the match is accepted anyway.

  Layer 2 — Dense Centroid Lookup (ONNX + numpy)
      • Text is tokenised by the HuggingFace tokenizer (no PyTorch needed).
      • Token embeddings are produced by the INT8-quantised ONNX encoder.
      • Mean-pooling + L2-normalisation → query vector q (D,).
      • Cosine similarity = q · C.T  where C is the pre-normalised centroid
        matrix (K×D) loaded from semantic_cache.npz.

  Layer 3 — Margin-of-Confidence OOD Filter
      • Accepts only if top_score ≥ min_score AND
        (top_score − second_best_score) ≥ min_margin.
      • Genuine commands always pull clearly ahead of the next-best intent;
        random noise or OOD speech distributes evenly across intents.

Runtime dependencies: numpy, onnxruntime, transformers (tokenizer only)
No PyTorch / sentence_transformers required at inference time.

Prepare the model artefacts first:
    python tools/prepare_model.py
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from core.logging_setup import get_logger as _get_logger

_log = _get_logger('semantic')


from .semantic_encoder import _OnnxEncoder
from .semantic_layers import _CYR_VOWELS, layer0_prefilter, layer1_sparse, margin_check
from .semantic_config import DEFAULT_CONFIG as _DEFAULT_CONFIG

# Cyrillic vowels used by the Layer 0 hallucination filter.

# ─── Classifier ───────────────────────────────────────────────────────────────

class SemanticIntentClassifier:
    """
    ONNX-backed multilingual intent classifier with OOD rejection.

    Typical usage
    ─────────────
        clf = SemanticIntentClassifier()
        intent = clf.classify_intent("сделай тише")   # → 'vol_down'
        intent = clf.classify_intent("мм тс")          # → None  (Layer 0)
        intent = clf.classify_intent("нейронная сеть") # → None  (OOD margin)

    With conversation state
    ───────────────────────
        intent = clf.classify_intent("да", is_waiting_answer=True)
        # → 'confirm_yes'  (intercepted by Layer 0, no neural path)
    """

    def __init__(self, config: dict | str | Path | None = None) -> None:
        """
        Parameters
        ----------
        config : dict | str | Path | None
            dict   — keys merged on top of _DEFAULT_CONFIG;
            str / Path — path to a JSON file with the same keys;
            None   — use defaults unchanged.
        """
        self._cfg: dict = dict(_DEFAULT_CONFIG)
        if isinstance(config, (str, Path)):
            with open(config, encoding='utf-8') as fh:
                self._cfg.update(json.load(fh))
        elif isinstance(config, dict):
            self._cfg.update(config)

        # ONNX inference session — created lazily on first call
        self._session: object | None = None  # onnxruntime.InferenceSession
        self._tokenizer: object | None = None  # transformers.PreTrainedTokenizerFast
        self._centroids: Optional[np.ndarray] = None
        self._labels: list[str] = []
        self._load_lock = threading.Lock()  # guards _ensure_loaded against races
        # When True, classify_intent returns None immediately instead of blocking
        self._async_mode: bool = False
        # Unload timer — frees model weights after prolonged inactivity
        self._unload_timer: Optional[threading.Timer] = None
        self._unload_lock = threading.Lock()
        self._unload_timeout: float | None = None  # cached setting

    # ── Model lifecycle (load / unload) ──────────────────────────────────────

    def _unload_model(self) -> None:
        """Free model weights from RAM. Next inference call reloads automatically."""
        with self._load_lock:
            if self._centroids is None:
                return
            self._session = None
            self._tokenizer = None
            self._centroids = None
            self._labels = []
        import gc
        gc.collect()
        try:
            from core.system.bootstrap import trim_memory
            trim_memory()
        except Exception:
            pass
        _log.info('Model unloaded to free RAM.')

    def _reset_unload_timer(self) -> None:
        """Restart the inactivity timer that auto-unloads the model."""
        if self._unload_timeout is None:
            try:
                from config_pack.config import get_settings_path
                import json as _json
                with open(get_settings_path(), encoding='utf-8') as _f:
                    self._unload_timeout = float(_json.load(_f).get('semantic_unload_timeout', 600.0))
            except Exception:
                self._unload_timeout = 600.0
        tout = self._unload_timeout
        if tout <= 0:
            return
        with self._unload_lock:
            if self._unload_timer is not None:
                self._unload_timer.cancel()
            self._unload_timer = threading.Timer(tout, self._unload_model)
            self._unload_timer.daemon = True
            self._unload_timer.start()

    # ── Lazy initialisation ───────────────────────────────────────────────────

    # Marker stored inside semantic_cache.npz to detect encoder-type mismatch.
    _CACHE_ENCODER_KEY = 'encoder_type'

    def _ensure_loaded(self) -> None:
        """Load centroid cache and ONNX session on first inference call.

        If the cache was built with a different encoder type (e.g. SentenceTransformer
        but now using ONNX), the centroids are automatically rebuilt in a background
        thread so the first inference is not blocked.
        """
        if self._centroids is not None:
            return  # fast path — no lock needed once fully initialised
        with self._load_lock:
            if self._centroids is not None:
                return  # another thread finished while we waited

            cache = Path(self._cfg['cache_path'])
            if not cache.exists():
                raise RuntimeError(
                    f'[SEMANTIC] Centroid cache not found: {cache}\n'
                    '           Run:  python tools/prepare_model.py'
                )

            encoder = self._build_encoder()
            current_enc_type = type(encoder).__name__

            data = np.load(cache, allow_pickle=True)
            cached_enc_type   = str(data.get(self._CACHE_ENCODER_KEY, 'SentenceTransformer'))
            cached_model_name = str(data.get('model_name', ''))
            current_model_name = self._cfg.get('model_name', '')
            centroids = data['centroids'].astype(np.float32)  # (K, D)
            labels    = data['labels'].tolist()                # K strings

            self._session   = encoder
            self._tokenizer = None
            self._labels    = labels
            self._centroids = centroids

            # Quantised ONNX produces smaller inter-class margins than full-precision ST.
            # Relax min_margin when using ONNX so legitimate commands are not rejected.
            if isinstance(encoder, _OnnxEncoder):
                self._cfg.setdefault('min_margin',            0.15)
                self._cfg.setdefault('is_command_min_margin', 0.20)
                if self._cfg['min_margin'] >= 0.15:
                    self._cfg['min_margin'] = 0.05
                if self._cfg['is_command_min_margin'] >= 0.20:
                    self._cfg['is_command_min_margin'] = 0.10

            _log.info('Loaded %d intent centroids (%dd) from %s [enc=%s, model=%s, margin=%.2f]',
                      len(self._labels), self._centroids.shape[1], cache,
                      current_enc_type, cached_model_name or '?', self._cfg['min_margin'])

            # Rebuild centroids in background if encoder class OR underlying model changed.
            # Both MiniLM and E5 produce _OnnxEncoder instances, so checking only
            # encoder_type would miss a model swap — model_name catches that case.
            needs_rebuild = (cached_enc_type != current_enc_type) or (
                bool(current_model_name) and cached_model_name != current_model_name
            )
            if needs_rebuild:
                _log.info(
                    'Encoder mismatch (type: %s→%s, model: %r→%r) — rebuilding centroids in background',
                    cached_enc_type, current_enc_type, cached_model_name, current_model_name,
                )
                threading.Thread(target=self._rebuild_cache_bg, daemon=True,
                                 name='SemanticCacheRebuild').start()

            self._reset_unload_timer()

    def _rebuild_cache_bg(self) -> None:
        """Rebuild centroid cache using the current encoder (runs in background thread)."""
        try:
            self.rebuild_cache()
            _log.info('Centroid cache rebuilt for new encoder type.')
        except Exception as e:
            _log.error('Background cache rebuild failed: %s', e, exc_info=True)

    def _build_encoder(self):
        """Load sentence encoder.

        Priority:
        1. Quantised ONNX model (``data/intent_model_onnx_quant/``) — no PyTorch.
        2. FP32 ONNX model (``data/intent_model_onnx/``) — no PyTorch.
        3. Fine-tuned SentenceTransformer (``data/intent_model/``) — needs PyTorch.
        4. Base HuggingFace model — needs PyTorch (download on first run).
        """
        for onnx_dir_key in ('onnx_model_dir', 'onnx_fp32_dir'):
            onnx_dir = Path(self._cfg.get(onnx_dir_key, ''))
            model_file = onnx_dir / ('model_quantized.onnx' if 'quant' in str(onnx_dir) else 'model.onnx')
            tok_file = onnx_dir / 'tokenizer.json'
            if model_file.exists() and tok_file.exists():
                try:
                    enc = _OnnxEncoder(str(model_file), str(tok_file))
                    _log.info('ONNX encoder loaded from %s (no PyTorch)', onnx_dir)
                    return enc
                except Exception as e:
                    _log.warning('ONNX encoder init failed (%s): %s — falling back', onnx_dir, e)

        # PyTorch fallback
        import os
        os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        from sentence_transformers import SentenceTransformer
        ft_dir = Path(self._cfg.get('ft_model_dir', 'data/intent_model'))
        if ft_dir.exists():
            _log.info('Loading fine-tuned SentenceTransformer from %s', ft_dir)
            return SentenceTransformer(str(ft_dir))
        model_name = self._cfg['model_name']
        _log.info('Using base SentenceTransformer: %s', model_name)
        return SentenceTransformer(model_name)

    # ── Encoding ─────────────────────────────────────────────────────────────

    def _encode(self, text: str) -> np.ndarray:
        """Encode text → unit-norm vector (works with both ONNX and ST backends)."""
        pfx = self._cfg.get('query_prefix', '')
        raw = self._session.encode(pfx + text if pfx else text)
        norm = np.linalg.norm(raw) + 1e-9
        return (raw / norm).astype(np.float32)

    def _encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode a list of texts; returns (N, D) normalised matrix.

        Uses true batched ONNX inference (_OnnxEncoder.encode_batch) when
        available — only rebuild_cache() calls this with more than one text,
        so this is where batching actually pays off.
        """
        pfx = self._cfg.get('query_prefix', '')
        prefixed = [pfx + t if pfx else t for t in texts]
        if hasattr(self._session, 'encode_batch'):
            raw = self._session.encode_batch(prefixed)  # (N, D) already normalised
            return raw.astype(np.float32)
        rows = [self._encode(t) for t in texts]
        return np.vstack(rows).astype(np.float32)

    # ── Module guard ──────────────────────────────────────────────────────────

    def _intent_allowed(self, intent: str) -> bool:
        """Return False if the intent's optional module is not enabled."""
        try:
            from core.system import module_enabled
        except Exception:
            return True
        for prefix, mod in self._cfg['module_map'].items():
            if intent.startswith(prefix) or intent == prefix:
                return module_enabled(mod)
        return True

    # ── Scoring helper ────────────────────────────────────────────────────────

    def _cosine_scores(self, text: str) -> np.ndarray:
        """
        Encode *text* and return cosine similarity against every centroid.

        Because centroids are pre-normalised (prepare_model.py) and the query
        is normalised in _encode(), cosine_sim(q, c_k) = q · c_k, which is a
        single matrix-vector multiply — no per-call norm loop.

        Returns shape (K,) float32.
        """
        q = self._encode(text)              # (D,) unit-norm
        return self._centroids @ q          # (K,)

    # ── Public API ────────────────────────────────────────────────────────────

    def warmup_async(self, on_done=None) -> None:
        """Start background model loading. classify_intent returns None until ready."""
        if self._centroids is not None:
            if on_done:
                on_done()
            return
        self._async_mode = True
        def _bg():
            self._ensure_loaded()
            self._async_mode = False
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True).start()

    def classify_intent(
        self,
        text: str,
        is_waiting_answer: bool = False,
    ) -> Optional[str]:
        """
        Full pipeline classification.

        Parameters
        ----------
        text : str
            Transcribed speech from STT.
        is_waiting_answer : bool
            Set True when Jarvis asked a yes/no question and is awaiting the
            user's response.  Enables the confirmation intercept in Layer 0.

        Returns
        -------
        str | None
            Intent name (e.g. 'vol_down') on success, None on rejection.
            Special values 'confirm_yes' / 'confirm_no' / 'confirm_cancel' are
            returned when a confirmation word is intercepted in Layer 0.
        """
        # Non-blocking fast path: return None while background loading is in progress.
        # The rule-based fallback in recognition.py will handle the command instead.
        if self._async_mode and self._centroids is None:
            return None
        self._ensure_loaded()

        # ── Layer 0: pre-filter / state machine ──────────────────────────────
        should_continue, override = layer0_prefilter(
            text, is_waiting_answer, self._cfg['confirm_map'], self._cfg['idle_min_tokens'],
        )
        if not should_continue:
            self._reset_unload_timer()
            return override  # None (rejected) or a confirm_* intent

        # ── Layer 2: dense centroid lookup ────────────────────────────────────
        scores = self._cosine_scores(text)   # (K,)

        top_idx   = int(np.argmax(scores))
        top_score = float(scores[top_idx])
        top_label = self._labels[top_idx]

        # ── Layer 1: sparse keyword boost (uncertain zone) ────────────────────
        if layer1_sparse(text, top_label, top_score, self._cfg['sparse_min_score'],
                          self._cfg['min_score'], self._cfg['sparse_roots']):
            # Sparse gate is confident — skip OOD filter
            self._reset_unload_timer()
            return top_label if self._intent_allowed(top_label) else None

        # ── Layer 3: margin-of-confidence OOD filter ──────────────────────────
        passed, intent, _ = margin_check(
            scores, self._labels,
            min_score=self._cfg['min_score'],
            min_margin=self._cfg['min_margin'],
        )
        if not passed:
            return None

        result = intent if self._intent_allowed(intent) else None
        self._reset_unload_timer()
        return result

    def top_k_candidates(self, text: str, k: int = 6) -> list[str]:
        """Return up to k intent names ranked by cosine similarity, ignoring
        the OOD margin gates — used by core/speech/llm_chat.py to narrow the
        ~270-intent action space down to a short list the LLM can arbitrate
        over, instead of pasting every intent name into one prompt (too big
        for a small model's context, and too many close options to pick
        from reliably). 'reported_speech' is never a real action, so it's
        excluded even if it scores highest.
        """
        self._ensure_loaded()
        scores = self._cosine_scores(text)
        order = np.argsort(scores)[::-1]
        out: list[str] = []
        for idx in order:
            label = self._labels[int(idx)]
            if label == 'reported_speech' or not self._intent_allowed(label):
                continue
            out.append(label)
            if len(out) >= k:
                break
        return out

    def is_command(self, text: str) -> bool:
        """
        Context filter — returns True if the phrase is plausibly a direct
        command to Jarvis rather than ambient speech or reported speech
        (quoting / describing what someone else said).

        The model was trained with auto-generated reported_speech examples
        covering every command wrapped in reporting-frame templates
        ("он говорит X", "я ему говорю X", etc.), so it detects the FRAMING
        context rather than just matching command keywords.
        """
        if self._async_mode and self._centroids is None:
            return True  # assume command during async load (safer: don't filter)
        self._ensure_loaded()

        if not _CYR_VOWELS.search(text.lower()):
            return False

        scores = self._cosine_scores(text)
        top_idx = int(np.argmax(scores))
        top_label = self._labels[top_idx]

        # If the classifier thinks this is reported/ambient speech → not a command
        if top_label == 'reported_speech':
            return False

        # Also require basic confidence (OOD rejection)
        passed, _, _ = margin_check(
            scores, self._labels,
            min_score=self._cfg['is_command_min_score'],
            min_margin=self._cfg['is_command_min_margin'],
        )
        return passed

    def rebuild_cache(self) -> None:
        """
        Re-encode all INTENTS through the ONNX model and save fresh centroids.

        Useful when INTENTS changes but you don't need to re-run fine-tuning.
        After this call the next classify_intent() reloads the new cache.
        """
        self._ensure_loaded()  # makes sure session + tokenizer are ready

        from core.nlp.intents import INTENTS

        _log.info('Rebuilding centroid cache...')

        intent_to_phrases: dict[str, list[str]] = {}
        for intent, phrases in INTENTS.items():
            if self._intent_allowed(intent):
                intent_to_phrases[intent] = phrases

        labels_sorted = list(intent_to_phrases.keys())
        dim = self._centroids.shape[1]
        new_centroids = np.zeros((len(labels_sorted), dim), dtype=np.float32)

        for i, intent in enumerate(labels_sorted):
            phrase_vecs = self._encode_batch(intent_to_phrases[intent])  # (n, D)
            mean_vec    = phrase_vecs.mean(axis=0)                        # (D,)
            norm        = np.linalg.norm(mean_vec) + 1e-9
            new_centroids[i] = mean_vec / norm

        cache = Path(self._cfg['cache_path'])
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache,
            centroids=new_centroids,
            labels=np.array(labels_sorted, dtype=object),
            encoder_type=np.array(type(self._session).__name__),
            model_name=np.array(self._cfg.get('model_name', '')),
        )

        self._centroids = new_centroids
        self._labels    = labels_sorted
        _log.info('Cache rebuilt: %d centroids → %s [enc=%s]',
                  len(labels_sorted), cache, type(self._session).__name__)


# ─── Module-level singleton (backward-compatible API) ─────────────────────────
# Callers that do `from core.nlp.semantic import classify_intent` continue to
# work without modification.  The singleton is created lazily.

_classifier: Optional[SemanticIntentClassifier] = None


def _get_classifier() -> SemanticIntentClassifier:
    global _classifier                   # noqa: PLW0603  (module-level singleton is intentional)
    if _classifier is None:
        _classifier = SemanticIntentClassifier()
    return _classifier


def is_command(text: str) -> bool:
    return _get_classifier().is_command(text)


def classify_intent(text: str, threshold: float = 0.48) -> Optional[str]:
    # `threshold` retained for call-site compatibility; actual value from config.
    return _get_classifier().classify_intent(text)


def top_k_candidates(text: str, k: int = 6) -> list[str]:
    return _get_classifier().top_k_candidates(text, k)


def rebuild_cache() -> None:
    _get_classifier().rebuild_cache()


def warmup() -> None:
    """Synchronously pre-load the model (blocks until ready)."""
    _get_classifier()._ensure_loaded()


def warmup_async(on_done=None) -> None:
    """Start background model loading. classify_intent returns None until ready."""
    _get_classifier().warmup_async(on_done)


def preload_pytorch() -> None:
    """Import PyTorch DLLs without loading the model weights.
    Satisfies the sherpa-onnx DLL ordering constraint on Windows (~2s).
    Call this first, then warmup_async() to load weights in background."""
    import os
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    # Disable CUDA to prevent pynvml 0xC0000005 crash on Windows when torch.cuda
    # initialises before the NVIDIA driver is fully ready (race with other DLL loads).
    # All inference in this project is CPU-only, so CUDA is never needed.
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
    import torch  # noqa: F401  — loads PyTorch DLLs as side effect; don't use sentence_transformers here
    _log.info('PyTorch DLLs preloaded (CUDA disabled)')
