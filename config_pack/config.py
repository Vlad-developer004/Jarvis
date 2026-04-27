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

def _secrets_env_path() -> str:
    import os
    return os.path.join(get_app_data_root(), 'secrets.env')

def _load_secrets() -> None:
    import os
    paths = [_secrets_env_path(), os.path.join(get_project_root(), '.env')]
    for p in paths:
        try:
            if os.path.exists(p):
                load_dotenv(p, override=False)
        except Exception:
            pass
_load_secrets()
MODEL_PATH = 'models/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16'
SILERO_VAD_PATH = 'models/silero_vad'
RATE = 16000
CHUNK_MS = 32
SILENCE_MS = 250
VAD_SILENCE_MS = 250
GAME_SILENCE_MS = 250
VAD_CONFIDENCE_THRESHOLD = 0.25
MIN_SPEECH_MS = 80
CALIBRATION_SEC = 0.8
NOISE_MULT = 1.4
MIN_THRESH = 50
MIC_GAIN = 2.5
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
TTS_ENGINE = 'piper'
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
