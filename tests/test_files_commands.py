"""Tests for core/handler/commands/files.py — the handlers behind
create/delete folder, delete file, cd, explorer navigation and file search.
Destructive by nature (folder/file deletion, filesystem writes), so this
was previously entirely untested at the handler layer. Real filesystem
operations here are confined to tmp_path; anything that would touch dialogs
or the live OS shell is mocked.
"""
import threading

import pytest

import core.handler.commands.files as files_cmd


class _FakeHandler:
    def __init__(self, settings=None):
        self._settings = settings or {}
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


# ── handle_files routing ─────────────────────────────────────────────────

def test_handle_files_routes_exact_command(monkeypatch):
    called = []
    monkeypatch.setitem(files_cmd._FILES_EXACT, 'empty_trash', lambda h, c, t: called.append((c, t)))
    handler = _FakeHandler()

    files_cmd.handle_files(handler, 'empty_trash', 'очисти корзину')

    assert called == [('empty_trash', 'очисти корзину')]


def test_handle_files_routes_recent_prefix_to_recent_file(monkeypatch):
    called = []
    monkeypatch.setattr(files_cmd, '_recent_file', lambda h, c, t: called.append(c))
    handler = _FakeHandler()

    files_cmd.handle_files(handler, 'recent_doc', 'открой последний документ')

    assert called == ['recent_doc']


def test_handle_files_unknown_command_does_nothing(monkeypatch):
    # Must not raise for a command that matches neither the exact table nor
    # the 'recent_' prefix.
    handler = _FakeHandler()
    files_cmd.handle_files(handler, 'totally_unknown', 'что угодно')
    assert handler.spoken == []
    assert handler.play_response_calls == []


# ── _empty_trash ──────────────────────────────────────────────────────────

def test_empty_trash_plays_response_on_success(monkeypatch):
    monkeypatch.setattr(files_cmd, 'empty_recycle_bin', lambda: (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._empty_trash(handler, 'empty_trash', 'очисти корзину')

    assert handler.play_response_calls


def test_empty_trash_silent_on_failure(monkeypatch):
    monkeypatch.setattr(files_cmd, 'empty_recycle_bin', lambda: (False, 'error'))
    handler = _FakeHandler()

    files_cmd._empty_trash(handler, 'empty_trash', 'очисти корзину')

    assert handler.play_response_calls == []


# ── _create_folder / _delete_folder (name already in the utterance) ──────

def test_create_folder_with_name_in_utterance(monkeypatch, tmp_path):
    monkeypatch.setattr(files_cmd, 'get_context_path', lambda h: str(tmp_path))
    created = []
    monkeypatch.setattr(files_cmd, 'create_folder_at',
                         lambda base, name: created.append((base, name)) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._create_folder(handler, 'create_folder', 'создай папку проекты')

    assert created == [(str(tmp_path), 'проекты')]
    assert handler.play_response_calls


def test_create_folder_speaks_error_when_creation_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(files_cmd, 'get_context_path', lambda h: str(tmp_path))
    monkeypatch.setattr(files_cmd, 'create_folder_at', lambda base, name: (False, 'already exists'))
    handler = _FakeHandler()

    files_cmd._create_folder(handler, 'create_folder', 'создай папку проекты')

    assert handler.spoken == ['already exists']
    assert handler.play_response_calls == []


def test_delete_folder_with_name_in_utterance(monkeypatch, tmp_path):
    monkeypatch.setattr(files_cmd, 'get_context_path', lambda h: str(tmp_path))
    deleted = []
    monkeypatch.setattr(files_cmd, 'delete_folder_at',
                         lambda base, name: deleted.append((base, name)) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._delete_folder(handler, 'delete_folder', 'удали папку старое')

    assert deleted == [(str(tmp_path), 'старое')]
    assert handler.play_response_calls


# ── _cd_folder ────────────────────────────────────────────────────────────

def test_cd_folder_navigates_when_name_present(monkeypatch, tmp_path):
    monkeypatch.setattr(files_cmd, 'get_context_path', lambda h: str(tmp_path))
    navigated = []
    monkeypatch.setattr(files_cmd, 'goto_folder',
                         lambda ctx, name: navigated.append((ctx, name)) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._cd_folder(handler, 'cd_folder', 'перейди в папку загрузки')

    assert navigated == [(str(tmp_path), 'загрузки')]
    assert handler.play_response_calls


def test_cd_folder_asks_for_name_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(files_cmd, 'get_context_path', lambda h: str(tmp_path))
    handler = _FakeHandler()

    files_cmd._cd_folder(handler, 'cd_folder', 'перейди')

    assert handler.interactive_state == 'cd_folder_ask'
    assert handler.spoken


# ── _explorer_goto ────────────────────────────────────────────────────────

def test_explorer_goto_opens_root_explorer_for_bare_request(monkeypatch):
    opened = []
    monkeypatch.setattr('subprocess.Popen', lambda args: opened.append(args))
    handler = _FakeHandler()

    files_cmd._explorer_goto(handler, 'explorer_goto', 'открой проводник')

    assert opened == [['explorer']]
    assert handler.play_response_calls


def test_explorer_goto_strips_filler_words_and_navigates(monkeypatch):
    navigated = []
    monkeypatch.setattr(files_cmd, 'navigate_to_system_folder',
                         lambda folder: navigated.append(folder) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._explorer_goto(handler, 'explorer_goto', 'перейди в загрузки')

    assert navigated == ['загрузки']
    assert handler.play_response_calls


def test_explorer_go_up_navigates_to_parent(monkeypatch):
    navigated = []
    monkeypatch.setattr(files_cmd, 'navigate_to_system_folder',
                         lambda folder: navigated.append(folder) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._explorer_go_up(handler, 'explorer_go_up', 'выйди на уровень выше')

    assert navigated == ['..']


# ── _find_file ────────────────────────────────────────────────────────────

def test_find_file_strips_known_prefix_and_searches(monkeypatch):
    # _find_file does `import threading` + `from actions.recent import
    # search_and_open_file` as LOCAL imports inside the function/closure, so
    # module-level attributes on files_cmd can't be patched — patch the real
    # source modules instead.
    monkeypatch.setattr('threading.Thread', _ImmediateThread)
    searched = []
    monkeypatch.setattr('actions.recent.search_and_open_file',
                         lambda q, t: searched.append((q, t)) or (True, 'found'))
    handler = _FakeHandler()

    files_cmd._find_file(handler, 'find_doc', 'найди документ отчёт за март')

    assert searched == [('отчёт за март', 'document')]


def test_find_file_asks_when_query_empty(monkeypatch):
    handler = _FakeHandler()

    files_cmd._find_file(handler, 'find_file', 'найди')

    assert handler.interactive_state == 'find_file_ask'
    assert handler.spoken


# ── _recent_file ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('cmd,expected_type,expected_offset', [
    ('recent_doc', 'document', 0),
    ('recent_doc_prev', 'document', 1),
    ('recent_sheet', 'spreadsheet', 0),
    ('recent_pres_prev', 'presentation', 1),
    ('recent_any', 'any', 0),
])
def test_recent_file_maps_command_to_type_and_offset(monkeypatch, cmd, expected_type, expected_offset):
    # _recent_file also does a local `from actions.recent import
    # open_recent_file` — patch the source module, not files_cmd.
    captured = []
    monkeypatch.setattr('actions.recent.open_recent_file',
                         lambda t, o: captured.append((t, o)) or (True, 'ok'))
    handler = _FakeHandler()

    files_cmd._recent_file(handler, cmd, 'открой последний')

    assert captured == [(expected_type, expected_offset)]
    assert handler.play_response_calls
