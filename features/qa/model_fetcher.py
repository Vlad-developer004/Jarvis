"""Dynamic model list fetcher with 24-hour disk cache.

Fetches available model IDs from each provider's API.
Limits (RPM/RPD/ctx/desc) are overlaid from data/model_limits.json.
Cache lives in data/model_cache.json.

Public API:
    get_models_for_ui(provider)   -> dict {model_id: {ctx, rpm, rpd, alias}}
    is_cache_stale(provider)      -> bool
    refresh_async(provider, api_key, on_done)  -> None (background)
    fetch_and_cache(provider, api_key)         -> bool
"""

import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from typing import Callable

from core.logging_setup import get_logger

_log = get_logger('model_fetcher')

_CACHE_TTL = 86400  # 24 h
_UNKNOWN = '?'


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _data_dir() -> str:
    if hasattr(sys, 'frozen'):
        return os.path.join(os.path.dirname(sys.executable), 'data')
    return os.path.abspath('data')


def _cache_path() -> str:
    return os.path.join(_data_dir(), 'model_cache.json')


def _limits_path() -> str:
    return os.path.join(_data_dir(), 'model_limits.json')


def _load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_json(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.warning('Failed to save %s: %s', path, e)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    'User-Agent': 'python-httpx/0.27.0',
    'Accept': 'application/json',
}

_PROVIDER_UA = {
    'groq':       'groq-python/0.9.0',
    'openai':     'openai-python/1.51.0',
    'anthropic':  'anthropic-python/0.36.0',
    'deepseek':   'openai-python/1.51.0',
    'openrouter': 'python-httpx/0.27.0',
    'google':     'google-generativeai/0.8.3',
}


def _http_get(url: str, headers: dict, timeout: int = 12, provider: str = '') -> dict:
    ua = _PROVIDER_UA.get(provider, _DEFAULT_HEADERS['User-Agent'])
    merged = {**_DEFAULT_HEADERS, 'User-Agent': ua, **headers}
    req = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


# ---------------------------------------------------------------------------
# Context window formatter
# ---------------------------------------------------------------------------

def _fmt_ctx(tokens: int) -> str:
    if not tokens:
        return _UNKNOWN
    if tokens >= 1_000_000:
        n = tokens / 1_000_000
        return f'{n:.0f}M' if n == int(n) else f'{n:.1f}M'
    if tokens >= 1000:
        n = tokens / 1000
        return f'{n:.0f}k' if n == int(n) else f'{n:.1f}k'
    return str(tokens)


# ---------------------------------------------------------------------------
# Provider-specific fetchers  ->  list[dict(id, ctx)]
# ---------------------------------------------------------------------------

def _fetch_groq(api_key: str) -> list[dict]:
    data = _http_get(
        'https://api.groq.com/openai/v1/models',
        {'Authorization': f'Bearer {api_key}'},
        provider='groq',
    )
    # Groq's /v1/models has no modality field at all (confirmed against
    # their own API reference — every model, chat or TTS/STT, reports the
    # same {id, context_window, max_completion_tokens, ...} shape with
    # nothing distinguishing the two). There is no data-driven way to tell
    # a text chat model from an audio one here; this substring list is the
    # only signal available and needs a new entry whenever Groq adds a
    # non-chat model family under a name that doesn't already match one of
    # these (it happened with canopylabs/orpheus and playai-tts, neither of
    # which contain any of the previous tokens).
    skip_tokens = ('whisper', 'distil', 'guard', 'tool-use', 'vision',
                   'orpheus', 'playai', 'tts')
    out = []
    for m in data.get('data', []):
        mid = m.get('id', '')
        if not mid or any(s in mid for s in skip_tokens):
            continue
        out.append({'id': mid, 'ctx': _fmt_ctx(m.get('context_window', 0))})
    return sorted(out, key=lambda x: x['id'])


def _fetch_openai(api_key: str) -> list[dict]:
    data = _http_get(
        'https://api.openai.com/v1/models',
        {'Authorization': f'Bearer {api_key}'},
        provider='openai',
    )
    # Exclusion-based on purpose, not an allowlist of chat-model prefixes —
    # an allowlist goes stale the moment OpenAI ships a new generation
    # (gpt-5, gpt-6, o5, ...): it would silently vanish from the catalog
    # until someone remembers to add the new prefix here, which defeats the
    # whole point of live-syncing the model list. Filter out only the
    # clearly non-chat-completion families instead — new chat models show
    # up automatically.
    skip_tokens = ('instruct', 'vision', 'realtime', 'audio', 'search',
                   'tts', 'whisper', 'dall-e', 'embedding', 'moderation',
                   'davinci', 'babbage', 'curie', 'ada-', 'transcribe',
                   'image', 'sora')
    out = []
    for m in data.get('data', []):
        mid = m.get('id', '')
        if not mid:
            continue
        if any(s in mid for s in skip_tokens):
            continue
        out.append({'id': mid, 'ctx': _UNKNOWN})
    return sorted(out, key=lambda x: x['id'])


