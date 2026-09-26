"""Song recognition ("what's this song?").

Recognition order, cheapest/most-local first:
  1. actions/song_cache.py — a local JSON cache of songs already recognized
     before, matched by audio fingerprint (actions/song_fingerprint.py).
     Instant, no network.
  2. Shazam, via the keyless `shazamio` library — this is the real Shazam
     backend, but reverse-engineered so it needs no signup or API key at
     all. This is the *default* recognizer, so a fresh Jarvis install can
     recognize songs immediately with zero configuration.
  3. AudD (https://audd.io/), only if the user has set AUDD_API_KEY in
     secrets.env — an optional fallback for when Shazam's endpoint has
     nothing (e.g. very new/regional releases) or is unreachable.
A successful hit from either #2 or #3 is written into the local cache, so
the *next* time that song plays, step #1 catches it offline.

Two audio sources:
  - 'mic'  — reads from the shared ring buffer the always-on engine keeps
    filled (core/audio_ring.py), rather than opening a second PyAudio stream
    on the same device (which on Windows can silently return near-silence
    instead of erroring — see _record_mic()'s docstring). Picks up music
    playing from a phone/speakers in the room, or from this PC if it's not
    on headphones.
  - 'pc'   — WASAPI loopback capture of this PC's own audio output, via the
    optional pyaudiowpatch dependency. Works even over headphones, where the
    mic would hear nothing. Falls back to 'mic' if pyaudiowpatch isn't
    installed or loopback isn't available on this machine.
"""
import os
import tempfile
import time
import wave

from core.logging_setup import get_logger

_log = get_logger('song_id')

_CHANNELS = 1
_CHUNK = 1024
_RECORD_SECONDS = 10


def _write_wav(path: str, raw: bytes, rate: int, channels: int) -> None:
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit PCM throughout
        wf.setframerate(rate)
        wf.writeframes(raw)


