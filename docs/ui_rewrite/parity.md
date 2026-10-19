# UI rewrite: inventory of the legacy UI (`ui/`)

Status: historical. The legacy `ui/` was removed on 2026-10-19; see host.md for what replaced it.
Stack is not chosen yet (web/WebView2 vs PySide6) - see "Open questions".

## 1. Size

- HUD: `ui/hud*.py`, ~5.2k lines (`hud.py` 689, `hud_monitoring.py` 642, `hud_ai_window.py` 630, `hud_utils.py` 562, `hud_renderer.py` 511, `hud_widgets.py` 475, `hud_layout.py` 418, `hud_timer_widget.py` 384).
- Dialogs: `ui/dialogs/**`, ~12k lines, 40+ files.
- Splash: `ui/splash.py`. Tray: `Win32Tray` in `ui/hud_window.py`.

## 2. Contract between core and UI (what the new UI must keep or replace)

Core code does NOT talk to the UI through a narrow API. It reaches into Tk internals:

| Coupling | Used from |
|---|---|
| `hud.STATE` / `HudState` (IDLE, LISTENING, SPEAKING, LOADING; has its own lock) | `core/engine/jarvis.py`, `core/speech/tts.py`, `main.py` |
| `hud._hud` (the live `JarvisHUD` instance) | `core/handler/interactive.py`, `commands/ai.py`, `commands/system.py`, `core/engine/ets2_commands.py`, `core/speech/tts.py` |
| `hud._hud_queue.put(callable)` - callbacks that run Tk code in the UI thread | `actions/game_timer.py`, `features/reminder.py`, `core/handler/yt_play.py`, `commands/notes.py` |
| `hud.root.after(...)` - direct Tk scheduling | `actions/game_timer.py`, `features/reminder.py`, `commands/song.py`, `main.py` |
| `hud.notify / clear_notify / error / not_running` | `core/speech/asr.py`, `core/speech/tts.py`, `core/responses.py`, `dispatch.py`, `commands/reactor.py` |
| `hud._settings`, `_load_hud_settings` | `actions/app_launcher.py`, `dispatch.py` |
| Tk helpers imported by non-UI code: `_center_window`, `_apply_window_icon`, `_set_dark_title_bar`, `_blend`, `hud_constants` colors, `hud_themes` | `features/reminder.py`, `actions/ets2_telemetry_installer.py`, `main.py` |
| AI window: `show_ai_window`, `update_ai_window_text`, `set_ai_window_image/video`, `hide_ai_window`, `cancel_hide_ai_window` | `commands/ai.py`, `info.py`, `song.py`, `interactive.py` |
| Timer/reminder widgets: `show/hide_timer_widget`, `update_timer_total`, `show_timer_done_popup`, `show/hide_reminder_widget` | `actions/game_timer.py`, `features/reminder.py`, `commands/notes.py` |
| Blocking dialogs called from handlers: `ask_text`, `ask_git_stage`, `open_yt_picker` (+`select_index`, `cancel_picker`, `is_picker_open`), `open_compose_dialog`, `open_cleanup_review`, `open_welcome`, `show_guard_alert` | `commands/files.py`, `utils.py`, `yt_play.py`, `interactive.py`, `integrations.py`, `system.py`, `dispatch.py`, `features/guard.py` |
| `hud_camera.set_guard_status` | `commands/system.py` |
| `voice_prompt_bridge` (`register/unregister/try_consume_voice_prompt`) - voice answers to dialogs | `features/reminder.py`, `core/engine/recognition.py` |

About 30 files outside `ui/` are affected. Conclusion: before any new UI,
introduce a single facade (e.g. `ui_api`) with the calls above, and move the
legacy code behind it first. Then the new UI becomes a second implementation
of the same facade, switchable by a setting.

## 3. Feature checklist

Status of 2026-10-19. `[x]` = there is a counterpart in the new window (see the other documents in this folder), `[ ]` = not done or not checked.

HUD window (`hud.py`, `hud_layout.py`, `hud_window.py`, `hud_renderer.py`, `hud_reactor_fx.py`):
- [x] Arc reactor, states IDLE/LISTENING/SPEAKING/LOADING, colour/themes (the "Core" in the hero; the microphone has its own switch in the side panel)
- [x] Side panels and strips (size tiers instead of collapsing panels; the panels can be hidden in Settings > Appearance)
- [x] Header message and notices (`heard`/`reply`, the `notices` topic)
- [x] Zoom (Ctrl +/-, 0 resets) and size tiers
- [ ] Multi-monitor placement, low-performance mode of the Tk renderer (not applicable to the new renderer: the "Economy" effects setting replaces it; multi-monitor placement is the Tauri shell's job: the window position and size are restored, and fall back to the centre when that monitor is gone; checked with a saved position and an off-screen one, not with a second physical monitor)
- [ ] Tray (`Win32Tray`), hide to tray: autostart and microphone toggles are in the window; the tray is done in the Tauri shell (icon, open/quit menu, close hides to the tray, single instance)
- [x] Sub-window tracking: not needed, the new window has no sub-windows (dialogs are inside the page)
- [x] Widgets: weather, system monitoring (also the System screen), timer, reminders, camera/guard
- [x] AI window (text, image, video note, streaming): the answer card
- [x] Themes and the interface language (Russian and Ukrainian)

Dialogs (`ui/dialogs/`), each with its counterpart:
- settings (+ tabs): Settings > Appearance, Tools, Modules, AI, Developer; voice settings = the Voice screen
- extensions (+ setup/common): the Extensions screen with setup forms
- keybind editor, spell editor: the profile editor on the Games screen
- mail (client/compose/reply/shared): the Mail screen and the compose window
- songs: the Songs screen; yt picker, name (`ask_text`), git stage, cleanup review, guard alert: the blocking dialogs (`web/prompts*.js`)
- manage (saved videos, quick links): cards in Settings > Tools
- perf monitor: the System screen (the pinned, compact and transparent modes are the small window `perfmini.html`)
- deck: the Commands screen (+ the alphabetical order switch)
- welcome: the first-run wizard
- file type, commit message dialogs: no callers in the core, not ported

Other: splash (the new window has its own start animation), voice prompt bridge (a shim hands spoken answers to the dialogs), window icon and dark title bar (the Tauri shell).

## 4. Existing tests touching the UI

`tests/test_hud_camera.py`, `test_hud_popup_menu.py`, `test_hud_multimonitor.py`,
`test_mail_setup_dialog.py`, `test_clipboard_paste_fallback.py`, `test_yt_picker_dlg.py`,
`test_reactor_and_browser_commands.py`, `test_settings_path_consistency.py`.
The project has 2200+ pytest tests in total; the UI-related ones above are the parity baseline.

## 5. Open questions

- Stack: web (WebView2) vs PySide6 - to be decided after a spike (transparent click-through overlay, game mode, DLL order vs torch/onnx, PyInstaller size, Python<->JS bridge).
- Design reference from the user is pending.
- Which dialogs are voice-driven (`voice_prompt_bridge`) and must keep that behavior.
