"""System-level consistency check: the module feature-profile presets are
duplicated in two places — core/system/modules.py (the runtime source of
truth, read by module_enabled()) and
ui/dialogs/settings_tabs/modules/premium_view.py (a second copy used only to
render the Settings UI's radio buttons/checkboxes and their initial state).

Found while adding the 'llm_chat_fallback' toggle: these two copies had
ALREADY drifted apart independently of that change — e.g. the 'minimal'
profile has system_monitoring/battery_monitor as True in modules.py but
False in premium_view.py. That means what the Settings UI *shows* as
enabled and what module_enabled() *actually* checks at runtime can silently
disagree. This test won't fix the duplication (that's a bigger refactor —
premium_view.py would need to import core.system.modules's presets instead
of hand-copying them), but it stops new drift from shipping unnoticed.
"""
import ast
from pathlib import Path

from core.system.modules import _PROFILE_PRESETS as RUNTIME_PRESETS

ROOT = Path(__file__).resolve().parent.parent
_UI_FILE = ROOT / 'ui' / 'dialogs' / 'settings_tabs' / 'modules' / 'premium_view.py'


def _extract_ui_presets() -> dict:
    """Parse premium_view.py's `_feature_presets = {...}` literal via ast
    instead of importing the module — it has heavy import-time UI/network
    dependencies (tkinter, customtkinter, features.qa) that don't belong in
    a fast test."""
    tree = ast.parse(_UI_FILE.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if '_feature_presets' in targets:
                return ast.literal_eval(node.value)
    raise AssertionError('_feature_presets literal not found in premium_view.py — did it move or get renamed?')


def test_ui_and_runtime_presets_have_the_same_keys():
    ui_presets = _extract_ui_presets()
    assert set(ui_presets.keys()) == set(RUNTIME_PRESETS.keys()), (
        'profile names differ between core/system/modules.py and premium_view.py'
    )
    for profile in ui_presets:
        ui_keys = set(ui_presets[profile].keys())
        runtime_keys = set(RUNTIME_PRESETS[profile].keys())
        # The UI file only lists switch-backed modules — extension-gated ones
        # like photoshop_voice/figma_voice have no checkbox of their own
        # (see core/system/modules.py's _EXTENSION_BACKED_MODULES comment),
        # so allow the runtime side to have extra keys the UI doesn't render.
        missing_in_ui = ui_keys - runtime_keys
        assert not missing_in_ui, f'{profile}: UI has keys runtime does not: {missing_in_ui}'


def test_ui_and_runtime_presets_agree_on_every_shared_value():
    ui_presets = _extract_ui_presets()
    mismatches = []
    for profile, ui_flags in ui_presets.items():
        runtime_flags = RUNTIME_PRESETS.get(profile, {})
        for key, ui_value in ui_flags.items():
            runtime_value = runtime_flags.get(key)
            if runtime_value is not None and runtime_value != ui_value:
                mismatches.append((profile, key, ui_value, runtime_value))
    assert not mismatches, (
        'UI-displayed default vs. actual runtime default disagree '
        '(profile, key, ui_value, runtime_value): ' + repr(mismatches)
    )
