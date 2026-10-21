# Split plan for files over 600 lines

`tests/test_file_size.py` freezes the current state (no new file over 600 lines, listed files may not grow); `tests/file_size_budget.json` is the list.

Procedure for each split, one file per change:
1. Characterization tests first (public functions and their observable results), run green on the unsplit file. For text-in/text-out code a golden file of
   outputs over a corpus, compared byte for byte before and after, is enough.
2. Move code without editing it. The old module re-exports the moved names so no caller changes in the same step.
3. `detect_changes` for the blast radius, full pytest, and a manual launch for UI, audio and Win32 parts.
4. Remove the re-exports in a separate step once callers import from the new place.
5. Lower the number in `tests/file_size_budget.json` (the test insists).

## Done (2026-10-20)

| File | Before | After | New modules |
|------|--------|-------|-------------|
| `core/speech/tts.py` | 2092 | 944 (after the Rust audio move and the ONNX hook) | `tts_markup.py` (tables, transliteration, g2p, SSML tags), `tts_normalize.py` (spoken-form normalization), `tts_cache.py` (speed and night volume, wav cache housekeeping), `tts_audio.py` (pygame mixer and device selection) |
| `features/qa/llm_processor.py` | 734 | 490 | `llm_keys.py` (API keys and client cache), `llm_prompt.py` (question detection, system prompt, history trimming) |
| `actions/calendar_hub.py` | 717 | 610 | `calendar_caldav.py` (CalDAV discovery and writes; imports from the hub, nothing imports it back) |
| `ui_next/web/app.html` | 765 | 427 | `app.js` (the main script, loaded at the same place as a classic script) |

The golden check for `tts_markup` and `tts_normalize` (110 outputs, Russian and Ukrainian) was identical before and after. Moved code is verbatim; the old
module imports the moved names, so `from core.speech.tts import normalize_for_tts` and the like still work.

## Still over the limit

| File | Lines | Proposed seam |
|------|-------|---------------|
| `core/speech/tts.py` | 944 | `TTSManager` (about 480 lines, its `_worker` alone is 241) and model loading (`_get_tts`, `_ensure_model`, retry). Highest risk: `inference_lock` and preload order. Split `_worker` into named steps only after a tracing test of the public API (`speak`, `speak_async`, `warmup_tts`) |
| `actions/calendar_hub.py` | 610 | one more helper module (the DAV read cache, 520-594) would bring it under the limit |
| `core/speech/llm_chat.py` | 661 | model loading and validation / prompt formatting / generation |
| `core/handler/interactive.py` (656), `core/nlp/commands.py` (659) | | per interactive flow / the normalization step vs the matching step |
| `actions/dev_projects.py` (636), `actions/youtube.py` (614), `features/ets2/phrases_job.py` (608) | | each is within 5-10 percent of the limit; one extracted helper module is enough |

Order: `llm_chat`, `commands.py`, `interactive.py`, the four small ones; `TTSManager` last.

## Core: `handle_recognized_text` and `core/engine/recognition.py`

`core/engine/recognition.py` is 597 lines, 40 under the hard limit, and `handle_recognized_text` (288-565) is about 280 of them. Its stages, in order:

1. barge-in: stop TTS when the phrase has a wake word or arrives during an interactive question;
2. the window's feed (`bridge.heard`) and the voice-prompt consumer;
3. interactive state: hand the text to `handler.handle_interactive` and return;
4. game mode: off-phrase, wake-word strip, `cast_command` / game-input match (318-412);
5. dictation mode (413);
6. wake-word and "is this addressed to Jarvis" context filter (422-437);
7. semantic parse (`_sem_parse`) and dispatch.

Proposed seam: move stage 4 into `core/engine/recognition_game.py` as `handle_game_mode_text(text, handler) -> bool` (True when it consumed the phrase),
and keep stages 1-3 and 5-7 where they are. Moved code verbatim, `recognition.py` imports it, so `from core.engine.recognition import handle_recognized_text`
keeps working. That alone takes the file to about 500 lines.

Before moving anything: a tracing test that calls `handle_recognized_text` with a fake handler for each stage (barge-in, interactive, game off-phrase,
game command, dictation, no-wake filtered out, wake plus command) and records the handler calls. The native audio and ASR layers are not touched by this split,
but the order of the early returns is the behaviour, and no existing test pins it for game mode.

`core/engine/jarvis.py` is already split the cheap way: the TTS echo window is `core/engine/echo_guard.py` (tested), HUD mode changes go through
`host.set_mode` / `host.set_mode_if`, and repeated failures in the loop are logged with `_warn_every` instead of swallowed. What is left in `run()` is the VAD
state machine, which should stay in one place until it has a replay test (recorded RMS and VAD sequences in, speaking/flush decisions out).
