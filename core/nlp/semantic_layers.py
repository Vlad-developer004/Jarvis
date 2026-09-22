"""Stateless classification layers for SemanticIntentClassifier — pre-filter,
sparse keyword gate, and margin-of-confidence OOD check. Split out of
semantic.py purely for file size; no behavior change. Each function takes
its config values as explicit arguments instead of reading `self._cfg`, so
none of this needs the classifier instance at all.
"""
from __future__ import annotations

import re
from typing import Optional

import numpy as np

# Cyrillic vowels used by the Layer 0 hallucination filter.
_CYR_VOWELS = re.compile(r'[аеёиоуыэюяіїєаеіоуАЕЁИОУЫЭЮЯІЇЄ]')


def layer0_prefilter(
    text: str,
    is_waiting_answer: bool,
    confirm_map: dict[str, str],
    idle_min_tokens: int,
) -> tuple[bool, Optional[str]]:
    """
    Fast, zero-neural pre-filter.

    Returns
    ───────
    (should_continue, intent_override)

    • (False, None)            — text rejected; caller returns None
    • (False, 'confirm_yes')   — text intercepted; caller returns that intent
    • (True,  None)            — text passes to neural pipeline
    """
    t = text.strip().lower()

    # ── Guard 1: hallucination filter ────────────────────────────────────
    # Vosk sometimes emits single consonants or non-speech artefacts.
    # A real Russian/Ukrainian phrase always contains at least one vowel.
    if not _CYR_VOWELS.search(t):
        return False, None  # pure consonant soup → drop

    tokens = t.split()

    # ── Guard 2: conversation state intercept ─────────────────────────────
    # When the system asked the user a yes/no question, short replies like
    # "да", "нет", "ок" must be matched without going through the encoder
    # (the encoder would try to map them to a full command intent).
    if is_waiting_answer and len(tokens) == 1:
        intent = confirm_map.get(tokens[0])
        if intent:
            return False, intent  # intercepted
        # Single word not in confirm_map while waiting → still pass through
        # (the user might have said a short command instead of answering)

    # ── Guard 3: IDLE short-word block ────────────────────────────────────
    # In IDLE state a single ambiguous word like "да" or "нет" that slips
    # through the microphone is too short to classify reliably.
    if not is_waiting_answer and len(tokens) < idle_min_tokens:
        # Allow explicit 1-word commands from the confirm_map only if
        # they unambiguously mean something (they don't in IDLE).
        return False, None

    return True, None  # pass to neural pipeline


def layer1_sparse(
    text: str,
    top_intent: str,
    top_score: float,
    sparse_min_score: float,
    min_score: float,
    sparse_roots: dict[str, str],
) -> bool:
    """
    Optional confidence booster for high-stakes intents.

    If `top_score` is in the "uncertain" zone [sparse_min_score, min_score)
    AND a known keyword root is a substring of the query, we accept the
    match even though it didn't clear the normal OOD thresholds.

    This handles cases like "выключи" (very short, low cosine) where the
    encoder is uncertain but the intent is unambiguous.

    Returns True if the sparse gate confidently confirms `top_intent`.
    """
    # Only activate in the uncertain zone — don't override a confident hit
    if top_score >= min_score or top_score < sparse_min_score:
        return False

    t = text.lower()
    for root, intent in sparse_roots.items():
        if root in t and intent == top_intent:
            return True
    return False


def margin_check(
    scores: np.ndarray,
    labels: list[str],
    min_score: float,
    min_margin: float,
) -> tuple[bool, str, float]:
    """
    Decide whether the closest centroid represents a genuine command.

    Method — "Margin of Confidence"
    ────────────────────────────────
    Real commands have ONE clearly dominant centroid.  Random speech or
    ambient noise projects roughly equidistant to all centroids, producing:
      (a) a low absolute top score, OR
      (b) a small gap between top-1 and top-2.

    We require BOTH gates to pass:

    Gate 1 — Absolute floor
        top_score ≥ min_score
        Rejects vectors globally far from the intent space.

    Gate 2 — Relative margin
        top_score − second_score ≥ min_margin
        `second_score` is the highest score among all centroids EXCEPT the
        winner.  Using the nearest *different* intent (not nearest phrase)
        means the gap always reflects true inter-class separation, not noise
        from multiple anchors of the same intent.

    Returns (passed: bool, top_intent: str, top_score: float).
    """
    top_idx   = int(np.argmax(scores))
    top_score = float(scores[top_idx])
    top_label = labels[top_idx]

    # Gate 1
    if top_score < min_score:
        return False, top_label, top_score

    # Gate 2 — second-best from a DIFFERENT intent
    # Since scores is 1-D (one score per centroid), every index is a
    # different intent already (by construction in prepare_model.py).
    other_mask  = np.ones(len(scores), dtype=bool)
    other_mask[top_idx] = False
    second_score = float(scores[other_mask].max()) if other_mask.any() else 0.0

    margin = top_score - second_score
    if margin < min_margin:
        return False, top_label, top_score

    return True, top_label, top_score
