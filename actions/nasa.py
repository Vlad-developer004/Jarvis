"""NASA Astronomy Picture of the Day (APOD) — one-shot cloud lookup gated
behind an explicit voice command, same pattern as actions/weather.py and
actions/currency.py. Free API, no signup required (DEMO_KEY), but that key
is rate-limited across everyone using it — set NASA_API_KEY in secrets.env
for a personal key from https://api.nasa.gov if DEMO_KEY starts failing.

The image itself is shown in the existing AI mini-window (ui/hud_ai_window.py,
same thumbnail box used for Wikipedia images during QA answers) rather than
opening a browser tab, so it stays inside the app.

NASA's API only ever returns title/explanation in English — there is no
translation. That text is shown as on-screen text, never spoken: this
project's TTS transliterates isolated Latin words phonetically for names
like "Tesla"/"SpaceX" embedded in Russian sentences (see
core/speech/tts.py's _transliterate_word), it does not speak English
prose — feeding it a whole English paragraph would just phoneticize every
word individually into gibberish.
"""
import hashlib
import os
import tempfile

_APOD_URL = 'https://api.nasa.gov/planetary/apod'
_apod_cache: dict[str, dict] = {}


def _download_file(url: str, prefix: str) -> str | None:
    try:
        import requests
        cache_dir = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')
        os.makedirs(cache_dir, exist_ok=True)
        h = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = '.png' if '.png' in url.lower() else '.jpg'
        path = os.path.join(cache_dir, f'{prefix}_{h}{ext}')
        if not os.path.exists(path):
            resp = requests.get(url, timeout=8.0, headers={'User-Agent': 'JarvisOS/1.5'})
            if resp.status_code != 200:
                return None
            with open(path, 'wb') as f:
                f.write(resp.content)
        return path
    except Exception:
        return None


def _download_video(url: str) -> str | None:
    """Downloads NASA's video-of-the-day link (usually YouTube/Vimeo) at the
    lowest available quality — this only ever gets shown muted inside a
    ~150px thumbnail box (see HUD_AI_Window.set_video), so there's no reason
    to pull a full-resolution file. Same yt_dlp dependency actions/youtube.py
    already uses for downloads."""
    try:
        import yt_dlp
        cache_dir = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')
        os.makedirs(cache_dir, exist_ok=True)
        h = hashlib.md5(url.encode('utf-8')).hexdigest()
        outtmpl = os.path.join(cache_dir, f'nasa_vid_{h}.%(ext)s')
        existing = [f for f in os.listdir(cache_dir) if f.startswith(f'nasa_vid_{h}.')]
        if existing:
            return os.path.join(cache_dir, existing[0])
        opts = {
            'format': 'worst[ext=mp4]/worst',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            # Same workaround as actions/youtube.py's download_youtube_video() —
            # YouTube's bot-detection blocks yt-dlp's default web client.
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        existing = [f for f in os.listdir(cache_dir) if f.startswith(f'nasa_vid_{h}.')]
        return os.path.join(cache_dir, existing[0]) if existing else None
    except Exception:
        return None


def get_apod() -> dict:
    """Returns a dict:
      {'ok': False, 'error': <localized text>}  — request failed
      {'ok': True, 'media_type': 'image', 'title': ..., 'explanation': ...,
       'image_path': <local path or None>}
      {'ok': True, 'media_type': 'video', 'title': ..., 'explanation': ...,
       'video_url': ...}
    title/explanation are NASA's raw English text — display only, never speak.
    """
    import time
    from core.i18n import get_speech_language
    lang = get_speech_language()
    today_key = time.strftime('%Y-%m-%d')  # APOD content for a given day never changes
    cached = _apod_cache.get(today_key)
    if cached:
        data = cached
    else:
        try:
            import requests
            api_key = os.environ.get('NASA_API_KEY') or 'DEMO_KEY'
            resp = requests.get(_APOD_URL, params={'api_key': api_key}, timeout=6.0)
            if resp.status_code != 200:
                raise Exception(f'HTTP {resp.status_code}')
            data = resp.json()
            _apod_cache.clear()
            _apod_cache[today_key] = data
        except Exception:
            err = 'Не вдалося отримати картинку дня від NASA.' if lang == 'uk' else 'Не удалось получить картинку дня от NASA.'
            return {'ok': False, 'error': err}

    title = data.get('title', '')
    explanation = data.get('explanation', '')
    media_type = data.get('media_type', 'image')

    if media_type == 'video':
        video_url = data.get('url')
        video_path = _download_video(video_url) if video_url else None
        return {'ok': True, 'media_type': 'video', 'title': title,
                'explanation': explanation, 'video_path': video_path}

    image_url = data.get('url')
    image_path = _download_file(image_url, 'nasa') if image_url else None
    return {'ok': True, 'media_type': 'image', 'title': title,
            'explanation': explanation, 'image_path': image_path}
