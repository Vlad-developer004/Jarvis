import os
import json
from dotenv import load_dotenv

def get_project_root() -> str:
    import sys
    import os
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_app_data_root() -> str:
    import os
    base = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
    if base:
        path = os.path.join(base, 'Jarvis')
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.join(get_project_root(), 'data')

def get_data_path(filename: str) -> str:
    """Returns path to data file, prioritizing AppData over project root."""
    import os, shutil
    appdata_file = os.path.join(get_app_data_root(), filename)
    bundled_file = os.path.join(get_project_root(), 'data', filename)
    
    if not os.path.exists(appdata_file) and os.path.exists(bundled_file):
        try:
            os.makedirs(os.path.dirname(appdata_file), exist_ok=True)
            if os.path.isfile(bundled_file):
                shutil.copy2(bundled_file, appdata_file)
        except Exception: pass
    
    os.makedirs(os.path.dirname(appdata_file), exist_ok=True)
    return appdata_file

def get_data_dir(dirname: str) -> str:
    """Returns path to data directory in AppData, migrating if needed."""
    import os, shutil
    appdata_dir = os.path.join(get_app_data_root(), dirname)
    bundled_dir = os.path.join(get_project_root(), 'data', dirname)
    
    if not os.path.exists(appdata_dir) and os.path.exists(bundled_dir):
        try:
            os.makedirs(os.path.dirname(appdata_dir), exist_ok=True)
            # Copy entire directory content
            shutil.copytree(bundled_dir, appdata_dir, dirs_exist_ok=True)
        except Exception: pass
        
    os.makedirs(appdata_dir, exist_ok=True)
    return appdata_dir

def get_settings_path() -> str:
    return get_data_path('jarvis_settings.json')

def get_secrets_path() -> str:
    """Single source of truth for where API keys / tokens live: always
    %APPDATA%\\Jarvis\\secrets.env (or LOCALAPPDATA, or <project>/data as a last
    resort) — same path whether running from source or a packaged .exe.
    Used by the startup loader below, llm_processor._load_api_key(), and the
    Settings UI save handler, so all three agree on one file."""
    import os
    return os.path.join(get_app_data_root(), 'secrets.env')

_secrets_env_path = get_secrets_path  # back-compat alias for any external callers

def _load_secrets() -> None:
    import os
    paths = [get_secrets_path(), os.path.join(get_project_root(), '.env')]
    for p in paths:
        try:
            if os.path.exists(p):
                load_dotenv(p, override=False)
        except Exception:
            pass
_load_secrets()
_ROOT = get_project_root()
MODEL_PATH = os.path.join(_ROOT, 'models', 'sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16')
SILERO_VAD_PATH = os.path.join(_ROOT, 'models', 'silero_vad')
RATE = 16000
CHUNK_MS = 32
SILENCE_MS = 160
VAD_SILENCE_MS = 160  # 160//CHUNK_MS=5 frames (~160ms), aligned with asr.py's
# normal-mode _vad_min_silence=0.16. Lower than this risks cutting off AI
# queries/dictation, where users pause mid-thought more than for short commands.
GAME_SILENCE_MS = 130  # Lower than normal mode: most players use headphones, so the
# mic doesn't pick up game audio, allowing faster end-of-command detection.
# 130//CHUNK_MS=4 frames (~128ms) — close to the practical floor for this energy/VAD
# scheme; going much lower risks cutting off trailing word sounds.
VAD_CONFIDENCE_THRESHOLD = 0.25
MIN_SPEECH_MS = 80
CALIBRATION_SEC = 0.8
NOISE_MULT = 1.4
MIN_THRESH = 50
MIC_GAIN = 2.5
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
TTS_ENGINE = 'silero'
def _read_stt_engine() -> str:
    p_str = get_settings_path()
    try:
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'stt_engine' in data:
                return data['stt_engine']
            cpu_phys = os.cpu_count() or 2
            engine = 'vosk' if cpu_phys <= 2 else 'gigaam'
            data['stt_engine'] = engine
            with open(p_str, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return engine
    except Exception:
        pass
    cpu_phys = os.cpu_count() or 2
    return 'vosk' if cpu_phys <= 2 else 'gigaam'
STT_ENGINE = _read_stt_engine()
JARVIS_VOLUME = 1.0
def _read_tts_warmup() -> bool:
    try:
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return bool(data.get('tts_warmup', True))
    except Exception:
        pass
    return True
TTS_WARMUP = _read_tts_warmup()
def _read_max_saved_videos() -> int:
    try:
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return int(data.get('max_saved_videos', 10))
    except Exception:
        pass
    return 10
MAX_SAVED_VIDEOS = _read_max_saved_videos()

def _read_tts_unload_timeout() -> float:
    try:
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return float(data.get('tts_unload_timeout', 300.0))
    except Exception:
        pass
    return 300.0
TTS_UNLOAD_TIMEOUT = _read_tts_unload_timeout()

def _read_wake_word_mode() -> str:
    try:
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return str(data.get('wake_word_mode', 'continuous'))
    except Exception:
        pass
    return 'continuous'
WAKE_WORD_MODE = _read_wake_word_mode()

def _read_wake_active_timeout() -> float:
    """How many seconds Jarvis keeps listening without the wake word after
    the last command, in 'continuous' wake mode — i.e. when it goes back to
    sleep. User-adjustable via Settings -> Voice; see
    ui/dialogs/settings_tabs/voice.py's wake-mode card."""
    try:
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return float(data.get('wake_active_timeout_sec', 30.0))
    except Exception:
        pass
    return 30.0
WAKE_ACTIVE_TIMEOUT_SEC = _read_wake_active_timeout()
