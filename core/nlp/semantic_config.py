"""Default configuration for SemanticIntentClassifier. Split out of
semantic.py purely for file size; no behavior change.
"""

DEFAULT_CONFIG: dict = {
    # ── Paths ────────────────────────────────────────────────────────────────
    # Directory produced by prepare_model.py (contains model.onnx + tokenizer)
    'onnx_model_dir': 'data/intent_model_onnx_quant',
    'onnx_fp32_dir':  'data/intent_model_onnx',
    'ft_model_dir':   'data/intent_model',
    'model_name':     'intfloat/multilingual-e5-small',
    # Prefix prepended to user queries at inference time.
    # E5 models need "query: " to activate retrieval-tuned representations.
    # Set to '' for non-E5 models.
    'query_prefix':   'query: ',
    # Centroid matrix + labels produced by prepare_model.py
    'cache_path':     'data/semantic_cache.npz',

    # ── OOD thresholds (classify_intent) ─────────────────────────────────────
    # Minimum cosine similarity for the winning centroid.
    'min_score':  0.45,
    # Minimum gap between top-1 and top-2 (different intent) cosine scores.
    'min_margin': 0.15,

    # ── Stricter thresholds for is_command() context filter ───────────────────
    'is_command_min_score':  0.55,
    'is_command_min_margin': 0.20,

    # ── Layer 0: short-word blocking ─────────────────────────────────────────
    # Texts with fewer tokens than this (when NOT waiting for an answer) are
    # silently dropped in IDLE state to prevent single-word hallucinations.
    'idle_min_tokens': 2,

    # ── Layer 0: confirmation vocabulary ─────────────────────────────────────
    # When is_waiting_answer=True, these tokens are matched literally and
    # returned as special intents without touching the neural path.
    # Format: { surface_form: intent_name }
    'confirm_map': {
        'да':   'confirm_yes',
        'ага':  'confirm_yes',
        'ок':   'confirm_yes',
        'окей': 'confirm_yes',
        'yes':  'confirm_yes',
        'нет':  'confirm_no',
        'не':   'confirm_no',
        'нє':   'confirm_no',
        'no':   'confirm_no',
        'стоп': 'confirm_cancel',
    },

    # ── Layer 1: sparse keyword roots (optional confidence boost) ─────────────
    # Maps a keyword root (lowercased, no diacritics needed) to an intent.
    # If the dense score is in the uncertain zone [sparse_min_score, min_score)
    # AND one of these roots is a substring of the query, the match is accepted.
    'sparse_roots': {
        'выключ':   'shutdown',
        'вимкни':   'shutdown',
        'перезагруз': 'restart',
        'перезавант': 'restart',
        'заблокуй клав': 'keyboard_lock',
        'заблокир клав': 'keyboard_lock',
    },
    # Score range in which sparse roots can override the OOD filter.
    'sparse_min_score': 0.35,

    # ── Module-availability guard ─────────────────────────────────────────────
    # Intent prefix → module name that must be enabled for the intent to be
    # included in the centroid matrix.  Intents not matched here are always on.
    'module_map': {
        'ps_':              'photoshop_voice',
        'figma_':           'figma_voice',
        'cinema_':          'cinema',
        'qa_search':        'qa',
        'net_profile_':     'network_profiles',
        'vpn_reminder':     'network_profiles',
        'health_disks':     'system_health',
        'calendar_next':    'calendar_ics',
        'inbox_unread':     'inbox_digest',
        'mail_compose':     'inbox_digest',
        'git_commit':       'git_integration',
        'translate_speech': 'translator',
    },
}
