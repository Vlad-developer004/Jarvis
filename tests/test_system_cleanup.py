"""Regression test for actions/system_control.py::run_basic_cleanup.

A PermissionError from os.listdir() on a protected directory (e.g.
C:\\Windows\\Prefetch without admin rights) used to propagate unhandled out
of the nested _rm_dir_contents() closure, killing the whole
'jarvis-cleanup'/'jarvis-cleanup-deep' background thread before later steps
(Recent folders, recycle bin) ever ran.

All real system side effects (DNS flush, event log clear, recycle bin empty)
are neutralized via monkeypatch — this test must never actually touch the
machine's DNS cache, event logs, or recycle bin.
"""
import ctypes
import os

import pytest

from actions import system_control


@pytest.fixture(autouse=True)
def _neutralize_system_side_effects(monkeypatch):
    monkeypatch.setattr(system_control.subprocess, 'run', lambda *a, **kw: None)
    monkeypatch.setattr(ctypes.windll.shell32, 'SHEmptyRecycleBinW', lambda *a: 0)


def test_run_basic_cleanup_survives_permission_denied_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('TEMP', str(tmp_path / 'temp'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'roaming'))
    monkeypatch.setenv('SystemRoot', str(tmp_path / 'windows'))
    monkeypatch.setenv('USERPROFILE', str(tmp_path / 'profile'))

    protected = tmp_path / 'windows' / 'Prefetch'
    protected.mkdir(parents=True)
    (protected / 'somefile.pf').write_text('x')

    # A harmless, listable dir further down the run — proves the cleanup
    # kept going after the PermissionError instead of aborting the thread.
    recent_dir = tmp_path / 'roaming' / 'Microsoft' / 'Windows' / 'Recent' / 'AutomaticDestinations'
    recent_dir.mkdir(parents=True)
    leftover_file = recent_dir / 'leftover.automaticDestinations-ms'
    leftover_file.write_text('y')

    real_listdir = os.listdir

    def _listdir(path):
        if os.path.normcase(os.path.abspath(str(path))) == os.path.normcase(str(protected)):
            raise PermissionError(5, 'Access is denied', str(protected))
        return real_listdir(path)

    monkeypatch.setattr(os, 'listdir', _listdir)

    freed_bytes, errors = system_control.run_basic_cleanup()

    assert errors >= 1  # the denied listdir was counted, not swallowed silently
    assert not leftover_file.exists()  # cleanup reached and cleared later steps
