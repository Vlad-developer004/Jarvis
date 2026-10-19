"""AI settings of the new UI (the old settings window, "Modules" tab, card "AI"): provider, model, API keys, local server address, generation parameters.

Where the data lives (the same places the old window and features/qa/llm_processor.py use):
  jarvis_settings.json (through core.settings_io): ai_provider, ai_model, ai_local_base_url, ai_temperature, ai_max_tokens, ai_top_k, ai_web_search_enabled, ai_mini_window, ai_models_all,
                                                  ai_fallback_enabled, ai_fallback_order, ai_budget_enabled, ai_daily_limit, ai_token_limit_in, ai_token_limit_out
  ai_usage.json next to the settings: today's request counters (features/qa/ai_router.py)
  secrets file (config_pack.config.get_secrets_path): GROQ_API_KEY, OPENAI_API_KEY, ... A key is never sent back to the screen, only whether one is set.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import date, timedelta

from core import settings_io

_log = logging.getLogger(__name__)
# id -> (name, secret name, page where the key is issued); the old window keeps the same table in ui/dialogs/settings_tabs/modules/constants.py
PROVIDERS = {
    'groq': ('Groq', 'GROQ_API_KEY', 'https://console.groq.com/keys'),
    'openai': ('OpenAI', 'OPENAI_API_KEY', 'https://platform.openai.com/api-keys'),
    'google': ('Google', 'GOOGLE_API_KEY', 'https://aistudio.google.com/app/apikey'),
    'deepseek': ('DeepSeek', 'DEEPSEEK_API_KEY', 'https://platform.deepseek.com/api_keys'),
    'anthropic': ('Anthropic', 'ANTHROPIC_API_KEY', 'https://console.anthropic.com/settings/keys'),
    'openrouter': ('OpenRouter', 'OPENROUTER_API_KEY', 'https://openrouter.ai/keys'),
    'local': ('Локальный сервер', 'LOCAL_LLM_API_KEY', ''),
}
NO_KEY_NEEDED = ('openrouter', 'local')            # the catalog of these can be read without a key
DEFAULT_LOCAL_URL = 'http://localhost:11434/v1'
_KEY_RE = re.compile(r'^[\x21-\x7e]{8,400}$')      # printable ASCII without spaces: no way to smuggle a second line into the secrets file
_MODEL_RE = re.compile(r'^[\w.:/\-+@]{1,120}$')
_lock = threading.Lock()


def _bad(code: str) -> dict:
    return {'ok': False, 'error': code}


def _s(key: str, default=None):
    return settings_io.read().get(key, default)


def _key_for(provider: str) -> str:
    try:
        from features.qa.llm_processor import _load_api_key
        return _load_api_key(provider)
    except Exception:
        return ''


def _models(provider: str) -> list[dict]:
    try:
        from features.qa import model_fetcher
        return [{'id': mid, 'ctx': str(v.get('ctx', '?')), 'rpm': str(v.get('rpm', '?')), 'rpd': str(v.get('rpd', '?')), 'alias': str(v.get('alias') or '')}
                for mid, v in model_fetcher.get_models_for_ui(provider).items()]
    except Exception:
        _log.debug('model list failed', exc_info=True)
        return []


def _num(key: str, default, cast):
    try:
        v = _s(key)
        return cast(v) if v not in (None, '', 0) else default
    except (TypeError, ValueError):
        return default


def _routing() -> dict:
    """Backup provider and budget: what is switched on, today's counters against the daily limits, and the last time another provider answered."""
    from features.qa import ai_router
    st = settings_io.read()
    use = ai_router.usage()
    primary = 'google' if str(st.get('ai_provider', 'groq')).lower() == 'gemini' else str(st.get('ai_provider', 'groq')).lower()
    rows = []
    for pid in ai_router.ORDER:
        n = int(use['counts'].get(pid, 0))
        if n or pid == primary:
            t = use['tokens'].get(pid, {})
            rows.append({'id': pid, 'name': PROVIDERS[pid][0], 'count': n, 'tin': int(t.get('in', 0)), 'tout': int(t.get('out', 0)),
                         'limit': ai_router.daily_limit(pid, str(st.get('ai_model') or '') if pid == primary else '', st, primary)})
    days = []
    for back in range(13, -1, -1):                    # the last 14 days, empty days included, oldest first
        day = (date.today() - timedelta(days=back)).isoformat()
        by = {p: {k: int(v.get(k, 0)) for k in ('req', 'in', 'out')} for p, v in (use['history'].get(day) or {}).items() if p in PROVIDERS}
        days.append({'date': day, 'req': sum(v['req'] for v in by.values()), 'in': sum(v['in'] for v in by.values()), 'out': sum(v['out'] for v in by.values()), 'by': by})
    own = ai_router._limits(st)
    order = [p for p in ai_router.fallback_order(st, primary) if ai_router.has_key(p)]
    return {'fallback': {'enabled': bool(st.get('ai_fallback_enabled', True)), 'order': order},
            'budget': {'enabled': bool(st.get('ai_budget_enabled', False)), 'limit': own['req'], 'limit_in': own['in'], 'limit_out': own['out'], 'usage': rows, 'days': days, 'primary': primary},
            'last_switch': use.get('last_switch') or {}}


