"""Tests for actions/game_input_parts/profile.py::merge_bundled_spells — additive
sync of the bundled profile into the user's AppData copy."""
import json

from actions.game_input_parts.profile import merge_bundled_spells


def _write(path, spells, **extra):
    path.write_text(json.dumps({"game": "G", "spells": spells, **extra}, ensure_ascii=False), encoding="utf-8")


def _spells(path):
    return json.loads(path.read_text(encoding="utf-8"))["spells"]


def test_adds_missing_spells_and_variants_and_keeps_backup(tmp_path):
    user, bundled = tmp_path / "u.json", tmp_path / "b.json"
    _write(user, [{"name": "A", "variants": ["a1"], "key": "x"}])
    _write(bundled, [{"name": "A", "variants": ["a1", "a2"], "key": "x"},
                     {"name": "B", "variants": ["b1"], "telemetry_action": "t"}])

    assert merge_bundled_spells(user, bundled) == 2  # one variant + one spell

    spells = {s["name"]: s for s in _spells(user)}
    assert spells["A"]["variants"] == ["a1", "a2"]
    assert spells["B"]["telemetry_action"] == "t"
    assert (tmp_path / "u.json.bak").exists()


def test_never_changes_or_removes_user_edits(tmp_path):
    user, bundled = tmp_path / "u.json", tmp_path / "b.json"
    _write(user, [{"name": "A", "variants": ["mine"], "key": "custom"}, {"name": "Own", "variants": ["o"], "key": "k"}])
    _write(bundled, [{"name": "A", "variants": ["mine"], "key": "default"}])

    assert merge_bundled_spells(user, bundled) == 0

    spells = {s["name"]: s for s in _spells(user)}
    assert spells["A"]["key"] == "custom" and "Own" in spells
    assert not (tmp_path / "u.json.bak").exists()  # nothing changed, nothing written


def test_idempotent(tmp_path):
    user, bundled = tmp_path / "u.json", tmp_path / "b.json"
    _write(user, [])
    _write(bundled, [{"name": "B", "variants": ["b1"], "key": "k"}])
    assert merge_bundled_spells(user, bundled) == 1
    assert merge_bundled_spells(user, bundled) == 0
    assert len(_spells(user)) == 1


def test_missing_files_are_a_noop(tmp_path):
    assert merge_bundled_spells(tmp_path / "nope.json", tmp_path / "also-nope.json") == 0
