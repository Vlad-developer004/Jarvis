# Dashboard design system (draft, page `ui_next/_spike/web/h.html`)

Based on the first reference (command-center dashboard), adapted to Jarvis. Dark navy glass, chamfered panels, rotating AI-core sphere.
Run: `ui_next/_spike/run_variant.ps1 h`. Data: CPU/RAM/disk/net are real, everything else is mock.

## Content (7 blocks instead of 11)

Removed (not Jarvis features or duplicates): Agents, Memory insights, Workflows, Conversations, Knowledge base; "Modules", "Active tasks" and
"Events feed" overlapped (reminders/calendar/mail were listed three times).

| Block | Job for an ordinary user |
|---|---|
| Core (sphere + live phrase + mic) | what Jarvis hears now and what it answers |
| What next | timer countdown, reminders, planned game session, "in 1 h 4 min" |
| History | what I said and what Jarvis did ("open calendar" -> Calendar opened) |
| State | plain-language health: Hearing / Voice / Answers / Internet chat |
| System | CPU, RAM, disk, battery, network |
| Quick actions | 4 big buttons, each shows the voice phrase that does the same |
| Weather | chip in the top bar; full panel only in the `wide` tier |

"State" rule: quiet when fine, explanatory when not. Model names (Vosk, sherpa-onnx, Silero, Groq) are tooltips and live in settings.
If something breaks: red banner "Jarvis cannot hear you" + action button ("Check microphone"), the top-bar pill turns red. Press `X` in the prototype to see it.

## Typography

