# Audit remediation plan

Source: the full audit of 2026-10-19 (manual review; no bandit/ruff/pip-audit were available). Each item has a fix, the tests that prove it and an acceptance line.
Rules for every phase: no commits without approval (show diff, wait, propose commits, suggest `/clear`); the startup order in `main.py`, Win32/COM code and the locks in `core/system/state.py` stay untouched (CLAUDE.md rules 1-4); docs are updated with each behavior change; a phase is done when its tests are green and, for UI/Win32/audio, the app was started by hand.

## Status (2026-10-19)

| Phase | State | Notes |
|-------|-------|-------|
| 0 protect the work | done | copies of all changed and untracked files in `C:\Users\tanja\jarvis_backup_20261019*`; `.gitattributes` already existed |
| 1 secrets and logs | done | `core/redact.py`, `core/secrets_store.py`, Telegram allow-list (`REMOTE_ALLOWED`), diagnostic prints moved to the logger |
| 2 updates and downloads | done in code | signed updates (`tools/sign_release.py`, `docs/releasing.md`), `core/download.py`; no public key is installed yet, so updates are announced but not installed until `genkey` is run; model hashes are not pinned yet |
| 3 bridge and window | done | CSP set and checked in the live window, SSE client cap, request timeout, XSS fix (weather city), mail CSS filter; file ACL and request rate limit skipped (loopback, per-user folder) |
| 4 quality gates | done | `ruff.toml`, `bandit.yaml`, `.github/workflows/ci.yml` (the Windows pytest job has not run on GitHub), dependency audit in `docs/security_deps.md`; dependency bumps not applied |
| 5 broad excepts | done for non-native code | 379 silent handlers now call `core.safe.swallow()`; 313 in 37 native Win32/COM/audio files left alone and frozen by `tests/except_budget.json` |
| 6 state | done | paired accessors in `core/system/state.py`, the existing lock untouched |
| 7 privacy | done | `allow_ip_lookup` setting (no UI switch yet), plain-http geolocation provider removed |
| 8 safe open | done | `core/safe_open.py` used by the voice, recent, media and session openers |
| 9 file splits | plan only, needs approval | `docs/split_plan.md`, `tests/test_file_size.py` freezes the sizes |
| 10 leftovers | checklist | `docs/ui_rewrite/manual_checks.md` |

Later the same day the old CustomTkinter UI was removed (see `docs/ui_rewrite/host.md`). Consequences for this plan: the three giant UI files listed in the split
plan (`voice.py`, `keybind_editor.py`, `dev.py`) and the other `ui/` files no longer exist, and the `ui/` entries of `tests/except_budget.json` and `tests/file_size_budget.json` are gone. The live
injection check found two more unescaped sinks in the window (notice texts in the header ticker and the bell list, prompt button labels); both are fixed and covered by `tests/test_ui_web_guards.py`.
The shell program is now `jarvis-ui.exe` (`ui_next/shell`), the pages are `ui_next/web/app.html` and friends, the check scripts are in `ui_next/devtools/`.

Correction to the audit text: `core/system/updater.py` was not a duplicate of `app_updater.py`. It was a stub that downloaded the latest release of a
third-party ETS2 plugin repository (a macOS archive was sitting in `data/update/`) and was never applied. It is removed, and the `updater` module switch
now controls the real self-updater.

## Phase 0. Protect the work (before anything else)

