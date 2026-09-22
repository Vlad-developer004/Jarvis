"""Tests for actions/game_audio.py — the MFCC feature extractor and
GameAudioMatcher's sample-gating (_MIN_SAMPLES, _MIN_READY_COMMANDS) and
match-confidence logic (absolute threshold + margin over the runner-up,
mirroring the same "margin of confidence" pattern used by the semantic
intent classifier). _TEMPLATES_DIR is redirected to tmp_path so tests never
touch real game-profile template files.
"""
import numpy as np
import pytest

import actions.game_audio as ga


def _fake_audio(seed: int, n_samples: int = 4000) -> bytes:
    """Deterministic pseudo-audio: distinct seeds produce distinct feature
    vectors, same seed always reproduces the same one."""
    rng = np.random.RandomState(seed)
    samples = (rng.randn(n_samples) * 3000).astype(np.int16)
    return samples.tobytes()


@pytest.fixture(autouse=True)
def _isolated_templates_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ga, '_TEMPLATES_DIR', tmp_path / 'audio_templates')


# ── extract_features ──────────────────────────────────────────────────────

def test_extract_features_returns_fixed_length_vector():
    vec = ga.extract_features(_fake_audio(1))
    assert vec.shape == (ga._N_MFCC * 3,)


def test_extract_features_is_deterministic_for_same_input():
    a = ga.extract_features(_fake_audio(42))
    b = ga.extract_features(_fake_audio(42))
    assert np.allclose(a, b)


def test_extract_features_empty_audio_returns_zero_vector():
    vec = ga.extract_features(b'')
    assert np.all(vec == 0)


def test_extract_features_is_unit_normalized_for_nonzero_input():
    vec = ga.extract_features(_fake_audio(7))
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 1e-4 or norm == 0.0


# ── GameAudioMatcher: sample gating ───────────────────────────────────────

def test_ready_count_zero_before_any_samples():
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    assert m.ready_count() == 0


def test_ready_count_requires_min_samples_per_command():
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    m.add_sample('fire', _fake_audio(1))
    assert m.ready_count() == 0  # only 1 sample, _MIN_SAMPLES=2
    m.add_sample('fire', _fake_audio(2))
    assert m.ready_count() == 1


def test_add_sample_caps_stored_samples_at_five():
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    for i in range(8):
        m.add_sample('fire', _fake_audio(i))
    assert len(m._vecs['fire']) == 5


def test_match_returns_none_below_min_ready_commands():
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    # Only 2 commands trained with enough samples; _MIN_READY_COMMANDS is 3
    for cmd_idx in range(2):
        for i in range(3):
            m.add_sample(f'cmd{cmd_idx}', _fake_audio(cmd_idx * 10 + i))
    assert m.match(_fake_audio(999)) is None


def test_match_finds_closest_trained_command(monkeypatch):
    monkeypatch.setattr(ga, '_MIN_READY_COMMANDS', 1)
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    for i in range(3):
        m.add_sample('fire', _fake_audio(100 + i))

    result = m.match(_fake_audio(100))  # same seed as a trained sample

    assert result is not None
    name, score = result
    assert name == 'fire'
    assert score >= ga._MATCH_THRESHOLD


def test_match_rejects_when_below_confidence_margin(monkeypatch):
    # Two commands with near-identical (noise-derived) templates should not
    # confidently resolve to either — mirrors the semantic classifier's
    # margin-of-confidence OOD gate.
    monkeypatch.setattr(ga, '_MIN_READY_COMMANDS', 1)
    monkeypatch.setattr(ga, '_MATCH_THRESHOLD', 0.99)  # force an impossible bar
    m = ga.GameAudioMatcher()
    m.set_profile('test_profile')
    for i in range(3):
        m.add_sample('fire', _fake_audio(1 + i))

    result = m.match(_fake_audio(500))  # unrelated audio

    assert result is None


# ── set_profile persistence round-trip ────────────────────────────────────

def test_set_profile_persists_and_reloads_samples():
    m = ga.GameAudioMatcher()
    m.set_profile('persist_test')
    m.add_sample('fire', _fake_audio(1))
    m.add_sample('fire', _fake_audio(2))

    m2 = ga.GameAudioMatcher()
    m2.set_profile('persist_test')

    assert m2.ready_count() == 1
    assert 'fire' in m2._vecs


def test_reset_profile_clears_samples_and_deletes_file():
    m = ga.GameAudioMatcher()
    m.set_profile('reset_test')
    m.add_sample('fire', _fake_audio(1))
    m.add_sample('fire', _fake_audio(2))
    path = m._path()
    assert path.exists()

    m.reset_profile()

    assert not path.exists()
    assert m._vecs == {}


def test_clear_resets_state_without_touching_file():
    m = ga.GameAudioMatcher()
    m.set_profile('clear_test')
    m.add_sample('fire', _fake_audio(1))
    path = m._path()

    m.clear()

    assert m._vecs == {}
    assert m._profile == ''
    assert path.exists()  # clear() does not delete the persisted file
