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
            rel = os.path.relpath(full, src_dir)
            out.append((full, os.path.join(dst_dir, rel)))
    return out
def _project_datas() -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []
    datas += _walk_datas(os.path.join(ROOT, "assets"), "assets", exts=(".ico", ".png", ".jpg", ".jpeg", ".webp", ".gif"))
    datas += _walk_datas(os.path.join(ROOT, "audio"), "audio", exts=(".wav", ".mp3", ".ogg"))
    gp_dir = os.path.join(ROOT, "data", "game_profiles")
    datas += _walk_datas(gp_dir, os.path.join("data", "game_profiles"), exts=(".json",))
    safe_files = [
        os.path.join(ROOT, "data", "extensions_catalog.json"),
        os.path.join(ROOT, "data", "jarvis_settings.example.json"),
    ]
    for p in safe_files:
        if os.path.exists(p):
            datas.append((p, os.path.join("data", os.path.basename(p))))
    return datas
datas = (
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
        "actions.game_input", "actions.git_commit", "actions.mouse",
        "actions.notes", "actions.ocr", "actions.recent", "actions.screenshot",
        "actions.sensor_bridge", "actions.session_ghost",
        "actions.system", "actions.system_control", "actions.volume",
        "actions.weather", "actions.windows", "actions.youtube",
        "actions.ets2_telemetry", "actions.ets2_telemetry_installer",
        "actions.briefing_config", "actions.calendar_ics", "actions.inbox_imap",
        "actions.mail_client",
        "core.system.updater",
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
        "ui.dialogs.settings_dlg", "ui.dialogs.mail_dlg", "ui.dialogs.name_dlg",
        "ui.dialogs.file_type_dlg", "ui.dialogs.manage_dlg", "ui.dialogs.welcome_dlg",
        "ui.dialogs.extensions", "ui.dialogs.editors", "ui.dialogs.commit_dlg",
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
        "dotenv", "winsound",
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