Bundled open-licence fonts with Cyrillic (OFL): **Tektur** (display: logo, clock, big numbers, panel titles) + **Onest** (all text and buttons).
Checked on a specimen sheet; rejected: Share Tech Mono (no Cyrillic), Unbounded (too wide), Russo One (heavy), Jura (too thin at small sizes).
For production subset to Latin+Cyrillic woff2 (~40-60 KB each instead of 160-190 KB TTF).
Sizes (rem, base 16 px at 1280x720): body 0.94, secondary 0.81, panel title 0.78 (Tektur, tracked), buttons 0.95 semibold with >= 2.9 rem hit area,
live phrase 1.55, timer 1.9, clock 1.45. Percent signs use Onest (Tektur's `%` reads as `/`).

## Scaling and thresholds

Everything is in `rem`. Root font = `16 px * clamp(min(W/1280, H/720), 0.85, 1.9)^0.8 * userZoom` (damped, so fullscreen grows ~1.4x not 1.5x). User zoom Ctrl +/-/0 (70-160 %).
Tier is chosen by width in rem (not px), so OS scaling and user zoom move the tier automatically. Config lives at the top of the script (`TIERS`, `SHORT_REM_H`, scale constants).

| Tier | Width (rem) | Typical window | Layout |
|---|---|---|---|
| mini | < 52 | ~600x420 | single column: status, core, next timer, nav as a bottom bar |
| compact | 52-72 | 800-1100 px | icon rail, core, What next + State; bottom: System + Quick (hints hidden) |
| standard | 72-100 | 1280x720 ... fullscreen 1080p | full layout, 3 columns + bottom row |
| wide | >= 100 | ultrawide (e.g. 1800x760) | + Weather panel, wider side column |

Height rule: below 38 rem the bottom row is dropped (`data-short`). Minimum window 560x400. History rows are trimmed to fit (`fitRows`), so more rows appear on larger screens.
Measured: 1280x720 -> 80x45 rem (standard); 1920x1080 fullscreen -> 87x49 rem (standard, 22 px); 1000x640 -> 71x46 rem (compact); 800x520 -> compact; 600x420 -> mini; 1800x760 -> wide.

## Cost (same machine, 30 fps cap, one canvas)
1280x720: 2.4 % CPU, 2.0 % GPU, 166 MB. Fullscreen 1920x1080: 2.0 % CPU, 4.5 % GPU, 163 MB (GPU grows with canvas area; use the Lite tier / lower fps in game mode).

## Open points
- Real content/wording for History and Quick actions (which commands matter most).
- Whether settings gets a "UI scale" slider and a manual tier override (thresholds are already in one config object).
- Light theme: not done.

## Update (page `app.html`, after feedback on weather, camera, status block)

- Removed the "State/models" panel. Status = a pill in the top bar + the ticker strip in the core for problems. Models only in Settings.
- Weather became a scene driven by real sunrise/sunset (day/night cycle), conditions: partly, clear, cloudy, rain, snow; UI background tints with daylight.
- Added "Camera and guard" (from the old HUD), "History" moved to the bottom row, quick buttons became suggestion chips, game-mode toggle in the top bar.
- Cost (1280x720, 30 fps core + 9 fps weather/camera): ~3 % CPU, 3-6 % GPU (counter is noisy), ~160 MB.
- Prototype controls: X (mic problem), N (notices), T (cycle time of day), W (cycle weather), Ctrl +/-/0 (zoom). Shell presets: `JARVIS_Q="t=12:00;w=rain;g;x;n;c"`.
- Full per-element reasoning: `feature_audit.md`.


## Polish layer (`web/fx.css`, `web/fx.js`)

Decoration that sits on top of the screens and can be switched off as a whole (`html[data-fx=lite]`: weak machines,
`prefers-reduced-motion`, or `JARVIS_Q=lite`). It is paused while the window is hidden (`html.fz-paused`).

| Piece | What it does | Idle cost |
|---|---|---|
| Glass panels | the panel fill is translucent, so the background field shows through | none |
| Background field | two light fields and a radar ring (`#fzbg`), shifted by the pointer (parallax, 1.1 s ease) | none |
| Screen entrance | on every view switch: heading line draws, heading text decodes, cards reveal one after another (clip only, no layout shift) | one-shot |
| Pointer light | a soft spotlight follows the pointer inside the hovered card; corner brackets close in | only while hovering |
| Press feedback | brightness flash on buttons, scale on press, halo on switches | one-shot |
| Numbers | system rings count to the new value (`fzNum`), the clock seconds drop in, tabular digits | one-shot |
| Edge ruler | fine tick scale on the right edge of every panel | none |

Measured on this machine (whole process tree, 100 % = all cores, 25 s each): a continuously running animation costs
about +4 to 5 % CPU per effect even when it is stepped down to 3 fps (the page then redraws at the display rate), so
the background is static and reacts to the pointer instead. With that, the full layer measures the same as `lite`
(about 10 % in both, the rest is the core canvas). Debug switches for such measurements: `JARVIS_Q=nx=glass,blob,ring,tick`.


## Controls, sounds, themes (second pass)

- **Keys** (`.cm-try`): chamfered plate, status notch on the left, a sheen that sweeps over it on hover, a charge line that fills along the bottom edge, press = sink.
- **Gates** (`.tgl`, `.gmode`): two-position switch that always shows both words (`ВЫКЛ | ВКЛ`); the lit window sits on the active one (green, amber for game mode). The labels are injected by `fx.js`.
- **Sounds** (`web/sfx.js`): synthesised with Web Audio, no files. Click, hover tick, switch on/off, screen change, toast chime. Master gain 0.2, created on the first gesture, throttled per sound, switch in the theme menu (`localStorage jarvisSfx`). Nothing runs while idle.
- **Themes**: ten in total; added `crimson` (Алая тревога, h 352) and `violet` (Ультрафиолет, h 268). Every screen was checked in each of them.

## CPU budget (target: at most 5 % of the machine)

Measured with `ui_next/_spike/measure_split.py` (CPU per process role: GPU / renderer / browser) and
`ui_next/_spike/cdp_profile.py` (WebView2 remote debugging: style / layout / script time, JS self-time profile, running animations).
The window with Jarvis connected and idle went from 7 to 10 % down to 3.5 to 4 %; the commands screen is about 1.7 %.

What was costing, and the rules that follow:
1. **Never animate layout properties.** The seconds bar under the clock tweened `width`, and the 16 microphone-level bars tweened `height`: layout and style recalculation ran about 80 times a second on every screen. Use `transform`, or step once per second.
2. **An endless CSS animation keeps the page redrawing at the display rate**, even a 0.7 rem LED, and stepping it down to 3 fps does not help. So nothing may loop while idle: `html[data-st=IDLE]` pauses the radar sweep, the glow, the status LED and the ticker; backgrounds are static and react to the pointer instead.
3. **The core canvas is the main cost.** Idle: about 12 fps (the globe turns slowly), active: 25 fps, pixel density capped at 1.25. The wave canvas has no `shadowBlur`.
4. **"Calm" counts as idle.** The core can stay in LISTENING for a long time after a stray noise; when it lasts over 8 s without speech the page treats it as idle (colour and captions stay).
5. `drawDecor()` (the static ring art) only re-renders when the colour or the size changes. Ring values have no transition.

Measurement switches (`JARVIS_Q=nx=...`): `idle`, `speak` (pin the demo state), `core`, `sky`, `cam` (skip a drawing block), `anim` (no CSS animations), `glass`, `blob`, `ring`, `pulse`.
Measurements on this machine are noisy (clock scaling): repeat a run three times before believing a difference below 1 point.


## Core, header, microphone card (third pass, from the reference image)

- **Core** (`drawDecor` in `app.html`): rendered once per colour/size into an offscreen canvas: 270-node mesh on a sphere with depth-graded links and hub nodes,
  atmosphere ring, rim light, two tilted orbits (back half behind the sphere, front half in front) with satellites, glowing concentric floor with a tick ring,
  side arcs, dust. No spinning globe and no radar wedge. Idle: a glint pass every 450 ms (hub nodes, stars). Listening/speaking: 25 fps with the voice equalizer ring,
  pulse waves and comets on top of the static art. Measured: idle 3.1 %, speaking 3.3 % (the old animated globe: 4 to 11 %).
- **Title**: lighter weight, cyan-white gradient with a soft glow; the subtitle has flanking lines.
- **Header**: game mode, theme and notifications are one control strip (one plate, hairline dividers); the theme button has a palette icon (it used to be an unclear cube).
- **Microphone card**: icon in a chamfered frame, value tiles for gain and threshold, each setting row is a plate with a gate switch.


## Skin "command" (theme «Командный центр», `web/skin.css`)

The look of the reference dashboard, scoped by `html[data-skin=command]` (a theme can carry `skin: 'command'`), so the other themes keep the angular look.
Cyan accent (h 197) on a fixed deep-navy fill (h 219), hairline cyan panel edge with a smaller chamfer, hexagonal status pill and a large cyan clock with the date above it,
outlined active menu item, round counters, rounded rows, and the whole core in the cyan family (green stays for "on" switches and OK states).
Also fixed: relative times ("N мин назад", "через N мин") are now correct across midnight (they arrive as HH:MM).

Controls in this skin follow the reference too: rounded buttons with a thin cyan outline and soft glow, pill chips and tags, rounded inputs, pill switches (both words stay visible),
a round microphone orb with halo rings, the clock with equal-size seconds. Core motion (cheap vector overlays at 10 fps while idle: a light band sweeping down the sphere,
satellites on both orbits, a bright arc running along the floor rings; the voice ring, waves and comets while speaking) measured at 3.2 to 3.6 % total CPU, the same as without it.

- Dropdowns: never use a native `<select>` list (it cannot be themed). `web/dropdown.js` (`fzDropdown.watch(root)`) swaps selects for a themed popup with search (over 8 items), keyboard and flip-up; the hidden select keeps its value and `change` event.
- Text fields in panels: `web/fields.js` (`fzFields.watch(root)`) wraps inputs in a frame with an icon by field kind, corner ticks, a charge line on focus and a clear button; the input element, id and events stay unchanged. Small numeric inputs (`inputmode=decimal`) stay plain.
- Dates: never use the native date input popup (browser calendar, wrong locale, unthemed). `web/datepick.js` (`fzDate.watch(root)`, already watching the whole body) replaces `<input type="date">` with a button and a themed Russian calendar (month and year views, keyboard, flip-up); the input stays hidden with its ISO value, `input` and `change` events and a `value` setter that updates the button.
