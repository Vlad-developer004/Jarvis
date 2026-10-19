# The window and the core (state after the old UI was removed, 2026-10-19)

The CustomTkinter HUD (`ui/`) is gone. The window is the Tauri program in `ui_next/shell/` with its pages in `ui_next/web/`; the core talks to it only through `ui_next/host.py` and the bridge (`ui_next/bridge/`).

```
core (Python)                         window process (Tauri + WebView2)
  host.py  -- publishes -->  bridge/hub.py (SSE /events)  -->  web/*.js
  host.py  <-- commands ---  bridge/hub.py (POST /cmd)    <--  web/*.js
  shell.py starts/stops the process, watches the tray's Quit
```

## What the core calls (`ui_next/host.py`)
| Call | Meaning |
|---|---|
| `STATE`, `HudState`, `set_mode` | LOADING / IDLE / LISTENING / SPEAKING, own lock |
| `notify(key, text, color, duration)`, `clear_notify`, `active_notices` | the ticker strip; severity from the colour (`CYAN`, `AMBER`, `RED`) |
| `show_window`, `open_view(name)`, `open_wizard`, `open_mail_compose`, `reactor(op, color)` | commands to the window through the `uicmd` topic |
| `show_ai_window`, `update_ai_window_text`, `set_ai_window_image/video`, `hide_ai_window`, `cancel_hide_ai_window` | the answer card (`answer` topic) |
| `show_alert`, `show_timer_done` | pop-ups with optional buttons (a due reminder with snooze), closed by hand, voice or timeout |
| `ask_text`, `ask_git_stage`, `open_cleanup`, `open_yt_picker` (+ `select_index`, `cancel_picker`, `is_picker_open`), `show_guard_alert` | blocking questions; without a window they count as cancelled |
| `exit_now` | closes the window process and the bridge, then ends the core |

Every call is a no-op that reports it did nothing while no window is connected, so the core never waits for a screen. A question brings the window out of the tray first.

## Topics and commands added with the removal
- Topics: `uicmd` (non-sticky: `show`, `view`, `wizard`, `compose`, `reactor`), `guard` (the camera guard's state, polled by the observer), `notices` now comes from `host.active_notices()`, `state` from `host.STATE`.
- Commands: `guard` ({on}: starts or stops the camera guard; the answer does not wait for the face learning, the `guard` topic follows).
- Removed: the `dialog` command (it opened old Tk dialogs).

## Where the old features went
Settings: Settings screen (`look` view: Appearance, Tools, Modules, AI, Developer) and the Voice screen; extensions, mail, calendar, songs, cinema, games and the profile editor, system monitor (and the small window `perfmini.html`), reminders and timers (screen plus pop-ups), the answer card, camera and guard, first-run wizard, tray. The ETS2 plugin installer asks for the game folder in the native folder dialog.

## Moved and deleted code
- `ui/voice_prompt_bridge.py` -> `ui_next/voice_prompt.py`; the Wikipedia picture lookup -> `actions/wiki_image.py` (certificates are verified now).
- Deleted: all of `ui/`, `ui_next/_spike_tk`, the design prototypes `a`-`h`, `dashboard`, `index`, the spike scripts and measurements. A copy of the old UI is in `C:\Users\tanja\jarvis_backup_old_ui_20261019` (outside the repository) and in git history.
