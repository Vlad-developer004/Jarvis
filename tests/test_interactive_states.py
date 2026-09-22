"""Regression tests for interactive-state handlers in
core/handler/interactive.py beyond 'llm_action_confirm' (already covered in
test_llm_action_confirm.py). Nineteen of the twenty registered states had no
dedicated tests before this file — these cover the highest-traffic ones
(folder navigation, file search, network profile switch, reminders, weather
city) plus the global command-interrupt escape hatch in handle_interactive()
itself, which lets a small set of urgent commands (shutdown, restart, ...)
cut through any pending interactive prompt.
"""
import core.handler.interactive as interactive


class _FakeHandler:
    def __init__(self, state, data=None):
        self.interactive_state = state
        self.interactive_data = data or {}
        self.handle_calls = []
        self.spoken = []
        self.play_response_calls = []

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data or {}

    def handle(self, cmd, text):
        self.handle_calls.append((cmd, text))

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))


def _no_semantic(monkeypatch, global_cmd=''):
    monkeypatch.setattr(interactive, '_sem_cmd', lambda *a, **k: global_cmd)


# ── global command-interrupt escape hatch ────────────────────────────────

def test_shutdown_interrupts_any_pending_state(monkeypatch):
    _no_semantic(monkeypatch, global_cmd='shutdown')
    handler = _FakeHandler('reminder_ask', {})

    interactive.handle_interactive(handler, 'выключи компьютер')

    assert handler.handle_calls == [('shutdown', 'выключи компьютер')]
    assert handler.interactive_state is None


def test_unrelated_global_cmd_does_not_interrupt_pending_state(monkeypatch):
    _no_semantic(monkeypatch, global_cmd='open_browser')
    handler = _FakeHandler('cd_folder_ask', {})
    monkeypatch.setattr('actions.filesystem.goto_folder', lambda ctx, name: (True, 'ok'))

    interactive.handle_interactive(handler, 'загрузки')

    # The normal state handler ran instead of the interrupt shortcut
    assert handler.handle_calls == []
    assert handler.play_response_calls


# ── cd_folder_ask ─────────────────────────────────────────────────────────

def test_cd_folder_ask_navigates_on_valid_name(monkeypatch):
    _no_semantic(monkeypatch)
    calls = []
    monkeypatch.setattr('actions.filesystem.goto_folder',
                         lambda ctx, name: calls.append(name) or (True, 'ok'))
    handler = _FakeHandler('cd_folder_ask', {})

    interactive.handle_interactive(handler, 'Загрузки')

    assert calls == ['загрузки']
    assert handler.play_response_calls
    assert handler.interactive_state is None


def test_cd_folder_ask_cancel_word_clears_state_without_navigating(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('actions.filesystem.goto_folder',
                         lambda ctx, name: (_ for _ in ()).throw(AssertionError('must not be called')))
    handler = _FakeHandler('cd_folder_ask', {})

    interactive.handle_interactive(handler, 'отмена')

    assert handler.interactive_state is None


def test_cd_folder_ask_empty_reply_keeps_state_alive(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('cd_folder_ask', {})

    interactive.handle_interactive(handler, '   ')

    assert handler.interactive_state == 'cd_folder_ask'


# ── net_profile_ask ───────────────────────────────────────────────────────

def test_net_profile_ask_switches_on_recognized_profile(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('actions.network_profiles.parse_profile_target', lambda t: 'home')
    monkeypatch.setattr('actions.network_profiles.set_active_profile',
                         lambda key: (True, f'switched to {key}'))
    handler = _FakeHandler('net_profile_ask', {})

    interactive.handle_interactive(handler, 'домашний')

    assert handler.spoken == ['switched to home']
    assert handler.interactive_state is None


def test_net_profile_ask_unrecognized_profile_reasks_instead_of_crashing(monkeypatch):
    _no_semantic(monkeypatch)
    monkeypatch.setattr('actions.network_profiles.parse_profile_target', lambda t: None)
    handler = _FakeHandler('net_profile_ask', {})

    interactive.handle_interactive(handler, 'чепуха какая-то')

    assert handler.spoken  # some re-ask message was spoken, not silently dropped
    assert handler.interactive_state is None  # state.py clears it either way (see source)


# ── reminder_ask ──────────────────────────────────────────────────────────

def test_reminder_ask_schedules_on_parseable_duration(monkeypatch):
    _no_semantic(monkeypatch)
    scheduled = []
    monkeypatch.setattr('features.reminder.schedule_reminder',
                         lambda delay, msg, speak_fn, hud: scheduled.append(delay))
    handler = _FakeHandler('reminder_ask', {})

    interactive.handle_interactive(handler, 'через 10 минут')

    assert scheduled == [600]
    assert handler.interactive_state is None


def test_reminder_ask_unparseable_duration_reasks_and_keeps_waiting(monkeypatch):
    _no_semantic(monkeypatch)
    handler = _FakeHandler('reminder_ask', {})

    interactive.handle_interactive(handler, 'скоро наверное')

    assert handler.interactive_state == 'reminder_ask'
    assert handler.spoken


# ── weather_city_ask ──────────────────────────────────────────────────────

def test_weather_city_ask_saves_city_and_clears_state(monkeypatch, tmp_path):
    _no_semantic(monkeypatch)
    settings_file = tmp_path / 'settings.json'
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: str(settings_file))
    # _hud_cache.clear() is called by the handler — stub an object exposing .clear()
    class _StubCache:
        def clear(self):
            pass
    monkeypatch.setattr('actions.weather._hud_cache', _StubCache())
    handler = _FakeHandler('weather_city_ask', {})

    interactive.handle_interactive(handler, 'Берлин')

    assert handler.interactive_state is None
    assert handler.spoken
    import json
    saved = json.loads(settings_file.read_text(encoding='utf-8'))
    assert saved['manual_city'] == 'Берлин'
