"""Opening named files and links: documents open, anything that can run code does not."""
import os

import pytest

from core import safe_open


@pytest.fixture
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(os, 'startfile', lambda p, *a: calls.append(p), raising=False)
    return calls


@pytest.mark.parametrize('name', ['setup.exe', 'run.BAT', 'x.cmd', 'a.ps1', 'a.vbs', 'a.js', 'a.msi', 'a.lnk', 'a.url', 'a.hta', 'a.reg', 'a.jar', 'a.scr',
                                  'report.pdf.exe', 'report.pdf.exe.', 'report.pdf.exe ', 'C:\\Users\\me\\Downloads\\tool.com', 'a.wsf', 'a.cpl'])
def test_code_running_files_are_refused(started, name):
    assert safe_open.is_runnable(name)
    with pytest.raises(PermissionError):
        safe_open.open_user_file(name)
    assert started == []


@pytest.mark.parametrize('name', ['report.pdf', 'notes.txt', 'movie.mkv', 'photo.JPG', 'table.xlsx', 'slides.pptx', 'archive.zip', 'README', 'dir.exe.d\\file.txt', 'x.exe.pdf'])
def test_documents_and_media_open(started, name):
    assert not safe_open.is_runnable(name)
    safe_open.open_user_file(name)
    assert started == [os.path.normpath(name)]


@pytest.mark.parametrize('url', ['https://example.com/a?b=1', 'http://example.com', 'mailto:a@b.test', 'HTTPS://EXAMPLE.COM'])
def test_web_and_mail_links_open(started, url):
    safe_open.open_user_link(url)
    assert started == [url]


@pytest.mark.parametrize('url', ['file:///c:/Windows/System32/calc.exe', 'ms-msdt:/id x', 'ftp://x.test', 'c:\\x.exe', 'javascript:alert(1)', 'https://x.test/\nboom', '', None,
                                 'https://' + 'a' * 2100])
def test_other_links_are_refused(started, url):
    with pytest.raises(PermissionError):
        safe_open.open_user_link(url)
    assert started == []


def test_voice_file_opening_refuses_an_executable(started, tmp_path):
    from actions import office_documents
    exe = tmp_path / 'tool.bat'
    exe.write_text('echo hi')
    ok, msg = office_documents.open_file(str(exe))
    assert ok is False and started == []
    doc = tmp_path / 'note.txt'
    doc.write_text('x')
    ok, _ = office_documents.open_file(str(doc))
    assert ok is True and started == [str(doc)]


def test_recent_file_opening_refuses_an_executable(started, monkeypatch, tmp_path):
    from actions import recent
    monkeypatch.setattr(recent, '_scan_recent_files', lambda file_type, limit: [str(tmp_path / 'x.exe')])
    ok, _ = recent.open_recent_file('any', 0)
    assert ok is False and started == []


def test_media_library_play_refuses_an_executable(started, tmp_path):
    from actions import media_library
    exe = tmp_path / 'movie.exe'
    exe.write_text('x')
    assert media_library.play({'path': str(exe)}) is False and started == []