def _normalize_gain(raw: bytes) -> bytes:
    """Boosts a quiet recording up to a healthy peak level. A phone's own
    speaker played back through this PC's mic is often much quieter than
    someone speaking directly into it — both Shazam and our local fingerprint
    matcher work off relative spectral peaks, not absolute loudness, but a
    signal buried near the noise floor still loses real peaks to quantization
    and picks up spurious ones from mic self-noise. Logs the peak level so a
    future "no_match" report shows whether the input was simply too quiet."""
    import numpy as np
    samples = np.frombuffer(raw, dtype=np.int16)
    if samples.size == 0:
        return raw
    peak = int(np.abs(samples).max())
    _log.info('recorded clip peak amplitude: %d / 32767', peak)
    if peak == 0:
        return raw
    target = 24000  # ~73% of full scale — headroom against inter-sample overshoot
    if peak >= target:
        return raw  # already loud enough (or clipping already) — don't touch it
    gain = min(target / peak, 12.0)  # cap so a near-silent clip doesn't blow up pure noise
    boosted = np.clip(samples.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
    return boosted.tobytes()


def _record_mic(seconds: float):
    """Returns (raw_16bit_mono_pcm, rate) or None.

    Does NOT open its own PyAudio stream on the mic — the always-on engine
    (core/engine/jarvis.py) already holds that device open continuously for
    wake-word/VAD. A second concurrent open on the same input device turned
    out to silently return near-silence on Windows instead of erroring
    (observed: peak amplitude 2/32767 while music was audibly playing right
    next to the mic) rather than sharing the device or raising — so this
    just waits out the window and reads it from the shared ring buffer
    (core/audio_ring.py) that the engine's loop keeps fed in real time.
    """
    try:
        from core import audio_ring
        time.sleep(seconds)
        raw, rate = audio_ring.read_last_seconds(seconds)
        if not raw:
            _log.error('mic ring buffer is empty — is the engine running?')
            return None
        return _normalize_gain(raw), rate
    except Exception as e:
        _log.error('mic recording failed: %s', e, exc_info=True)
        return None


def _record_loopback(seconds: float):
    """Returns (raw_bytes, rate, channels) or None if unavailable."""
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        return None
    try:
        pa = pyaudio.PyAudio()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = pa.get_device_info_by_index(wasapi_info['defaultOutputDevice'])
            if not default_speakers.get('isLoopbackDevice', False):
                for loopback in pa.get_loopback_device_info_generator():
                    if default_speakers['name'] in loopback['name']:
                        default_speakers = loopback
                        break
                else:
                    return None
            rate = int(default_speakers['defaultSampleRate'])
            channels = int(default_speakers['maxInputChannels']) or 2
            stream = pa.open(format=pyaudio.paInt16, channels=channels, rate=rate,
                              input=True, input_device_index=default_speakers['index'],
                              frames_per_buffer=_CHUNK)
            try:
                n_chunks = int(rate / _CHUNK * seconds)
                frames = [stream.read(_CHUNK, exception_on_overflow=False) for _ in range(n_chunks)]
            finally:
                stream.stop_stream()
                stream.close()
            return _normalize_gain(b''.join(frames)), rate, channels
        finally:
            pa.terminate()
    except Exception as e:
        _log.error('loopback recording failed: %s', e, exc_info=True)
        return None


def _download_cover(url: str) -> str | None:
    if not url:
        return None
    try:
        import hashlib
        import requests
        cache_dir = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')
        os.makedirs(cache_dir, exist_ok=True)
        h = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = '.png' if '.png' in url.lower() else '.jpg'
        path = os.path.join(cache_dir, f'song_{h}{ext}')
        if not os.path.exists(path):
            resp = requests.get(url, timeout=8.0)
            if resp.status_code != 200:
                return None
            with open(path, 'wb') as f:
                f.write(resp.content)
        return path
    except Exception:
        return None


def _youtube_search_url(artist: str, title: str) -> str:
    from urllib.parse import quote_plus
    return f'https://www.youtube.com/results?search_query={quote_plus(f"{artist} {title}".strip())}'


_SHAZAM_LOCALE = {
    'ru': ('ru-RU', 'RU'),
    'uk': ('uk-UA', 'UA'),
}


def _query_shazam(wav_path: str) -> dict:
    """Keyless recognition via the real Shazam backend (shazamio library —
    no API key, no signup, works out of the box).

    Requests results in the app's own language/region: for a Russian/
    Ukrainian-catalog song this gets back the artist/title already in
    Cyrillic straight from Shazam's own data — the authoritative spelling,
    not a guess. That matters because reconstructing it algorithmically from
    a Latin transliteration can't be made 100% reliable in general (the
    Cyrillic->Latin scheme itself is lossy — е and э both become "e", й and
    ы both become "y" — so several different Cyrillic words can transliterate
    to the same Latin spelling; no reverse algorithm can un-collapse that).
    A general online translator would be worse, not better, here: band names
    that are also ordinary English words (Queen, Kiss, Genesis, Poison) would
    get translated by *meaning* ("Queen" -> "Королева") instead of by sound.
    core/speech/tts.py's _reverse_translit_cyrillic() remains as a fallback
    for whatever still comes back in Latin script (AudD, or a catalog with no
    Cyrillic entry at all) — an approximation, but better than nothing.
    """
    try:
        import asyncio
        from shazamio import Shazam
        from core.i18n import get_language
        lang, country = _SHAZAM_LOCALE.get(get_language(), ('en-US', 'GB'))

        async def _run():
            return await Shazam(language=lang, endpoint_country=country).recognize(wav_path)

        data = asyncio.run(_run())
    except ImportError as e:
        _log.error('shazamio not installed: %s', e)
        return {'ok': False, 'error': 'not_installed'}
    except Exception as e:
        _log.error('Shazam request failed: %s', e, exc_info=True)
        return {'ok': False, 'error': 'network'}

    track = data.get('track')
    if not track:
        return {'ok': False, 'error': 'no_match'}

    title = track.get('title', '')
    artist = track.get('subtitle', '')
    cover_url = (track.get('images') or {}).get('coverart', '')

    # Shazam's own response nests provider deep-links inconsistently across
    # regions/versions — scan every action URI in 'hub' rather than assume a
    # fixed path, and just take whatever Spotify/Apple Music links show up.
    spotify_url = ''
    apple_music_url = ''
    hub = track.get('hub') or {}
    all_actions = list(hub.get('actions') or [])
    for opt in hub.get('options') or []:
        all_actions.extend(opt.get('actions') or [])
    for provider in hub.get('providers') or []:
        all_actions.extend(provider.get('actions') or [])
    for action in all_actions:
        uri = action.get('uri', '') or ''
        if 'spotify' in uri and not spotify_url:
            spotify_url = uri
        elif ('music.apple.com' in uri or 'itunes.apple.com' in uri) and not apple_music_url:
            apple_music_url = uri

    return {
        'ok': True,
        'title': title,
        'artist': artist,
        'album': '',
        'release_date': '',
        'spotify_url': spotify_url,
        'apple_music_url': apple_music_url,
        'youtube_url': _youtube_search_url(artist, title),
        'cover_path': _download_cover(cover_url),
    }


def _query_audd(wav_path: str) -> dict:
    api_token = os.environ.get('AUDD_API_KEY', '').strip()
    if not api_token:
        return {'ok': False, 'error': 'no_key'}
    try:
        import requests
        with open(wav_path, 'rb') as f:
            r = requests.post(
                'https://api.audd.io/',
                # apple_music/spotify are only requested for their cover art
                # and direct links — the fingerprint match itself already
                # comes back on a bare request, this just enriches the result.
                data={'api_token': api_token, 'return': 'apple_music,spotify'},
                files={'file': f},
                timeout=20,
            )
        data = r.json()
    except Exception as e:
        _log.error('AudD request failed: %s', e, exc_info=True)
        return {'ok': False, 'error': 'network'}
    if data.get('status') != 'success':
        _log.error('AudD API error: %s', data.get('error'))
        return {'ok': False, 'error': 'api_error'}
    result = data.get('result')
    if not result:
        return {'ok': False, 'error': 'no_match'}

    title = result.get('title', '')
    artist = result.get('artist', '')
    spotify = result.get('spotify') or {}
    apple = result.get('apple_music') or {}

    cover_url = ''
    images = (spotify.get('album') or {}).get('images') or []
    if images:
        cover_url = images[0].get('url', '')
    if not cover_url and apple.get('artwork'):
        # Apple's artwork URL is a template like ".../{w}x{h}bb.jpg"
        tmpl = apple['artwork'].get('url', '')
        if tmpl:
            cover_url = tmpl.replace('{w}', '600').replace('{h}', '600')

    return {
        'ok': True,
        'title': title,
        'artist': artist,
        'album': result.get('album', ''),
        'release_date': result.get('release_date', ''),
        'spotify_url': (spotify.get('external_urls') or {}).get('spotify', ''),
        'apple_music_url': apple.get('url', ''),
        'youtube_url': _youtube_search_url(artist, title),
        'cover_path': _download_cover(cover_url),
    }


def _match_cache(raw: bytes, rate: int, channels: int):
    """Returns (hit_or_None, query_hashes) — hashes are returned either way
    so the caller can remember() them into the cache on a fresh network hit."""
    try:
        from actions.song_fingerprint import fingerprint_pcm
        from actions import song_cache
        hashes = fingerprint_pcm(raw, rate, channels)
        return song_cache.match(hashes), hashes
    except Exception as e:
        _log.error('local cache match failed: %s', e, exc_info=True)
        return None, []


def recognize_song(source: str = 'mic', seconds: float = _RECORD_SECONDS) -> dict:
    raw = rate = channels = None
    if source == 'pc':
        rec = _record_loopback(seconds)
        if rec is not None:
            raw, rate, channels = rec
        else:
            source = 'mic'  # no loopback support here — fall back
    if raw is None:
        rec = _record_mic(seconds)
        if rec is None:
            return {'ok': False, 'error': 'record_failed'}
        raw, rate = rec
        channels = _CHANNELS
    if not raw:
        return {'ok': False, 'error': 'record_failed'}

    cache_hit, query_hashes = _match_cache(raw, rate, channels)
    if cache_hit:
        return cache_hit

    tmp_path = os.path.join(tempfile.gettempdir(), f'jarvis_songid_{int(time.time() * 1000)}.wav')
    try:
        _write_wav(tmp_path, raw, rate, channels)

        res = _query_shazam(tmp_path)
        if res.get('ok'):
            res['source'] = 'shazam'
        else:
            shazam_err = res.get('error')
            _log.info('Shazam gave no result (%s), trying AudD fallback', shazam_err)
            audd_res = _query_audd(tmp_path)
            if audd_res.get('ok'):
                res = audd_res
                res['source'] = 'audd'
            elif shazam_err == 'no_match':
                # Shazam *did* answer, it just doesn't know this recording —
                # that's the true, useful reason. AudD failing too (usually
                # just because no key is configured) shouldn't overwrite it
                # with a misleading "service unavailable" message.
                res = {'ok': False, 'error': 'no_match'}
            else:
                res = audd_res

        if res.get('ok') and query_hashes:
            try:
                from actions import song_cache
                song_cache.remember(res, query_hashes)
            except Exception:
                pass
        return res
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
