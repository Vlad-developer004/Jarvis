def test_files_module_reports_its_version(native_files):
    assert native_files.version().count('.') == 2


def test_win_module_reports_its_version(native_win):
    assert native_win.version().count('.') == 2
