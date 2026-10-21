import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata
ROOT = os.path.dirname(os.path.abspath(SPEC))
def gather(pkg):
    d, b, h = collect_all(pkg)
    return d, b, h
sher_d, sher_b, sher_h = gather("sherpa_onnx")
pil_d,  pil_b,  pil_h  = gather("PIL")
wsdk_d, wsdk_b, wsdk_h = gather("winsdk")
# llama_cpp's compiled runtime (ggml/llama/mtmd .dll) lives in its own lib/
# subfolder, loaded via os.add_dll_directory() at import time (see
# llama_cpp/_ctypes_extensions.py) — there's no bundled PyInstaller hook for
# it, so without this explicit collect_all() the whole lib/ folder is simply
# missing from a frozen build. import llama_cpp then fails at
# add_dll_directory() with WinError 3 (path not found) — llm_chat.py's
# warmup catches that (never fatal to startup), but the local LLM fallback
# is then permanently broken with no way to recover: unlike a missing
# model.gguf (core/speech/llm_downloader.py), this is a missing DLL, not
# something re-downloading the model fixes.
llama_d, llama_b, llama_h = gather("llama_cpp")
try:
    tt_d, tt_b, tt_h = gather("truck_telemetry")
except Exception:
    tt_d, tt_b, tt_h = [], [], []

anth_d, anth_b, anth_h = gather("anthropic")
oa_d,   oa_b,   oa_h   = gather("openai")
def _walk_datas(src_dir: str, dst_dir: str, exts: tuple[str, ...] | None = None) -> list[tuple[str, str]]:
    # PyInstaller's `datas` tuple is (source_file, DEST_DIRECTORY): the file
    # is placed inside DEST_DIRECTORY under its own basename. Passing the
    # full destination *file* path here (including the filename) makes
    # PyInstaller create a directory with that name and nest the file one
    # level deeper (e.g. data/locales/ru.json ends up being a directory
    # containing data/locales/ru.json/ru.json) — every __file__-relative
    # open() of these paths then fails with PermissionError. The dest must
    # be the *directory* portion only.
    out: list[tuple[str, str]] = []
    if not os.path.isdir(src_dir):
        return out
    for base, _dirs, files in os.walk(src_dir):
        for fn in files:
            if fn.startswith('.'):
                continue
            if exts and (not fn.lower().endswith(exts)):
                continue
            full = os.path.join(base, fn)
            rel_dir = os.path.relpath(base, src_dir)
            dest_subdir = dst_dir if rel_dir == '.' else os.path.join(dst_dir, rel_dir)
            out.append((full, dest_subdir))
    return out
def _project_datas() -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []
    datas += _walk_datas(os.path.join(ROOT, "assets"), "assets", exts=(".ico", ".png", ".jpg", ".jpeg", ".webp", ".gif"))
    datas += _walk_datas(os.path.join(ROOT, "audio"), "audio", exts=(".wav", ".mp3", ".ogg"))
    gp_dir = os.path.join(ROOT, "data", "game_profiles")
    datas += _walk_datas(gp_dir, os.path.join("data", "game_profiles"), exts=(".json",))
    # core/i18n.py resolves this dir via Path(__file__).parent.parent, not
    # config_pack.config.get_data_dir() — so it must be bundled here (lands
    # next to the frozen core/i18n.py inside the PyInstaller archive), not
    # copied next to Jarvis.exe by build.bat like the config_pack.config-based
    # data files below. Missing this silently ships a build with no RU/UK
    # strings at all (i18n.tr() would just echo raw keys).
    locales_dir = os.path.join(ROOT, "data", "locales")
    datas += _walk_datas(locales_dir, os.path.join("data", "locales"), exts=(".json",))
    # Same __file__-relative pattern in features/planetbase/installer.py —
    # this is the compiled mod payload (PBPatcher.exe, telemetry DLL) it
    # deploys into the game, not the mod's C# source (that's in mods/,
    # dev-only, never needed at runtime).
    integrations_dir = os.path.join(ROOT, "data", "integrations")
    datas += _walk_datas(integrations_dir, os.path.join("data", "integrations"))
    safe_files = [
        os.path.join(ROOT, "data", "extensions_catalog.json"),
        os.path.join(ROOT, "data", "jarvis_settings.example.json"),
        os.path.join(ROOT, "data", "update_pubkey.txt"),
        os.path.join(ROOT, "data", "model_hashes.json"),
        os.path.join(ROOT, "data", "optional_packages.json"),
    ]
    for p in safe_files:
        if os.path.exists(p):
            datas.append((p, "data"))
    return datas
