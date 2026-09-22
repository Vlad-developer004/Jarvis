"""Tests for core/handler/commands/system.py — shutdown/restart, brightness,
wifi/bluetooth toggles, guard mode, shutdown timer, reminders. Previously
untested at the handler layer despite containing some of the most
destructive/irreversible commands in the project (shutdown, restart,
system cleanup). All underlying actions.* calls are mocked — this tests the
routing and text-parsing logic, not the real OS side effects.
"""
import pytest

import core.handler.commands.system as sys_cmd
from core.system import app_state


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []
        self.interactive_state = None
        self.interactive_data = None

    def speak(self, text, wait=False):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data


# ── handle_system routing ────────────────────────────────────────────────

def test_handle_system_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(sys_cmd._SYSTEM_ACTIONS, 'listen_off', lambda h, t, a: called.append((t, a)))
    handler = _FakeHandler()

    sys_cmd.handle_system(handler, 'listen_off', 'замолчи', 0)

    assert called == [('замолчи', 0)]


def test_handle_system_unknown_command_does_nothing():
    handler = _FakeHandler()
    sys_cmd.handle_system(handler, 'not_a_real_command', 'text', 0)
    assert handler.spoken == []


def test_system_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(sys_cmd._SYSTEM_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_SYSTEM_ACTIONS has non-existent intent keys: {unknown}'


# ── _fmt_delay ────────────────────────────────────────────────────────────

def test_fmt_delay_seconds_uses_correct_plural():
    assert sys_cmd._fmt_delay(1) == '1 секунду'
    assert sys_cmd._fmt_delay(3) == '3 секунды'
    assert sys_cmd._fmt_delay(10) == '10 секунд'


def test_fmt_delay_minutes_delegates_to_minute_formatter():
    result = sys_cmd._fmt_delay(120)
    assert 'секунд' not in result


# ── shutdown / restart (irreversible — must actually call through) ───────

def test_sys_shutdown_calls_through_to_real_action(monkeypatch):
    called = []
    monkeypatch.setattr('actions.system.shutdown_pc', lambda: called.append(True))
    handler = _FakeHandler()

    sys_cmd._sys_shutdown(handler, 'выключи компьютер', 0)

    assert called == [True]
    assert handler.play_response_calls


def test_sys_restart_calls_through_to_real_action(monkeypatch):
    called = []
    monkeypatch.setattr('actions.system.restart_pc', lambda: called.append(True))
    handler = _FakeHandler()

    sys_cmd._sys_restart(handler, 'перезагрузи компьютер', 0)

    assert called == [True]


# ── wifi / bluetooth toggle word-detection ───────────────────────────────

@pytest.mark.parametrize('text,expected_enabled', [
    ('включи вайфай', True),
    ('отключи вайфай', False),
    ('выключи вайфай', False),
    ('выруби вайфай', False),
])
def test_wifi_toggle_detects_on_off_from_text(monkeypatch, text, expected_enabled):
    captured = []
    monkeypatch.setattr('actions.system.toggle_wifi', lambda enabled: captured.append(enabled) or True)
    handler = _FakeHandler()

    sys_cmd._sys_wifi_toggle(handler, text, 0)

    assert captured == [expected_enabled]


@pytest.mark.parametrize('text,expected_enabled', [
    ('включи блютуз', True),
    ('выключи блютуз', False),
])
def test_bluetooth_toggle_detects_on_off_from_text(monkeypatch, text, expected_enabled):
    captured = []
    monkeypatch.setattr('actions.system.toggle_bluetooth', lambda enabled: captured.append(enabled) or True)
    handler = _FakeHandler()

    sys_cmd._sys_bluetooth_toggle(handler, text, 0)

    assert captured == [expected_enabled]


# ── shutdown_timer ────────────────────────────────────────────────────────

def test_shutdown_timer_schedules_on_parseable_duration(monkeypatch):
    scheduled = []
    monkeypatch.setattr('actions.system_control.schedule_shutdown', lambda delay: scheduled.append(delay))
    handler = _FakeHandler()

    sys_cmd._sys_shutdown_timer(handler, 'выключи через 10 минут', 0)

    assert scheduled == [600]
    assert handler.spoken


def test_shutdown_timer_speaks_error_when_unparseable(monkeypatch):
    monkeypatch.setattr('actions.system_control.schedule_shutdown',
                         lambda delay: (_ for _ in ()).throw(AssertionError('must not schedule')))
    handler = _FakeHandler()

    sys_cmd._sys_shutdown_timer(handler, 'выключи как-нибудь потом', 0)

    assert handler.spoken


# ── cancel_timer ──────────────────────────────────────────────────────────

def test_cancel_timer_calls_through(monkeypatch):
    called = []
    monkeypatch.setattr('actions.system_control.cancel_shutdown', lambda: called.append(True))
    handler = _FakeHandler()

    sys_cmd._sys_cancel_timer(handler, 'отмени таймер', 0)

    assert called == [True]
    assert handler.spoken


# ── reminder ──────────────────────────────────────────────────────────────

def test_reminder_schedules_on_parseable_duration(monkeypatch):
    scheduled = []
    monkeypatch.setattr('features.reminder.schedule_reminder',
                         lambda delay, msg, speak_fn, hud: scheduled.append((delay, msg)))
    handler = _FakeHandler()

    sys_cmd._sys_reminder(handler, 'напомни через 5 минут выпить воды', 0)

    assert scheduled
    assert scheduled[0][0] == 300


def test_reminder_asks_when_duration_unparseable(monkeypatch):
    handler = _FakeHandler()

    sys_cmd._sys_reminder(handler, 'напомни мне что-нибудь', 0)

    assert handler.interactive_state == 'reminder_ask'
    assert handler.spoken


# ── listen_off / listen_on (app_state flag) ──────────────────────────────

def test_listen_off_sets_ignore_mode(monkeypatch):
    monkeypatch.setattr(app_state, 'ignore_mode', False)
    handler = _FakeHandler()

    sys_cmd._sys_listen_off(handler, 'замолчи', 0)

    assert app_state.ignore_mode is True


def test_listen_on_clears_ignore_mode(monkeypatch):
    monkeypatch.setattr(app_state, 'ignore_mode', True)
    handler = _FakeHandler()

    sys_cmd._sys_listen_on(handler, 'слушай', 0)

    assert app_state.ignore_mode is False


# ── guard mode ────────────────────────────────────────────────────────────

def test_guard_on_success_speaks_confirmation(monkeypatch):
    monkeypatch.setattr('features.guard.start_guard', lambda: (True, 'ok'))
    handler = _FakeHandler()

    sys_cmd._sys_guard_on(handler, 'включи охрану', 0)

    assert len(handler.spoken) == 2  # 'activating' then 'on'


def test_guard_on_failure_speaks_error_not_confirmation(monkeypatch):
    monkeypatch.setattr('features.guard.start_guard', lambda: (False, 'camera busy'))
    handler = _FakeHandler()

    sys_cmd._sys_guard_on(handler, 'включи охрану', 0)

    assert len(handler.spoken) == 2  # 'activating' then the error message
    assert 'camera busy' in handler.spoken[-1]
