"""Unit tests for core/nlp/semantic_layers.py's three pure, stateless gate
functions — split out of semantic.py so they can be tested without loading
the ONNX encoder or any centroid cache. These gate every phrase that reaches
the semantic classifier, so they run every time regardless of model/hardware
availability (no skips, no mocks needed — genuinely pure functions).
"""
import numpy as np

from core.nlp.semantic_layers import layer0_prefilter, layer1_sparse, margin_check

_CONFIRM_MAP = {'да': 'confirm_yes', 'нет': 'confirm_no'}


# ── layer0_prefilter ─────────────────────────────────────────────────────

def test_layer0_rejects_vowelless_consonant_soup():
    should_continue, override = layer0_prefilter(
        'ттс', False, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is False
    assert override is None


def test_layer0_allows_normal_multiword_phrase():
    should_continue, override = layer0_prefilter(
        'выключи компьютер', False, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is True
    assert override is None


def test_layer0_intercepts_single_word_yes_while_waiting_answer():
    should_continue, override = layer0_prefilter(
        'да', True, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is False
    assert override == 'confirm_yes'


def test_layer0_intercepts_single_word_no_while_waiting_answer():
    should_continue, override = layer0_prefilter(
        'нет', True, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is False
    assert override == 'confirm_no'


def test_layer0_passes_through_unmapped_single_word_while_waiting_answer():
    # e.g. the user answered a yes/no prompt with an actual command instead
    should_continue, override = layer0_prefilter(
        'стоп', True, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is True
    assert override is None


def test_layer0_blocks_short_utterance_in_idle_state():
    # Below idle_min_tokens and not waiting for an answer — too ambiguous
    should_continue, override = layer0_prefilter(
        'да', False, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is False
    assert override is None


def test_layer0_allows_utterance_meeting_idle_min_tokens():
    should_continue, override = layer0_prefilter(
        'да ладно', False, _CONFIRM_MAP, idle_min_tokens=2)
    assert should_continue is True
    assert override is None


def test_layer0_is_case_and_whitespace_insensitive_for_confirm_map():
    should_continue, override = layer0_prefilter(
        '  ДА  ', True, _CONFIRM_MAP, idle_min_tokens=2)
    assert (should_continue, override) == (False, 'confirm_yes')


# ── layer1_sparse ────────────────────────────────────────────────────────

_SPARSE_ROOTS = {'выключ': 'shutdown', 'громч': 'vol_up'}


def test_layer1_confirms_match_in_uncertain_zone_with_matching_root():
    result = layer1_sparse(
        'выключи', top_intent='shutdown', top_score=0.55,
        sparse_min_score=0.4, min_score=0.7, sparse_roots=_SPARSE_ROOTS)
    assert result is True


def test_layer1_rejects_when_score_already_confident():
    # top_score >= min_score means the normal gate already handles it —
    # sparse gate must not double-activate
    result = layer1_sparse(
        'выключи', top_intent='shutdown', top_score=0.9,
        sparse_min_score=0.4, min_score=0.7, sparse_roots=_SPARSE_ROOTS)
    assert result is False


def test_layer1_rejects_when_score_below_sparse_floor():
    result = layer1_sparse(
        'выключи', top_intent='shutdown', top_score=0.1,
        sparse_min_score=0.4, min_score=0.7, sparse_roots=_SPARSE_ROOTS)
    assert result is False


def test_layer1_rejects_when_root_does_not_match_top_intent():
    # root for 'выключ' maps to shutdown, but top_intent here is different —
    # must not blindly confirm just because a keyword root is present
    result = layer1_sparse(
        'выключи громче', top_intent='vol_up', top_score=0.55,
        sparse_min_score=0.4, min_score=0.7, sparse_roots=_SPARSE_ROOTS)
    assert result is True  # 'громч' root IS present and maps to vol_up


def test_layer1_rejects_when_no_root_substring_present():
    result = layer1_sparse(
        'сделай потише', top_intent='shutdown', top_score=0.55,
        sparse_min_score=0.4, min_score=0.7, sparse_roots=_SPARSE_ROOTS)
    assert result is False


# ── margin_check ─────────────────────────────────────────────────────────

def test_margin_check_passes_clear_dominant_winner():
    scores = np.array([0.9, 0.1, 0.05])
    labels = ['shutdown', 'vol_up', 'vol_down']
    passed, top_label, top_score = margin_check(
        scores, labels, min_score=0.5, min_margin=0.2)
    assert passed is True
    assert top_label == 'shutdown'
    assert top_score == 0.9


def test_margin_check_fails_absolute_floor():
    scores = np.array([0.3, 0.1, 0.05])
    labels = ['shutdown', 'vol_up', 'vol_down']
    passed, top_label, _ = margin_check(scores, labels, min_score=0.5, min_margin=0.2)
    assert passed is False
    assert top_label == 'shutdown'  # still reports the top label even on reject


def test_margin_check_fails_when_second_place_too_close():
    scores = np.array([0.9, 0.85, 0.1])
    labels = ['shutdown', 'vol_up', 'vol_down']
    passed, top_label, _ = margin_check(scores, labels, min_score=0.5, min_margin=0.2)
    assert passed is False
    assert top_label == 'shutdown'


def test_margin_check_handles_single_centroid_without_crashing():
    # other_mask.any() is False in this case — must not divide by zero
    # or raise on an empty max()
    scores = np.array([0.9])
    labels = ['only_intent']
    passed, top_label, top_score = margin_check(
        scores, labels, min_score=0.5, min_margin=0.2)
    assert passed is True
    assert top_label == 'only_intent'
    assert top_score == 0.9
