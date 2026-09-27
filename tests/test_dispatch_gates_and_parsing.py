"""Tests for core/handler/dispatch.py's module gates and the pure
text-parsing helpers (parse_folder_name, parse_cd_name) — none of these had
dedicated tests before, despite gating whether a whole class of commands
runs at all and being the exact string-slicing logic that decides which
folder gets created/deleted/navigated to from a voice command.
"""
import pytest

from core.handler.dispatch import _MODULE_GATES, parse_folder_name, parse_cd_name
from core.system.modules import _PROFILE_PRESETS, _EXTENSION_BACKED_MODULES


# ── _MODULE_GATES consistency ────────────────────────────────────────────

def test_module_gates_reference_real_modules():
    known_modules = set(_PROFILE_PRESETS['full'].keys()) | _EXTENSION_BACKED_MODULES
    bad = [mod for _pred, mod, _msg in _MODULE_GATES if mod not in known_modules]
    assert not bad, f'_MODULE_GATES references non-existent modules: {bad}'


@pytest.mark.parametrize('cmd,expected_module', [
    ('qa_search', 'qa'),
    ('cinema_play', 'cinema'),
    ('game_mode_on', 'games'),
    ('ps_open', 'photoshop_voice'),
    ('figma_open', 'figma_voice'),
    ('net_profile_status', 'network_profiles'),
    ('health_disks', 'system_health'),
    ('calendar_next', 'calendar_ics'),
    ('inbox_unread', 'inbox_digest'),
    ('mail_compose', 'inbox_digest'),
])
def test_module_gate_predicate_matches_expected_command(cmd, expected_module):
    matched = [mod for pred, mod, _msg in _MODULE_GATES if pred(cmd)]
    assert expected_module in matched


def test_module_gate_predicates_do_not_false_positive_on_unrelated_commands():
    # A command sharing no prefix/membership with any gated group must not
    # accidentally trip a gate (e.g. a startswith() typo matching too much).
    for pred, mod, _msg in _MODULE_GATES:
        assert not pred('totally_unrelated_command_xyz'), (
            f'gate for module {mod!r} false-positives on an unrelated command')


# ── parse_folder_name ────────────────────────────────────────────────────

def test_parse_folder_name_create_basic():
    assert parse_folder_name('создай папку проекты', 'create') == ('проекты', None)


def test_parse_folder_name_create_strips_leading_novuyu():
    assert parse_folder_name('создай папку новую проекты', 'create') == ('проекты', None)


def test_parse_folder_name_create_strips_zdes():
    assert parse_folder_name('создай папку здесь проекты', 'create') == ('проекты', None)


def test_parse_folder_name_delete_basic():
    assert parse_folder_name('удали папку старое', 'delete') == ('старое', None)


def test_parse_folder_name_multiword_name():
    assert parse_folder_name('создай папку рабочие документы', 'create') == ('рабочие документы', None)


def test_parse_folder_name_without_papku_keyword_falls_back_to_verb():
    # No 'папку' token — parses off the create/delete verb directly
    assert parse_folder_name('создай проекты', 'create') == ('проекты', None)


def test_parse_folder_name_returns_empty_when_nothing_after_keyword():
    assert parse_folder_name('создай папку', 'create') == ('', None)


def test_parse_folder_name_returns_empty_for_unrelated_text():
    assert parse_folder_name('включи музыку', 'create') == ('', None)


def test_parse_folder_name_extracts_location_clause():
    # "создай папку в папке Downloads" — no name given, target folder is the location
    assert parse_folder_name('создай папку в папке downloads', 'create') == ('', 'downloads')


def test_parse_folder_name_with_name_and_location_clause():
    assert parse_folder_name('создай папку отчеты в папке downloads', 'create') == ('отчеты', 'downloads')


# ── parse_cd_name ────────────────────────────────────────────────────────

def test_parse_cd_name_with_papku_keyword():
    assert parse_cd_name('перейди в папку загрузки') == 'загрузки'


def test_parse_cd_name_strips_navigation_filler_words():
    assert parse_cd_name('перейди в папку сюда загрузки здесь') == 'загрузки'


def test_parse_cd_name_generic_open_verb_without_papku():
    assert parse_cd_name('открой в рабочий стол') == 'рабочий стол'


def test_parse_cd_name_returns_empty_for_unrelated_text():
    assert parse_cd_name('включи музыку') == ''
