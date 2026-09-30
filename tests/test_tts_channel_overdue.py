"""Regression: a long sentence must not be cut off by the stuck-channel safety net.

The blind stuck-timeout used to fire ~6 s after the last chunk was handed to the
channel even when the sound's real length (deadline) said it was still playing,
so any sentence/answer longer than ~6 s was chopped mid-word."""
from core.speech.tts import _channel_overdue

_TIMEOUT = 6.0


def test_long_sentence_is_not_cut_at_the_blind_timeout():
    # 12.4 s sound started at t=0, deadline ~13.2 s; channel "stuck" since t=0.
    assert _channel_overdue(now=6.5, deadline=13.2, stuck_since=0.0, stuck_timeout=_TIMEOUT) is False
    assert _channel_overdue(now=12.9, deadline=13.2, stuck_since=0.0, stuck_timeout=_TIMEOUT) is False


def test_latched_busy_channel_is_cleared_after_the_deadline():
    assert _channel_overdue(now=13.3, deadline=13.2, stuck_since=0.0, stuck_timeout=_TIMEOUT) is True


def test_unknown_length_falls_back_to_the_blind_timeout():
    assert _channel_overdue(now=5.0, deadline=None, stuck_since=0.0, stuck_timeout=_TIMEOUT) is False
    assert _channel_overdue(now=6.5, deadline=None, stuck_since=0.0, stuck_timeout=_TIMEOUT) is True
