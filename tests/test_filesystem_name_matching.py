"""Tests for actions/filesystem.py's voice-name matching helpers:
get_name_variants (transliteration variants used to match a spoken name
against a real file/folder name) and resolve_folder_for_hint (turning a
spoken "в папке X" location into an actual directory).
"""
from pathlib import Path

import actions.filesystem as fs


# ── get_name_variants — foreign-name transliteration ─────────────────────

def test_get_name_variants_adds_plain_h_variant_for_german_style_names():
    # "Манхольт" (German "Manholt") transliterates via the base Cyrillic
    # table to "mankholt" (х -> kh); a plain "h" variant must also be
    # produced so it matches the real filename "Manholt".
    variants = fs.get_name_variants('манхольт')
    assert 'manholt' in variants
    assert 'mankholt' in variants  # original variant still present


def test_get_name_variants_unaffected_for_names_without_kh():
    # A name with no "х" at all should not gain any spurious "kh"/"h" variant.
    variants = fs.get_name_variants('привет')
    assert fs._translit_cyr_to_lat('привет') in variants
    assert not any('kh' in v for v in variants)


def test_get_name_variants_keeps_original_kh_for_genuine_guttural_words():
    # "техника" -> "tekhnyka" is a real transliteration (guttural х), not a
    # German name — the new "h" variant is added alongside it, not instead.
    variants = fs.get_name_variants('техника')
    assert 'tekhnyka' in variants
    assert 'tehnyka' in variants


# ── resolve_folder_for_hint ────────────────────────────────────────────────

def test_resolve_folder_for_hint_no_hint_returns_base(tmp_path):
    base, warn = fs.resolve_folder_for_hint(None, str(tmp_path))
    assert base == tmp_path.resolve()
    assert warn is None


def test_resolve_folder_for_hint_direct_subfolder_match(tmp_path):
    target = tmp_path / 'downloads'
    target.mkdir()

    base, warn = fs.resolve_folder_for_hint('downloads', str(tmp_path))

    assert base == target.resolve()
    assert warn is None


def test_resolve_folder_for_hint_fuzzy_subfolder_match(tmp_path):
    target = tmp_path / 'Загрузки'
    target.mkdir()

    base, warn = fs.resolve_folder_for_hint('загрузк', str(tmp_path))

    assert base == target.resolve()
    assert warn is None


def test_resolve_folder_for_hint_not_found_warns_and_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, '_find_folder_anywhere', lambda *a, **k: None)

    base, warn = fs.resolve_folder_for_hint('нет-такой-папки', str(tmp_path))

    assert base == tmp_path.resolve()
    assert warn is not None
    assert 'нет-такой-папки' in warn
