"""Regression test for a real bug reported 2026-09-22: after successfully
saving mail credentials ("пароль сохранён"), voice commands still reported
the mail module as disabled. Root cause — core/handler/dispatch.py gates
mail voice commands on the separate 'inbox_digest' feature-module flag (and
core.extensions.ExtensionManager's install state), not on whether
mail_account credentials exist. The fresh-install call site in
ui/dialogs/extensions.py's _do_install correctly set that flag after saving,
but the "Настройки" (reconfigure) call site — used once the module already
shows as installed — only called _refresh_cards(), never touching the flag.
Fixed by making ui/dialogs/extensions_setup.py::_ask_mail_setup itself
install the extension and set the flag on any successful save, regardless
of which caller opened it or what its on_done callback does.
"""
import tkinter as tk

import pytest

import ui.dialogs.extensions_setup as extensions_setup


class _FakeHud:
    _F = 'Consolas'
    zoom_factor = 1.0


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        r = tk.Tk()
    yield r
    r.destroy()


def _find_button_by_text(widget, text):
    for child in widget.winfo_children():
        try:
            if child.cget('text') == text:
                return child
        except Exception:
            pass
        found = _find_button_by_text(child, text)
        if found is not None:
            return found
    return None


def test_reconfigure_style_on_done_still_installs_and_enables_module(root, monkeypatch):
    """on_done here is a bare no-op — mirrors extensions.py's
    `_reconfig_mail` call site (`_ask_mail_setup(win, hud, _refresh_cards)`),
    which never itself calls ext_mgr.install()/_set_feature_module_flag()."""
    saved = {}
    monkeypatch.setattr('actions.mail_client.save_mail_account',
                         lambda *a, **k: saved.setdefault('called', a))
    installed = []
    monkeypatch.setattr(extensions_setup.ext_mgr, 'install', lambda eid: installed.append(eid))
    flags = []
    monkeypatch.setattr(extensions_setup, '_set_feature_module_flag',
                         lambda key, enabled: flags.append((key, enabled)))

    on_done_called = []
    extensions_setup._ask_mail_setup(root, _FakeHud(), lambda: on_done_called.append(True))
    root.update()

    dlg = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    from core import i18n
    save_btn = _find_button_by_text(dlg, i18n.tr('buttons.save'))
    assert save_btn is not None

    email_entries = [w for w in dlg.winfo_children()]  # noqa: F841 (kept for debugging if this fails)
    # Fill the required fields via the dialog's own entries by locating them:
    # simplest reliable path is to drive the widgets the same way a user
    # would — but StringVars aren't reachable from outside, so instead we
    # locate the email/password CTkEntry widgets by placeholder text.
    def _find_entries(widget, out):
        for child in widget.winfo_children():
            if child.winfo_class() in ('Entry',) or 'CTkEntry' in type(child).__name__:
                out.append(child)
            _find_entries(child, out)
    import customtkinter as ctk
    entries = []
    def _find_ctk_entries(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkEntry):
                entries.append(child)
            _find_ctk_entries(child)
    _find_ctk_entries(dlg)
    assert len(entries) >= 2
    email_entry, pwd_entry = entries[0], entries[1]
    email_entry.insert(0, 'me@gmail.com')
    pwd_entry.insert(0, 'app-password-123')

    save_btn._command()
    root.update()

    assert saved.get('called') is not None
    assert installed == ['feature_mail_client']
    assert flags == [('inbox_digest', True)]
    assert on_done_called == [True]
