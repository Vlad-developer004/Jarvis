import json
import os
import re as _re
import threading
import time

from core.logging_setup import get_logger
from core.safe import swallow as _swallow
from features.qa.llm_keys import (  # noqa: F401
    _api_key_cache, _clients, _load_api_key, _load_api_key_uncached, _lock, _log, invalidate_clients,
)
from features.qa.llm_prompt import (  # noqa: F401
    _DEFAULT_CTX_TOKENS, _FILLER, _HISTORY_BUDGET_FRACTION, _QUESTION_PHRASES, _QUESTION_WORDS, _build_messages, _clean, _estimate_tokens, _get_model_ctx_tokens, _max_tokens, _parse_ctx_tokens, _trim_history, get_sys_prompt, is_real_question, wrap_llm_stream,
)






















# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------















# ---------------------------------------------------------------------------
# Universal entry point
# ---------------------------------------------------------------------------

def ask_llm(topic: str, question: str, timeout: int = 10, last_ans: str = '', stream: bool = False, sys_prompt: str = '', max_tokens: int = 0, history: list[dict] = None, announce: bool = False):
    """Answer a question through the chosen provider, with a backup provider and the daily budget (features/qa/ai_router.py).

    `announce=True` (the voice assistant's own questions) lets Jarvis say aloud that another provider answered."""
    from . import ai_router
    kwargs = dict(topic=topic, question=question, timeout=timeout, last_ans=last_ans, stream=stream, sys_prompt=sys_prompt, max_tokens=max_tokens, history=history)
    return ai_router.ask(_ask_llm_single, announce, stream, kwargs)


def _ask_llm_single(topic: str, question: str, timeout: int = 10, last_ans: str = '', stream: bool = False, sys_prompt: str = '', max_tokens: int = 0, history: list[dict] = None, _force: tuple = None):
    """Route a QA request to the configured LLM provider (`_force` = (provider, model) replaces the configured one).


    If stream=True, returns a generator of text chunks.

    history, when given (see core/handler/interactive.py's qa_clarify follow-
    up flow), carries the REAL prior turns of this conversation rather than
    just the single previous topic/answer — trimmed to fit the current
    model's own context window (see _trim_history) before being sent.
    """
    try:
        import json
        from config_pack.config import get_settings_path
        settings_path = get_settings_path()
        if os.path.exists(settings_path):
            with open(settings_path, encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}
    except Exception:
        settings = {}

    provider = settings.get('ai_provider', 'groq').lower()
    model = settings.get('ai_model', '')
    if _force:
        provider, model = _force[0].lower(), _force[1]
    # 0/None means "use this provider's own default" everywhere below —
    # only overridden once the user actually touches the sliders in
    # settings_tabs/modules/premium_view.py.
    temperature = settings.get('ai_temperature')
    user_max_tokens = settings.get('ai_max_tokens')
    if user_max_tokens:
        max_tokens = int(user_max_tokens)
    top_k = settings.get('ai_top_k') or None  # only meaningful for 'local' (see _ask_openai_compat)
    use_native_search = bool(settings.get('ai_web_search_enabled', False))

    params = dict(topic=topic, question=question, model=model,
                  timeout=timeout, last_ans=last_ans, stream=stream, sys_prompt=sys_prompt,
                  max_tokens=max_tokens, temperature=temperature)

    def _with_history(p: str, m: str) -> dict:
        params['history'] = _trim_history(history, p, m, question, sys_prompt or get_sys_prompt(),
                                           reply_budget=max_tokens or 400)
        return params

    if provider == 'groq':
        if model == 'llama-3.1-405b-reasoning':
            model = 'llama-3.3-70b-versatile'
        params['model'] = model or 'llama-3.3-70b-versatile'
        return _ask_openai_compat('groq', **_with_history('groq', params['model']))
    elif provider == 'openai':
        if use_native_search:
            # Only these two OpenAI models actually run a real web search per
            # request (see _ask_openai_compat's native_search branch) — no
            # client-side tool loop, OpenAI does the search itself. Picking
            # one overrides whatever chat model was configured, same as the
            # user switching models manually — cheaper mini variant unless
            # they already explicitly chose the full one.
            params['model'] = model if model == 'gpt-4o-search-preview' else 'gpt-4o-mini-search-preview'
            return _ask_openai_compat('openai', native_search=True, **_with_history('openai', params['model']))
        params['model'] = model or 'gpt-4o-mini'
        return _ask_openai_compat('openai', **_with_history('openai', params['model']))
    elif provider in ('google', 'gemini'):
        params['model'] = model or 'gemini-1.5-flash'
        return ask_gemini(**_with_history('google', params['model']))
    elif provider == 'deepseek':
        params['model'] = model or 'deepseek-chat'
        return _ask_openai_compat('deepseek', **_with_history('deepseek', params['model']))
    elif provider == 'anthropic':
        params['model'] = model or 'claude-3-5-sonnet-latest'
        return ask_anthropic(**_with_history('anthropic', params['model']))
    elif provider == 'openrouter':
        # No native_search here — OpenRouter has no per-request search flag
        # of its own; a user who wants live search picks an already-search-
        # grounded model from the catalog (e.g. perplexity/sonar) instead.
        params['model'] = model or 'deepseek/deepseek-chat'
        return _ask_openai_compat('openrouter', **_with_history('openrouter', params['model']))
    elif provider == 'local':
        # Self-hosted OpenAI-compatible server (Ollama, llama.cpp's
        # llama-server, TabbyAPI, ...) — same /v1/chat/completions contract
        # as the cloud providers above, only the base_url is user-configured
        # instead of a fixed constant (see settings_tabs/modules/premium_view.py).
        base_url = (settings.get('ai_local_base_url') or '').strip() or 'http://localhost:11434/v1'
        params['model'] = model or 'local-model'
        return _ask_openai_compat('local', base_url_override=base_url, top_k=top_k,
                                   **_with_history('local', params['model']))

    params['model'] = 'llama-3.3-70b-versatile'
    return _ask_openai_compat('groq', **_with_history('groq', params['model']))


