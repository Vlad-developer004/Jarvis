"""Tests for core/handler/commands/windows.py, mouse.py, clip.py —
window management, mouse control, clipboard operations. Previously
untested at the handler layer. Real OS-touching calls (pyautogui clicks/
mouse movement, actual window operations) are mocked throughout — these
tests must never move the real cursor or click on the host machine.
"""
import core.handler.commands.windows as win_cmd
import core.handler.commands.mouse as mouse_cmd
import core.handler.commands.clip as clip_cmd
from core.system import app_state


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))


# ── windows.py ────────────────────────────────────────────────────────────

def test_handle_window_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(win_cmd._WINDOW_ACTIONS, 'min_win', lambda h, t, a: called.append(t))
    handler = _FakeHandler()

    win_cmd.handle_window(handler, 'min_win', 'сверни окно', 0)

    assert called == ['сверни окно']


def test_handle_window_routes_snap_prefix(monkeypatch):
    called = []
    monkeypatch.setattr(win_cmd, '_win_snap', lambda h, cmd, t, a: called.append(cmd))
    handler = _FakeHandler()

    win_cmd.handle_window(handler, 'win_snap_left', 'прижми окно слева', 0)

    assert called == ['win_snap_left']


def test_window_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(win_cmd._WINDOW_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_WINDOW_ACTIONS has non-existent intent keys: {unknown}'


def test_win_snap_extracts_direction_from_command(monkeypatch):
    captured = []
    monkeypatch.setattr(win_cmd, 'snap_window', lambda direction: captured.append(direction))
    handler = _FakeHandler()

    win_cmd._win_snap(handler, 'win_snap_right', 'прижми справа', 0)

    assert captured == ['right']
    assert handler.play_response_calls


def test_min_all_falls_back_to_hotkey_on_failure(monkeypatch):
    monkeypatch.setattr(win_cmd, 'minimize_all_windows', lambda: (False, 'no windows api'))
    hotkeys = []
    monkeypatch.setattr('pyautogui.hotkey', lambda *keys: hotkeys.append(keys))
    handler = _FakeHandler()

    win_cmd._min_all(handler, 'сверни всё', 0)

    assert hotkeys == [('win', 'd')]
    assert handler.play_response_calls


def test_min_all_plays_response_directly_on_success(monkeypatch):
    monkeypatch.setattr(win_cmd, 'minimize_all_windows', lambda: (True, 'ok'))
    monkeypatch.setattr('pyautogui.hotkey',
                         lambda *keys: (_ for _ in ()).throw(AssertionError('must not fall back')))
    handler = _FakeHandler()

    win_cmd._min_all(handler, 'сверни всё', 0)

    assert handler.play_response_calls


def test_move_monitor_defaults_amount_to_one(monkeypatch):
    captured = []
    monkeypatch.setattr(win_cmd, 'move_to_monitor', lambda n: captured.append(n) or True)
    handler = _FakeHandler()

    win_cmd._move_monitor(handler, 'перенеси на другой монитор', 0)

    assert captured == [1]


def test_move_monitor_uses_explicit_amount(monkeypatch):
    captured = []
    monkeypatch.setattr(win_cmd, 'move_to_monitor', lambda n: captured.append(n) or True)
    handler = _FakeHandler()

    win_cmd._move_monitor(handler, 'перенеси на монитор 2', 2)

    assert captured == [2]


def test_move_monitor_speaks_error_on_failure(monkeypatch):
    monkeypatch.setattr(win_cmd, 'move_to_monitor', lambda n: False)
    handler = _FakeHandler()

    win_cmd._move_monitor(handler, 'перенеси на монитор 5', 5)

    assert handler.spoken
    assert handler.play_response_calls == []


# ── mouse.py ──────────────────────────────────────────────────────────────

def test_mouse_faster_increases_speed_and_speaks(monkeypatch):
    monkeypatch.setattr(app_state, 'mouse_speed', 1.0)
    handler = _FakeHandler()

    mouse_cmd._mouse_faster(handler, 'быстрее', 0)

    assert app_state.mouse_speed == 1.5
    assert handler.spoken


def test_mouse_slower_decreases_speed_with_floor(monkeypatch):
    monkeypatch.setattr(app_state, 'mouse_speed', 0.12)
    handler = _FakeHandler()

    mouse_cmd._mouse_slower(handler, 'медленнее', 0)

    assert app_state.mouse_speed == 0.1  # clamped, would otherwise go below floor


def test_mouse_click_calls_pyautogui_click(monkeypatch):
    clicked = []
    monkeypatch.setattr('pyautogui.click', lambda: clicked.append(True))
    handler = _FakeHandler()

    mouse_cmd._mouse_click(handler, 'клик', 0)

    assert clicked == [True]
    assert handler.play_response_calls


def test_handle_mouse_direction_sets_movement_state(monkeypatch):
    # Prevent the real background movement loop from starting — it would
    # call pyautogui.moveRel() against the actual OS cursor otherwise.
    monkeypatch.setattr(mouse_cmd, '_ensure_mouse_loop_started', lambda: None)
    monkeypatch.setattr(app_state, 'mouse_moving', False)
    handler = _FakeHandler()

    mouse_cmd.handle_mouse(handler, 'mouse_right', 'мышь вправо', 0)

    assert (app_state.mouse_dx, app_state.mouse_dy) == (1, 0)
    assert app_state.mouse_moving is True
    assert handler.play_response_calls


def test_handle_mouse_unknown_command_does_nothing(monkeypatch):
    monkeypatch.setattr(mouse_cmd, '_ensure_mouse_loop_started', lambda: None)
    handler = _FakeHandler()

    mouse_cmd.handle_mouse(handler, 'not_a_mouse_cmd', 'text', 0)

    assert handler.spoken == []
    assert handler.play_response_calls == []


# ── clip.py ───────────────────────────────────────────────────────────────

def test_handle_clip_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(clip_cmd._CLIP_ACTIONS, 'undo', lambda h, t, a: called.append(t))
    handler = _FakeHandler()

    clip_cmd.handle_clip(handler, 'undo', 'отмени', 0)

    assert called == ['отмени']


def test_clip_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    # 'clip_paste_n' is registered here but has no NLU pattern anywhere
    # (not in INTENTS, not in commands_data.py's CANON_SIMPLE) — dead code,
    # unreachable by voice. Flagged rather than silently removed/wired up.
    known_dead = {'clip_paste_n'}
    unknown = set(clip_cmd._CLIP_ACTIONS.keys()) - set(INTENTS.keys()) - known_dead
    assert not unknown, f'_CLIP_ACTIONS has non-existent intent keys: {unknown}'


def test_clip_paste_without_filename_uses_plain_clipboard_paste(monkeypatch):
    pasted = []
    monkeypatch.setattr(clip_cmd, 'clipboard_paste', lambda: pasted.append(True) or True)
    handler = _FakeHandler()

    clip_cmd._clip_paste(handler, 'вставь', 0)

    assert pasted == [True]
    assert handler.play_response_calls


def test_clip_paste_with_filename_finds_and_pastes_file(monkeypatch):
    searched = []
    monkeypatch.setattr('actions.system_parts.files_paste.find_and_paste_file',
                         lambda target_filename: searched.append(target_filename) or (True, 'ok'))
    handler = _FakeHandler()

    clip_cmd._clip_paste(handler, 'вставь отчёт.docx', 0)

    assert searched == ['отчёт.docx']
    assert handler.play_response_calls


def test_clip_paste_n_converts_one_based_amount_to_zero_based_index(monkeypatch):
    captured = []
    monkeypatch.setattr(clip_cmd, 'clipboard_paste_nth', lambda idx: captured.append(idx) or True)
    handler = _FakeHandler()

    clip_cmd._clip_paste_n(handler, 'вставь третье', 3)

    assert captured == [2]


def test_clip_paste_n_clamps_zero_amount_to_zero_index(monkeypatch):
    captured = []
    monkeypatch.setattr(clip_cmd, 'clipboard_paste_nth', lambda idx: captured.append(idx) or True)
    handler = _FakeHandler()

    clip_cmd._clip_paste_n(handler, 'вставь', 0)

    assert captured == [0]  # max(0, 0-1) must not go negative