def _filter_datas(datas_list):
    # Strictly exclude any personal or session data
    forbidden = {
        'jarvis_settings.json', 'sessions.json', 'exe_cache.json',
        'game_cache.json', 'mic_profile.json', 'disabled_keyboards.json',
        'update_ready.json', 'extensions_installed.json', 'game_mode_prefs.json',
        'last_voice.json', 'last_input.json', 'user_data.json', 'history.json',
        'tokens.json', 'cache.json', 'qa.log', 'main.log', 'debug.log'
    }
    filtered = []
    for src, dst in datas_list:
        # Normalize separators for consistent matching. dst is a DEST
        # DIRECTORY (see _walk_datas), so a trailing slash is added before
        # prefix checks below — otherwise a file living right at
        # "data/locales" (dst == "data/locales", no trailing slash) would
        # fail `startswith('data/locales/')` and get silently dropped.
        d_norm = dst.replace('\\', '/')
        d_norm_slash = d_norm + '/'
        name = os.path.basename(src)
        if name in forbidden or name == '.env' or name == 'secrets.env' or name.endswith('.log'):
            continue
        
        # If it's in data/ but not in one of these known-safe/needed groups,
        # skip it — this protects personal/session data that might land in
        # data/ in the future. Keep this allowlist in sync with
        # _project_datas() above whenever a new __file__-relative data dir
        # is added there.
        if d_norm.startswith('data/'):
            is_gp = d_norm_slash.startswith('data/game_profiles/')
            is_locales = d_norm_slash.startswith('data/locales/')
            is_integrations = d_norm_slash.startswith('data/integrations/')
            is_safe = name in ['extensions_catalog.json', 'jarvis_settings.example.json', 'update_pubkey.txt', 'model_hashes.json', 'optional_packages.json']
            if not (is_gp or is_locales or is_integrations or is_safe):
                continue
        
        filtered.append((src, dst))
    return filtered

datas = _filter_datas(
    sher_d + pil_d + wsdk_d + tt_d
    + anth_d + oa_d + llama_d
    + _project_datas()
    + collect_data_files("num2words")
    + collect_data_files("wikipedia")
)
# The Russian ONNX voice (core/speech/tts_onnx.py): silero_onnx goes next to the program as plain source files, not into the archive, because it is
# imported through a loader that lifts the package's "torch must not be loaded" asserts, and compiled code would still carry them.
try:
    datas = datas + collect_data_files("silero_onnx", include_py_files=True)
except Exception:
    pass
ICON_PATH = os.path.join(ROOT, "assets", "icon.ico")
# The window is a separate program (ui_next/shell, built by build.bat with cargo) that the core starts; its pages are inside it.
SHELL_EXE = os.path.join(ROOT, "ui_next", "shell", "src-tauri", "target", "release", "jarvis-ui.exe")
if not os.path.isfile(SHELL_EXE):
    raise SystemExit("jarvis-ui.exe is missing: build the window first (cd ui_next/shell/src-tauri && cargo build --release), or run build.bat")
datas = datas + copy_metadata("cmudict") + collect_data_files("cmudict")      # cmudict asks importlib.metadata for its version and reads its dictionary file; without them Latin words in speech fall back to letter-by-letter
datas = datas + [(SHELL_EXE, "shell")]
# The native audio program (native/jarvis_audio, see docs/native.md) is required: speech, the microphone and volume run through it.
_AUDIO_EXE = os.path.join(ROOT, "native", "target", "release", "jarvis_audio.exe")
if not os.path.isfile(_AUDIO_EXE):
    raise SystemExit("jarvis_audio.exe is missing: build it (cd native && cargo build --release -p jarvis_audio), or run build.bat")
