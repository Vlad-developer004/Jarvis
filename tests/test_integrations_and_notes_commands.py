"""Tests for core/handler/commands/integrations.py (network profiles, VPN
reminder, disk health, calendar, mail) and core/handler/commands/notes.py
(voice notes, reminder cancellation) — both previously untested at the
handler layer.
"""
import threading

import core.handler.commands.integrations as integ_cmd
import core.handler.commands.notes as notes_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []
        self.interactive_state = None
        self.interactive_data = None

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


# ── handle_integrations routing ──────────────────────────────────────────

def test_handle_integrations_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(integ_cmd._INTEGRATIONS_ACTIONS, 'vpn_reminder', lambda h, t: called.append(t))
    handler = _FakeHandler()

    integ_cmd.handle_integrations(handler, 'vpn_reminder', 'нужен ли впн')

    assert called == ['нужен ли впн']


def test_integrations_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(integ_cmd._INTEGRATIONS_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_INTEGRATIONS_ACTIONS has non-existent intent keys: {unknown}'


# ── net_profile_switch ────────────────────────────────────────────────────

def test_net_profile_switch_with_recognized_target(monkeypatch):
    monkeypatch.setattr('actions.network_profiles.parse_profile_target', lambda t: 'home')
    monkeypatch.setattr('actions.network_profiles.set_active_profile',
                         lambda key: (True, f'switched to {key}'))
    handler = _FakeHandler()

    integ_cmd._net_profile_switch(handler, 'переключи на домашний профиль')

    assert handler.spoken == ['switched to home']
    assert handler.interactive_state is None


def test_net_profile_switch_without_target_asks(monkeypatch):
    monkeypatch.setattr('actions.network_profiles.parse_profile_target', lambda t: None)
    handler = _FakeHandler()

    integ_cmd._net_profile_switch(handler, 'переключи профиль')

    assert handler.interactive_state == 'net_profile_ask'
    assert handler.spoken


# ── inbox_unread (background thread) ─────────────────────────────────────

def test_inbox_unread_speaks_progress_then_result(monkeypatch):
    monkeypatch.setattr(threading, 'Thread', _ImmediateThread)
    monkeypatch.setattr('actions.inbox_imap.unread_count_voice', lambda: '3 непрочитанных')
    handler = _FakeHandler()

    integ_cmd._inbox_unread(handler, 'сколько непрочитанных писем')

    assert handler.spoken == ['Проверяю почту...', '3 непрочитанных']


# ── net_profile_status / vpn_reminder / health_disks / calendar_next ────

def test_net_profile_status_speaks_description(monkeypatch):
    monkeypatch.setattr('actions.network_profiles.describe_network_state', lambda: 'дома, вайфай')
    handler = _FakeHandler()

    integ_cmd._net_profile_status(handler, 'какой сейчас профиль сети')

    assert handler.spoken == ['дома, вайфай']


def test_vpn_reminder_speaks_result(monkeypatch):
    monkeypatch.setattr('actions.network_profiles.vpn_reminder_for_active', lambda: 'включи впн')
    handler = _FakeHandler()

    integ_cmd._vpn_reminder(handler, 'нужен ли впн')

    assert handler.spoken == ['включи впн']


def test_health_disks_speaks_result(monkeypatch):
    monkeypatch.setattr('actions.system_health_extra.disk_health_voice', lambda: 'диски в порядке')
    handler = _FakeHandler()

    integ_cmd._health_disks(handler, 'как там диски')

    assert handler.spoken == ['диски в порядке']


def test_calendar_next_speaks_result(monkeypatch):
    monkeypatch.setattr('actions.calendar_ics.next_events_summary', lambda ctx: 'встреча в 15:00')
    handler = _FakeHandler()

    integ_cmd._calendar_next(handler, 'что дальше по календарю')

    assert handler.spoken == ['встреча в 15:00']


# ── notes.py ──────────────────────────────────────────────────────────────

def test_note_save_strips_keywords_and_saves(monkeypatch):
    saved = []
    monkeypatch.setattr(notes_cmd, 'save_note', lambda note: saved.append(note) or (True, 'ok'))
    handler = _FakeHandler()

    notes_cmd.handle_notes(handler, 'note_save', 'запиши заметку купить молоко', 0)

    assert saved == ['купить молоко']
    assert handler.play_response_calls


def test_note_save_empty_text_asks_for_note(monkeypatch):
    handler = _FakeHandler()

    notes_cmd.handle_notes(handler, 'note_save', 'запиши заметку', 0)

    assert handler.interactive_state == 'note_ask'
    assert handler.spoken


def test_note_save_speaks_error_on_failure(monkeypatch):
    monkeypatch.setattr(notes_cmd, 'save_note', lambda note: (False, 'disk error'))
    handler = _FakeHandler()

    notes_cmd.handle_notes(handler, 'note_save', 'запиши заметку купить молоко', 0)

    assert handler.play_response_calls == []
    assert handler.spoken


def test_cancel_reminder_success_plays_response(monkeypatch):
    monkeypatch.setattr(notes_cmd, 'cancel_reminders', lambda: (True, 'cancelled'))
    handler = _FakeHandler()

    notes_cmd.handle_notes(handler, 'cancel_reminder', 'отмени напоминание', 0)

    assert handler.play_response_calls


def test_cancel_reminder_failure_speaks_message(monkeypatch):
    monkeypatch.setattr(notes_cmd, 'cancel_reminders', lambda: (False, 'нет активных напоминаний'))
    handler = _FakeHandler()

    notes_cmd.handle_notes(handler, 'cancel_reminder', 'отмени напоминание', 0)

    assert handler.spoken == ['нет активных напоминаний']
    assert handler.play_response_calls == []
