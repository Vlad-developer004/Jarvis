"""Tests for actions/orphan_scan.py — the deep-cleanup orphan folder
scanner. High-stakes logic: _is_known() decides which AppData folders are
"safe to flag for deletion" vs. protected, and a false negative here (a
real program's folder wrongly treated as orphaned) risks the review dialog
offering to delete live user data. delete_candidates() actually calls
shutil.rmtree(), tested only against throwaway tmp_path directories.
"""
import os
import time

import actions.orphan_scan as scan


# ── _norm ─────────────────────────────────────────────────────────────────

def test_norm_lowercases_and_strips_non_alphanumeric():
    assert scan._norm('My-App_2024!') == 'myapp2024'


def test_norm_empty_string():
    assert scan._norm('') == ''


# ── _is_known: safe-skip whitelist ───────────────────────────────────────

def test_is_known_flags_windows_system_folders_as_known():
    assert scan._is_known('Microsoft', set()) is True
    assert scan._is_known('Temp', set()) is True
    assert scan._is_known('Packages', set()) is True


def test_is_known_prefix_match_catches_variants():
    # 'microsoft' is a _SAFE_SKIP token; 'Microsoft SDKs' should also match
    # via the startswith() prefix rule, not just an exact name.
    assert scan._is_known('Microsoft SDKs', set()) is True


def test_is_known_never_flags_jarvis_own_data():
    assert scan._is_known('Jarvis', set()) is True
    assert scan._is_known('JarvisVoiceAssistant', set()) is True


def test_is_known_skips_dotfiles_and_clsid_folders():
    assert scan._is_known('.config', set()) is True
    assert scan._is_known('{ABCDEF12-3456-7890}', set()) is True


def test_is_known_skips_empty_normalized_name():
    assert scan._is_known('---', set()) is True


# ── _is_known: installed-program matching ────────────────────────────────

def test_is_known_matches_installed_program_by_substring():
    installed = {scan._norm('Discord Inc.')}
    assert scan._is_known('Discord', installed) is True


def test_is_known_matches_when_folder_name_contains_program_name():
    installed = {scan._norm('Steam')}
    assert scan._is_known('SteamLibraryCache', installed) is True


def test_is_known_fuzzy_matches_close_typo_in_installed_name():
    installed = {scan._norm('Notion')}
    # Close enough that partial_ratio should catch it even with an extra char
    assert scan._is_known('Notionn', installed) is True


def test_is_known_returns_false_for_genuinely_unmatched_folder():
    installed = {scan._norm('Discord'), scan._norm('Steam')}
    assert scan._is_known('SomeUninstalledAppXYZ123', installed) is False


# ── _dir_size ─────────────────────────────────────────────────────────────

def test_dir_size_sums_file_sizes(tmp_path):
    (tmp_path / 'a.txt').write_bytes(b'x' * 100)
    (tmp_path / 'b.txt').write_bytes(b'y' * 250)
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 'c.txt').write_bytes(b'z' * 50)

    assert scan._dir_size(str(tmp_path)) == 400


def test_dir_size_empty_directory_is_zero(tmp_path):
    assert scan._dir_size(str(tmp_path)) == 0


# ── find_orphan_candidates age filtering ─────────────────────────────────

def test_find_orphan_candidates_skips_recently_modified_folders(tmp_path, monkeypatch):
    recent = tmp_path / 'SomeRecentApp'
    recent.mkdir()
    (recent / 'f.txt').write_text('x', encoding='utf-8')

    monkeypatch.setattr(scan, 'get_installed_program_names', lambda: set())
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'does_not_exist'))

    candidates = scan.find_orphan_candidates()

    # Freshly created dir is younger than MIN_AGE_DAYS -> excluded
    assert not any(c['name'] == 'SomeRecentApp' for c in candidates)


def test_find_orphan_candidates_includes_old_unknown_folder(tmp_path, monkeypatch):
    old = tmp_path / 'OldUnknownApp'
    old.mkdir()
    (old / 'f.txt').write_text('x' * 10, encoding='utf-8')
    old_time = time.time() - (scan.MIN_AGE_DAYS + 5) * 86400
    os.utime(old, (old_time, old_time))

    monkeypatch.setattr(scan, 'get_installed_program_names', lambda: set())
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'does_not_exist'))

    candidates = scan.find_orphan_candidates()

    assert any(c['name'] == 'OldUnknownApp' for c in candidates)


def test_find_orphan_candidates_excludes_known_safe_folder_even_if_old(tmp_path, monkeypatch):
    old = tmp_path / 'Microsoft'
    old.mkdir()
    old_time = time.time() - (scan.MIN_AGE_DAYS + 5) * 86400
    os.utime(old, (old_time, old_time))

    monkeypatch.setattr(scan, 'get_installed_program_names', lambda: set())
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'does_not_exist'))

    candidates = scan.find_orphan_candidates()

    assert not any(c['name'] == 'Microsoft' for c in candidates)


def test_find_orphan_candidates_sorted_largest_first(tmp_path, monkeypatch):
    old_time = time.time() - (scan.MIN_AGE_DAYS + 5) * 86400
    small = tmp_path / 'SmallOldApp'
    small.mkdir()
    (small / 'f.txt').write_bytes(b'x' * 10)
    os.utime(small, (old_time, old_time))

    big = tmp_path / 'BigOldApp'
    big.mkdir()
    (big / 'f.txt').write_bytes(b'x' * 10000)
    os.utime(big, (old_time, old_time))

    monkeypatch.setattr(scan, 'get_installed_program_names', lambda: set())
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'does_not_exist'))

    candidates = scan.find_orphan_candidates()
    names_in_order = [c['name'] for c in candidates]

    assert names_in_order.index('BigOldApp') < names_in_order.index('SmallOldApp')


# ── delete_candidates ─────────────────────────────────────────────────────

def test_delete_candidates_removes_directory_and_reports_freed_bytes(tmp_path):
    target = tmp_path / 'ToDelete'
    target.mkdir()
    (target / 'f.txt').write_bytes(b'x' * 500)

    freed, errors = scan.delete_candidates([str(target)])

    assert not target.exists()
    assert freed == 500
    assert errors == 0


def test_delete_candidates_counts_errors_for_nonexistent_path(tmp_path):
    missing = tmp_path / 'DoesNotExist'

    freed, errors = scan.delete_candidates([str(missing)])

    assert errors == 1
