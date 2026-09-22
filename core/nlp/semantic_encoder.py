"""ONNX sentence encoder used by SemanticIntentClassifier. Split out of
semantic.py purely for file size; no behavior change.
"""
from collections import OrderedDict

import numpy as np

# Voice commands are short; 128 tokens was sized for generic sentences.
# Lower max_length means less padding/compute per call with no accuracy loss
# for the phrases this project actually receives.
_DEFAULT_MAX_LENGTH = 48

# Cap on the encode() memoisation cache — repeated short commands
# ("тише", "громче", "стоп") skip tokenizer+ONNX entirely on a hit.
_ENCODE_CACHE_SIZE = 256


class _OnnxEncoder:
    """Lightweight ONNX-based sentence encoder — no PyTorch required.

    Uses the HuggingFace ``tokenizers`` (Rust) library for tokenisation and
    ``onnxruntime`` for inference.  Both are already in the project's dependency
    tree (sherpa-onnx pulls in onnxruntime; tokenizers is a transformers dep).

    Output: L2-normalised float32 vector, same shape as SentenceTransformer.
    """

    def __init__(self, model_path: str, tokenizer_path: str, max_length: int = _DEFAULT_MAX_LENGTH) -> None:
        import onnxruntime as _ort
        from tokenizers import Tokenizer as _Tok

        opts = _ort.SessionOptions()
        opts.graph_optimization_level = _ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.enable_cpu_mem_arena = True
        opts.enable_mem_pattern = True
        # Voice commands arrive one at a time (no concurrent inference), so a
        # single-threaded op executor avoids thread-pool overhead per call.
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1

        self._sess = _ort.InferenceSession(
            model_path,
            sess_options=opts,
            providers=['CPUExecutionProvider'],
        )
        self._tok = _Tok.from_file(tokenizer_path)
        self._tok.enable_padding()
        self._tok.enable_truncation(max_length=max_length)
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def _run(self, ids: np.ndarray, mask: np.ndarray) -> np.ndarray:
        ttype = np.zeros_like(ids)
        out = self._sess.run(
            ['last_hidden_state'],
            {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': ttype},
        )[0]  # (N, seq, D)
        m = mask[..., np.newaxis].astype(np.float32)
        pooled = (out * m).sum(axis=1) / m.sum(axis=1).clip(min=1e-9)  # mean pool
        norm = np.linalg.norm(pooled, axis=1, keepdims=True) + 1e-9
        return (pooled / norm).astype(np.float32)  # (N, D)

    def encode(self, text: str) -> np.ndarray:
        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            return cached

        enc = self._tok.encode(text)
        ids  = np.array([enc.ids],            dtype=np.int64)
        mask = np.array([enc.attention_mask], dtype=np.int64)
        vec = self._run(ids, mask)[0]  # (D,)

        self._cache[text] = vec
        if len(self._cache) > _ENCODE_CACHE_SIZE:
            self._cache.popitem(last=False)
        return vec

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """True batched inference — used by rebuild_cache() where dozens of
        phrases per intent are encoded together instead of one call each."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        encs = self._tok.encode_batch(texts)
        ids  = np.array([e.ids            for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        return self._run(ids, mask)  # (N, D)


