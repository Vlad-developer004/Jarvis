"""Which AI service answers: the chosen one, a backup when it fails, and a daily request budget.

`llm_processor.ask_llm` hands every question to `ask()` here. The chain is the provider from the settings first, then (if "backup provider" is on) the other providers that have a key, then the
local server if its address is set. A provider is skipped when the budget mode is on and today's requests have reached its daily limit; a provider that gives no answer is replaced by the next one.
When the answer comes from another provider than the chosen one, and the question came from the voice assistant (`announce`), Jarvis says so once.

Settings (jarvis_settings.json): ai_fallback_enabled (default True), ai_fallback_order (list of provider ids; default: those with a key), ai_budget_enabled (default False),
ai_daily_limit (0 = take the limit from the model catalog, else requests per day for the chosen provider), ai_token_limit_in / ai_token_limit_out (tokens per day sent / received, 0 = no limit, chosen provider).
Counters (requests and estimated tokens, today and the last 30 days) live in ai_usage.json next to the settings. Tokens are estimated from the text (about 3 characters each), not read from the provider.
"""
from __future__ import annotations

import itertools
import json
import os
import threading
import time
from datetime import date

from core.logging_setup import get_logger

_log = get_logger('qa.router')
_lock = threading.Lock()
MAX_CHAIN = 3
HISTORY_DAYS = 30
FALLBACK_TIMEOUT = 8
WARN_AT = 0.8
ORDER = ('groq', 'openai', 'google', 'deepseek', 'anthropic', 'openrouter', 'local')
NAMES = {'groq': 'Groq', 'openai': 'OpenAI', 'google': 'Google', 'deepseek': 'DeepSeek', 'anthropic': 'Anthropic', 'openrouter': 'OpenRouter', 'local': 'локальный сервер'}


def _settings() -> dict:
    try:
        from core import settings_io
        return settings_io.read()
    except Exception:
        return {}


def _usage_path() -> str:
    from core import settings_io
    return os.path.join(os.path.dirname(settings_io._path()), 'ai_usage.json')


