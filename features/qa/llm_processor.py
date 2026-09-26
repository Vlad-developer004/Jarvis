import json
import os
import re as _re
import threading
import time

from core.logging_setup import get_logger

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
            pass
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


def _clean(text: str) -> str:
    text = _re.sub(r'\*\*?|__?|~~|`{1,3}', '', text)
    text = _re.sub(r'\n{2,}', ' ', text)
    text = _re.sub(r'\s{2,}', ' ', text).strip()
    return text


_FILLER = {
    'да', 'нет', 'ну', 'ок', 'окей', 'хорошо', 'ладно', 'понятно', 'ясно',
    'пожалуйста', 'стоп', 'хватит', 'подожди', 'погоди', 'всё',
    'отлично', 'супер', 'класс', 'хм', 'ааа', 'эм', 'ну да', 'конечно',
    'поняла', 'ага', 'угу', 'нее', 'неет',
}

_QUESTION_WORDS = {
    'кто такой', 'зачем', 'как', 'когда', 'где', 'кто', 'что', 'куда', 'откуда',
    'какой', 'какая', 'какие', 'какое', 'чем', 'кем', 'чего', 'сколько',
    'найди', 'объясни', 'поищи', 'расскажи', 'подробнее', 'почему', 'зачем',
}
_QUESTION_PHRASES = (
    'кто такой', 'что такое', 'расскажи о', 'расскажи про',
    'подробнее о', 'а если', 'а как',
)


def is_real_question(text: str) -> bool:
    text = text.strip().lower()
    words = text.split()
    if len(words) < 2:
        return False
    if text in _FILLER or all(w in _FILLER for w in words):
        return False
    if any(p in text for p in _QUESTION_PHRASES):
        return True
    if any(w in _QUESTION_WORDS for w in words):
        return True
    content_words = [w for w in words if len(w) >= 4 and w not in _FILLER]
    return len(content_words) >= 2


def get_sys_prompt() -> str:
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'
    lang_name = 'украинский' if lang == 'uk' else 'русский'
    return (
        f'КРИТИЧЕСКОЕ ПРАВИЛО: Начни свой ответ строго со строки вида: '
        f'[Subject: <главный субъект/объект вопроса в именительном падеже на языке {lang_name}>], '
        f'после чего сделай перенос строки и пиши сам ответ. '
        f'Пример начала ответа:\n[Subject: Тони Старк]\nТони Старк — это...\n\n'
        f'Ты — J.A.R.V.I.S., лаконичный и профессиональный ИИ-ассистент, созданный Тони Старком. '
        f'Обязательно отвечай на языке: {lang_name}. '
        f'Отвечай максимально кратко (1-3 предложения), строго по существу, '
        f'в стиле Тони Старка: вежливо, остроумно, но уверенно. '
        f'Если вопрос пользователя не связан с предыдущей темой разговора, отвечай на новый вопрос, '
        f'игнорируя предыдущий контекст. '
        f'Твой ответ озвучивается голосом (TTS), поэтому можешь изредка использовать разметку для '
        f'более живого звучания: *слово* — выделить голосом одно ключевое слово в предложении '
        f'(не более одного на предложение), <break time="300ms"/> — короткая драматическая пауза '
        f'(не более одной на весь ответ). Используй это только когда это действительно уместно, '
        f'не в каждом ответе. Не используй никакую другую разметку (markdown, теги, списки).'
    )


def wrap_llm_stream(generator, on_subject_found):
    """Strip [Subject: ...] prefix from streaming LLM response.

    Calls on_subject_found(subject) once the subject tag is parsed,
    then yields clean text chunks.
    """
    buffer = ''
    prefix_parsed = False
    subject_extracted = False

    for chunk in generator:
        if not chunk:
            continue

        if not prefix_parsed:
            buffer += chunk
            if ']' in buffer:
                start_idx = buffer.find('[Subject:')
                end_idx = buffer.find(']')
                if start_idx != -1 and end_idx > start_idx:
                    subject = buffer[start_idx + len('[Subject:'):end_idx].strip()
                    if on_subject_found and not subject_extracted:
                        subject_extracted = True
                        on_subject_found(subject)
                    rest = buffer[end_idx + 1:].lstrip()
                    prefix_parsed = True
                    buffer = ''
                    if rest:
                        yield rest
                else:
                    prefix_parsed = True
                    yield buffer
                    buffer = ''
            elif len(buffer) > 120:
                prefix_parsed = True
                yield buffer
                buffer = ''
        else:
            yield chunk

    if buffer:
        yield buffer


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_messages(topic: str, question: str, last_ans: str) -> list[dict]:
    if topic and last_ans:
        return [
            {'role': 'user', 'content': topic},
            {'role': 'assistant', 'content': last_ans},
            {'role': 'user', 'content': question},
        ]
    prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
    return [{'role': 'user', 'content': prompt}]


def _max_tokens(question: str) -> int:
    q_low = (question or '').lower()
    return 220 if any(p in q_low for p in _QUESTION_PHRASES) else 140


# ---------------------------------------------------------------------------
# Universal entry point
# ---------------------------------------------------------------------------

