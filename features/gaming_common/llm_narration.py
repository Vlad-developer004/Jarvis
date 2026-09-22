"""Shared "is AI narration configured for this game?" + LLM call plumbing.
Extracted from features/ets2/llm.py and features/planetbase/llm.py, which
had near-identical settings/API-key checks around different system prompts
and prompt builders (those stay per-game — only the boilerplate moves here).
"""
from core.logging_setup import get_logger

_log = get_logger('gaming_common.llm')


def _load_settings() -> dict:
    try:
        import json, os
        from config_pack.config import get_settings_path
        sp = get_settings_path()
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def has_llm_configured(enabled_settings_key: str, default_enabled: bool = True) -> bool:
    """True if an API key exists and this game's AI narration isn't
    explicitly disabled via `enabled_settings_key` in jarvis_settings.json."""
    try:
        settings = _load_settings()
        if not settings.get(enabled_settings_key, default_enabled):
            return False
        provider = settings.get('ai_provider', 'groq')
        from features.qa.llm_processor import _load_api_key
        return bool(_load_api_key(provider))
    except Exception:
        return False


def ask_llm_narration(sys_prompt: str, prompt: str, max_tokens: int = 300, timeout: int = 12) -> str:
    """Calls the configured LLM with a game-specific system prompt and user
    prompt. Returns '' on any failure — callers fall back to their own
    static phrase banks."""
    try:
        from features.qa.llm_processor import ask_llm, _clean
        result = ask_llm(
            topic='',
            question=prompt,
            timeout=timeout,
            sys_prompt=sys_prompt,
            max_tokens=max_tokens,
        )
        if isinstance(result, str) and result.strip():
            return _clean(result)
    except Exception as e:
        _log.warning('Game LLM narration error: %s', e)
    return ''
