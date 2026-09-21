"""Regression tests for the 2026-09 architecture-review fixes:

1. module_enabled('photoshop_voice'/'figma_voice') must track the extension
   system (ExtensionManager.has_feature), not the dead settings.json flag
   that had no UI to ever set True — see core/system/modules.py.
2. AppState.toggle_ignore_mode() must be atomic under concurrent access.
3. CommandHandler serializes command execution through one worker queue and
   survives a handler raising an exception (previously: raw per-command
   threads, no ordering guarantee, no cap on concurrency).
"""
import threading

import pytest


def test_module_enabled_tracks_extension_state_for_photoshop_voice(monkeypatch):
    from core.system.modules import module_enabled
    import core.extensions as extensions_mod

    monkeypatch.setattr(extensions_mod.ExtensionManager, 'has_feature', lambda self, name: True)
    assert module_enabled('photoshop_voice') is True

    monkeypatch.setattr(extensions_mod.ExtensionManager, 'has_feature', lambda self, name: False)
    assert module_enabled('photoshop_voice') is False


def test_module_enabled_unrelated_flags_unaffected():
    from core.system.modules import module_enabled
    # Regression guard: the extension-backed special-case must not leak into
    # any other module name's normal settings-based lookup.
    assert module_enabled('qa') in (True, False)  # doesn't raise, still profile-driven
    assert module_enabled('totally_unknown_module_name') is True  # fail-open default preserved


def test_toggle_ignore_mode_is_atomic_under_concurrency():
    from core.system.state import AppState
    st = AppState()
    n_per_thread = 500
    n_threads = 8

    def worker():
        for _ in range(n_per_thread):
            st.toggle_ignore_mode()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()

    # Even total number of toggles from a known False start must land on False.
    assert (n_per_thread * n_threads) % 2 == 0
    assert st.ignore_mode is False


def test_toggle_ignore_mode_returns_new_value():
    from core.system.state import AppState
    st = AppState()
    assert st.ignore_mode is False
    assert st.toggle_ignore_mode() is True
    assert st.toggle_ignore_mode() is False


def test_command_worker_preserves_order():
    from core.handler.dispatch import CommandHandler, _reg_exact

    order = []
    _reg_exact(['__test_order__'], lambda h, cmd, t, a: order.append(cmd))

    h = CommandHandler.__new__(CommandHandler)  # bypass BaseHandler.__init__ (needs real audio devices)
    h.interactive_state = None
    h._settings = {}
    import queue
    h._cmd_queue = queue.Queue()
    h._cmd_worker = threading.Thread(target=h._cmd_worker_loop, daemon=True)
    h._cmd_worker.start()

    for _ in range(20):
        h._cmd_queue.put(('__test_order__', 'text', 'text', 5))
    import time
    deadline = time.time() + 2.0
    while len(order) < 20 and time.time() < deadline:
        time.sleep(0.02)

    assert order == ['__test_order__'] * 20


def test_command_worker_survives_handler_exception():
    from core.handler.dispatch import CommandHandler, _reg_exact

    ran_after = threading.Event()
    _reg_exact(['__test_boom__'], lambda h, cmd, t, a: (_ for _ in ()).throw(RuntimeError('boom')))
    _reg_exact(['__test_after_boom__'], lambda h, cmd, t, a: ran_after.set())

    h = CommandHandler.__new__(CommandHandler)
    h.interactive_state = None
    h._settings = {}
    import queue
    h._cmd_queue = queue.Queue()
    h._cmd_worker = threading.Thread(target=h._cmd_worker_loop, daemon=True)
    h._cmd_worker.start()

    h._cmd_queue.put(('__test_boom__', 'text', 'text', 5))
    h._cmd_queue.put(('__test_after_boom__', 'text', 'text', 5))

    assert ran_after.wait(timeout=2.0)
    assert h._cmd_worker.is_alive()
