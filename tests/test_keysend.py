"""Tests for actions/keysend.py's key-sequence construction logic
(press/hold/hotkey). This module sends REAL synthetic key events via
WinAPI SendInput — every test here mocks _send() (or _user32.SendInput for
the one test that needs it) so nothing is ever actually injected into the
host machine's input queue. What's verified is the down/up ordering and
sequence shape, which is exactly the part that's easy to get subtly wrong
(e.g. releasing modifiers in the wrong order, or forgetting a key-up).
"""
import actions.keysend as keysend

_KEYEVENTF_KEYUP = 0x0002


def _is_key_up(built_input) -> bool:
    return bool(built_input.union.ki.dwFlags & _KEYEVENTF_KEYUP)


def test_press_sends_down_then_up(monkeypatch):
    captured = []
    monkeypatch.setattr(keysend, '_send', lambda inputs: captured.append(inputs))

    keysend.press('a')

    assert len(captured) == 1
    seq = captured[0]
    assert len(seq) == 2
    assert _is_key_up(seq[0]) is False
    assert _is_key_up(seq[1]) is True


def test_key_down_and_key_up_send_single_events(monkeypatch):
    captured = []
    monkeypatch.setattr(keysend, '_send', lambda inputs: captured.append(inputs))

    keysend.key_down('shift')
    keysend.key_up('shift')

    assert len(captured) == 2
    assert _is_key_up(captured[0][0]) is False
    assert _is_key_up(captured[1][0]) is True


def test_hotkey_two_keys_presses_modifier_then_main_and_releases_correctly(monkeypatch):
    captured = []
    monkeypatch.setattr(keysend, '_send', lambda inputs: captured.append(inputs))

    keysend.hotkey('ctrl', 'c')

    assert len(captured) == 1
    seq = captured[0]
    assert len(seq) == 4
    # order: mod-down, main-down, main-up, mod-up
    assert [_is_key_up(s) for s in seq] == [False, False, True, True]


def test_hotkey_three_keys_releases_modifiers_in_reverse_order(monkeypatch):
    captured = []
    monkeypatch.setattr(keysend, '_send', lambda inputs: captured.append(inputs))

    keysend.hotkey('ctrl', 'shift', 'a')

    seq = captured[0]
    assert len(seq) == 6
    # ctrl-down, shift-down, a-down, a-up, shift-up, ctrl-up
    assert [_is_key_up(s) for s in seq] == [False, False, False, True, True, True]
    # verify the release order is the exact reverse of the press order
    ctrl_vk = keysend.resolve_vk('ctrl')
    shift_vk = keysend.resolve_vk('shift')
    down_vks = [s.union.ki.wScan for s in seq[:2]]
    up_vks = [s.union.ki.wScan for s in seq[4:]]
    assert down_vks == list(reversed(up_vks))


def test_hold_sleeps_for_requested_duration_between_down_and_up(monkeypatch):
    captured = []
    slept = []
    monkeypatch.setattr(keysend, '_send', lambda inputs: captured.append(inputs))
    monkeypatch.setattr(keysend.time, 'sleep', lambda secs: slept.append(secs))

    keysend.hold('space', duration=0.3)

    assert len(captured) == 2  # one down event, one up event
    assert _is_key_up(captured[0][0]) is False
    assert _is_key_up(captured[1][0]) is True
    assert slept == [0.3]


def test_send_raises_when_sendinput_reports_fewer_events_sent(monkeypatch):
    monkeypatch.setattr(keysend._user32, 'SendInput', lambda count, ptr, size: count - 1)

    import pytest
    with pytest.raises(RuntimeError):
        keysend.press('a')
