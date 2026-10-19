# Audit of the old HUD: keep, drop or redo (draft)

Rule for every element: does an ordinary user need it? what is the best way to show it? what from the old HUD is worth reusing?
Sources: old HUD screenshot, `ui/hud_*.py`, `features/guard.py`, `actions/weather.py`. Items marked (?) were not verified in code.
Prototype: `ui_next/web/app.html` (keys: X mic problem, N notices, T time of day, W weather, Ctrl +/- zoom).

| Old element | Needed? | Decision and implementation | Data / reuse |
|---|---|---|---|
| Title bar "JARVIS OS v0.1.0" | version no, clock yes | Clock and date stay in the top bar; version moves to Settings > About | existing |
| Battery bar (System profiles) | laptops only | One metric inside "System"; warning goes to the ticker below 20 % | psutil battery (sidecar) |
| Mic gain / threshold block | rarely | Not on the dashboard. A live mic level lives in the Voice page and settings; calibration stays there (from beta) | `core/speech`, VAD thresholds |
| Command buttons (Monitor, Command base, Settings, Extensions, Mail, Songs, Autostart) | navigation, not content | Become the left navigation (Commands, Mail, Songs, Extensions, Settings). Autostart is a settings toggle; System monitor opens as a page | existing dialogs |
| Game mode section | yes, core feature | Toggle in the top bar (always visible); profiles on the Games page. In game mode the dashboard stops rendering and only the compact overlay stays | `actions/system_parts/game_mode.py`, profiles |
| Storage (RAM, disk) + network | partly | One "System" panel: CPU, RAM, disk, battery, network speed. "Link speed" dropped (it was always "...") | Rust sensor sidecar |
| Atmosphere (weather) | yes, and it can be much richer | Big panel with a sky scene tied to real sunrise/sunset: sun and moon travel along an arc, dusk colours, stars and city lights at night, clouds, rain, snow. Plus the existing advice ("take an umbrella") and "N degrees warmer than yesterday" which already exist for voice replies | `get_weather_hud`: temp, feels, desc, WMO icon, wind, humidity, pressure, sunrise, sunset; advice and yesterday compare in `actions/weather.py` |
| Sunrise / sunset big numbers (top strip) | merged | Shown as the ends of the sun arc inside the weather scene, plus "time to sunset/sunrise" | same data |
| Top progress bar "0% ... -/-" (?) | unclear purpose | Dropped. Real progress (model download, update) is shown in the ticker only while it runs | ticker |
| Clock, date, uptime | clock yes, uptime no | Uptime goes to About | - |
| Reactor + status pill "INITIALIZATION" | yes | The AI-core sphere with state colour (waiting / listening / speaking) and a live phrase; loading shows as progress in the ticker, not as a mysterious word | `HudState` |
| Side arrows "<<" ">>" | no | Replaced by responsive tiers (mini/compact/standard/wide) | - |
| Camera preview with face box + standby reticle | yes, but merged with guard | One panel "Camera and guard": preview and guard mode, buttons, state, last event. The camera can be held by only one of them (as in the old code), so the camera button is disabled while the guard is on | `ui/hud_camera.py`, `features/guard.py` (owner/intruder recognition every 4 s, 30 s alert cooldown, Telegram) |
| Header messages (`hud.notify(key, text, color)`) | yes | The ticker strip at the top of the core; calm greeting when nothing is wrong. Severity: info (cyan), warning (amber), error (red + status pill "Needs attention") | `notify` / `clear_notify` map 1:1 to ticker items |
| "Everything works" / models status | no as a panel | Removed. One pill in the top bar (green "Jarvis works", red "Needs attention") plus the ticker for problems. Model names (Vosk, sherpa-onnx, Silero, Groq) live in Settings > Models | health from existing checks |
| Quick action buttons | partly | Replaced by suggestion chips under the live phrase ("say: set a timer for 10 minutes"): they teach voice commands and cost no panel | static list, later from usage |
| Timer / reminder widgets and popups | yes | "What next": timer countdown, reminders, planned game session. Due reminder = toast + voice | `hud_timer_widget`, `features/reminder.py` |
| AI answer window (text, image, video, streaming) | yes, not in the prototype yet | Slide-over panel on the right with the streamed answer and media; closes on its own | `hud_ai_window.py` |
| Performance monitor dialog | rarely | Done: the System screen (`perf.js`, `bridge/perf.py`) and the small monitor window (`perfmini.html`, opened by the "Мини-окно" button: pinned on top, short, transparent) | `perf_monitor.py` |
| Tray, zoom buttons | tray yes, zoom no | Tray by the Tauri shell (done: icon, open/quit menu, the close button hides to the tray, a second launch brings the window forward); zoom replaced by the UI scale (Ctrl +/-) and size tiers | - |
| Settings, mail, extensions, songs, spell/keybind editors | yes | Later screens; same design system | `ui/dialogs/*` |

New in the prototype (ideas, to confirm): sky scene as an ambient indicator of time of day; global tint of the UI by daylight; guard last-event line;
suggestion chips; ticker; game-mode toggle in the top bar. Night mode: the idea is to tie "quiet at night" to the daylight cycle, but whether Jarvis has an automatic
night schedule is not verified; check `core/handler/base.py` before promising it.

Open questions for the owner: which events deserve the ticker (battery, mail, reminders, guard alerts, errors)? Should the sky tint the whole window or stay inside the panel? Is the guard last-event (and an intruder snapshot) wanted on the dashboard?