def ask_llm(topic: str, question: str, timeout: int = 10, last_ans: str = '', stream: bool = False, sys_prompt: str = '', max_tokens: int = 0):
    """Route a QA request to the configured LLM provider.

    If stream=True, returns a generator of text chunks.
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
    # 0/None means "use this provider's own default" everywhere below —
    # only overridden once the user actually touches the sliders in
    # settings_tabs/modules/premium_view.py.
    temperature = settings.get('ai_temperature')
    user_max_tokens = settings.get('ai_max_tokens')
    if user_max_tokens:
        max_tokens = int(user_max_tokens)
    top_k = settings.get('ai_top_k') or None  # only meaningful for 'local' (see _ask_openai_compat)

    params = dict(topic=topic, question=question, model=model,
                  timeout=timeout, last_ans=last_ans, stream=stream, sys_prompt=sys_prompt,
                  max_tokens=max_tokens, temperature=temperature)

    if provider == 'groq':
        if model == 'llama-3.1-405b-reasoning':
            model = 'llama-3.3-70b-versatile'
        params['model'] = model or 'llama-3.3-70b-versatile'
        return _ask_openai_compat('groq', **params)
    elif provider == 'openai':
        params['model'] = model or 'gpt-4o-mini'
        return _ask_openai_compat('openai', **params)
    elif provider in ('google', 'gemini'):
        params['model'] = model or 'gemini-1.5-flash'
        return ask_gemini(**params)
    elif provider == 'deepseek':
        params['model'] = model or 'deepseek-chat'
        return _ask_openai_compat('deepseek', **params)
    elif provider == 'anthropic':
        params['model'] = model or 'claude-3-5-sonnet-latest'
        return ask_anthropic(**params)
    elif provider == 'openrouter':
        params['model'] = model or 'deepseek/deepseek-chat'
        return _ask_openai_compat('openrouter', **params)
    elif provider == 'local':
        # Self-hosted OpenAI-compatible server (Ollama, llama.cpp's
        # llama-server, TabbyAPI, ...) — same /v1/chat/completions contract
        # as the cloud providers above, only the base_url is user-configured
        # instead of a fixed constant (see settings_tabs/modules/premium_view.py).
        base_url = (settings.get('ai_local_base_url') or '').strip() or 'http://localhost:11434/v1'
        params['model'] = model or 'local-model'
        return _ask_openai_compat('local', base_url_override=base_url, top_k=top_k, **params)

    params['model'] = 'llama-3.3-70b-versatile'
    return _ask_openai_compat('groq', **params)


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
        'default_max_tokens': 140,
        'default_timeout': 8,
    },
    'openai': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': None,
        'extra_headers': {},
        'default_max_tokens': 250,
        'default_timeout': 12,
    },
    'deepseek': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': 'https://api.deepseek.com',
        'extra_headers': {},
        'default_max_tokens': 250,
        'default_timeout': 12,
    },
    'openrouter': {
        'lib': 'openai', 'cls': 'OpenAI',
        'base_url': 'https://openrouter.ai/api/v1',
        'extra_headers': {
            'HTTP-Referer': 'https://github.com/vlad-developer/jarvis',
            'X-Title': 'J.A.R.V.I.S. HUD',
        },
        'default_max_tokens': 300,
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
        'default_max_tokens': 250,
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
        messages.extend(_build_messages(topic, question, last_ans))
        max_toks = max_tokens if max_tokens > 0 else (_max_tokens(question) if provider == 'groq' else cfg['default_max_tokens'])
        tout = timeout or cfg['default_timeout']

        req_kwargs: dict = dict(model=model, messages=messages, timeout=tout)
        if _needs_openai_reasoning_params(provider, model):
            req_kwargs['max_completion_tokens'] = max_toks
        else:
            req_kwargs['max_tokens'] = max_toks
            req_kwargs['temperature'] = temperature if temperature is not None else 0.3
        if top_k is not None and provider == 'local':
            # Not part of the OpenAI schema — only actually honored by
            # local inference servers (llama.cpp/Ollama/TabbyAPI), which
            # accept extra sampling fields in the request body.
            req_kwargs['extra_body'] = {'top_k': top_k}

        if stream:
            def _gen():
                try:
                    with client.chat.completions.with_streaming_response.create(
                        stream=True, **req_kwargs,
                    ) as raw:
                        try:
                            _capture_rate_limit_headers(provider, model, raw.headers)
                        except Exception:
                            pass
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
            pass
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
               temperature: float = None):
    api_key = _load_api_key('google')
    if not api_key:
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
        if topic and last_ans:
            contents.extend([
                {'role': 'user', 'parts': [topic]},
                {'role': 'model', 'parts': [last_ans]},
                {'role': 'user', 'parts': [question]},
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            contents.append({'role': 'user', 'parts': [prompt]})

        gen_cfg = {'max_output_tokens': max_tokens if max_tokens > 0 else 250,
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
                  temperature: float = None):
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

        messages = list(_build_messages(topic, question, last_ans))
        temp = temperature if temperature is not None else 0.4

        if stream:
            def _gen():
                try:
                    with client.messages.stream(
                        model=model, max_tokens=max_tokens if max_tokens > 0 else 250, temperature=temp,
                        system=sys_prompt or get_sys_prompt(), messages=messages, timeout=timeout,
                    ) as stream_ctx:
                        for text in stream_ctx.text_stream:
                            yield text.replace('\n', ' ')
                except Exception as e:
                    _log.error('Anthropic stream error: %s', e)
            return _gen()

        message = client.messages.create(
            model=model, max_tokens=max_tokens if max_tokens > 0 else 250, temperature=temp,
            system=sys_prompt or get_sys_prompt(), messages=messages, timeout=timeout,
        )
        return _clean(message.content[0].text) if message.content else ''
    except Exception as e:
        import traceback
        _log.error('Anthropic error: %s: %s\n%s', type(e).__name__, e, traceback.format_exc())
        return iter([]) if stream else ''