# ---------------------------------------------------------------------------
# Live rate-limit capture — opportunistic, from real response headers
# ---------------------------------------------------------------------------
# RPM is account/tier-specific and none of these providers expose it via a
# models-listing endpoint — the only place it ever shows up is the
# "x-ratelimit-limit-requests" response header OpenAI and Groq both send on
# every actual chat completion. So instead of a static guess in
# data/model_limits.json going stale the moment someone's usage tier
# changes, capture it here after a real call and let
# model_fetcher.get_models_for_ui() prefer this over the static file.
_live_limits_lock = threading.Lock()


def _live_limits_path() -> str:
    # Reuse model_fetcher's own data-dir resolution (not config_pack's) so
    # both modules agree on the exact same path in both dev and frozen
    # (PyInstaller) builds — they resolve "data/" slightly differently.
    from features.qa.model_fetcher import _data_dir
    return os.path.join(_data_dir(), 'model_live_limits.json')


def _capture_rate_limit_headers(provider: str, model: str, headers) -> None:
    try:
        rpm = int(headers.get('x-ratelimit-limit-requests', ''))
    except (TypeError, ValueError):
        return
    path = _live_limits_path()
    with _live_limits_lock:
        try:
            data = {}
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
            data[f'{provider}:{model}'] = {'rpm': rpm, 'captured_at': int(time.time())}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.warning('Failed to persist live rate limit for %s: %s', provider, e)


# ---------------------------------------------------------------------------
# OpenAI-compatible providers  (Groq, OpenAI, DeepSeek, OpenRouter)
# ---------------------------------------------------------------------------

_OPENAI_COMPAT: dict[str, dict] = {
    'groq': {
        'lib': 'groq', 'cls': 'Groq',
        'base_url': None,
        'extra_headers': {},
        'default_max_tokens': 220,
        'default_timeout': 8,
    },
    'openai': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': None,
        'extra_headers': {},
        'default_max_tokens': 350,
        'default_timeout': 12,
    },
    'deepseek': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': 'https://api.deepseek.com',
        'extra_headers': {},
        'default_max_tokens': 350,
        'default_timeout': 12,
    },
    'openrouter': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': 'https://openrouter.ai/api/v1',
        'extra_headers': {
            'HTTP-Referer': 'https://github.com/vlad-developer/jarvis',
            'X-Title': 'J.A.R.V.I.S. HUD',
        },
        'default_max_tokens': 400,
        'default_timeout': 15,
    },
    'local': {
        # Ollama / llama.cpp's llama-server / TabbyAPI all speak the same
        # OpenAI-compatible /v1 API — 'base_url' is None here because,
        # unlike the cloud providers above, it's not a fixed constant: the
        # actual address (host:port chosen by the user) comes in per-call
        # via base_url_override, read from settings in ask_llm().
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': None,
        'extra_headers': {},
        'default_max_tokens': 350,
        'default_timeout': 20,  # local inference can be slower than cloud
    },
}