def _fetch_google(api_key: str) -> list[dict]:
    data = _http_get(
        f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}',
        {},
        provider='google',
    )
    out = []
    for m in data.get('models', []):
        if 'generateContent' not in m.get('supportedGenerationMethods', []):
            continue
        name = m.get('name', '').replace('models/', '')
        if not name.startswith('gemini-'):
            continue
        out.append({'id': name, 'ctx': _fmt_ctx(m.get('inputTokenLimit', 0))})
    return sorted(out, key=lambda x: x['id'])


def _fetch_deepseek(api_key: str) -> list[dict]:
    data = _http_get(
        'https://api.deepseek.com/models',
        {'Authorization': f'Bearer {api_key}'},
        provider='deepseek',
    )
    return sorted(
        [{'id': m.get('id', ''), 'ctx': _UNKNOWN}
         for m in data.get('data', []) if m.get('id')],
        key=lambda x: x['id'],
    )


def _fetch_anthropic(api_key: str) -> list[dict]:
    data = _http_get(
        'https://api.anthropic.com/v1/models',
        {'x-api-key': api_key, 'anthropic-version': '2023-06-01'},
        provider='anthropic',
    )
    out = []
    for m in data.get('data', []):
        mid = m.get('id', '')
        if mid:
            ctx = _fmt_ctx(m.get('context_window', 0))
            out.append({'id': mid, 'ctx': ctx})
    return sorted(out, key=lambda x: x['id'])


def _fetch_openrouter(api_key: str = '') -> list[dict]:
    """Fetch free models from OpenRouter (no key required for browsing)."""
    headers: dict = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    data = _http_get('https://openrouter.ai/api/v1/models', headers, timeout=15, provider='openrouter')
    out = []
    for m in data.get('data', []):
        mid = m.get('id', '')
        if not mid:
            continue
        pricing = m.get('pricing', {})
        try:
            prompt_price = float(pricing.get('prompt', '1') or '1')
        except (ValueError, TypeError):
            prompt_price = 1.0
        if prompt_price > 0 and not mid.endswith(':free'):
            continue
        ctx = _fmt_ctx(m.get('context_length', 0))
        out.append({'id': mid, 'ctx': ctx})
    return sorted(out, key=lambda x: x['id'])


def _fetch_local(api_key: str = '', base_url: str = '') -> list[dict]:
    """Ollama / llama.cpp's llama-server / TabbyAPI — all three expose the
    same OpenAI-compatible GET /v1/models, so one fetcher covers them."""
    base = (base_url or 'http://localhost:11434/v1').rstrip('/')
    headers: dict = {}
    if api_key and api_key != 'not-needed':
        headers['Authorization'] = f'Bearer {api_key}'
    data = _http_get(f'{base}/models', headers, timeout=5, provider='local')
    out = []
    for m in data.get('data', []):
        mid = m.get('id', '')
        if mid:
            out.append({'id': mid, 'ctx': _UNKNOWN})
    return sorted(out, key=lambda x: x['id'])