def usage() -> dict:
    """Today's counters: {'date', 'counts': {provider: n}, 'warned': [provider], 'last_switch': {...}}; a new day starts from zero."""
    try:
        with open(_usage_path(), 'r', encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    today = date.today().isoformat()
    if d.get('date') != today:
        d = {'date': today, 'counts': {}, 'tokens': {}, 'warned': [], 'last_switch': d.get('last_switch') or {}, 'history': d.get('history') or {}}
    d.setdefault('counts', {})
    d.setdefault('tokens', {})
    d.setdefault('warned', [])
    d.setdefault('history', {})
    return d


def _limits(st: dict) -> dict:
    """The user's own daily limits for the chosen provider: {'req', 'in', 'out'}; 0 = none."""
    def n(key):
        try:
            return max(0, int(st.get(key) or 0))
        except (TypeError, ValueError):
            return 0
    return {'req': n('ai_daily_limit'), 'in': n('ai_token_limit_in'), 'out': n('ai_token_limit_out')}


def estimate_tokens(text: str) -> int:
    try:
        from features.qa.llm_processor import _estimate_tokens
        return int(_estimate_tokens(text))
    except Exception:
        return max(1, len(text) // 3) if text else 0


def _input_text(kwargs: dict) -> str:
    parts = [str(kwargs.get('sys_prompt') or ''), str(kwargs.get('topic') or ''), str(kwargs.get('question') or ''), str(kwargs.get('last_ans') or '')]
    for h in kwargs.get('history') or []:
        parts.append(str(h.get('content', '')) if isinstance(h, dict) else str(h))
    return ' '.join(p for p in parts if p)


def _tally(gen, done):
    """Passes a stream through and reports the estimated size of what was received when it ends (or is dropped)."""
    got = []
    try:
        for piece in gen:
            got.append(piece)
            yield piece
    finally:
        done(estimate_tokens(''.join(got)))


def _save_usage(d: dict) -> None:
    try:
        path = _usage_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
    except OSError:
        _log.debug('usage not saved', exc_info=True)


def reset_usage() -> None:
    with _lock:
        d = usage()
        d['counts'], d['tokens'], d['warned'] = {}, {}, []
        d['history'].pop(d['date'], None)
        _save_usage(d)


def _norm(pid: str) -> str:
    pid = str(pid or '').lower()
    return 'google' if pid == 'gemini' else pid


def has_key(pid: str) -> bool:
    if pid == 'local':
        return bool(str(_settings().get('ai_local_base_url') or '').strip())      # no key needed; "configured" means the user gave an address
    try:
        from features.qa.llm_processor import _load_api_key
        return bool(_load_api_key(pid))
    except Exception:
        return False


def daily_limit(pid: str, model: str, st: dict | None = None, primary: str = '') -> int:
    """Requests per day for a provider: the user's own number for the chosen provider, else the catalog value for its model; 0 = unknown / unlimited (local)."""
    st = st if st is not None else _settings()
    if pid == 'local':
        return 0
    try:
        own = int(st.get('ai_daily_limit') or 0)
    except (TypeError, ValueError):
        own = 0
    if own > 0 and pid == (primary or _norm(st.get('ai_provider', 'groq'))):
        return own
    try:
        from features.qa import model_fetcher
        rpd = model_fetcher.get_models_for_ui(pid).get(model or '', {}).get('rpd')
        return int(str(rpd).replace(',', '').replace(' ', '')) if rpd is not None else 0
    except Exception:
        return 0


def fallback_order(st: dict, primary: str) -> list[str]:
    raw = st.get('ai_fallback_order')
    order = [_norm(x) for x in raw] if isinstance(raw, list) and raw else [p for p in ORDER]
    return [p for p in order if p in NAMES and p != primary]


def chain(st: dict | None = None) -> list[tuple[str, str]]:
    """[(provider, model)] in the order they are tried; the chosen one first with its model, the backups with their own default model."""
    st = st if st is not None else _settings()
    primary = _norm(st.get('ai_provider', 'groq'))
    out = [(primary, str(st.get('ai_model') or ''))]
    if st.get('ai_fallback_enabled', True):
        out += [(p, '') for p in fallback_order(st, primary) if has_key(p)]
    return out[:MAX_CHAIN + 1]


def _announce(key: str, **fmt) -> None:
    try:
        from core.engine.jarvis import get_engine
        from core.responses import spk
        eng = get_engine()
        if eng is not None:
            eng.handler.speak(spk(key, **fmt), persist=False)
    except Exception:
        _log.debug('announce failed', exc_info=True)


def _got_answer(res, stream: bool):
    """(ok, result): a stream is checked by its first piece, which is then put back."""
    if not stream:
        return bool(res and str(res).strip()), res
    try:
        first = next(res)
    except StopIteration:
        return False, iter([])
    except Exception:
        return False, iter([])
    return True, itertools.chain([first], res)


def ask(single, announce: bool, stream: bool, kwargs: dict):
    """Runs `single(**kwargs, _force=(provider, model))` along the chain; returns the first real answer (or the empty result of the last attempt)."""
    st = _settings()
    candidates = chain(st)
    primary = candidates[0][0]
    budget = bool(st.get('ai_budget_enabled', False))
    pool = candidates
    if budget:
        use = usage()
        lim = _limits(st)

        def used_up(p, m):
            cap = daily_limit(p, m, st, primary)
            if cap and use['counts'].get(p, 0) >= cap:
                return True
            t = use['tokens'].get(p, {})
            return p == primary and any(lim[k] and t.get(k, 0) >= lim[k] for k in ('in', 'out'))
        open_ = [(p, m) for p, m in candidates if not used_up(p, m)]
        pool = open_ or candidates[:1]                    # everything is used up: still try the chosen one, the service itself decides
    empty = iter([]) if stream else ''
    for n, (pid, model) in enumerate(pool):
        kw = dict(kwargs)
        if n > 0 and kw.get('timeout'):
            kw['timeout'] = min(kw['timeout'], FALLBACK_TIMEOUT)
        try:
            ok, res = _got_answer(single(**kw, _force=(pid, model)), stream)
        except Exception:
            _log.debug('provider %s failed', pid, exc_info=True)
            ok, res = False, empty
        if not ok:
            continue
        tin = estimate_tokens(_input_text(kwargs))
        if stream:
            res = _tally(res, lambda tout, pid=pid, model=model, tin=tin: _count(pid, st, primary, model, budget, announce, tin, tout))
        else:
            _count(pid, st, primary, model, budget, announce, tin, estimate_tokens(str(res)))
        if pid != primary:
            reason = 'limit' if primary not in [p for p, _ in pool] else 'error'
            _switched(primary, pid, reason, announce)
        return res
    return empty


def _count(pid: str, st: dict, primary: str, model: str, budget: bool, announce: bool, tin: int = 0, tout: int = 0) -> None:
    warns = []
    with _lock:
        d = usage()
        d['counts'][pid] = int(d['counts'].get(pid, 0)) + 1
        t = d['tokens'].setdefault(pid, {'in': 0, 'out': 0})
        t['in'], t['out'] = int(t.get('in', 0)) + tin, int(t.get('out', 0)) + tout
        day = d['history'].setdefault(d['date'], {}).setdefault(pid, {'req': 0, 'in': 0, 'out': 0})
        day['req'], day['in'], day['out'] = day['req'] + 1, day['in'] + tin, day['out'] + tout
        for old in sorted(d['history'])[:-HISTORY_DAYS]:
            d['history'].pop(old, None)
        if budget:
            lim = _limits(st)
            checks = [('req', d['counts'][pid], daily_limit(pid, model, st, primary), 'запросов'), ('in', t['in'], lim['in'] if pid == primary else 0, 'токенов на вход'),
                      ('out', t['out'], lim['out'] if pid == primary else 0, 'токенов на выход')]
            for kind, val, cap, what in checks:
                if cap and val >= cap * WARN_AT and f'{pid}:{kind}' not in d['warned']:
                    d['warned'].append(f'{pid}:{kind}')
                    warns.append((val, cap, what))
        _save_usage(d)
    if warns and announce:
        val, cap, what = warns[0]
        _announce('ai.budget_warn', n=val, limit=cap, what=what, provider=NAMES.get(pid, pid))


def _switched(frm: str, to: str, reason: str, announce: bool) -> None:
    with _lock:
        d = usage()
        d['last_switch'] = {'from': frm, 'to': to, 'reason': reason, 'at': int(time.time())}
        _save_usage(d)
    _log.info('AI answer from %s instead of %s (%s)', to, frm, reason)
    if announce:
        _announce('ai.switched_limit' if reason == 'limit' else 'ai.switched_error', frm=NAMES.get(frm, frm), to=NAMES.get(to, to))
