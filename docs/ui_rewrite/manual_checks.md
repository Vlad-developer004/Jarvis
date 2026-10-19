# Manual checks that need a person or hardware

Each item has what to do and what must be true. Tick it off here when done.

- [ ] **Ukrainian texts**: switch the language to Ukrainian, open every screen and the wizard; a native speaker reads the texts. No Russian-only letters, no mixed words.
- [ ] **Voice flows on the real core**: say a command from each category (timer, weather, media, calendar add, cinema); the reply appears and is spoken in the window.
- [ ] **git commit and cleanup flows**: run them from the window; the confirmation dialogs appear in the new window and the action completes.
- [ ] **Packaging**: `build.bat`, start `dist\Jarvis\Jarvis.exe`, the new window opens , tray works, nothing is missing (fonts, locales). Check `jarvis.spec` still carries your own change.
- [ ] **4K at 150%**: open the window on a 4K screen with Windows scale 150%; no clipped labels, sidebar usable, zoom 160% still readable.
- [ ] **Second monitor**: move the window to the second screen, close, start again: it returns there; unplug that monitor, start: it opens centered on the main one.
- [ ] **Tray**: icon visible, left click opens, right-click menu "open"/"quit" works, close button hides to tray.
- [ ] **Update**: put a test release (zip, `SHA256SUMS`, `.sig`) on a private repo or a local mock, run the check from Settings > Tools; a wrong signature must be refused (see `docs/releasing.md`).
- [ ] **Telegram**: send "тише" from your chat (works) and "выключи компьютер" (refused, nothing happens); send from another account (ignored).
- [ ] **Live injection check**: `python ui_next/_spike/cdp_xss.py <exe>` and `cdp_csp.py <exe>` after any UI change; both must report no problems.
