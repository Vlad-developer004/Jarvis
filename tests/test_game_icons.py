import base64
import os
import sys

import pytest

from ui_next.bridge import gameicons


def test_find_exe_skips_helpers_and_picks_largest(tmp_path):
    (tmp_path / 'game.exe').write_bytes(b'x' * 500)
    (tmp_path / 'unins000.exe').write_bytes(b'x' * 900)
    sub = tmp_path / 'bin'
    sub.mkdir()
    (sub / 'game64.exe').write_bytes(b'x' * 700)
    deep = sub / 'a' / 'b'
    deep.mkdir(parents=True)
    (deep / 'huge.exe').write_bytes(b'x' * 5000)
    assert gameicons.find_exe(str(tmp_path)) == str(sub / 'game64.exe')


def test_find_exe_missing_dir():
    assert gameicons.find_exe('') == ''
    assert gameicons.find_exe(r'Z:\no\such\dir') == ''


@pytest.mark.skipif(sys.platform != 'win32', reason='Win32 icon extraction')
def test_icon_uri_for_a_system_exe():
    uri = gameicons.icon_uri(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'wbem'))
    # wbem holds several exes; any of them has an icon or none does, but the result must be '' or a valid PNG data URI
    assert uri == '' or base64.b64decode(uri.split(',', 1)[1])[:4] == b'\x89PNG'
