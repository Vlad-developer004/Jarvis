"""Tests for actions/office_documents.py — filename sanitization, the
IDE-vs-Notepad safety logic in open_file()/_compose_ide_argv() (files must
never be silently run as executables), and plain-text file creation.
Previously untested. Word/Excel/PowerPoint creators need a real win32com
Office install and are not covered here (same reasoning as other
OS-integration-heavy code this session left out); create_plain_text_file()
uses only the filesystem, so it's covered directly with tmp_path.
"""
from pathlib import Path

import actions.office_documents as office


# ── filename sanitization ────────────────────────────────────────────────

def test_sanitize_document_stem_strips_invalid_windows_chars():
    assert office.sanitize_document_stem('отчёт: план/бюджет') == 'отчёт план бюджет'


def test_sanitize_document_stem_collapses_whitespace():
    assert office.sanitize_document_stem('  много   пробелов  ') == 'много пробелов'


def test_sanitize_document_stem_strips_trailing_dots_and_spaces():
    assert office.sanitize_document_stem('имя файла... ') == 'имя файла'


def test_sanitize_document_stem_empty_input_returns_empty():
    assert office.sanitize_document_stem('') == ''
    assert office.sanitize_document_stem(None) == ''


# ── _compose_ide_argv (security-relevant: never silently execute a file) ──

def test_compose_ide_argv_returns_none_for_python_interpreter():
    # If the foreground process happens to be python.exe, we must NOT hand
    # it a .py file as an argv — that would execute the file instead of
    # opening it for editing.
    assert office._compose_ide_argv('C:\\Python312\\python.exe', 'C:\\proj\\script.py') is None


def test_compose_ide_argv_returns_none_for_pythonw():
    assert office._compose_ide_argv('C:\\Python312\\pythonw.exe', 'C:\\proj\\script.py') is None


def test_compose_ide_argv_recognizes_vscode():
    argv = office._compose_ide_argv('C:\\Users\\x\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe', 'C:\\proj\\a.py')
    assert argv is not None
    assert argv[0].lower().endswith('code.exe')
    assert argv[1] == str(Path('C:\\proj\\a.py'))


def test_compose_ide_argv_recognizes_cursor():
    argv = office._compose_ide_argv('C:\\Users\\x\\AppData\\Local\\Programs\\cursor\\Cursor.exe', 'C:\\proj\\a.py')
    assert argv is not None


def test_compose_ide_argv_recognizes_jetbrains_by_path_substring():
    argv = office._compose_ide_argv('C:\\Program Files\\JetBrains\\PyCharm\\bin\\pycharm64.exe', 'C:\\proj\\a.py')
    assert argv is not None


def test_compose_ide_argv_unrecognized_exe_returns_none():
    assert office._compose_ide_argv('C:\\SomeApp\\random_app.exe', 'C:\\proj\\a.py') is None


def test_compose_ide_argv_devenv_uses_edit_flag():
    argv = office._compose_ide_argv('C:\\VS\\devenv.exe', 'C:\\proj\\a.cs')
    assert argv[1] == '/Edit'


# ── create_plain_text_file ────────────────────────────────────────────────

def test_create_plain_text_file_writes_content(tmp_path):
    target = tmp_path / 'notes.txt'
    ok, res = office.create_plain_text_file(str(target), content='привет мир')

    assert ok is True
    assert Path(res).read_text(encoding='utf-8') == 'привет мир'


def test_create_plain_text_file_rejects_existing_file(tmp_path):
    target = tmp_path / 'notes.txt'
    target.write_text('уже тут', encoding='utf-8')

    ok, msg = office.create_plain_text_file(str(target))

    assert ok is False
    assert 'уже существует' in msg


def test_create_plain_text_file_rejects_name_that_sanitizes_to_empty(tmp_path):
    target = tmp_path / '...txt'
    ok, msg = office.create_plain_text_file(str(target))
    assert ok is False


def test_create_plain_text_file_defaults_extension_to_txt(tmp_path):
    target = tmp_path / 'noext'
    ok, res = office.create_plain_text_file(str(target))
    assert ok is True
    assert res.endswith('.txt')


def test_create_python_file_adds_py_extension_and_shebang_comment(tmp_path):
    target = tmp_path / 'script'
    ok, res = office.create_python_file(str(target))

    assert ok is True
    assert res.endswith('.py')
    assert 'coding: utf-8' in Path(res).read_text(encoding='utf-8')


# ── CREATE_BY_KIND / extension registries consistency ─────────────────────

def test_create_by_kind_covers_all_plain_web_exts():
    for ext in office._PLAIN_WEB_EXTS:
        assert ext in office.CREATE_BY_KIND, f'{ext} missing from CREATE_BY_KIND'


def test_ide_open_exts_is_superset_of_plain_web_exts_plus_py_and_md():
    assert set(office._PLAIN_WEB_EXTS) <= office._IDE_OPEN_EXTS
    assert 'py' in office._IDE_OPEN_EXTS
    assert 'md' in office._IDE_OPEN_EXTS


def test_office_exts_never_overlap_ide_open_exts():
    # Office docs are opened via os.startfile (Word/Excel/PowerPoint), code
    # files never are — these two sets must stay disjoint or open_file()'s
    # branch logic silently picks the wrong path for some extension.
    assert not (office._OFFICE_EXTS & office._IDE_OPEN_EXTS)
