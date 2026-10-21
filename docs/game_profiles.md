# Game profiles

`data/game_profiles/<game>.json` (and `<game>_uk.json`) hold the spoken commands of a game. Loader and matcher: `actions/game_input_parts/profile.py`,
execution: `actions/game_input_parts/runtime.py`. `tests/test_game_profiles.py` checks every file.

## Spell fields

| Field | Meaning |
|-------|---------|
| `name`, `variants` | Name and spoken phrases. A phrase may appear in one spell only. |
| `key`, `keys`, `mouse`, `binding` | What to press. `binding` is looked up in the profile's `bindings`, so it must exist there. |
| `sequence` | Steps: `{"binding"/"key"/"keys", "hold"}`, `{"wait"}`. |
| `telemetry_action` | Handled in code (`core/engine/ets2_commands.py` for ETS2, `features/planetbase`, `features/fs22`). Needs no `sequence`. |
| `lights_target`, `wiper_target` | Driven from telemetry (ETS2). |
| `response` | Spoken after the action. |
| `hold_start` / `hold_end` | Hold a key until the matching `hold_end`. |
| `assign: true` | A spell the player must bind to a key. Until then, asking for it answers "не назначено на клавишу" instead of staying silent. |
| `alert_sound: "red_alert"` | Plays that alert sound when the spell is cast. |

## Conditional steps

A sequence step can carry `"when": {"engineEnabled": false}`. The step runs only if every named telemetry field has that value
(`engineEnabled`, `parkBrake`, `lightsHazards`, `lightsBeamHigh`, `lightsBeamLow`); without telemetry it runs. The ETS2 engine commands use this so that
starting the engine twice (or after the game kept it running) never toggles it off again.

## RU and UK copies

The UK file has the same commands as the RU one (same actions, same bindings); it may add phrases and use its own spelling of a name, never lose RU phrases.
When you change a RU profile, apply the same change to the UK file. Existing user copies in `%APPDATA%\Jarvis` are not rewritten, except Planetbase,
whose new spells are merged in by name.
