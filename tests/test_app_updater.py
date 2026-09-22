"""Unit tests for core/system/app_updater.py.

These stay offline: _fetch_latest_release/_download/_stage_update are
monkeypatched rather than hitting the real GitHub API, per repo convention
(see test_ets2_monitor.py) of testing the surrounding logic, not the network.
"""
import zipfile

import pytest

import core.system.app_updater as app_updater


@pytest.fixture(autouse=True)
def _reset_available_version():
    app_updater._set_available_version(None)
    yield
    app_updater._set_available_version(None)


def test_parse_version_orders_numerically_not_lexically():
    # Lexical comparison would put "1.10.0" before "1.9.0" — must not happen.
    assert app_updater._parse_version("v1.10.0") > app_updater._parse_version("v1.9.0")


def test_parse_version_strips_v_prefix():
    assert app_updater._parse_version("v2.0.0") == (2, 0, 0)
    assert app_updater._parse_version("2.0.0") == (2, 0, 0)


def test_parse_version_non_numeric_segment_falls_back_to_zero():
    assert app_updater._parse_version("v1.2.beta") == (1, 2, 0)


def test_check_for_update_skips_when_no_release(monkeypatch):
    monkeypatch.setattr(app_updater, "_fetch_latest_release", lambda: None)
    app_updater.check_for_update()
    assert app_updater.get_available_version() is None


def test_check_for_update_skips_when_not_newer(monkeypatch):
    monkeypatch.setattr(
        app_updater, "_fetch_latest_release",
        lambda: {"tag_name": f"v{app_updater.APP_VERSION}", "assets": []},
    )
    app_updater.check_for_update()
    assert app_updater.get_available_version() is None


def test_check_for_update_records_newer_version_without_downloading_when_disabled(monkeypatch):
    monkeypatch.setattr(app_updater.config, "AUTO_UPDATE_ENABLED", False)
    monkeypatch.setattr(
        app_updater, "_fetch_latest_release",
        lambda: {"tag_name": "v999.0.0", "assets": [{"name": "Jarvis.zip", "browser_download_url": "http://x"}]},
    )
    staged = []
    monkeypatch.setattr(app_updater, "_stage_update", lambda asset, tag: staged.append(tag) or True)

    app_updater.check_for_update()

    assert app_updater.get_available_version() == "999.0.0"
    assert staged == []  # must not download when the setting is off


def test_check_for_update_downloads_when_enabled(monkeypatch):
    monkeypatch.setattr(app_updater.config, "AUTO_UPDATE_ENABLED", True)
    monkeypatch.setattr(
        app_updater, "_fetch_latest_release",
        lambda: {"tag_name": "v999.0.0", "assets": [{"name": "Jarvis.zip", "browser_download_url": "http://x"}]},
    )
    staged = []
    monkeypatch.setattr(app_updater, "_stage_update", lambda asset, tag: staged.append(tag) or True)

    app_updater.check_for_update()

    assert staged == ["v999.0.0"]


def test_check_for_update_skips_when_no_zip_asset(monkeypatch):
    monkeypatch.setattr(app_updater.config, "AUTO_UPDATE_ENABLED", True)
    monkeypatch.setattr(
        app_updater, "_fetch_latest_release",
        lambda: {"tag_name": "v999.0.0", "assets": [{"name": "Jarvis.exe", "browser_download_url": "http://x"}]},
    )
    called = []
    monkeypatch.setattr(app_updater, "_stage_update", lambda asset, tag: called.append(1) or True)

    app_updater.check_for_update()

    assert called == []


def test_safe_extract_zip_blocks_path_traversal(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")

    dest = tmp_path / "dest"
    dest.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        with pytest.raises(RuntimeError):
            app_updater._safe_extract_zip(zf, dest)


def test_safe_extract_zip_allows_normal_entries(tmp_path):
    zip_path = tmp_path / "ok.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Jarvis.exe", "binary-ish content")

    dest = tmp_path / "dest"
    dest.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        app_updater._safe_extract_zip(zf, dest)

    assert (dest / "Jarvis.exe").read_text() == "binary-ish content"


def test_is_update_staged_reflects_ready_file(tmp_path, monkeypatch):
    ready = tmp_path / "ready.json"
    monkeypatch.setattr(app_updater, "UPDATE_READY", ready)
    assert app_updater.is_update_staged() is False
    ready.write_text("{}", encoding="utf-8")
    assert app_updater.is_update_staged() is True


def test_apply_and_restart_noop_when_not_frozen(tmp_path, monkeypatch):
    ready = tmp_path / "ready.json"
    ready.write_text('{"version": "999.0.0", "staged_dir": "%s"}' % tmp_path, encoding="utf-8")
    monkeypatch.setattr(app_updater, "UPDATE_READY", ready)
    monkeypatch.setattr(app_updater.sys, "frozen", False, raising=False)

    assert app_updater.apply_and_restart() is False
