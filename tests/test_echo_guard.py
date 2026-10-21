from core.engine.echo_guard import EchoGuard


def test_never_played_is_not_covered():
    assert EchoGuard().update(False, now=1000.0) is False


def test_playing_is_covered():
    assert EchoGuard().update(True, now=10.0) is True


def test_tail_keeps_covering_after_playback_stops():
    g = EchoGuard(tail_sec=0.6)
    g.update(True, now=10.0)
    assert g.update(False, now=10.3) is True
    assert g.update(False, now=10.59) is True


def test_tail_expires():
    g = EchoGuard(tail_sec=0.6)
    g.update(True, now=10.0)
    assert g.update(False, now=10.7) is False


def test_new_playback_restarts_tail():
    g = EchoGuard(tail_sec=0.6)
    g.update(True, now=10.0)
    g.update(True, now=10.5)
    assert g.update(False, now=11.0) is True
