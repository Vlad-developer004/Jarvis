"""Regression guard for core/handler/commands/creative.py's Photoshop/Figma
hotkey tables: every action in _PS_ACTIONS / _FIGMA_ACTIONS must be reachable
by at least one voice phrase in _PS_SHORT / _FIGMA_SHORT (core/nlp/commands_data.py),
otherwise the hotkey exists but nothing can ever trigger it. 12 such orphaned
Photoshop actions (export, merge down, group/ungroup, invert, levels, curves,
hue/sat, color balance, mask, default/swap colors) were found and fixed
2026-09-22 — this test exists to catch the next one."""
from core.handler.commands.creative import _PS_ACTIONS, _FIGMA_ACTIONS
from core.nlp.commands_data import _PS_SHORT, _FIGMA_SHORT


def test_every_ps_action_has_a_voice_phrase():
    reachable = set(_PS_SHORT.values())
    orphaned = set(_PS_ACTIONS) - reachable
    assert not orphaned, f"ps_* actions with no _PS_SHORT phrase: {sorted(orphaned)}"


def test_every_figma_action_has_a_voice_phrase():
    reachable = set(_FIGMA_SHORT.values())
    orphaned = set(_FIGMA_ACTIONS) - reachable
    assert not orphaned, f"figma_* actions with no _FIGMA_SHORT phrase: {sorted(orphaned)}"


def test_every_ps_short_phrase_maps_to_a_real_action():
    unknown = set(_PS_SHORT.values()) - set(_PS_ACTIONS)
    assert not unknown, f"_PS_SHORT phrases pointing at undefined actions: {sorted(unknown)}"


def test_every_figma_short_phrase_maps_to_a_real_action():
    unknown = set(_FIGMA_SHORT.values()) - set(_FIGMA_ACTIONS)
    assert not unknown, f"_FIGMA_SHORT phrases pointing at undefined actions: {sorted(unknown)}"
