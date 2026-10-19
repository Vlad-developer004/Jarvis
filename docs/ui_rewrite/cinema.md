# Cinema (new UI)

The "Кино" module used to be a stub: no command reached it, and its code scraped a site whose address was empty. It is rebuilt without keys, accounts or scraping.

## What it does

- **Now playing.** Any app that has a Windows media session (browser tabs with a video, VLC, Spotify, the Windows player) is listed with title, position and controls.
  Code: `actions/now_playing.py` (WinRT `GlobalSystemMediaTransportControlsSessionManager`, one background thread with its own event loop). Needs
  `winrt-Windows.Media.Control` and its companions (`requirements-system-optional.txt`); without them everything answers "nothing playing".
  Shown as a capsule under the core on the overview (while playing, and for two minutes after a pause) and on the "Кино" screen.
- **Voice** (words in `actions/media_phrases.py`, handler in `core/handler/commands/cinema.py`, all behind the "cinema" module switch):
  `cinema_seek` ("перемотай на 5 минут назад", "перемотай на отметку 1:20:00"), `cinema_now` ("что сейчас играет"), `cinema_left` ("сколько осталось до конца"),
  `cinema_watch` ("включи фильм X", "найди сериал X сезон 2 серия 3 на Netflix", "где посмотреть X"). Plain "сколько осталось" is still the timer, "что за песня" is still song recognition.
- **Where to watch.** The user's services (`actions/cinema_services.py`): a name and a site. Known services open their own search page; for the rest Jarvis searches that site
  through the web search (`site:domain title`). Any site can be added, optionally with its search address containing `{q}`. The preset list includes 1+1 video and Телепортал;
  their search addresses are not verified, so they use the site search.

- **My library.** Folders with the user's own films and series (`actions/media_library.py`, card "Моя библиотека" on the "Кино" screen). Season and episode are read from the file name
  (`S02E03`, `2x03`, "Сезон 2" / "Серия 3", or a `Season 2` folder); a file without an episode mark is a movie, the year is taken from the name. Files open in the program Windows has set
  for them (`os.startfile`), so any player works. The last watched episode of each series is remembered (`cinema.library` in `jarvis_settings.json`).
  Voice: `cinema_continue` ("продолжи сериал Шерлок", "продолжи смотреть" for the last one, "включи следующую серию X"). "Включи фильм/сериал X" plays the local file first when the title is in a folder and
  no online service is named ("... на Netflix" still goes online). A folder is scanned up to 6 levels deep and 20000 files; the result is cached for two minutes (the "Обновить" button rescans).
  The screen sends only paths the scan already knows, so it cannot make Jarvis open an arbitrary file.

- **Series dates (TVmaze).** `actions/tv_info.py` asks TVmaze (free, no key, no account; shown as a credit "TVmaze, CC BY-SA" on the screen) for a show's status and the dates of the previous and next
  episode, cached for six hours. Voice: `cinema_when` ("когда выйдет следующая серия Шерлока"; without a title it takes the last series watched from the library). The screen has the same in
  "Когда новая серия" and "Когда новая" on a library row. TVmaze indexes mostly English titles, so a Russian name may not be found; a network error and an unknown title both read as "no data".

- **Watch later.** A list of titles (`actions/watch_later.py`, `cinema.later`): "добавь Дюна в список просмотра", "посмотрю позже сериал Шерлок", "что в списке просмотра" (`cinema_later`, `cinema_later_list`);
  on the screen the "Посмотреть позже" card has "Искать" (opens the search in the chosen service) and "Убрать".
- **Cinema mode.** `actions/cinema_mode.py`: "включи режим кино" dims every display to the chosen level (5 to 80 %, default 30, set on the screen) through `screen_brightness_control`, "выключи режим кино"
  puts each display back to its own earlier brightness. The earlier values are stored in the settings, so they survive a restart. A display that does not accept brightness commands is reported, not faked.
- **Next episode into the calendar.** After "Когда новая серия" the screen offers "Добавить в календарь": an all-day event "Show: серия 2x03" on the local day of the air date (once; a repeat is refused).

## Deliberately not done

No per-player integrations (VLC web interface needs a password, mpv needs an IPC option): the Windows media sessions already give play, pause, next, previous and seeking for both. No TMDB or other keyed APIs, no Trakt/Simkl (they need app registration), no Jellyfin (needs a server account), no clicking on the screen, no scraping.

## Status

The block is complete. Possible later additions: Jellyfin (needs a server account), a notifications/focus switch inside the cinema mode, and series dates for Russian titles (TVmaze is English-first).

Tests: `tests/test_now_playing.py`, `test_media_phrases.py`, `test_cinema_media_voice.py`, `test_cinema_services.py`, `test_ui_bridge_cinema.py`, `test_media_library.py`, `test_tv_info.py`, `test_cinema_extras.py`.
