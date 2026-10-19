# Settings screen (new UI): Appearance, Tools, Modules, AI and Developer

Opened from the "Настройки" button in the left navigation. Files: `ui_next/_spike/web/look.js` (screen), `look.css` (screen and dashboard panel switches),
`look_boot.js` (reads the preferences before the first paint and exposes `window.LOOK`).

The theme menu that used to sit in the top bar is gone: themes and the sound switch live only here.

Everything applies at once and is stored in the window's `localStorage` (not in the core settings). The old settings window has no button here any more: what it still had (the old HUD's theme, widgets and scroll bar, full screen) does not apply to this window.

| Block | What it does | Key |
|---|---|---|
| Color theme | 11 ready themes as tiles (a mock of the window in that theme's colours) and "Свой цвет": hue and saturation sliders, previewed live on the open window, saved with "Применить" (the page reloads and returns to this screen) | `jarvisTheme`, `jarvisCustom` `{h, sk}` |
| Theme by time of day | day theme, night theme, night start and end; the page reloads when the schedule crosses day or night (checked every 30 s). Picking a theme by hand turns the schedule off | `jarvisAuto` |
| Interface size | 70..160 %, same value as Ctrl + / Ctrl - / Ctrl 0 | `uiScale` |
| Effects | "auto" (follows the system and the shell's quality hint), "full", "lite" (`html[data-fx=lite]`) | `jarvisFx` |
| Sounds | on/off and master volume (5..60 %), the same switch as in the theme menu | `jarvisSfx`, `jarvisSfxVol` |
| Overview panels | show or hide: Что дальше, Погода, Камера и охрана, Система, История, Подсказки под ядром (`html[data-hide]`, CSS in `look.css`; the remaining panels refill the space; when a whole zone is off, the side column or the bottom row disappears and the core takes its place) | `jarvisHide` |

"Сбросить внешний вид" removes all of the keys above and reloads.

Not here: fullscreen (a job of the Tauri shell). The interface language is described in the section "Interface language" below.

## Tools tab

Cards: saved videos (limit, search, list with thumbnail, title, author, length and date, open, delete; the details are fetched by `bridge/video_meta.py` from YouTube's public oEmbed endpoint and the watch page in the background, cached in memory, and only for youtube.com / youtu.be links), quick links (voice phrase to a link; add, change, open, delete; the service is named from the address), apps kept open in game mode, app launch rules (switch to the open window or always open a new one),
Telegram remote control (token is write-only), updates (auto-install switch, check now, install and restart). Backend: the `tools` command, see `bridge.md`.
The programs picker reads the Windows uninstall registry, the same source as the old window. Tests: `tests/test_ui_bridge_tools.py`.

## Modules tab

Profile (full / assistant / minimal) with a restart note, a tile with a switch for each of 16 modules plus a load estimate (weights as in the old window), morning briefing flags
and calendar reminders (on/off, lead time). A switch equal to its profile is not stored, so it follows the profile; a switch that differs is marked "вручную" and can be reset.
Differences from the old window: no automatic `pip install` on toggles (the old window synced `requirements-base.txt` in the background), no semantic-cache rebuild (it
imported a name that does not exist), and saving the briefing no longer drops `calendar_reminder_*`. Backend: the `modules` command; tests: `tests/test_ui_bridge_modules.py`.

## Developer tab

`web/dev.js`, backend `ui_next/bridge/dev.py` (`dev` command). Four cards, all saved at once:

- **Рабочее окружение**: apps whose focus tells Jarvis the current project (`context_apps`, with the installed-programs picker shared with the Tools tab through `window.toolsPickApp`), the switch "search in parent folders" (`allow_parent_search`) and the folder search depth 1 to 10 (`folder_search_depth`).
- **Новый файл: расширения**: `programming_file_extensions`.
- **Редактор по умолчанию**: editors found on the PC plus own ones added with a file dialog (`custom:<exe path>`, removable); the choice is `dev_default_editor`.
- **Проекты: за работу**: name, folder (native folder dialog or a search by name on the disk) and an optional editor per project; "Открыть" starts it as the voice command does. A project whose folder is gone is marked.

Everything goes through `core/settings_io.py`, so the old window and the core read the same values. Tests: `tests/test_ui_bridge_dev.py`.

## AI tab

`web/ai.js`, backend `ui_next/bridge/ai.py` (`ai` command). Cards: **Провайдер и модель** (tiles for Groq, OpenAI, Google, DeepSeek, Anthropic, OpenRouter and a local server, the model list with context and rate limits, a field for a model that is not listed, "Обновить список"),
**Ключ** (write-only: the screen shows only "key saved" and never receives a key; replacing and deleting need the key field or a second click) or **Локальный сервер** (address and an optional key), **Проверка связи** (one tiny request, shows the answer time),
**Как отвечает ИИ** (three presets, temperature, answer length, top-k for the local server only) and **Дополнительно** (OpenAI web search, the answer window). Picking a provider or saving a key refreshes the model list on its own.
Settings are the same keys the old window writes (`ai_provider`, `ai_model`, `ai_local_base_url`, `ai_temperature`, `ai_max_tokens`, `ai_top_k`, `ai_web_search_enabled`, `ai_mini_window`), so `features/qa/llm_processor.py` needs no change. Tests: `tests/test_ui_bridge_ai.py`.

## Backup, wizard, backup AI provider and budget

- **Резервная копия** (Tools tab, `bridge/backup.py`): one JSON file with the settings, the user's own calendar events and the appearance choices. API keys, passwords and tokens are never written (detected by key name at any depth), neither are values that belong to this PC (audio devices, window sizes, last location).
  Restoring is two steps: the file is read and described, then applied after a click; the current settings are copied to `jarvis_settings.before_restore.json` first, settings are merged key by key (a secret already held by the current section stays), calendar events are added only when missing. Tests: `tests/test_ui_bridge_backup.py`.
- **Мастер первой настройки** (`web/wizard.js`, `bridge/wizard.py`): language, microphone (device and calibration), form of address, feature profile, AI key, finish. It opens by itself once after the core connects until it is finished or skipped, and from Tools > "Пройти мастер" or `window.openWizard()`.
  Current values are preselected and every choice is applied at once through the voice, modules and ai commands, so walking through without touching anything changes nothing. Esc closes it without remembering, "Пропустить мастер" remembers.
- **Запасной сервис и бюджет** (AI tab, `features/qa/ai_router.py`): every question goes along a chain: the chosen provider, then the other providers that have a key (order `ai_fallback_order`, default Groq, OpenAI, Google, DeepSeek, Anthropic, OpenRouter) and the local server when its address is set.
  A provider that returns nothing (error, timeout, empty answer; for a stream the first piece decides) is replaced by the next one; Jarvis says so aloud for his own voice questions, game narration stays silent. With the budget mode on, requests are counted per provider per day (`ai_usage.json`);
  at 80% of the daily limit Jarvis warns once, at the limit the provider is skipped. The limit is the user's number for the chosen provider (`ai_daily_limit`), else the `rpd` of the model in the catalog; unknown means no limit. If everything is used up, the chosen provider is still tried.
  Besides requests the router counts tokens (estimated from the text, about 3 characters each): what was sent (input) and what came back (output), per provider per day, with 30 days of history shown as a 14-day chart on the AI tab (requests / input / output, per provider or all). The user can set daily limits for the chosen provider for requests, input tokens and output tokens (0 = none); the 80% warning and the skip at the limit apply to each.
  The "Проверка связи" button asks the chosen provider only, so a backup cannot hide a broken key. Tests: `tests/test_ai_router.py`.

## Answer card

`web/answer.js`, `ui_next/bridge/answer.py`. The old HUD's small answer window (an AI answer that streams in, the NASA picture of the day, a recognised song) is a floating card in the bottom right corner of the new window: subject, streaming text that follows the end unless the user scrolls up, a picture (Wikipedia thumbnail for answers, cover for songs, shrunk to a small JPEG), a cross to dismiss.
It closes by itself after the speech ends plus a reading pause, as before. The switch "Окно с ответом ИИ" (`ai_mini_window`) still decides whether it appears. The core's calls did not change: `ui/hud_ai_window.py` offers each event to the new window first and opens its Tk window only when no new window is connected.
A video (the picture of the day can be one) is announced but not played in the card. Tests: `tests/test_ui_bridge_answer.py`.

## Dialogs the core waits for

`web/prompts.js`, `prompts_list.js`, `ui_next/bridge/prompts.py` and `dialogs.py`. Five old Tk dialogs are modal windows of the new window: **a name or text** (new folder, new file with its folder and type, delete by name, macro name; `ask_text`), **the files and options of a git commit** (`ask_git_stage`: message, branch or a new one, push with force / upstream / pull request title, a searchable file list),
**the deep cleanup review** (nothing is checked beforehand; the folders are deleted for good, which the dialog says), **which video to play** (cards with thumbnails and a countdown; a click or a spoken "первое" picks, no answer plays the first, "отмена" plays nothing) and **the camera guard alert** (the picture and a notice).
Each old function offers the dialog to the new window first and opens its Tk window only when no new window is connected, so nothing changes for the old UI. Spoken "создай" / "отмена" / "коммит" press the same buttons through the old voice-prompt bridge.
One dialog is open at a time (a new one cancels the old one). The core never trusts the screen: answers are checked against what was offered. `ask_commit_message` and `ask_file_kind` have no callers and were not ported. Tests: `tests/test_ui_bridge_prompts.py`.

## Commands screen: what replaced the old "deck"
The old deck window (`ui/dialogs/deck.py`) is covered by the Commands screen (`web/cmds.js`): search (ranked, with simple Russian stemming; it does not match the technical command id), category rail, several example phrases per command, copy a phrase, a "try it" button, and the "only with a run button" filter. The one thing the deck had and the screen lacked, ordering by name, is the "По алфавиту" switch (one A to Z list of the general commands, or A to Z inside a category). The deck's third ordering, by the technical id, is not carried over.

## Interface language (Russian and Ukrainian)
The language is the core's setting (`language` in the Voice screen, the wizard, the old window, or a voice command). The core publishes it on the sticky `lang` topic; `web/i18n.js` follows it and reloads the page when it differs from what the window shows (the browser keeps the last one, so the first paint is already right). Changing it in the window goes through `J.send('voice', {op: 'set', key: 'language'})`, which the layer also notices.

How the texts are translated:
- **Window texts.** The source is Russian. With Ukrainian chosen, `i18n.js` replaces the texts at the moment they are drawn: text nodes and the `title`, `placeholder`, `aria-label` and `alt` attributes, for what is on the page and for everything added later (a `MutationObserver`; no screen has to know about languages). The catalog is `web/i18n_uk.js` (`I18N_UK`: Russian fragment to Ukrainian, matched as whole words or phrases inside longer text, longest first; `I18N_WORDS`: short words such as months and "из", replaced as whole words). A line built from parts ("Найдено: 5 команд") is therefore translated piece by piece.
- **Left alone on purpose.** What people and services wrote (mail, the answer card, the history of phrases, event titles, what plays) and the voice phrases of the command catalog, so that no half-translated mix appears and the phrase shown is the one the core matches. Containers are marked `translate="no"` or listed in `SKIP` in `i18n.js`; `I18N.keep(text)` protects a piece placed inside a sentence of the screen.
- **Texts that come from the core** are translated there: the command names and descriptions (`bridge/commands_meta_uk.py`, used by `bridge/catalog.py`), the category titles, the currency names (`actions/currency_pairs.supported(uk)`). The command phrases are shown with Ukrainian ones first (`_ukrainian_first`, by letters only). The catalog is rebuilt when the language changes. Descriptions of extensions come from `data/extensions_catalog*.json`; the ones the window knows are in `i18n_uk.js`.
- **Adding a text.** Write it in Russian in the screen. To translate it, add an entry `"Russian text": "Ukrainian text",` to `I18N_UK` in `web/i18n_uk.js` (one entry per line, no final dot or colon in the key: they are cut before the lookup); `I18N.missing()` in the browser console lists what is still Russian on the page (it looks for letters and endings Russian has and Ukrainian lacks, so it is a hint, not a proof).
- **Test hook.** `sessionStorage.uiLangTest = 'uk'` forces the language for one window without touching the stored one.
- Not translated: spoken texts (the core's own `core/i18n`), the old Tk windows, texts of services (weather descriptions, mail).
Tests: `tests/test_ui_i18n.py`.

## One look for every theme, and short or narrow windows
- The look of the first theme ("Командный центр", the `command` skin in `skin.css` and `buttons.css`) is now the look of all themes: `data-skin=command` is set on every theme and a theme only changes the colours. The dark background takes the theme's hue (`--navy-h`, saturation scaled by `--ns`; the first theme keeps its own navy), so Matrix is green, Cyberpunk pink, and so on. The old angular look is gone.
- Short windows (`fitHero`, `fitNav`, `fitSide` in `app.html`): the lower part of the hero gives way when it would take more than 45% of the hero (the player first, then the wave, then the reply line); the menu scrolls when even the compact menu does not fit; a side panel whose content would be cut off is hidden instead.
- The narrow tier (`mini`) hides the right part of the header (the game mode switch and the bell), which left an empty capsule, and keeps the status pill clear of the clock.

## Screen sizes, system scale and interface zoom

The page works in CSS pixels, so the Windows scale (100/125/150/200%) only changes the window's size in CSS pixels; the root font then follows the window (`layout()` in `app.html`). Checked with an emulated matrix of 14 window sizes (720p, 768p, Full HD at 100/125/150/200%, 2K, 4K at 100/150/200%, small, tiny and short windows) by 3 interface zooms (80%, 100%, 160%) on all 12 screens.

- The interface zoom (Ctrl +/-, the slider in the appearance settings) is limited to 80-160%; a stored value outside it is clamped on load.
- The root font never goes below 13px, and the micro labels (formerly 0.5-0.64rem) are at least `max(.65rem, 9px)`, so nothing becomes unreadable in a small window with a reduced zoom.
- The maximum window-based growth is 2.3 (was 1.9), so a 4K screen at 100% is not left with tiny text.
- Compact tier (a narrow or low window with an icon-only menu): the menu gets the tight spacing and, if it still does not fit, scrolls; before, the Settings icon was cut off at the bottom.
- Known limits: at 160% zoom in a window below about 1550px the mail list shows one or two letters (the tabs take the height); the button labels with letter-spacing can be clipped by a pixel at the same zoom.