def _get_openai_compat_client(provider: str, api_key: str, base_url_override: str = None):
    """Return cached client, recreating it if the API key or (for 'local',
    where it's user-editable) the base_url changed."""
    cfg = _OPENAI_COMPAT[provider]
    cache_key = f'{provider}:{base_url_override}' if base_url_override else provider
    with _lock:
        entry = _clients.get(cache_key)
        if entry and entry[1] == api_key:
            return entry[0]
        # Key/URL changed or first call — (re)create client.
        lib = __import__(cfg['lib'])
        cls = getattr(lib, cfg['cls'])
        kwargs: dict = {'api_key': api_key}
        eff_base_url = base_url_override or cfg['base_url']
        if eff_base_url:
            kwargs['base_url'] = eff_base_url
        if cfg['extra_headers']:
            kwargs['default_headers'] = cfg['extra_headers']
        client = cls(**kwargs)
        _clients[cache_key] = (client, api_key, None)
        return client


def prewarm() -> None:
    """Builds the configured cloud provider's client before the first question: the library import alone is ~1 s. Does nothing without a key, with
    the QA module off, or for a local/Gemini provider; sends no request."""
    try:
        from core.system import module_enabled
        if not module_enabled('qa'):
            return
        from features.qa import ai_router
        provider = ai_router.chain()[0][0]
        if provider not in _OPENAI_COMPAT or provider == 'local':
            return
        api_key = _load_api_key(provider)
        if api_key:
            _get_openai_compat_client(provider, api_key)
    except Exception:
        _swallow()


_OPENAI_REASONING_RE = _re.compile(r'^o\d+(-mini|-preview|-pro)?$')


def _needs_openai_reasoning_params(provider: str, model: str) -> bool:
    """True only for OpenAI's actual o-series reasoning endpoints (o1, o3,
    o4-mini, ...), which reject `temperature`/`top_p` outright (400 error)
    and require `max_completion_tokens` instead of `max_tokens`. Other
    providers hosting reasoning-flavored models (DeepSeek's
    deepseek-reasoner, Groq's deepseek-r1-distill-*) accept the normal
    OpenAI-compatible params fine — temperature is just ignored there, not
    rejected — so this is intentionally narrow to OpenAI's o-series, not a
    general "is this a reasoning model" flag."""
    if provider != 'openai':
        return False
    return bool(_OPENAI_REASONING_RE.match((model or '').lower()))


def _is_openai_search_preview(provider: str, model: str) -> bool:
    """True for OpenAI's gpt-4o(-mini)-search-preview — these run a real web
    search on OpenAI's side per request (no client-side tool loop needed),
    but like the o-series reasoning models they reject sampling params
    outright (400: 'incompatible request arguments... temperature, top_p,
    frequency_penalty, presence_penalty'), just for an unrelated reason."""
    return provider == 'openai' and (model or '').endswith('-search-preview')


def _ask_openai_compat(
    provider: str,
    topic: str,
    question: str,
    model: str,
    timeout: int = 10,
    last_ans: str = '',
    stream: bool = False,
    sys_prompt: str = '',
    max_tokens: int = 0,
    base_url_override: str = None,
    temperature: float = None,
    top_k: int = None,
    native_search: bool = False,
    history: list[dict] = None,
):
    cfg = _OPENAI_COMPAT[provider]
    api_key = _load_api_key(provider)
    if not api_key:
        if provider == 'local':
            api_key = 'not-needed'  # OpenAI client requires a non-empty string; local servers ignore it
        else:
            return iter([]) if stream else ''

    try:
        client = _get_openai_compat_client(provider, api_key, base_url_override)
        messages = [{'role': 'system', 'content': sys_prompt or get_sys_prompt()}]
        messages.extend(_build_messages(topic, question, last_ans, history=history))
        max_toks = max_tokens if max_tokens > 0 else (_max_tokens(question) if provider == 'groq' else cfg['default_max_tokens'])
        tout = timeout or cfg['default_timeout']

        req_kwargs: dict = dict(model=model, messages=messages, timeout=tout)
        if _needs_openai_reasoning_params(provider, model):
            req_kwargs['max_completion_tokens'] = max_toks
        else:
            req_kwargs['max_tokens'] = max_toks
            if not _is_openai_search_preview(provider, model):
                req_kwargs['temperature'] = temperature if temperature is not None else 0.3
        if top_k is not None and provider == 'local':
            # Not part of the OpenAI schema — only actually honored by
            # local inference servers (llama.cpp/Ollama/TabbyAPI), which
            # accept extra sampling fields in the request body.
            req_kwargs['extra_body'] = {'top_k': top_k}
        if native_search:
            # Model itself runs the search server-side; empty dict = default
            # search context size, no extra config needed for our use case.
            req_kwargs['web_search_options'] = {}

        if stream:
            def _gen():
                try:
                    with client.chat.completions.with_streaming_response.create(
                        stream=True, **req_kwargs,
                    ) as raw:
                        try:
                            _capture_rate_limit_headers(provider, model, raw.headers)
                        except Exception:
                            _swallow()
                        for chunk in raw.parse():
                            delta = chunk.choices[0].delta.content
                            if delta:
                                yield delta.replace('\n', ' ')
                except Exception as e:
                    _log.error('%s stream error: %s', provider, e)
            return _gen()

        raw = client.chat.completions.with_raw_response.create(**req_kwargs)
        try:
            _capture_rate_limit_headers(provider, model, raw.headers)
        except Exception:
            _swallow()
        completion = raw.parse()
        text = completion.choices[0].message.content.strip()
        return _clean(text) if text else ''
    except Exception as e:
        _log.error('%s error: %s: %s', provider, type(e).__name__, e)
        return iter([]) if stream else ''


