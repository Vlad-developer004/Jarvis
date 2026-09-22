"""Tests for actions/clipboard.py — clipboard history management (dedup,
MAX_HISTORY cap) and the paste-by-index logic. keysend.press/hotkey send
real OS-level key events and are mocked in every test here; pyperclip is
mocked too so tests never touch the real system clipboard. The module-level
_clipboard_history list is reset before each test via monkeypatch so tests
don't leak state into each other.
"""
import actions.clipboard as clip


def _isolated_history(monkeypatch, initial=None):
    monkeypatch.setattr(clip, '_clipboard_history', list(initial or []))
    monkeypatch.setattr(clip.keysend, 'hotkey', lambda *a, **k: None)
    monkeypatch.setattr(clip.keysend, 'press', lambda *a, **k: None)


# ── clipboard_copy history behavior ───────────────────────────────────────

def test_clipboard_copy_adds_new_text_to_history_front(monkeypatch):
    _isolated_history(monkeypatch, ['old text'])
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: 'new text')

    ok, msg = clip.clipboard_copy()

    assert ok is True
    assert clip._clipboard_history[0] == 'new text'
    assert clip._clipboard_history[1] == 'old text'


def test_clipboard_copy_does_not_duplicate_when_same_as_most_recent(monkeypatch):
    _isolated_history(monkeypatch, ['same text'])
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: 'same text')

    clip.clipboard_copy()

    assert clip._clipboard_history == ['same text']


def test_clipboard_copy_enforces_max_history_cap(monkeypatch):
    full_history = [f'item {i}' for i in range(clip.MAX_HISTORY)]
    _isolated_history(monkeypatch, full_history)
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: 'brand new item')

    clip.clipboard_copy()

    assert len(clip._clipboard_history) == clip.MAX_HISTORY
    assert clip._clipboard_history[0] == 'brand new item'
    assert 'item 19' not in clip._clipboard_history  # oldest entry evicted


def test_clipboard_copy_ignores_whitespace_only_clipboard(monkeypatch):
    _isolated_history(monkeypatch, [])
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: '   ')

    ok, msg = clip.clipboard_copy()

    assert ok is True
    assert clip._clipboard_history == []


def test_clipboard_copy_truncates_message_preview(monkeypatch):
    _isolated_history(monkeypatch, [])
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: 'x' * 100)

    ok, msg = clip.clipboard_copy()

    assert ok is True
    assert len(msg) < 100


# ── clipboard_paste_nth ────────────────────────────────────────────────────

def test_clipboard_paste_nth_valid_index_returns_success(monkeypatch):
    _isolated_history(monkeypatch, ['a', 'b', 'c'])
    copied = []
    monkeypatch.setattr(clip.pyperclip, 'copy', lambda text: copied.append(text))

    ok, msg = clip.clipboard_paste_nth(1)

    assert ok is True
    assert copied == ['b']


def test_clipboard_paste_nth_out_of_range_returns_error(monkeypatch):
    _isolated_history(monkeypatch, ['a'])

    ok, msg = clip.clipboard_paste_nth(5)

    assert ok is False


def test_clipboard_paste_nth_negative_index_returns_error(monkeypatch):
    _isolated_history(monkeypatch, ['a', 'b'])

    ok, msg = clip.clipboard_paste_nth(-1)

    assert ok is False


def test_clipboard_paste_nth_empty_history_always_errors(monkeypatch):
    _isolated_history(monkeypatch, [])

    ok, msg = clip.clipboard_paste_nth(0)

    assert ok is False


# ── clipboard_cut history behavior (mirrors copy) ─────────────────────────

def test_clipboard_cut_adds_to_history(monkeypatch):
    _isolated_history(monkeypatch, [])
    monkeypatch.setattr(clip.pyperclip, 'paste', lambda: 'вырезанный текст')

    ok, msg = clip.clipboard_cut()

    assert ok is True
    assert clip._clipboard_history == ['вырезанный текст']


# ── simple always-succeed wrappers (just verify no exceptions / correct shape) ──

def test_clipboard_paste_returns_success_tuple(monkeypatch):
    monkeypatch.setattr(clip.keysend, 'hotkey', lambda *a, **k: None)
    ok, msg = clip.clipboard_paste()
    assert ok is True


def test_undo_redo_select_all_return_success_tuples(monkeypatch):
    monkeypatch.setattr(clip.keysend, 'hotkey', lambda *a, **k: None)
    assert clip.undo_action()[0] is True
    assert clip.redo_action()[0] is True
    assert clip.select_all()[0] is True


def test_clipboard_actions_wrap_exceptions_into_error_tuple(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError('keyboard driver failed')
    monkeypatch.setattr(clip.keysend, 'hotkey', _boom)

    ok, msg = clip.undo_action()

    assert ok is False
    assert 'keyboard driver failed' in msg
