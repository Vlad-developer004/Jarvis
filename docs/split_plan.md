# Split plan for files over 600 lines

Nothing here is done yet: the project rule is to propose a plan and wait for approval before splitting. `tests/test_file_size.py` freezes the
current state (no new file over 600 lines, listed files may not grow); `tests/file_size_budget.json` is the list.

Procedure for each split, one file per change:
1. Characterization tests first (public functions and their observable results), run green on the unsplit file.
2. Move code without editing it. The old module re-exports the moved names so no caller changes in the same step.
3. `detect_changes` for the blast radius, full pytest, and a manual launch for UI, audio and Win32 parts.
4. Remove the re-exports in a separate step once callers import from the new place.
5. Lower the number in `tests/file_size_budget.json` (the test insists).

## core/speech/tts.py (2092 lines): split in this order, riskiest last

| New module | Content (current line ranges) | Risk |
|------------|-------------------------------|------|
| `tts_normalize.py` | text normalization: `_expand_*`, `_inflect_last`, `_ordinal_case`, `_fix_number_noun_agreement`, `normalize_for_tts`, `_apply_address_form`, `_apply_stress`, `_transliterate_word` (about 1459-1975) | low: pure text functions, already covered by tests |
| `tts_markup.py` | SSML/markup helpers: `_protect_ssml_tags`, `_restore_ssml_tags`, `strip_speech_markup`, `_reverse_translit_cyrillic`, `_g2p_word`, cmudict (111-259) | low |
| `tts_cache.py` | wav cache: `_evict_wav_cache`, `_schedule_cache_eviction`, `_generate_cached`, `_save_wav_native_speed`, `_apply_wav_speed`, speed and night-volume settings (261-430, 1189-1254) | medium |
| `tts_audio.py` | mixer and devices: `ensure_mixer_init`, `apply_audio_devices`, `_resolve_sdl_device_name`, `_get_audio_device_name`, `wait_for_pygame_mixer_idle`, `_recover_mixer_if_dead` (1255-1468, 581) | high: SDL/pygame init order, keep import-time order unchanged |
| `tts.py` (rest) | `TTSManager` (587-1070, its `_worker` alone is 241 lines), model loading (`_get_tts`, `_ensure_model`), public API (`speak`, `speak_async`, `warmup_tts`) | highest: `inference_lock`, preload order; split `_worker` into named steps only after a tracing test of the public API |

## UI files that are one giant function

`ui/dialogs/settings_tabs/voice.py` (`build_voice_tab`, 1499 lines), `ui/dialogs/keybind_editor.py` (`open_keybind_editor`, 1064),
`ui/dialogs/settings_tabs/dev.py` (`build_dev_tab`, 884) are old CustomTkinter code with deep closures over local widgets. Splitting them means
rewriting the closures, which tests do not cover and which the new window (`ui_next`) replaces. Recommendation: do not split; freeze them in the
size budget and retire them with the old UI. `premium_view.py`, `appearance.py`, `hud*.py` follow the same reasoning.

## The 600-750 line group

| File | Proposed seam |
|------|---------------|
| `actions/calendar_hub.py` (717) | sources and storage (`Source`, load/save, passwords) / event model and occurrences / sync with CalDAV and ICS / the voice-facing entry points |
| `features/qa/llm_processor.py` (734) | provider clients / prompt building / usage and limits (the new `ai_router.py` already took routing) |
| `core/speech/llm_chat.py` (661) | model loading and validation / prompt formatting / generation |
| `core/handler/interactive.py` (666), `core/nlp/commands.py` (659) | per interactive flow / the normalization step vs the matching step |
| `actions/dev_projects.py` (636), `actions/youtube.py` (614), `core/engine/ets2_commands.py` (614), `features/ets2/phrases_job.py` (608) | outline when its turn comes; each is within 5-10 percent of the limit, so one extracted helper module is enough |
| `ui_next/web/app.html` (749) | move the inline scripts (layout, weather, sensors) to `layout.js`, `weather.js`; the page keeps markup and styles |

Order: `tts_normalize`, `tts_markup`, `app.html` scripts, `calendar_hub`, `llm_processor`, then the rest; `tts_audio` and `TTSManager` last.
