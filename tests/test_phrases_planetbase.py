"""Tests for features/planetbase/phrases_planetbase.py, split out of
monitor.py for file size (see that module's docstring). Nothing here
exercises game logic — just that the phrase banks are structurally sound
and that value-interpolating functions actually embed their arguments,
since monitor.py trusts these to always return a non-empty, speakable list.
"""
import features.planetbase.phrases_planetbase as phrases
import features.planetbase.monitor as monitor


# ── _INTROS ──────────────────────────────────────────────────────────

def test_intros_cover_every_tone_used_by_monitor():
    # monitor._alert() does _INTROS.get(tone, [""]) — a missing tone silently
    # degrades to a blank intro instead of failing loudly, so this is the
    # only thing that would catch a typo'd or removed tone key.
    used_tones = {"critical", "warn", "good", "congrats", "alert", "info"}
    assert used_tones <= phrases._INTROS.keys()


def test_every_intro_bank_is_a_nonempty_list_of_nonempty_strings():
    for tone, bank in phrases._INTROS.items():
        assert isinstance(bank, list) and bank, f"empty intro bank for {tone!r}"
        assert all(isinstance(s, str) and s.strip() for s in bank)


# ── Zero-arg phrase functions: just need to be non-empty and speakable ──

_ZERO_ARG_FUNCS = [
    phrases._phrases_water_deficit,
    phrases._phrases_water_marginal,
    phrases._phrases_medical_critical,
    phrases._phrases_materials_low,
    phrases._phrases_food_low,
    phrases._phrases_sandstorm_start,
    phrases._phrases_sandstorm,
    phrases._phrases_solar_flare,
    phrases._phrases_blizzard_start,
    phrases._phrases_blizzard,
    phrases._phrases_disaster_generic_start,
    phrases._phrases_disaster_generic,
    phrases._phrases_disaster_end,
]


def test_zero_arg_phrase_functions_return_nonempty_strings():
    for fn in _ZERO_ARG_FUNCS:
        result = fn()
        assert isinstance(result, list) and result, f"{fn.__name__} returned nothing"
        assert all(isinstance(s, str) and s.strip() for s in result)


# ── Value-interpolating functions: verify the value actually lands ──

def test_power_phrases_embed_percentage():
    assert all('42' in s for s in phrases._phrases_power_low(42))
    assert all('7' in s for s in phrases._phrases_power_critical(7))


def test_water_phrases_embed_percentage():
    assert all('30' in s for s in phrases._phrases_water_low(30))
    assert all('5' in s for s in phrases._phrases_water_critical(5))


def test_oxygen_phrases_embed_colonist_and_capacity_counts():
    for s in phrases._phrases_oxygen_critical(colonists=12, cap=10):
        assert '12' in s and '10' in s
    for s in phrases._phrases_oxygen_low(colonists=8, cap=10):
        assert '8' in s and '10' in s


def test_medical_low_embeds_amount():
    assert all('3' in s for s in phrases._phrases_medical_low(3))


def test_milestone_embeds_colonist_count():
    assert all('100' in s for s in phrases._phrases_milestone(100))


def test_all_quiet_embeds_colonists_and_modules():
    result = phrases._phrases_all_quiet(colonists=15, modules=6)
    assert any('15' in s for s in result)
    assert any('6' in s for s in result)


# ── Singular/plural branches ─────────────────────────────────────────

def test_arrival_uses_singular_phrasing_for_one_colonist():
    result = phrases._phrases_arrival(1)
    assert all('1' not in s for s in result)


def test_arrival_embeds_count_for_multiple_colonists():
    assert all('5' in s for s in phrases._phrases_arrival(5))


def test_death_uses_singular_phrasing_for_one_colonist():
    result = phrases._phrases_death(1)
    assert all('1' not in s for s in result)


def test_death_embeds_count_for_multiple_colonists():
    assert all('4' in s for s in phrases._phrases_death(4))


# ── _phrases_food_item_low: depleted vs low-stock branch ─────────────

def test_food_item_low_depleted_branch_when_amount_is_zero():
    result = phrases._phrases_food_item_low("Мяса", 0)
    assert all('мяса' in s.lower() for s in result)
    assert not any(str(0) in s and 'мяса' not in s.lower() for s in result)


def test_food_item_low_shortage_branch_embeds_amount_when_positive():
    result = phrases._phrases_food_item_low("Овощей", 7)
    assert all('овощей' in s.lower() and '7' in s for s in result)


# ── Cross-check against monitor.py's actual call sites ───────────────

def test_monitor_imports_every_phrase_symbol_used_here():
    # Guards against the split silently dropping a symbol monitor.py needs.
    assert monitor._phrases_power_low is phrases._phrases_power_low
    assert monitor._phrases_arrival is phrases._phrases_arrival
    assert monitor._INTROS is phrases._INTROS