| # | Task | Done when |
|---|------|-----------|
| 0.1 | Backup branch or `git stash -u` copy of the whole working tree (95 changed/untracked paths). | A second copy exists outside the working folder. |
| 0.2 | Add `.gitattributes` (`* text=auto`, `*.bat text eol=crlf`, binaries marked) so CRLF/LF does not pollute the diff. | `git diff --stat` shows no whitespace-only files. |
| 0.3 | Owner-driven commit split of the uncommitted work (see "Commits" below). | Tree is clean except `jarvis.spec` (owner's own change). |

## Phase 1. Secrets and logs (small, safe, highest value)

**1.1 Telegram token in logs** (`features/remote_control/client.py`, `features/guard.py`)
- Add `core/redact.py`: `redact(text)` masks `bot<digits>:<token>` in URLs and any value of known secret env vars.
- Replace `print(... {e!r})` in `_get_updates` with `_log.warning('getUpdates failed: %s', type(e).__name__)`; run every exception text through `redact`.
- Tests (`tests/test_redact.py`, `tests/test_remote_control.py`): a `requests.ConnectionError` whose text contains the bot URL never reaches the log/stdout (caplog + capsys); `redact` masks token shapes, leaves normal text alone.

**1.2 Remote control authorization** (`client.py`, `__init__.py`)
- Refuse to start and to dispatch when `TELEGRAM_CHAT_ID` is empty (explicit check in `_poll_loop`, not an accident of `if not text`).
- Allow-list of voice commands for the remote channel (`REMOTE_ALLOWED`), everything else answers "needs confirmation at the PC"; power/file/delete commands never run remotely without a local confirm.
- Stop printing the command text; log the matched command id at DEBUG.
- Tests: empty chat id => no dispatch; foreign chat id => ignored; update without `message` => ignored; allowed command dispatches; forbidden command is refused and `handler.handle` is not called.

**1.3 Safe `secrets.env` writes** (`actions/mail_client.py::_update_env_var`, move to `core/secrets_store.py`)
- Atomic write (temp file + `os.replace`), exact key match (`line.split('=',1)[0].strip() == key`), reject values with `\n`, `\r`, `\0`; escape `"` and `\`; keep other lines and comments byte-for-byte.
- Optional second step: keep passwords in Windows Credential Manager (`keyring`) with a migration from `secrets.env`; decide after 1.3a with the owner (adds a dependency).
- Tests (`tests/test_secrets_store.py`): value with quote/newline cannot inject a second variable; key `JARVIS_IMAP_PASS` does not overwrite `JARVIS_IMAP_PASS_2`; crash between write and replace leaves the old file intact (monkeypatch `os.replace` to raise); round trip through `dotenv`.

**1.4 Replace `print` diagnostics with the logger** (youtube, ets2_commands, remote, dev_projects, profile)
- `_log.debug` for URLs, key presses and queries; no raw user text at INFO.
- Test: a source scan test (`tests/test_no_secret_prints.py`) failing on `print(` with `token|password|TELEGRAM|api_key` in `core actions features ui_next/bridge`.

## Phase 2. Integrity of downloads and updates

**2.1 Signed/hashed updates** (`core/system/app_updater.py`)
- Release publishes `SHA256SUMS` (+ detached signature, ed25519; the public key is embedded in the app). `_stage_update` downloads both, verifies, and only then extracts. Missing or wrong checksum => the update is dropped and logged.
- `UPDATE_DIR` relative to the app/data root (`get_app_data_root()`), not the current directory.
- Extract with a member allow-list (no absolute paths, no `..`, no reserved device names, size cap); `apply_update.bat` quotes paths and checks `robocopy` exit code (<8) before deleting the staged folder.
- Tests (`tests/test_app_updater.py`): bad hash rejected; bad signature rejected; zip with `../evil` rejected; zip bomb (size cap) rejected; tag compare (`v1.10.0` > `v1.9.9`); not frozen => `apply_and_restart` is False; half-downloaded file never becomes `ready.json`; staged version equal to the tag is not downloaded twice.
- Release checklist (docs/releasing.md): how to produce `SHA256SUMS` and the signature in `build.bat`.

**2.2 Remove the dead updater** (`core/system/updater.py`)
- Confirm with `trace_path` that nothing imports it (only `app_updater` is used), delete it and its tests.
- Test: the existing suite stays green; `tests/test_deferred_imports.py` still passes.

**2.3 Model downloads** (`core/speech/asr.py`, `core/speech/llm_downloader.py`, `actions/ets2_telemetry_installer.py`, `features/qa/model_fetcher.py`)
- One shared helper `core/download.py`: streamed download to `.part`, size check against `Content-Length`, SHA-256 against a pinned value in `data/model_hashes.json`, then `os.replace`.
- tar: `extractall(filter='data')` (Python 3.12) plus the existing path check; zip: shared safe-extract helper (also used by 2.1).
- Failures are logged and shown to the user instead of `except Exception: os.remove(...)`.
- Tests (`tests/test_download.py`): wrong hash => file removed and error surfaced; truncated stream => error; tar with a symlink to outside is refused; zip traversal refused; cancel leaves no `.part`.

## Phase 3. UI bridge and window hardening

**3.1 Bridge limits** (`ui_next/bridge/hub.py`)
- Cap simultaneous SSE clients (e.g. 8) and request rate on `/cmd`; reject extra clients with 429.
- Restrict `ui_bridge.json` to the current user (`icacls` inheritance removal) or delete it as soon as the shell has read it.
- Tests (`tests/test_ui_bridge.py` additions): ninth SSE client gets 429; wrong Host, wrong Origin, no token => 403; oversize body => 400; token compare is constant-time path (uses `hmac.compare_digest`); the info file is removed on `stop`.

**3.2 CSP and Tauri surface** (`ui_next/shell/src-tauri/tauri.conf.json`, capabilities)
- Set a strict CSP: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src http://127.0.0.1:*`.
- Drop `withGlobalTauri` if the pages can use the module API; keep capability lists minimal per window.
- Tests: a Python test parses the config and fails if `csp` is null or contains `*` / `unsafe-eval`; CDP smoke (`cdp_one.py`) loads every screen with the CSP on and reports zero console violations.

**3.3 `innerHTML` review (142 sites)**
- Inventory every `innerHTML` assignment; each either goes through `esc()` or becomes `textContent`/DOM building. Add `tests/test_ui_xss.py`: for each screen's renderer run a table of hostile strings (`<img onerror>`, `"><script>`) through the bridge fixtures with CDP and assert nothing executes and the text appears escaped.
- Static guard test: new `innerHTML +=` with a template literal containing `${` that is not wrapped in `esc(` fails the suite (allow-list for audited lines).

**3.4 Mail sanitizer** (`ui_next/bridge/mail_render.py`)
- `fragment()` (outgoing) strips `url(`, `@import`, `style` with remote resources; replace regex CSS cleaning with a small declaration parser (property allow-list).
- Tests (`tests/test_mail_render.py`): obfuscated cases (`ur\6c(`, `u&#114;l(`, comments inside `url`, `expression`, `-moz-binding`, `<svg onload>`, `<meta refresh>`, `<base>`, `javascript:` with whitespace/entities, `data:text/html` image src) never survive; remote images blocked unless asked; CSP meta present; `mailto:`/`https:` links rewritten to `data-url`.

## Phase 4. Quality gates

**4.1 CI** (`.github/workflows/ci.yml`): Windows runner, Python 3.12, `pip install -r requirements-dev.txt`, `pytest -q`, `ruff check`, `bandit -r core actions features ui_next/bridge -ll`, `pip-audit -r requirements-base.txt`. Jobs fail on new findings; a baseline file lists accepted ones with a reason.
**4.2 Tooling config**: `ruff.toml` (start with `E,F,B,S,BLE`, per-file ignores for tests), `bandit.yaml`, add the tools to `requirements-dev.txt`.
**4.3 Dependency hygiene**: upper bounds for `>=` packages, a hashed lock file (`pip-compile --generate-hashes`) for release builds, weekly `pip-audit` job.
**4.4 Tests for the gates themselves**: `tests/test_repo_hygiene.py` — no tracked secrets (`secrets.env`, `.env`, tokens by regex), no `shell=True`, no `verify=False`, no `eval/exec` outside the allow-list, `.gitattributes` present.

## Phase 5. Error handling (1089 broad `except Exception`)

Approach: observability first, narrowing second, never touching native Win32/COM blocks (rule 2).
1. Add `core/safe.py::log_exc(logger, msg)` helper and `@guarded` decorator for background threads.
2. Mechanical pass by module, highest count first: `tts.py` (49), `hud_monitoring.py` (48), `session_ghost*` (42), `weather.py` (18), `morning_briefing.py` (17). Each `except Exception: pass` becomes `except Exception: _log.debug(..., exc_info=True)`; where the failure is expected, narrow to the real exception types.
3. Ratchet test `tests/test_except_budget.py`: counts silent `except ...: pass` per directory against a stored budget file; the number may only go down.
Tests per touched module: a failure injected into the formerly silent branch is logged once and the feature degrades as before (behavior unchanged).

## Phase 6. State and concurrency

- `core/system/state.py`: keep the existing lock (rule 3); add locked accessors for the compound fields (`interactive_data`, `game_mode` + `game_profile` pair) and migrate callers gradually.
- Tests (`tests/test_state_threads.py`): N threads toggling `ignore_mode` and updating the game pair never produce a torn pair; stress run of 10k iterations.

## Phase 7. Privacy and network behavior

- Settings switch "Allow external lookups" (default on for current behavior, documented): gates `ipify.org`, `ipwho.is` and similar; one function `core/netpolicy.py::allowed(host)`.
- README/docs: list every external host the app can contact and why; offline mode really sends nothing.
- Tests: with the switch off, a monkeypatched `requests.get` is never called by weather/IP code; the host list in the docs equals the hosts found by a source scan.

## Phase 8. Launching files and processes

- Central `core/safe_open.py::open_user_file(path)`: refuses executable/script extensions (`.exe .bat .cmd .ps1 .js .vbs .lnk` from untrusted input), resolves the real path, and is the only caller of `os.startfile` for user-supplied paths (existing callers migrated one by one).
- Tests: table of extensions and `..\` / UNC / short-name (`PROGRA~1`) paths; allowed documents open through a mocked `startfile`.

## Phase 9. Structure (files over 600 lines)

Only after phases 1-4 are green. One file at a time, each as its own change with a plan shown first (rule: >600 lines => propose, no solo refactor):
`core/speech/tts.py` (2092), `ui/dialogs/settings_tabs/voice.py` (1508), `ui/dialogs/keybind_editor.py` (1078), `ui/dialogs/settings_tabs/dev.py` (894), `features/qa/llm_processor.py` (733), `actions/calendar_hub.py` (717), `ui/hud.py` (689), plus the rest of the list and `ui_next/web/app.html` (749).
Safety net per split: characterization tests written before moving code, import-compatibility shims, `detect_changes` blast radius, manual launch for UI/audio parts. `tts.py` is the riskiest (inference lock, preload order): split last, with a tracing test of the public API.
Guard test: `tests/test_file_size.py` fails above 600 lines with an allow-list that shrinks.

## Phase 10. UI rewrite leftovers (from the previous stage)

Native review of Ukrainian texts, live voice/git/cleanup flows on the real core, packaging build through `build.bat`, real 4K at 150%, second monitor, tray menu in Ukrainian. Each gets a manual checklist in `docs/ui_rewrite/` and, where possible, a CDP/Win32 script in tests.

## Order and effort

| Order | Phase | Size | Risk of breaking things |
|-------|-------|------|-------------------------|
| 1 | 0 protect the work | tiny | none |
| 2 | 1 secrets and logs | small | low |
| 3 | 2 updates and downloads | medium | medium (release process changes) |
| 4 | 4 CI and gates | small-medium | none |
| 5 | 3 bridge and window | medium | low-medium (CSP can break pages: test with CDP) |
| 6 | 7, 8 privacy, safe open | small-medium | low |
| 7 | 5, 6 errors, state | large, incremental | low if logging-only first |
| 8 | 9 file splits | large | highest, last |
| 9 | 10 leftovers | needs the owner | n/a |

## Commits (when the owner says so)

1. Existing UI rewrite/calendar/cinema work (already written), excluding `jarvis.spec`.
2. Audit fixes, one commit per phase (1, 2, 3, 4...), each with its tests.
Show the diff first, wait for approval, then suggest `/clear`.

## Definition of done for the whole plan

All phase tests green in CI; `pip-audit` and `bandit` clean or baselined with reasons; the budget tests (`except`, file size) in place; docs updated (`docs/audit_plan.md` statuses, README network section, releasing guide); manual launch of the app, the new UI, tray, mail, calendar and update dry run by hand.
