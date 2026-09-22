import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs
ROOT = os.path.dirname(os.path.abspath(SPEC))
def gather(pkg):
    d, b, h = collect_all(pkg)
    return d, b, h
ctk_d,  ctk_b,  ctk_h  = gather("customtkinter")
sher_d, sher_b, sher_h = gather("sherpa_onnx")
pgm_d,  pgm_b,  pgm_h  = gather("pygame")
cv2_d,  cv2_b,  cv2_h  = gather("cv2")
pil_d,  pil_b,  pil_h  = gather("PIL")
vosk_d, vosk_b, vosk_h = gather("vosk")
wsdk_d, wsdk_b, wsdk_h = gather("winsdk")
try:
    tt_d, tt_b, tt_h = gather("truck_telemetry")
except Exception:
    tt_d, tt_b, tt_h = [], [], []

anth_d, anth_b, anth_h = gather("anthropic")
oa_d,   oa_b,   oa_h   = gather("openai")
gen_d,  gen_b,  gen_h  = gather("google.generativeai")
sel_d,  sel_b,  sel_h  = gather("selenium")
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
            is_safe = name in ['extensions_catalog.json', 'jarvis_settings.example.json']
            if not (is_gp or is_locales or is_integrations or is_safe):
                continue
        
        filtered.append((src, dst))
    return filtered

datas = _filter_datas(
    ctk_d + sher_d + pgm_d + cv2_d + pil_d + vosk_d + wsdk_d + tt_d
    + anth_d + oa_d + gen_d + sel_d
    + _project_datas()
    + collect_data_files("num2words")
    + collect_data_files("wikipedia")
)
ICON_PATH = os.path.join(ROOT, "assets", "icon.ico")
binaries = ctk_b + sher_b + pgm_b + cv2_b + pil_b + vosk_b + wsdk_b + tt_b + anth_b + oa_b + gen_b + sel_b
hiddenimports = (
    ctk_h + sher_h + pgm_h + cv2_h + pil_h + vosk_h + wsdk_h + tt_h + [
        "customtkinter",
        "tkinter", "tkinter.ttk", "tkinter.font",
        "PIL._tkinter_finder",
        "ui.hud_constants", "ui.hud_state", "ui.hud_utils", "ui.hud_widgets", "ui.hud_commands", "ui.splash",
        "ui.hud_layout", "ui.hud_monitoring", "ui.hud_renderer", "ui.hud_window", "ui.hud_camera", "ui.hud_weather",
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
        "actions.weather", "actions.windows", "actions.youtube",
        "actions.ets2_telemetry", "actions.ets2_telemetry_installer",
        "actions.briefing_config", "actions.calendar_ics", "actions.inbox_imap",
        "actions.mail_client", "actions.meetings", "actions.programming_extensions",
        "actions.dev_projects", "actions.game_timer", "actions.nasa",
        "actions.keysend", "actions.keysend_parts.keymap",
        "actions.system_parts.push_to_talk",
        "core.system.updater", "core.address", "core.responses",
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
        "features.remote_control", "features.remote_control.client",
        "features.qa.model_fetcher",
        "ui.dialogs.extensions_common", "ui.dialogs.extensions_setup",
        "ui.dialogs.keybind_editor", "ui.dialogs.mail_client_dlg",
        "ui.dialogs.mail_compose_dlg", "ui.dialogs.mail_shared",
        "ui.dialogs.settings_tabs.tools_remote", "ui.dialogs.spell_editor",
        "ui.dialogs.yt_picker_dlg", "ui.dialogs.deck",
        "ui.hud_ai_window", "ui.hud_reactor_fx", "ui.hud_timer_widget",
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
        "ui.dialogs.settings_dlg", "ui.dialogs.name_dlg",
        "ui.dialogs.file_type_dlg", "ui.dialogs.manage_dlg", "ui.dialogs.welcome_dlg",
        "ui.dialogs.extensions", "ui.dialogs.commit_dlg",
        "ui.dialogs.settings_tabs.appearance",
        "ui.dialogs.settings_tabs.voice",
        "ui.dialogs.settings_tabs.modules",
        "ui.dialogs.settings_tabs.modules.premium_view",
        "ui.dialogs.settings_tabs.modules.base",
        "ui.dialogs.settings_tabs.modules.constants",
        "ui.dialogs.settings_tabs.dev",
        "ui.dialogs.settings_tabs.tools",
        "sherpa_onnx", "vosk",
        "pyaudio", "sounddevice",
        "numpy",
        "psutil", "wmi", "comtypes", "comtypes.client",
        "win32api", "win32con", "win32gui", "win32process",
        "win32clipboard", "win32com", "win32com.client",
        "pythoncom", "pywintypes",
        "pygetwindow", "pyperclip", "pyautogui",
        "pydirectinput", "pycaw", "pycaw.pycaw",
        "requests", "urllib3",
        "pygame", "pygame.mixer",
        "cv2",
        "rapidfuzz",
        "yt_dlp",
        "screen_brightness_control",
        "speedtest", "winsdk",
        "num2words", "g2p_en",
        "dotenv", "winsound", "pyperclip",
        "pystray", "pystray._win32",
        "importlib_resources", "importlib.resources",
        "webbrowser", "socket", "threading", "queue",
        "groq", "httpx", "anyio", "httpcore", "h11", "sniffio",
        "anthropic", "openai", "google.generativeai", "selenium",
    ]
)
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
        "torchaudio", "torchvision",
        "tensorflow", "tensorflow_core", "tensorboard", "keras",
        "llvmlite", "numba",
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
