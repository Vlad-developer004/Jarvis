"""ui_next.host: the core's side of the window (state, notices, commands, pop-ups) and ui_next.shell (starting the window process)."""
import threading
import time

import pytest

from ui_next import bridge, host, shell


class FakeHub:
    def __init__(self, on=True):
        self.on = on
        self.sent = []

    def has_clients(self):
        return self.on

    def publish(self, topic, payload, sticky=True):
        self.sent.append((topic, payload, sticky))


@pytest.fixture
def hub(monkeypatch):
    h = FakeHub()
    monkeypatch.setattr(bridge, '_hub', h)
    return h


def test_state_is_shared_and_has_its_own_lock():
    host.STATE.mode = host.HudState.SPEAKING
    assert host.STATE.mode == 'SPEAKING'
    host.set_mode(host.HudState.IDLE)
    assert host.STATE.mode == 'IDLE'


def test_notices_are_joined_updated_and_cleared():
    host.notify('a', 'first', host.AMBER)
    host.notify('b', 'second')
    host.notify('a', 'first again', host.RED)
    assert host.active_notices() == [('a', 'first again', host.RED), ('b', 'second', host.CYAN)]
    host.clear_notify('a')
    host.clear_notify('b')
    assert host.active_notices() == []


def test_a_notice_with_a_duration_clears_itself():
    host.notify('short', 'x', duration=30)
    assert [n[0] for n in host.active_notices()] == ['short']
    for _ in range(50):
        if not host.active_notices():
            break
        time.sleep(0.02)
    assert host.active_notices() == []


def test_commands_reach_the_window_only_when_it_is_connected(hub, monkeypatch):
    assert host.command('view', name='look') is True
    assert hub.sent[-1] == ('uicmd', {'op': 'view', 'name': 'look'}, False)
    hub.on = False
    assert host.command('view', name='look') is False


def test_open_view_brings_the_window_forward_first(hub):
    assert host.open_view('perf') is True
    assert [p['op'] for _t, p, _s in hub.sent] == ['show', 'view']


def test_reactor_mail_and_wizard_commands(hub):
    host.reactor('color', 'red')
    host.open_mail_compose()
    host.open_wizard()
    ops = [(p['op'], p.get('what'), p.get('color')) for _t, p, _s in hub.sent if p['op'] in ('reactor', 'compose', 'wizard')]
    assert ops == [('reactor', 'color', 'red'), ('compose', None, None), ('wizard', None, None)]


def test_show_window_starts_the_shell_when_no_window_is_connected(hub, monkeypatch):
    hub.on = False
    started = []
    monkeypatch.setattr(shell, 'ensure_running', lambda: started.append(1) or True)
    assert host.show_window() is True and started == [1]


def test_alert_carries_actions_and_accepts_only_their_ids(hub, monkeypatch):
    from ui_next.bridge import prompts
    seen = {}
    monkeypatch.setattr(prompts, 'open_prompt', lambda kind, data, ctx, done, **kw: seen.update(kind=kind, data=data, ctx=ctx, kw=kw) or True)
    assert host.show_alert('Напоминание', 'позвонить', actions=[{'id': 'snooze5', 'label': 'Отложить'}], voice=(('ок',), ('стоп',)), timeout=60) is True
    assert seen['kind'] == 'notice' and seen['data']['actions'] == [{'id': 'snooze5', 'label': 'Отложить', 'primary': False}]
    assert seen['ctx']['validate']('snooze5') == 'snooze5' and seen['ctx']['validate']('evil') is None
    assert seen['kw'] == {'timeout': 60, 'voice': (('ок',), ('стоп',))}


def test_alert_without_a_window_reports_it():
    assert host.show_alert('x', 'y') is False


def test_the_answer_card_obeys_the_settings_switch(monkeypatch):
    from core import settings_io
    taken = []
    monkeypatch.setattr(bridge, 'answer_event', lambda kind, *a: taken.append(kind) or True)
    monkeypatch.setattr(settings_io, 'read', lambda: {'ai_mini_window': False})
    host.show_ai_window('Марс')
    monkeypatch.setattr(settings_io, 'read', lambda: {})
    host.show_ai_window('Марс')
    assert taken == ['show']


def test_questions_without_a_window_count_as_cancelled():
    assert host.ask_text(title='t', header='h') is None
    assert host.ask_git_stage('.', []) is None
    assert host.open_yt_picker([], lambda *a: None) is False
    assert host.is_picker_open() is False


def test_exit_now_closes_the_shell_and_the_bridge_before_exiting(monkeypatch):
    order = []
    monkeypatch.setattr(shell, 'stop', lambda: order.append('shell'))
    monkeypatch.setattr(bridge, 'stop', lambda: order.append('bridge'))
    import os
    monkeypatch.setattr(os, '_exit', lambda code: order.append(('exit', code)))
    host.exit_now(3)
    assert order == ['shell', 'bridge', ('exit', 3)]


# ---- shell.py ----
def test_find_exe_prefers_the_override_then_the_built_program(tmp_path, monkeypatch):
    exe = tmp_path / 'my.exe'
    exe.write_text('x')
    monkeypatch.setenv('JARVIS_SHELL_EXE', str(exe))
    assert shell.find_exe() == exe
    monkeypatch.setenv('JARVIS_SHELL_EXE', str(tmp_path / 'missing.exe'))
    monkeypatch.setattr(shell, '_roots', lambda: [tmp_path])
    assert shell.find_exe() is None
    (tmp_path / 'jarvis-ui.exe').write_text('x')
    assert shell.find_exe() == tmp_path / 'jarvis-ui.exe'


class FakeProc:
    def __init__(self, lifetime):
        self.lifetime = lifetime
        self.done = threading.Event()
        self.terminated = False

    def wait(self):
        time.sleep(self.lifetime)
        self.done.set()

    def poll(self):
        return 0 if self.done.is_set() else None

    def terminate(self):
        self.terminated = True


@pytest.fixture
def fresh_shell(monkeypatch):
    monkeypatch.setattr(shell, '_proc', None)
    monkeypatch.setattr(shell, '_started_at', 0.0)


def test_launch_without_a_program_returns_false(fresh_shell, monkeypatch):
    monkeypatch.setattr(shell, 'find_exe', lambda: None)
    assert shell.launch() is False and shell.is_running() is False


def test_a_quick_exit_means_a_window_was_already_open_and_does_not_quit_the_core(fresh_shell, monkeypatch):
    monkeypatch.setattr(shell, '_MIN_LIFETIME', 0.5)
    proc = FakeProc(0.05)
    monkeypatch.setattr(shell, '_proc', proc)
    monkeypatch.setattr(shell, '_started_at', time.monotonic())
    quits = []
    shell.watch(lambda: quits.append(1))
    time.sleep(0.3)
    assert quits == []


def test_a_window_that_lived_a_while_and_closed_quits_the_core(fresh_shell, monkeypatch):
    monkeypatch.setattr(shell, '_MIN_LIFETIME', 0.1)
    proc = FakeProc(0.25)
    monkeypatch.setattr(shell, '_proc', proc)
    monkeypatch.setattr(shell, '_started_at', time.monotonic())
    quits = []
    shell.watch(lambda: quits.append(1))
    for _ in range(60):
        if quits:
            break
        time.sleep(0.02)
    assert quits == [1]


def test_stop_terminates_a_running_shell(fresh_shell, monkeypatch):
    proc = FakeProc(0)
    monkeypatch.setattr(shell, '_proc', proc)
    shell.stop()
    assert proc.terminated is True