datas = datas + [(_AUDIO_EXE, "native")]
binaries = sher_b + pil_b + wsdk_b + tt_b + anth_b + oa_b + llama_b
hiddenimports = (
    sher_h + pil_h + wsdk_h + tt_h + llama_h + [
        "core.speech.asr", "core.audio_utils", "core.nlp.commands", "core.extensions",
        "core.handler", "core.mic_calibration", "core.responder", "core.system.state",
        "core.speech.tts", "core.system.windows",
        "actions.app_launcher", "actions.bluetooth", "actions.clipboard",
        "actions.command_vault", "actions.currency", "actions.dictation",
        "actions.explorer", "actions.filesystem", "actions.game_audio",
        "actions.game_input", "actions.git_commit",
        "actions.notes", "actions.ocr", "actions.recent", "actions.screenshot",
        "actions.sensor_bridge", "actions.session_ghost",
        "actions.system", "actions.system_control", "actions.volume",
        "actions.weather", "actions.weather_codes", "actions.weather_geo", "actions.weather_forecast", "actions.weather_extra", "actions.weather_cache", "core.nlp.weather_route", "actions.windows", "actions.youtube",
        "actions.ets2_telemetry", "actions.ets2_telemetry_installer",
        "actions.briefing_config", "actions.calendar_ics", "actions.inbox_imap",
        "actions.mail_client", "actions.meetings", "actions.programming_extensions",
        "actions.dev_projects", "actions.game_timer", "actions.nasa",
        "actions.keysend", "actions.keysend_parts.keymap",
        "actions.system_parts.push_to_talk",
        "core.system.app_updater", "core.address", "core.responses",
        "core.engine.ets2_commands", "core.handler.yt_play",
        "core.handler.commands.reactor",
        "core.nlp.commands_data", "core.nlp.intents", "core.nlp.semantic",
        "core.nlp.semantic_encoder",
        "core.speech.asr_manager", "core.speech.sound",
        "features.ets2.llm", "features.ets2.monitor_state",
        "features.ets2.monitor_checks_progress", "features.ets2.monitor_checks_safety",
        "features.ets2.monitor_checks_speed",
        "features.ets2.phrases_common", "features.ets2.phrases_driving",
        "features.ets2.phrases_job", "features.ets2.phrases_warnings",
        "features.planetbase", "features.planetbase.installer",
        "features.planetbase.monitor", "features.planetbase.telemetry",
        "features.planetbase.commands", "features.planetbase.extras",
        "features.planetbase.advisor", "features.planetbase.autopilot",
        "features.planetbase.autosave", "features.planetbase.history",
        "features.planetbase.journal", "features.planetbase.knowledge",
        "features.planetbase.planet", "core.speech.pacing",
        "features.remote_control", "features.remote_control.client",
        "features.qa.model_fetcher",
        "truck_telemetry",
        "truck_telemetry.truck_telemetry",
        "truck_telemetry.telemetry_version",
        "truck_telemetry.telemetry_version.v1_10",
        "truck_telemetry.telemetry_version.v1_12",
        "truck_telemetry.telemetry_version.unpack",
        "features.battery", "features.cinema", "features.gaming",
        "features.guard", "features.lag_hunter", "features.morning_briefing",
        "features.calendar_reminders",
        "features.qa", "features.ets2.monitor",
        "sherpa_onnx", "srt",   # srt: pure-Python dependency of the vosk package, which is downloaded on first use
        # standard-library modules that only the downloaded packages (core/optional_pkgs.py) import: nothing in Jarvis itself pulls them into the installer
        "email.mime", "email.mime.base", "email.mime.multipart", "email.mime.nonmultipart", "email.mime.text", "email.mime.application",
        "email.mime.audio", "email.mime.image",
        "jarvis_files", "jarvis_win",   # native modules, imported by name at run time
        "sounddevice",
        "numpy",
        "psutil", "wmi", "comtypes", "comtypes.client",
        "win32api", "win32con", "win32gui", "win32process",
        "win32clipboard", "win32com", "win32com.client",
        "pythoncom", "pywintypes",
        "pygetwindow", "pyperclip", "pyautogui",
        "pydirectinput",
        "requests", "urllib3",
        "rapidfuzz",
        "yt_dlp",
        "screen_brightness_control",
        "speedtest", "winsdk",
        "num2words",
        "dotenv", "winsound", "pyperclip",
        "importlib_resources", "importlib.resources",
        "webbrowser", "socket", "threading", "queue",
        "groq", "httpx", "anyio", "httpcore", "h11", "sniffio",
        "anthropic", "openai",
    ]
)
hiddenimports += collect_submodules("ui_next", filter=lambda name: "devtools" not in name)   # the bridge modules are imported on demand
# Libraries shared with the downloaded packages (core/optional_pkgs.py): the bundled copy wins at import time, so it must be whole (the installer's own code
# would otherwise pull in only the submodules it happens to use, e.g. tqdm without tqdm.auto).
for _pkg in ("tqdm", "colorama", "idna", "charset_normalizer", "requests", "urllib3", "cryptography", "cffi", "pycparser", "pydantic"):
    hiddenimports += collect_submodules(_pkg)
a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(ROOT, "runtime_hooks")],
    hooksconfig={},
    runtime_hooks=[os.path.join(ROOT, "runtime_hooks", "rthook_jaraco.py")],
    excludes=[
        "matplotlib", "notebook", "IPython", "pytest", "setuptools",
        "torch", "torchaudio", "torchvision", "sentence_transformers",   # no PyTorch in the build
        "tensorflow", "tensorflow_core", "tensorboard", "keras",
        "llvmlite", "numba",
        "silero_onnx",      # shipped as source in datas above
        # ML stacks of the dev environment that no Jarvis module imports (the build must not depend on what happens to be installed)
        "transformers", "sklearn", "pandas", "pyarrow", "datasets", "huggingface_hub", "hf_xet", "av", "librosa", "openwakeword",
        "google", "googleapiclient", "grpc", "selenium", "cv2", "vosk", "scipy",   # downloaded on first use (core/optional_pkgs.py) or not shipped
        "sentencepiece",   # nothing imports it; PyInstaller's isolated import of it dies with 0xC0000005 during analysis
        "g2p_en", "nltk",   # no Jarvis module imports them (cmudict is read directly); they would bring ~13 MB of nltk_data
        "tkinter", "_tkinter",   # the old Tk interface is gone; pyautogui/pymsgbox only use it for message boxes, which Jarvis never opens
        "faster_whisper", "setfit", "peft", "optimum", "accelerate", "evaluate", "ultralytics", "deepface", "retinaface", "seaborn",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_PATH,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Jarvis",
)