_FETCHERS: dict[str, Callable] = {
    'groq':       _fetch_groq,
    'openai':     _fetch_openai,
    'google':     _fetch_google,
    'deepseek':   _fetch_deepseek,
    'anthropic':  _fetch_anthropic,
    'openrouter': _fetch_openrouter,
    'local':      _fetch_local,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_cache_stale(provider: str, ttl: int = _CACHE_TTL) -> bool:
    cache = _load_json(_cache_path())
    fetched_at = cache.get(provider, {}).get('fetched_at', 0)
    return (time.time() - fetched_at) > ttl


_RETRY_COOLDOWN = 300  # 5 min before retrying a failed fetch


def fetch_and_cache(provider: str, api_key: str = '', base_url: str = '') -> bool:
    """Fetch model list from provider API and persist to disk cache.

    Returns True on success. On failure writes a short-TTL tombstone to the
    cache so is_cache_stale() stays False for _RETRY_COOLDOWN seconds,
    preventing 403 spam on repeated panel opens.
    """
    fetcher = _FETCHERS.get(provider)
    if not fetcher:
        _log.warning('Unknown provider: %s', provider)
        return False
    try:
        models = fetcher(api_key, base_url) if provider == 'local' else fetcher(api_key)
        if not models:
            _log.warning('Empty model list returned for %s', provider)
            _write_tombstone(provider)
            return False
        cache = _load_json(_cache_path())
        cache[provider] = {'fetched_at': int(time.time()), 'models': models}
        _save_json(_cache_path(), cache)
        _log.info('Cached %d models for %s', len(models), provider)
        return True
    except Exception as e:
        import urllib.error as _ue
        if isinstance(e, _ue.HTTPError):
            _log.warning('Fetch failed for %s: HTTP %s %s', provider, e.code, e.reason)
        else:
            _log.warning('Fetch failed for %s: %s', provider, e)
        _write_tombstone(provider)
        return False


def _write_tombstone(provider: str) -> None:
    """Write a cache entry with short TTL so we don't retry for _RETRY_COOLDOWN seconds."""
    cache = _load_json(_cache_path())
    existing_models = cache.get(provider, {}).get('models', None)
    # Keep existing models if any; just push fetched_at back so stale check gives cooldown
    cache[provider] = {
        'fetched_at': int(time.time()) - _CACHE_TTL + _RETRY_COOLDOWN,
        'models': existing_models,
    }
    _save_json(_cache_path(), cache)


def _live_limits_path() -> str:
    return os.path.join(_data_dir(), 'model_live_limits.json')


def _live_rpm(provider: str, model_id: str) -> str | int:
    """RPM captured from a real x-ratelimit-limit-requests response header
    (see llm_processor._capture_rate_limit_headers) — reflects the caller's
    actual account/tier, unlike the static model_limits.json guess, so it
    takes priority when we have it."""
    live = _load_json(_live_limits_path())
    entry = live.get(f'{provider}:{model_id}')
    return entry['rpm'] if entry else _UNKNOWN


def get_models_for_ui(provider: str) -> dict:
    """Return {model_id: {ctx, rpm, rpd, alias}} ready for the UI.

    Models come from disk cache (dynamic).
    Limits (rpm/rpd/desc) are overlaid from model_limits.json, then rpm is
    overridden by a live-captured value if one exists (see _live_rpm).
    If no cache exists yet, falls back to the limits file model list.
    """
    cache = _load_json(_cache_path())
    limits = _load_json(_limits_path())
    prov_limits: dict = limits.get(provider, {})
    cached_models = cache.get(provider, {}).get('models')  # list[{id, ctx}] or None

    if cached_models is None:
        # No cache yet — show limits entries as initial fallback
        return {
            mid: {
                'ctx':   info.get('ctx', _UNKNOWN),
                'rpm':   _live_rpm(provider, mid) if _live_rpm(provider, mid) != _UNKNOWN else info.get('rpm', _UNKNOWN),
                'rpd':   info.get('rpd', _UNKNOWN),
                'alias': info.get('desc', mid),
            }
            for mid, info in prov_limits.items()
        }

    result = {}
    for entry in cached_models:
        mid = entry['id']
        api_ctx = entry.get('ctx', _UNKNOWN)
        lim = prov_limits.get(mid, {})
        # Prefer context window from API; fall back to limits file
        ctx = api_ctx if (api_ctx and api_ctx != _UNKNOWN) else lim.get('ctx', _UNKNOWN)
        live_rpm = _live_rpm(provider, mid)
        result[mid] = {
            'ctx':   ctx,
            'rpm':   live_rpm if live_rpm != _UNKNOWN else lim.get('rpm', _UNKNOWN),
            'rpd':   lim.get('rpd', _UNKNOWN),
            'alias': lim.get('desc', ''),
        }
    return result


def refresh_async(
    provider: str,
    api_key: str,
    on_done: Callable[[str, dict], None] | None = None,
    base_url: str = '',
) -> None:
    """Fetch provider models in a background daemon thread.

    Calls on_done(provider, models_dict) from the worker thread when done.
    The caller is responsible for dispatching to the UI thread if needed.
    """
    def _work():
        ok = fetch_and_cache(provider, api_key, base_url)
        if on_done:
            models = get_models_for_ui(provider) if ok else {}
            try:
                on_done(provider, models)
            except Exception as e:
                _log.warning('refresh_async callback error: %s', e)

    threading.Thread(target=_work, daemon=True, name=f'mfetch-{provider}').start()