# ---------------------------------------------------------------------------
# Gemini  (model is passed per-request, not at construction time)
# ---------------------------------------------------------------------------

def ask_gemini(topic: str, question: str, model: str, timeout: int = 12,
               last_ans: str = '', stream: bool = False, sys_prompt: str = '', max_tokens: int = 0,
               temperature: float = None, history: list[dict] = None):
    api_key = _load_api_key('google')
    if not api_key:
        return iter([]) if stream else ''
    from core.optional_pkgs import ensure
    if not ensure('gemini'):        # the SDK is not in the installer: fetched on first use
        return iter([]) if stream else ''
    try:
        import google.generativeai as genai

        with _lock:
            entry = _clients.get('google')
            # Recreate if key or model changed.
            _active_sys = sys_prompt or get_sys_prompt()
            if not entry or entry[1] != api_key or entry[2] != model or (len(entry) > 3 and entry[3] != _active_sys):
                genai.configure(api_key=api_key)
                client = genai.GenerativeModel(
                    model_name=model,
                    system_instruction=_active_sys,
                )
                _clients['google'] = (client, api_key, model, _active_sys)
            else:
                client = entry[0]

        contents: list[dict] = []
        if history:
            # Gemini's SDK uses 'model' where OpenAI-style history says
            # 'assistant' — same (question, answer) pairs, different label.
            contents.extend({'role': ('model' if m['role'] == 'assistant' else 'user'),
                              'parts': [m['content']]} for m in history)
            contents.append({'role': 'user', 'parts': [question]})
        elif topic and last_ans:
            contents.extend([
                {'role': 'user', 'parts': [topic]},
                {'role': 'model', 'parts': [last_ans]},
                {'role': 'user', 'parts': [question]},
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            contents.append({'role': 'user', 'parts': [prompt]})

        gen_cfg = {'max_output_tokens': max_tokens if max_tokens > 0 else 350,
                   'temperature': temperature if temperature is not None else 0.4}

        if stream:
            def _gen():
                try:
                    response = client.generate_content(contents, generation_config=gen_cfg, stream=True)
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text.replace('\n', ' ')
                except Exception as e:
                    _log.error('Gemini stream error: %s', e)
            return _gen()

        response = client.generate_content(contents, generation_config=gen_cfg)
        return _clean(response.text) if response.text else ''
    except Exception as e:
        _log.error('Gemini error: %s: %s', type(e).__name__, e)
        return iter([]) if stream else ''


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def ask_anthropic(topic: str, question: str, model: str, timeout: int = 15,
                  last_ans: str = '', stream: bool = False, sys_prompt: str = '', max_tokens: int = 0,
                  temperature: float = None, history: list[dict] = None):
    api_key = _load_api_key('anthropic')
    if not api_key:
        return iter([]) if stream else ''
    try:
        with _lock:
            entry = _clients.get('anthropic')
            if not entry or entry[1] != api_key:
                import anthropic as _ant
                client = _ant.Anthropic(api_key=api_key)
                _clients['anthropic'] = (client, api_key, None)
            else:
                client = entry[0]

        messages = list(_build_messages(topic, question, last_ans, history=history))
        temp = temperature if temperature is not None else 0.4

        if stream:
            def _gen():
                try:
                    with client.messages.stream(
                        model=model, max_tokens=max_tokens if max_tokens > 0 else 350, temperature=temp,
                        system=sys_prompt or get_sys_prompt(), messages=messages, timeout=timeout,
                    ) as stream_ctx:
                        for text in stream_ctx.text_stream:
                            yield text.replace('\n', ' ')
                except Exception as e:
                    _log.error('Anthropic stream error: %s', e)
            return _gen()

        message = client.messages.create(
            model=model, max_tokens=max_tokens if max_tokens > 0 else 350, temperature=temp,
            system=sys_prompt or get_sys_prompt(), messages=messages, timeout=timeout,
        )
        return _clean(message.content[0].text) if message.content else ''
    except Exception as e:
        import traceback
        _log.error('Anthropic error: %s: %s\n%s', type(e).__name__, e, traceback.format_exc())
        return iter([]) if stream else ''

