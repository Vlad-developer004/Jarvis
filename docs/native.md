# Native (Rust) parts

File search, the window list, volume control, speech and sound playback, the microphone and the output-device check run in Rust.
There is no Python fallback: a missing or broken part fails where it is used (`core.native.NativeUnavailable`), while the rest of the
app keeps running. `build.bat` stops if the native parts cannot be built.

| Part | Kind | Used by |
|---|---|---|
| `native/jarvis_files` | PyO3 module | `actions/file_walk.py` -> `actions/recent.py`, `actions/filesystem.py` (file and folder search) |
| `native/jarvis_win` | PyO3 module | `actions/win_list.py` -> `actions/youtube.py`, `actions/system_parts/media.py` (window picking) |
| `native/jarvis_audio` | program (sidecar) | `core/native_audio.py` -> TTS and sounds, microphone, volume and ducking, output-device check |

Modules are imported on first use (`core/native.py`), never at the top of `main.py`, so the crash-sensitive startup order is unchanged.
The program is found next to the app (`native/` or `_internal/native/`), or in `native/target/release/` in a source checkout.

## Build

Needs Rust (`cargo`) and `maturin` (`pip install -r requirements-dev.txt`). `build.bat` does all of it:

```
cd native
cargo build --release -p jarvis_audio                                    :: native/target/release/jarvis_audio.exe
python -m maturin build --release -m jarvis_files/Cargo.toml --out dist  :: wheels in native/dist
python -m maturin build --release -m jarvis_win/Cargo.toml --out dist
pip install --force-reinstall --no-deps dist/*.whl
```

`jarvis.spec` bundles `jarvis_audio.exe` (the build stops without it) and lists the two modules as hidden imports. Editing anything in
`ui_next/web/` still needs the window rebuilt separately; the native parts are independent of it.

## jarvis_files

`walk(roots, max_depth, want="files"|"dirs", exts, skip_exts, skip_dirs, skip_hidden)` lists files or folders in parallel and returns
`(parent_dir, name, mtime)` sorted by path. Name matching (variants, transliteration, `rapidfuzz`) stays in Python. Measured
(`python tools/bench_native.py`, p50): the scan folders (about 230 files) 12 ms with Python's `os.walk` -> 5 ms, the desktop tree 12 ms
-> 6 ms, a tree of 98 000 files 1900 ms -> 150-225 ms. `tests/native/test_files_parity.py` checks it against an independent `os.walk`
reference in the test.

## jarvis_win

`list_windows(visible_only=False)` returns every top-level window in z-order as `(hwnd, title, exe, visible, iconic, class_name)`;
`exe` is the lower-case file name of the owning process ("" when it cannot be read). On the development machine (155 windows) it matches
the pywin32 listing exactly and reads the process of 154 windows (pywin32 asked for too many rights and managed 142); 6.6 ms -> 1.1 ms.

## jarvis_audio

One program, several modes:

| Mode | Does |
|---|---|
| `--version` | prints the version |
| `--query-output` | the default playback device: `{"name", "kind", "is_headphones", ...}`, from the Windows endpoint form factor, not from its name |
| `--list-devices` | input and output devices by name, the defaults marked |
| `--capture --rate R --chunk N [--device NAME]` | the microphone as mono 16-bit PCM in chunks of N samples on stdout (see below) |
| `--serve` | a service: volume control and playback, one JSON request per line on stdin, one answer per line on stdout |
| `--selftest-playback`, `--analyse-loopback MS` | record the output device (WASAPI loopback) and report dropouts, glitches and pitch of a test tone |

### Playback and volume (`--serve`)

An optional `"id"` in a request is echoed back. COM lives only in this program, so a Core Audio fault cannot take Jarvis down, and
when stdin closes (Jarvis exited or crashed) it gives back every volume it had lowered.

