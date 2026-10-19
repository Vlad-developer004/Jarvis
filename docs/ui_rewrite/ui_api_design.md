# `ui_api` facade: design (draft, not implemented)

Goal: core/actions/features stop touching Tk internals. They call one facade.
Legacy Tk UI implements it first (zero behavior change), the new UI is a second
implementation, chosen by a setting. Baseline: 2392 passed, 45 skipped.

## Observed patterns in core (what the facade must replace)

1. `hud._hud.root.after(ms, lambda: hud._hud.show_msg_stream(t))` - hop to the UI thread (interactive.py, ai.py, ets2_commands.py, tts.py).
2. `hud._hud_queue.put(lambda: show_timer_widget(hud, ...))` - queue Tk code to the UI thread (game_timer, reminder, notes, yt_play, system).
3. `has_hud = hud._hud is not None` guards - "is a UI running" checks.
4. Module functions `hud.notify(key, text, color, duration)` / `clear_notify(key)` / `show_hud()`.
5. Blocking dialogs invoked from worker threads that return a value (`ask_text`, `ask_git_stage`, ...).
6. Non-UI files that build their own Tk windows: `features/reminder.py::_show_reminder_window`, `actions/ets2_telemetry_installer.py`. These must move into the UI layer.

## Proposed API (`ui_api/__init__.py`, Protocol `UiBackend` + module-level `ui`)

Thread rule: every method is safe to call from ANY thread; the backend marshals to its UI thread. Callers never receive widgets or `root`.

```
# lifecycle / threading
ui.available() -> bool                    # replaces `hud._hud is not None`
ui.show()                                 # show_hud()
ui.post(fn)                               # run fn on UI thread (replaces _hud_queue.put)
ui.post_later(ms, fn)                     # replaces root.after(ms, fn)

# state (neutral module, no Tk import)
STATE, HudState                           # moved as-is, keep its Lock

# header / notices
ui.notify(key, text, color=None, duration=None);  ui.clear_notify(key)
ui.say_line(text, color=None, duration=3000)      # show_msg
ui.stream_line(text);  ui.end_stream_line(delay_ms=0)   # show_msg_stream / hide_msg_stream

# AI window
ui.ai_show();  ui.ai_text(text);  ui.ai_image(path_or_bytes);  ui.ai_video(path)
ui.ai_hide(delay_ms=0);  ui.ai_cancel_hide()

# timer / reminder widgets
ui.timer_show(seconds, label);  ui.timer_update_total(seconds);  ui.timer_hide();  ui.timer_done_popup(label)
ui.reminder_show(seconds, message);  ui.reminder_hide();  ui.reminder_popup(message, speak_fn)

# reactor / guard / settings
ui.reactor_color(name|None);  ui.reactor_pulse();  ui.reactor_glitch()
ui.guard_status(...)                      # hud_camera.set_guard_status
ui.settings_get(key, default);  ui.settings_set(key, value)   # replaces hud._settings / _load_hud_settings

# dialogs (called from worker threads, block until result or None on cancel)
ui.ask_text(prompt, default="") -> str|None
ui.ask_git_stage(...);  ui.pick_youtube(results) -> index|None
ui.open_mail_compose(...);  ui.review_cleanup(items);  ui.open_welcome();  ui.guard_alert(...)
# voice answers to dialogs stay in ui/voice_prompt_bridge (backend-agnostic: pure Python)
```

Theme colors (`_CYAN`, `_RED`, `_AMBER`, ...) used by core become semantic names
(`"info" | "warn" | "error"`), resolved by the backend. Open: confirm the set.

## Migration steps (each = one commit, pytest must stay 2392 passed)

1. Add `ui_api/` + `LegacyTkBackend` that delegates 1:1 to current `ui.hud` / dialogs. No caller changes. Add a tiny contract test (all methods exist, safe when no UI is running).
2. Move `HudState`/`STATE` to a neutral module; keep `ui.hud_state` re-export.
3. Migrate callers by group: (a) notify/asr/tts, (b) interactive/ai streaming, (c) game_timer/reminder/notes, (d) dialogs, (e) settings access. Update tests that patch `hud._hud` / `hud.root` to patch the facade.
4. Move the two foreign Tk windows (reminder popup, telemetry installer) into the legacy backend.
5. Only then start the new backend behind `ui_backend = "legacy" | "next"`.

## Risks

- ~30 files and the tests that monkeypatch `hud._hud`, `hud.root`, `_hud_queue` (e.g. `test_reactor_and_browser_commands.py`, `test_game_timer_commands.py`) need updating in step 3.
- Do not change startup order in `main.py` (binding rule 1) - the facade import must stay lazy/cheap and Tk-free.
- `core/system/state.py` locks untouched; `HudState` lock preserved.
- Blocking dialogs: the new backend must preserve "call from worker thread, wait for result" semantics.
