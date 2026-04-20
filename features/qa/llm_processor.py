import os
import re as _re
import threading

# Clients cache
_clients = {}
_lock = threading.Lock()

def _load_api_key(provider: str) -> str:
    """Find API key for specified provider in env or secrets.env files."""
    env_map = {
        'groq': 'GROQ_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'gemini': 'GOOGLE_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY'
    }
    key_name = env_map.get(provider.lower(), 'GROQ_API_KEY')
    
    val = os.environ.get(key_name, '')
    if val: return val
    
    import sys
    search_paths = []
    if hasattr(sys, 'frozen'):
        search_paths.append(os.path.join(os.path.dirname(sys.executable), '.env'))
        search_paths.append(os.path.join(os.path.dirname(sys.executable), 'secrets.env'))
    search_paths.append(os.path.abspath('.env'))
    search_paths.append(os.path.abspath('secrets.env'))
    appdata = os.environ.get('APPDATA', '') or os.environ.get('LOCALAPPDATA', '')
    if appdata:
        search_paths.append(os.path.join(appdata, 'Jarvis', 'secrets.env'))
        
    for env_path in search_paths:
        try:
            if os.path.exists(env_path):
                with open(env_path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f'{key_name}='):
                            return line[len(f'{key_name}='):].strip().strip('"').strip("'")
        except Exception: pass
    return ''

def _log_qa(msg: str):
    try:
        os.makedirs('logs', exist_ok=True)
        with open('logs/qa.log', 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            print(f"[QA] {msg}") # Console output for faster debugging
    except: pass

def _clean(text: str) -> str:
    text = _re.sub(r'\*\*?|__?|~~|`{1,3}', '', text)
    text = _re.sub(r'\n{2,}', ' ', text)
    text = _re.sub(r'\s{2,}', ' ', text).strip()
    return text

_FILLER = {
    'да', 'нет', 'ну', 'ок', 'окей', 'хорошо', 'ладно', 'понятно', 'ясно',
    'пожалуйста', 'стоп', 'хватит', 'подожди', 'погоди', 'всё',
    'отлично', 'супер', 'класс', 'хм', 'ааа', 'эм', 'ну да', 'конечно',
    'поняла', 'ага', 'угу', 'нее', 'неет'
}

_QUESTION_WORDS = {
    'кто такой', 'зачем', 'как', 'когда', 'где', 'кто', 'что', 'куда', 'откуда',
    'какой', 'какая', 'какие', 'какое', 'чем', 'кем', 'чего', 'сколько',
    'найди', 'объясни', 'поищи',
}
_QUESTION_PHRASES = ('кто такой', 'что такое', 'расскажи о')

def is_real_question(text: str) -> bool:
    text = text.strip().lower()
    words = text.split()
    if len(words) < 2: return False
    if text in _FILLER or all(w in _FILLER for w in words): return False
    if any(p in text for p in _QUESTION_PHRASES): return True
    if any(w in _QUESTION_WORDS for w in words): return True
    content_words = [w for w in words if len(w) >= 4 and w not in _FILLER]
    return len(content_words) >= 2

def ask_llm(topic: str, question: str, timeout: int = 10, last_ans: str = '', stream: bool = False):
    """Universal entry point for QA, uses settings to determine provider and model.
    If stream=True, returns a generator of text chunks.
    """
    try:
        import json
        settings_path = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, encoding='utf-8') as f:
                settings = json.load(f)
        else: settings = {}
    except Exception: settings = {}

    provider = settings.get('ai_provider', 'groq').lower()
    model = settings.get('ai_model', '')
    
    params = {
        'topic': topic,
        'question': question,
        'model': model,
        'timeout': timeout,
        'last_ans': last_ans,
        'stream': stream
    }

    if provider == 'groq':
        params['model'] = model or 'llama-3.3-70b-versatile'
        return ask_groq(**params)
    elif provider == 'openai':
        params['model'] = model or 'gpt-4o-mini'
        return ask_openai(**params)
    elif provider in ('google', 'gemini'):
        params['model'] = model or 'gemini-1.5-flash'
        return ask_gemini(**params)
    elif provider == 'deepseek':
        params['model'] = model or 'deepseek-chat'
        return ask_deepseek(**params)
    elif provider == 'anthropic':
        params['model'] = model or 'claude-3-5-sonnet-latest'
        return ask_anthropic(**params)
    
    return ask_groq(topic, question, 'llama-3.3-70b-versatile', timeout, last_ans, stream=stream)