| `op` | Arguments | Does |
|---|---|---|
| `ping` | | `{"ok", "version"}` |
| `play` | `path`, `volume` (0..4), `channel` | decodes a WAV/MP3/Ogg file and queues it; answers its length in `seconds` |
| `play_pcm` | `data` (base64 16-bit PCM), `rate`, `channels`, `volume`, `channel` | the same for synthesised sound |
| `stop` | `channel` (`tts`, `sfx`, `all`) | cuts playback; answers once it took effect |
| `player_status` | | `busy`, `queued`, `remaining`, `ready`, `device`, `rebuilds`, `error` |
| `sessions` / `duck` / `unduck` | `enable`, `skip_pid` | audio sessions; lower other apps to 45% while Jarvis speaks (nested calls counted, the program's own voice is never lowered); give them back |
| `set_app` / `set_session` | `name` or `session`, `level` | volume of one program or session |
| `master_get` / `master_set` | `level`, `muted` | the default device's volume and mute |

Channel `tts` is one queue whose clips play back to back without a gap (the speech); `sfx` clips mix over whatever plays (UI sounds,
the "Да, сэр" replies). The output stream follows the Windows default device and is re-opened when it fails or the default changes
(headphones unplugged), keeping the queue; with no device at all, requests are dropped rather than played minutes later. The buffer is
40 ms; `JARVIS_AUDIO_BUFFER_MS` changes it. Python side: `core/native_audio.py` (`play`, `play_pcm`, `stop`, `is_busy`, `wait_idle`),
used by `core/speech/tts.py` (worker, `stop`, `is_speaking`), `core/speech/sound.py`, `core/responder.py` and `actions/volume.py`.

### Microphone (`--capture`)

The device is opened at its own rate, mixed down to mono and converted to the requested rate with a windowed-sinc resampler
(no aliasing: a 12 kHz tone does not appear at 4 kHz), then cut into chunks. stdout carries frames: a type byte (1 = PCM, 2 = JSON
event), a 4-byte little-endian length, the payload. Events: `started` (device name), `error`, `dropped`, `reopening`. A device that
fails, or the default input changing while none is named, makes the program re-open it by itself; a name that matches nothing falls
back to the default. `MicStream` in `core/native_audio.py` gives the engine the two calls it used on a PyAudio stream, `read()` and
`close()`; `read()` raises `OSError` when nothing arrives for 2 s, which the engine treats as a lost device and re-opens.
`core/audio_utils.py`: `open_input`, `open_input_resilient`.

The microphone is saved by name (`audio_input_device_name`). The old `audio_input_device_index` (a PortAudio index) is migrated once by
`core/audio_migrate.py` where PyAudio is still installed, otherwise dropped and the Windows default input is used. The calibration no
longer sweeps sample rates (that depended on the driver's converter); it uses the configured rate.

## How the audio was checked

Nobody has to listen. A second program records the output device and analyses the test tone with a lock-in filter at its pitch, so
other sounds on the machine hardly matter: length, dropouts (the tone getting quiet), glitches (phase jumps from skipped samples) and
pitch.

- Old path (pygame/SDL, buffer 4096) and the Rust player, a 1.2 s tone at 24 kHz played to a 48 kHz device, 8 runs each, with 0, 8 and
  24 busy processes on 8 logical CPUs: no defective run for either (`pygame` 0/8, Rust 40 ms 0/8, Rust 85 ms 0/8 in each case).
- Rust player in `tests/native/test_audio_playback_e2e.py` (opt-in, `JARVIS_AUDIO_TESTS=1`, makes quiet test tones): a clip arrives whole
  at 440 Hz, three queued clips make one unbroken 3 s tone, `stop` cuts speech short, an effect mixes over speech, the shipped MP3
  effects play.
- Microphone, same device read at the same time by PyAudio and by `--capture`: equal level (RMS 11.2 against 11.1) and a waveform
  correlation of 0.998 (`tests/native/test_mic_capture_live.py` checks chunk size, pace and level on the real microphone).

Reading the microphone through PyAudio never lost samples either (PortAudio buffers them); under heavy load the delay came from the
Python code consuming the audio, which this change does not touch.

## Rules

- Anything that touches COM or an audio device runs in `jarvis_audio.exe`, not inside the Python process.
- A native part ships with a test of its own (Rust unit tests, `tests/native/`, mocks for the Python clients) and, where it can be
  measured, a number from `tools/bench_native.py`.
- CI (`native` job) runs `cargo clippy -D warnings`, `cargo test`, builds everything and runs the parity tests.
