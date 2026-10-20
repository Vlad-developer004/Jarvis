"""API-key lookup and the per-provider client cache for features.qa.llm_processor (moved out unchanged)."""

from core.logging_setup import get_logger
from core.safe import swallow as _swallow
import os
import threading

_log = get_logger('qa')

# ---------------------------------------------------------------------------
# Client cache  {provider: (client_object, api_key_used, model_used)}
# model_used is only stored for providers that embed it at construction time.
# ---------------------------------------------------------------------------
_clients: dict[str, tuple] = {}

_lock = threading.Lock()

# API keys essentially never change mid-session, but _load_api_key() used to
# scan up to 5 candidate file paths on disk on every single AI query. Cache
# the result per provider; invalidate_clients() (already called whenever the
# user edits a key in settings) clears this too.
_api_key_cache: dict[str, str] = {}

def _load_api_key(provider: str) -> str:
    """Find API key for specified provider in env or secrets.env files."""
    provider = provider.lower()
    with _lock:
        cached = _api_key_cache.get(provider)
    if cached is not None:
        return cached
    key = _load_api_key_uncached(provider)
    with _lock:
        _api_key_cache[provider] = key
    return key

def _load_api_key_uncached(provider: str) -> str:
    env_map = {
        'groq': 'GROQ_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'gemini': 'GOOGLE_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'openrouter': 'OPENROUTER_API_KEY',
        # Optional — most local servers (Ollama, llama.cpp's llama-server)
        # don't check it at all; TabbyAPI can be configured to require one.
        'local': 'LOCAL_LLM_API_KEY',
    }
    key_name = env_map.get(provider.lower(), 'GROQ_API_KEY')

    val = os.environ.get(key_name, '')
    if val:
        return val

    # Fallback for the rare case os.environ wasn't populated yet (config_pack.config
    # normally loads this at import time). Single source of truth: the same
    # %APPDATA%\Jarvis\secrets.env the Settings UI writes to and config.py reads
    # at startup — see config_pack.config.get_secrets_path().
    from config_pack.config import get_secrets_path, get_project_root
    for env_path in (get_secrets_path(), os.path.join(get_project_root(), '.env')):
        try:
            if os.path.exists(env_path):
                with open(env_path, encoding='utf-8-sig') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f'{key_name}='):
                            return line[len(f'{key_name}='):].strip().strip('"').strip("'")
        except Exception:
            _swallow()
    return ''

def invalidate_clients(provider: str | None = None) -> None:
    """Drop cached LLM client(s) so they are recreated with fresh credentials.

    Call this after the user changes an API key or switches AI model in settings.
    Pass provider name to invalidate only that provider, or None to clear all.
    """
    with _lock:
        if provider is None:
            _clients.clear()
            _api_key_cache.clear()
        else:
            p = provider.lower()
            # 'local' clients are cached under 'local:<base_url>' (see
            # _get_openai_compat_client) since the URL is user-editable —
            # drop every cached client for this provider, not just a
            # same-named key that no longer matches.
            for k in [k for k in _clients if k == p or k.startswith(f'{p}:')]:
                _clients.pop(k, None)
            _api_key_cache.pop(p, None)
    _log.info('LLM client cache invalidated: %s', provider or 'all')
