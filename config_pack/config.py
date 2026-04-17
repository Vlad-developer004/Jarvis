import os
from dotenv import load_dotenv
def _secrets_env_path() -> str:
    appdata = os.environ.get('APPDATA', '') or os.environ.get('LOCALAPPDATA', '')
    if appdata:
        return os.path.join(appdata, 'Jarvis', 'secrets.env')
    return os.path.abspath('.env')
def _load_secrets() -> None:
    paths = [_secrets_env_path(), os.path.abspath('.env')]
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
SILENCE_MS = 150
VAD_SILENCE_MS = 150
GAME_SILENCE_MS = 220
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
    import json
    import os
    from pathlib import Path
    p = Path('data') / 'jarvis_settings.json'
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            if 'stt_engine' in data:
                return data['stt_engine']
            cpu_phys = os.cpu_count() or 2
            engine = 'vosk' if cpu_phys <= 2 else 'gigaam'
            data['stt_engine'] = engine
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return engine
    except Exception:
        pass
    cpu_phys = os.cpu_count() or 2
    return 'vosk' if cpu_phys <= 2 else 'gigaam'
STT_ENGINE = _read_stt_engine()
JARVIS_VOLUME = 1.0
def _read_tts_warmup() -> bool:
    import json
    from pathlib import Path
    try:
        p = Path('data') / 'jarvis_settings.json'
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            return bool(data.get('tts_warmup', False))
    except Exception:
        pass
    return False
TTS_WARMUP = _read_tts_warmup()
def _read_max_saved_videos() -> int:
    import json
    from pathlib import Path
    try:
        p = Path('data') / 'jarvis_settings.json'
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            return int(data.get('max_saved_videos', 10))
    except Exception:
        pass
    return 10
MAX_SAVED_VIDEOS = _read_max_saved_videos()