def get_sys_prompt():
    return (
        'Ты — J.A.R.V.I.S., лаконичный и профессиональный ИИ-ассистент. '
        'Отвечай максимально кратко (1-3 предложения), по существу, '
        'в стиле Тони Старка: вежливо, но уверенно. Используй русский язык. '
        'Если вопрос пользователя не связан с предыдущей темой разговора, просто ответь на новый вопрос, '
        'игнорируя предыдущий контекст разговора.'
    )

def ask_groq(topic: str, question: str, model: str, timeout: int = 8, last_ans: str = '', stream: bool = False):
    global _clients
    api_key = _load_api_key('groq')
    if not api_key: 
        if stream: return iter([])
        return ''
    try:
        with _lock:
            if 'groq' not in _clients:
                from groq import Groq
                _clients['groq'] = Groq(api_key=api_key)
        
        q_low = (question or '').lower()
        max_toks = 220 if any(p in q_low for p in _QUESTION_PHRASES) else 140
        
        messages = [{'role': 'system', 'content': get_sys_prompt()}]
        if topic and last_ans:
            messages.extend([
                {'role': 'user', 'content': topic},
                {'role': 'assistant', 'content': last_ans},
                {'role': 'user', 'content': question}
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            messages.append({'role': 'user', 'content': prompt})

        if stream:
            def _gen():
                try:
                    completion = _clients['groq'].chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_toks,
                        temperature=0.3,
                        timeout=timeout,
                        stream=True
                    )
                    for chunk in completion:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            # Minimal cleaning for stream to preserve punctuation
                            yield delta.replace('\n', ' ')
                except Exception as e:
                    _log_qa(f"Groq Stream Error: {e}")
            return _gen()

        completion = _clients['groq'].chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_toks,
            temperature=0.3,
            timeout=timeout
        )
        text = completion.choices[0].message.content.strip()
        return _clean(text) if text else ''
    except Exception as e:
        import traceback
        _log_qa(f"Groq Error: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
        if stream: return iter([])
        return ''

def ask_openai(topic: str, question: str, model: str, timeout: int = 12, last_ans: str = '', stream: bool = False):
    global _clients
    api_key = _load_api_key('openai')
    if not api_key:
        if stream: return iter([])
        return ''
    try:
        with _lock:
            if 'openai' not in _clients:
                from openai import OpenAI
                _clients['openai'] = OpenAI(api_key=api_key)
        
        messages = [{'role': 'system', 'content': get_sys_prompt()}]
        if topic and last_ans:
            messages.extend([
                {'role': 'user', 'content': topic},
                {'role': 'assistant', 'content': last_ans},
                {'role': 'user', 'content': question}
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            messages.append({'role': 'user', 'content': prompt})

        if stream:
            def _gen():
                try:
                    completion = _clients['openai'].chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=250,
                        temperature=0.4,
                        timeout=timeout,
                        stream=True
                    )
                    for chunk in completion:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content.replace('\n', ' ')
                except Exception as e:
                    _log_qa(f"OpenAI Stream Error: {e}")
            return _gen()

        completion = _clients['openai'].chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=250,
            temperature=0.4,
            timeout=timeout
        )
        text = completion.choices[0].message.content.strip()
        return _clean(text) if text else ''
    except Exception as e:
        _log_qa(f"OpenAI Error: {type(e).__name__}: {str(e)}")
        if stream: return iter([])
        return ''

def ask_deepseek(topic: str, question: str, model: str, timeout: int = 12, last_ans: str = '', stream: bool = False):
    global _clients
    api_key = _load_api_key('deepseek')
    if not api_key:
        if stream: return iter([])
        return ''
    try:
        with _lock:
            if 'deepseek' not in _clients:
                from openai import OpenAI
                _clients['deepseek'] = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        messages = [{'role': 'system', 'content': get_sys_prompt()}]
        if topic and last_ans:
            messages.extend([
                {'role': 'user', 'content': topic},
                {'role': 'assistant', 'content': last_ans},
                {'role': 'user', 'content': question}
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            messages.append({'role': 'user', 'content': prompt})

        if stream:
            def _gen():
                try:
                    completion = _clients['deepseek'].chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=250,
                        temperature=0.4,
                        timeout=timeout,
                        stream=True
                    )
                    for chunk in completion:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content.replace('\n', ' ')
                except Exception as e:
                    _log_qa(f"DeepSeek Stream Error: {e}")
            return _gen()

        completion = _clients['deepseek'].chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=250,
            temperature=0.4,
            timeout=timeout
        )
        text = completion.choices[0].message.content.strip()
        return _clean(text) if text else ''
    except Exception as e:
        _log_qa(f"DeepSeek Error: {type(e).__name__}: {str(e)}")
        if stream: return iter([])
        return ''

def ask_gemini(topic: str, question: str, model: str, timeout: int = 12, last_ans: str = '', stream: bool = False):
    global _clients
    api_key = _load_api_key('google')
    if not api_key:
        if stream: return iter([])
        return ''
    try:
        with _lock:
            if 'google' not in _clients:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                _clients['google'] = genai.GenerativeModel(
                    model_name=model,
                    system_instruction=get_sys_prompt()
                )
        
        contents = []
        if topic and last_ans:
            contents.extend([
                {'role': 'user', 'parts': [topic]},
                {'role': 'model', 'parts': [last_ans]},
                {'role': 'user', 'parts': [question]}
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            contents.append({'role': 'user', 'parts': [prompt]})

        if stream:
            def _gen():
                try:
                    response = _clients['google'].generate_content(
                        contents,
                        generation_config={"max_output_tokens": 250, "temperature": 0.4},
                        stream=True
                    )
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text.replace('\n', ' ')
                except Exception as e:
                    _log_qa(f"Gemini Stream Error: {e}")
            return _gen()

        response = _clients['google'].generate_content(
            contents,
            generation_config={"max_output_tokens": 250, "temperature": 0.4}
        )
        return _clean(response.text) if response.text else ''
    except Exception as e:
        _log_qa(f"Gemini Error: {type(e).__name__}: {str(e)}")
        if stream: return iter([])
        return ''

def ask_anthropic(topic: str, question: str, model: str, timeout: int = 15, last_ans: str = '', stream: bool = False):
    global _clients
    api_key = _load_api_key('anthropic')
    if not api_key:
        if stream: return iter([])
        return ''
    try:
        with _lock:
            if 'anthropic' not in _clients:
                import anthropic
                _clients['anthropic'] = anthropic.Anthropic(api_key=api_key)
        
        messages = []
        if topic and last_ans:
            messages.extend([
                {"role": "user", "content": topic},
                {"role": "assistant", "content": last_ans},
                {"role": "user", "content": question}
            ])
        else:
            prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
            messages.append({"role": "user", "content": prompt})

        if stream:
            def _gen():
                try:
                    with _clients['anthropic'].messages.stream(
                        model=model,
                        max_tokens=250,
                        temperature=0.4,
                        system=get_sys_prompt(),
                        messages=messages,
                        timeout=timeout
                    ) as stream_ctx:
                        for text in stream_ctx.text_stream:
                            yield text.replace('\n', ' ')
                except Exception as e:
                    _log_qa(f"Anthropic Stream Error: {e}")
            return _gen()

        message = _clients['anthropic'].messages.create(
            model=model,
            max_tokens=250,
            temperature=0.4,
            system=get_sys_prompt(),
            messages=messages,
            timeout=timeout
        )
        return _clean(message.content[0].text) if message.content else ''
    except Exception as e:
        import traceback
        _log_qa(f"Anthropic Error: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
        if stream: return iter([])
        return ''

def check_relevance(topic: str, question: str) -> bool:
    # Always return True or implement relevance check for all providers if needed.
    # For now, let's keep it simple using Groq if available as it was the previous default.
    return True

def unload_qa():
    """Unload resources and free memory for the QA module."""
    global _clients
    with _lock:
        _clients.clear()
    import gc
    gc.collect()
