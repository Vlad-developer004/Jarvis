"""ONNX sentence encoder used by SemanticIntentClassifier. Split out of
semantic.py purely for file size; no behavior change.
"""
import numpy as np

class _OnnxEncoder:
    """Lightweight ONNX-based sentence encoder — no PyTorch required.

    Uses the HuggingFace ``tokenizers`` (Rust) library for tokenisation and
    ``onnxruntime`` for inference.  Both are already in the project's dependency
    tree (sherpa-onnx pulls in onnxruntime; tokenizers is a transformers dep).

    Output: L2-normalised float32 vector, same shape as SentenceTransformer.
    """

    def __init__(self, model_path: str, tokenizer_path: str, max_length: int = 128) -> None:
        import onnxruntime as _ort
        from tokenizers import Tokenizer as _Tok

        self._sess = _ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider'],
        )
        self._tok = _Tok.from_file(tokenizer_path)
        self._tok.enable_padding()
        self._tok.enable_truncation(max_length=max_length)

    def encode(self, text: str) -> np.ndarray:
        enc = self._tok.encode(text)
        ids  = np.array([enc.ids],             dtype=np.int64)
        mask = np.array([enc.attention_mask],   dtype=np.int64)
        ttype = np.zeros_like(ids)

        out = self._sess.run(
            ['last_hidden_state'],
            {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': ttype},
        )[0]  # (1, seq, D)

        m = mask[..., np.newaxis].astype(np.float32)
        pooled = (out * m).sum(axis=1) / m.sum(axis=1).clip(min=1e-9)  # mean pool
        norm = np.linalg.norm(pooled, axis=1, keepdims=True) + 1e-9
        return (pooled / norm).astype(np.float32)[0]  # (D,)