def get_state() -> dict:
    prov = str(_s('ai_provider', 'groq')).lower()
    prov = 'google' if prov == 'gemini' else prov
    if prov not in PROVIDERS:
        prov = 'groq'
    models = _models(prov)
    model = str(_s('ai_model', '') or '')
    return {'ok': True, 'provider': prov, 'model': model, 'models': models,
            'providers': [{'id': k, 'name': v[0], 'site': v[2], 'has_key': bool(_key_for(k)), 'needs_key': k not in NO_KEY_NEEDED} for k, v in PROVIDERS.items()],
            'local_url': str(_s('ai_local_base_url', '') or '') or DEFAULT_LOCAL_URL,
            'temperature': _num('ai_temperature', 0.3, float), 'max_tokens': _num('ai_max_tokens', 250, int), 'top_k': _num('ai_top_k', 40, int),
            **_routing(), 'web_search': bool(_s('ai_web_search_enabled', False)), 'models_all': bool(_s('ai_models_all', False)), 'mini_window': bool(_s('ai_mini_window', True))}


def _invalidate(provider: str | None) -> None:
    try:
        from features.qa.llm_processor import invalidate_clients
        invalidate_clients(provider)
    except Exception:
        _log.debug('invalidate_clients failed', exc_info=True)


def set_provider(pid: str) -> dict:
    pid = str(pid or '').lower()
    if pid not in PROVIDERS:
        return _bad('not_found')
    changes = {'ai_provider': pid}
    ids = [m['id'] for m in _models(pid)]
    if str(_s('ai_model', '') or '') not in ids:                  # the model of another provider means nothing here
        changes['ai_model'] = ids[0] if ids else ''
    return {'ok': True} if settings_io.update(changes) else _bad('write_failed')


def set_model(mid: str) -> dict:
    mid = str(mid or '').strip()
    if not _MODEL_RE.match(mid):
        return _bad('bad_value')
    return {'ok': True} if settings_io.update({'ai_model': mid}) else _bad('write_failed')


def key_save(provider: str, key: str) -> dict:
    provider, key = str(provider or '').lower(), str(key or '').strip()
    if provider not in PROVIDERS:
        return _bad('not_found')
    if not _KEY_RE.match(key):
        return _bad('bad_value')
    from actions.mail_client import _update_env_var
    env = PROVIDERS[provider][1]
    _update_env_var(env, key)
    os.environ[env] = key
    _invalidate(provider)
    return {'ok': True}


def key_clear(provider: str) -> dict:
    provider = str(provider or '').lower()
    if provider not in PROVIDERS:
        return _bad('not_found')
    from actions.mail_client import _update_env_var
    env = PROVIDERS[provider][1]
    _update_env_var(env, '')
    os.environ.pop(env, None)
    _invalidate(provider)
    return {'ok': True}


def set_local_url(url: str) -> dict:
    url = str(url or '').strip()
    if url and not (url.lower().startswith(('http://', 'https://')) and len(url) <= 300 and not any(c in url for c in ' \r\n\0')):
        return _bad('bad_value')
    if not settings_io.update({'ai_local_base_url': url}):
        return _bad('write_failed')
    _invalidate('local')
    return {'ok': True}


def set_params(data: dict) -> dict:
    """temperature 0..1, max_tokens 50..2000, top_k 1..100; only the keys present are changed."""
    rules = {'temperature': ('ai_temperature', 0.0, 1.0, lambda v: round(float(v), 2)), 'max_tokens': ('ai_max_tokens', 50, 2000, lambda v: int(round(float(v)))),
             'top_k': ('ai_top_k', 1, 100, lambda v: int(round(float(v))))}
    changes = {}
    for name, (key, lo, hi, cast) in rules.items():
        if name in data:
            try:
                v = cast(data[name])
            except (TypeError, ValueError):
                return _bad('bad_value')
            if not lo <= v <= hi:
                return _bad('bad_value')
            changes[key] = v
    if not changes:
        return _bad('bad_value')
    return {'ok': True} if settings_io.update(changes) else _bad('write_failed')


