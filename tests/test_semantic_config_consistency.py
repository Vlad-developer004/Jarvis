"""Referential-integrity checks for core/nlp/semantic_config.py's
DEFAULT_CONFIG. These dicts are hand-maintained and easy to let drift
silently: a typo'd intent name in confirm_map/sparse_roots, or a module name
in module_map that no longer exists, wouldn't raise anywhere at runtime — it
would just quietly stop taking effect. Each check here mirrors a real bug
class already found once in this project (see test_module_presets_consistency.py).
"""
from core.nlp.semantic_config import DEFAULT_CONFIG
from core.nlp.intents import INTENTS
from core.system.modules import _PROFILE_PRESETS, _EXTENSION_BACKED_MODULES


_SYNTHETIC_CONTROL_INTENTS = frozenset({'confirm_yes', 'confirm_no', 'confirm_cancel'})


def test_confirm_map_values_are_real_intents_or_synthetic_control_intents():
    # confirm_yes/no/cancel are handled directly by interactive.py's state
    # machine and deliberately never registered in INTENTS (see
    # core/handler/interactive.py) — only flag anything outside that set.
    bad = {tok: intent for tok, intent in DEFAULT_CONFIG['confirm_map'].items()
           if intent not in INTENTS and intent not in _SYNTHETIC_CONTROL_INTENTS}
    assert not bad, f'confirm_map points at non-existent intents: {bad}'


def test_sparse_roots_values_are_real_intents():
    bad = {root: intent for root, intent in DEFAULT_CONFIG['sparse_roots'].items()
           if intent not in INTENTS}
    assert not bad, f'sparse_roots points at non-existent intents: {bad}'


def test_module_map_values_are_real_modules():
    known_modules = set(_PROFILE_PRESETS['full'].keys()) | _EXTENSION_BACKED_MODULES
    bad = {prefix: mod for prefix, mod in DEFAULT_CONFIG['module_map'].items()
           if mod not in known_modules}
    assert not bad, f'module_map points at non-existent modules: {bad}'


_KNOWN_FORWARD_LOOKING_PREFIXES = frozenset({
    # 'cinema' module/toggle exists and is wired up, but no cinema_* intent
    # has been implemented yet — kept as a placeholder for that feature
    # rather than removed. Confirmed with the project owner (2026-09-22).
    'cinema_',
})


def test_module_map_prefixes_actually_match_some_intent():
    # A prefix that matches zero real intent names is dead config — likely a
    # stale entry from a renamed/removed intent (or an intentional
    # not-yet-implemented placeholder, see _KNOWN_FORWARD_LOOKING_PREFIXES).
    dead = []
    for prefix in DEFAULT_CONFIG['module_map']:
        if prefix in _KNOWN_FORWARD_LOOKING_PREFIXES:
            continue
        if prefix.endswith('_'):
            if not any(name.startswith(prefix) for name in INTENTS):
                dead.append(prefix)
        else:
            if prefix not in INTENTS:
                dead.append(prefix)
    assert not dead, f'module_map prefixes match no known intent: {dead}'


def test_ood_thresholds_are_sane_bounds():
    cfg = DEFAULT_CONFIG
    assert 0 < cfg['min_score'] <= 1
    assert 0 < cfg['min_margin'] <= 1
    assert 0 < cfg['is_command_min_score'] <= 1
    assert 0 < cfg['is_command_min_margin'] <= 1
    assert 0 < cfg['sparse_min_score'] <= 1
    # is_command() is documented as a stricter filter than classify_intent()
    assert cfg['is_command_min_score'] >= cfg['min_score']
    assert cfg['is_command_min_margin'] >= cfg['min_margin']
    # sparse gate only activates below the normal floor, by construction
    assert cfg['sparse_min_score'] < cfg['min_score']
