# JARVIS — offline voice assistant for Windows

*[Русская версия](README.ru.md)*

This is an offline voice assistant for Windows: you talk, it acts. This document is an introduction and reference — what it is, what it's actually good at, how to install and run it, and where the rough edges are.

---

## What it is

A background Windows program listening for a wake word ("Jarvis"), turning speech into one of ~280 core recognized commands, and executing the matching action — opening apps, managing windows/files/clipboard, controlling games, reading system status out loud, and more. On top of that base, game profiles and extensions add their own dedicated voice macro sets when relevant (Euro Truck Simulator 2, Farming Simulator 22, Hogwarts Legacy, Planetbase, Photoshop, Figma — each with dozens more commands of its own), so the real total in an active session is considerably higher. Speech recognition, intent matching, and speech synthesis all run on-device; nothing about a spoken command leaves the machine unless a specific feature explicitly needs the network (weather, YouTube, NASA's picture of the day, optional cloud Q&A).

## Strengths — what's actually solid here

- **Fully local by default.** ASR (Vosk/sherpa-onnx), intent classification, and TTS (Silero) need no internet connection and send nothing anywhere. Network calls only happen for features that inherently need them, and each is opt-in.
- **Layered intent recognition, not a single brittle matcher.** A phrase goes through an exact-keyword table, then a semantic classifier (sentence embeddings + centroid similarity with an explicit margin-of-confidence gate to reject ambiguous input rather than guess), then a fuzzy rule-based matcher, before finally falling back to a local LLM — each layer is cheap and only the phrases that miss the earlier ones pay for the more expensive ones.
- **Automated test coverage.** 2000+ tests (unit, integration against a real GGUF model, and interactive-state coverage), several of which were built specifically to catch real command-misrecognition bugs.
- **Deliberately cautious around irreversible actions.** Shutdown, restart, delete, cleanup, and anything else hard to undo always asks for a spoken yes/no before running — including when the request came from the fuzzier local-LLM fallback rather than the exact matcher.
- **Built for real multitasking use**, in particular gaming: a full Euro Truck Simulator 2 integration that proactively warns about fuel, fatigue, fines, and gear wear during play, without being asked.
- **Extensible without touching core code**: new voice macros, game profiles, and app integrations register through an Extension Manager rather than hardcoded branches.

## Known rough edges (read before you rely on it)

- The **local LLM fallback** (see below) is a small, CPU-only 1B model. It's the last-resort layer for phrases nothing else recognized, and it will sometimes misfire or answer awkwardly — that's expected for its size, not a bug to report. Treat it as working infrastructure with a model that can be upgraded later, not a finished feature.
- A few command-recognition edge cases are still being found and fixed as they come up in real use. If a phrase is misrecognized, that's useful to report — several real bugs this way have already been fixed and covered by regression tests.

---

## Quick start

```bash
git clone <this repository's URL>
cd Jarvis
pip install -r requirements.txt
python main.py
```

On first launch a welcome window opens where you pick how JARVIS should address you and see cards with the key features. After that, just say **"Jarvis"**.

### Dependency tiers

`requirements.txt` pulls only the base set (`requirements-base.txt`) — enough for voice control, dictation, timers, files, and system commands. Some features need extra packages and quietly disable themselves without those, without breaking anything else:

| File | What it enables |
|---|---|
| `requirements-base.txt` | ASR/TTS (Vosk, sherpa-onnx, Silero), semantic NLU, local LLM fallback (llama-cpp-python), base system commands |
| `requirements-vision-game.txt` | OpenCV — NASA picture-of-the-day video preview, camera-based guard mode |
| `requirements-web-qa.txt` | `yt-dlp` — YouTube search/download, AI answers (Groq/OpenAI/Gemini) |
| `requirements-system-optional.txt` | Wi-Fi control via the WinRT API |
| `requirements-full.txt` | Everything combined |
| `requirements-dev.txt` | + `pytest`, `pyflakes` for development |

Install `requirements-full.txt` if you want every feature available with no surprises.

---

## Talking to Jarvis (wake word)

By default Jarvis "sleeps" and doesn't react to conversations around it — that's intentional, it's not eavesdropping. Say **"Jarvis"** to wake it up.

It then stays active for a while (30 seconds by default, **adjustable via a slider** in Settings → Voice) and won't require repeating the name before every command. In the same settings you can choose:

- **Reply once per wake** — "Yes, sir" only on wake-up, then silently extends the active window without repeating itself.
- **Always reply to the name** — acknowledges every time it hears its name.

If a phrase wasn't recognized, Jarvis now **says so out loud** ("didn't catch that, repeat please") instead of staying silent, so you always know whether it heard you.

---

## Command reference — if you forget what to say

There are a lot of commands, and you don't need to memorize them. Just say at any time:

> "show all commands" / "command reference"

— and a window opens listing **every** voice command by category, with several phrasing options for each (pause works with "pause", "stop", or "halt"). The same window is reachable via the ◈ button in the UI.

---

## What Jarvis can do

**Cleanup and system**
- "Jarvis, clean up" — clears temp files, browser caches, recycle bin, frees memory.
- "Shut down in an hour", "turn off bluetooth", "turn on wifi".

**Internet and media**
- "Open youtube", "search the internet for a pizza recipe".
- "Play song X" — if YouTube returns several similar videos (music video/live/cover), Jarvis shows preview cards and lets you pick by click or voice ("the second one").
- "Show NASA's picture of the day" — astronomy photo or video of the day with description, right inside the assistant window, no browser needed.

**Games (Euro Truck Simulator 2 and others)**
- "Truck status", "cruise control to 90", "increase retarder".
- Jarvis proactively warns about fuel, driver fatigue, fines, equipment wear, trailer hitching/unhitching — unprompted, during gameplay.
- AI narrates a pre-trip briefing and a post-delivery summary (needs a Groq/OpenAI/Gemini key).

**Assistant and notes**
- "Remind me to turn off the oven in 20 minutes".
- "Dictation mode" — types what you say into any text field, with punctuation.

**Local AI fallback (offline, infrastructure in place, model quality still limited)**
- When a phrase doesn't match any known command, instead of staying silent Jarvis hands it to a small local LLM (a LoRA fine-tune of Vikhr-Llama-3.2-1B, GGUF, CPU-only — no cloud, no API cost) running through `core/speech/llm_chat.py`.
- The model either resolves the request to a real action (function-calling over the intent list, retrieved via the existing semantic embeddings — not a fixed hardcoded list) and executes it through the normal dispatch pipeline, or replies conversationally in Jarvis's persona, with the reply streamed out loud sentence-by-sentence as it's generated. It also keeps short-term context, so quick follow-ups work.
- Irreversible/disruptive actions (shutdown, restart, delete, cleanup, …) always ask for a spoken yes/no confirmation before running — a fuzzy guess from the LLM is never enough to power off the machine on its own.
- Toggle: Settings → Modules → "Local AI (fallback)"; memory-retention timeout is adjustable in Settings → Voice.
- **Honest expectation-setting**: this is a 1B-parameter model running purely on CPU as a *fallback* behind the exact matcher, the semantic classifier, and the fuzzy rule-based matcher — it only ever sees the phrases none of those recognized. It will occasionally misfire or reply awkwardly, and it is not meant to replace those primary paths or match cloud-model reliability. What's solid is the *infrastructure* around it — grammar-constrained function-calling, retrieval-based candidate narrowing, conversation context, streaming playback, destructive-action confirmation — all of which stays valid and keeps improving independently of which model sits behind it. Swapping in a better/larger fine-tune later needs no code changes.

**Other**
- Voice macros for applications (Photoshop, Figma, and more via the Extension Manager).
- PC resource monitoring, window management, clipboard, mail.

---

## Where to find settings

The ⚙️ gear button in the UI, or say "open settings".

- **Voice tab** — mic sensitivity, gain, wake-word mode and "sleep" timer, one-click calibration, local-AI memory-retention timeout.
- **Interface tab** — themes, transparency, scale.
- **Extension Manager** — game profiles and extra skills, installed as needed.
- **Modules tab** — per-feature toggles, including the local AI fallback described above.

---

## Building a standalone `.exe`

Everything is built via PyInstaller using the `jarvis.spec` file, wrapped by `build.bat`.

```bash
pip install -r requirements-full.txt   # so the build includes every optional feature
pip install pyinstaller
build.bat
```

The script:
1. Runs PyInstaller against `jarvis.spec` (can take a few minutes — Silero TTS pulls in PyTorch).
2. Copies `assets/`, `audio/`, `models/`, `config_pack/` next to `Jarvis.exe`.
3. Copies static data (game profiles, extension catalog, the semantic NLU ONNX model, embedding cache) into `dist\Jarvis\data\` — but **not** your personal `jarvis_settings.json`, `.env`/`secrets.env`, or logs, so API keys or history never leak by accident.

The result is a `dist\Jarvis\` folder with `Jarvis.exe` and everything it needs; copy it to another machine as-is (Windows 10/11 x64).

For an installer instead of a plain folder, use `build_installer.bat` (builds via `jarvis_installer.iss`, Inno Setup).

**What's intentionally NOT copied**: personal settings, command history, saved API keys, debug logs — these get created fresh on first run on a new machine.

---

## Why this exists

1. **Multitasking** — no need to hunt for a folder or setting by hand, especially while driving in a game.
2. **Speed** — things like clearing memory or checking the weather happen by voice in a second.
3. **Privacy** — speech recognition and command logic run locally; only explicitly network-bound requests (weather, YouTube, NASA, AI) reach the internet, and only if you use them.

If something isn't working right, open Settings → Voice → "TEST AND CALIBRATE" — that fixes 90% of recognition issues.

---

## License

Provided "as is", with no warranty of any kind — see [`EULA.txt`](EULA.txt) for details. A non-commercial, free pet project.