def set_flag(key: str, on) -> dict:
    return {'ok': True} if settings_io.update({key: bool(on)}) else _bad('write_failed')


def set_budget(data: dict) -> dict:
    """{on?: bool, limit?, limit_in?, limit_out?}: the limits mode and the daily limits for the chosen provider: requests (0 = the model catalog's), tokens sent, tokens received (0 = none)."""
    changes = {}
    if 'on' in data:
        changes['ai_budget_enabled'] = bool(data['on'])
    for name, key, top in (('limit', 'ai_daily_limit', 1_000_000), ('limit_in', 'ai_token_limit_in', 1_000_000_000), ('limit_out', 'ai_token_limit_out', 1_000_000_000)):
        if name in data:
            try:
                n = int(float(data[name]))
            except (TypeError, ValueError):
                return _bad('bad_value')
            if not 0 <= n <= top:
                return _bad('bad_value')
            changes[key] = n
    if not changes:
        return _bad('bad_value')
    return {'ok': True} if settings_io.update(changes) else _bad('write_failed')


def usage_reset() -> dict:
    from features.qa import ai_router
    ai_router.reset_usage()
    return {'ok': True}


def refresh(provider: str = '') -> dict:
    """Asks the provider for its model list and caches it (blocks up to the request timeout). The key is read here, never passed from the screen."""
    from features.qa import model_fetcher
    provider = str(provider or _s('ai_provider', 'groq')).lower()
    if provider not in PROVIDERS:
        return _bad('not_found')
    key = _key_for(provider)
    if not key and provider not in NO_KEY_NEEDED:
        return _bad('no_key')
    base = (str(_s('ai_local_base_url', '') or '') or DEFAULT_LOCAL_URL) if provider == 'local' else ''
    with _lock:
        ok = model_fetcher.fetch_and_cache(provider, key, base, show_all=bool(_s('ai_models_all', False)))
    return {'ok': True, 'count': len(_models(provider))} if ok else _bad('unreachable' if provider == 'local' else 'fetch_failed')


def test() -> dict:
    """One tiny request through the configured provider and model: shows that the key, the model and the connection work, and how long an answer takes."""
    from features.qa.llm_processor import _ask_llm_single
    prov = str(_s('ai_provider', 'groq')).lower()
    if prov not in PROVIDERS or (prov not in NO_KEY_NEEDED and not _key_for('google' if prov == 'gemini' else prov)):
        return _bad('no_key')
    t0 = time.time()
    try:
        reply = _ask_llm_single('проверка связи', 'Ответь одним словом: готов.', timeout=20, max_tokens=30)     # the chosen provider only: a backup must not hide a broken key
    except Exception:
        _log.debug('ai test failed', exc_info=True)
        return _bad('failed')
    ms = int((time.time() - t0) * 1000)
    text = str(reply or '').strip()
    return {'ok': True, 'ms': ms, 'reply': text[:120]} if text else {**_bad('empty'), 'ms': ms}


def run(data: dict) -> dict:
    """Entry of the `ai` bridge command: op `state` | `provider` {id} | `model` {id} | `key_save` {provider, key} | `key_clear` {provider} | `local_url` {url} | `params` {temperature?, max_tokens?, top_k?}
    | `web_search` {on} | `models_all` {on} | `fallback` {on} | `budget` {on?, limit?} | `usage_reset` | `mini_window` {on} | `refresh` {provider?} | `test`. A change answers with the fresh state; no answer ever contains a key."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return get_state()
    if op == 'test':
        return test()
    table = {'provider': lambda: set_provider(data.get('id')), 'model': lambda: set_model(data.get('id')), 'key_save': lambda: key_save(data.get('provider'), data.get('key')),
             'key_clear': lambda: key_clear(data.get('provider')), 'local_url': lambda: set_local_url(data.get('url')), 'params': lambda: set_params(data),
             'web_search': lambda: set_flag('ai_web_search_enabled', data.get('on')), 'models_all': lambda: set_flag('ai_models_all', data.get('on')), 'fallback': lambda: set_flag('ai_fallback_enabled', data.get('on')), 'budget': lambda: set_budget(data),
             'usage_reset': usage_reset, 'mini_window': lambda: set_flag('ai_mini_window', data.get('on')), 'refresh': lambda: refresh(data.get('provider', ''))}
    fn = table.get(op)
    if fn is None:
        return _bad('bad_op')
    res = fn()
    return {**get_state(), 'ok': True, **({'count': res['count']} if 'count' in res else {})} if res.get('ok') else res
