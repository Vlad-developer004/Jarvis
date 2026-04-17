import os
import re as _re
_groq_client = None
def _load_groq_key() -> str:
    val = os.environ.get('GROQ_API_KEY', '')
    if val: return val
    appdata = os.environ.get('APPDATA', '') or os.environ.get('LOCALAPPDATA', '')
    env_path = os.path.join(appdata, 'Jarvis', 'secrets.env') if appdata else os.path.abspath('.env')
    try:
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('GROQ_API_KEY='):
                    return line[len('GROQ_API_KEY='):].strip().strip('"').strip("'")
    except Exception:
        pass
    try:
        with open(os.path.abspath('.env'), encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('GROQ_API_KEY='):
                    return line[len('GROQ_API_KEY='):].strip().strip('"').strip("'")
    except Exception:
        pass
    return ''
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
def ask_groq(topic: str, question: str, timeout: int = 8) -> str:
    global _groq_client
    api_key = _load_groq_key()
    if not api_key: return ''
    prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
    try:
        if _groq_client is None:
            from groq import Groq
            _groq_client = Groq(api_key=api_key)
        q_low = (question or '').lower()
        max_toks = 220 if any(p in q_low for p in ('кто такой', 'что такое', 'расскажи о')) else 140
        completion = _groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Ты — J.A.R.V.I.S., лаконичный и профессиональный ИИ-ассистент. '
                        'Отвечай максимально кратко (1-3 предложения), по существу, '
                        'в стиле Тони Старка: вежливо, но уверенно. Используй русский язык.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=max_toks,
            temperature=0.3,
        )
        text = completion.choices[0].message.content.strip()
        return _clean(text) if text else ''
    except Exception: return ''
def check_relevance(topic: str, question: str) -> bool:
    global _groq_client
    api_key = _load_groq_key()
    if not api_key or not topic or not question: return True
    try:
        if _groq_client is None:
            from groq import Groq
            _groq_client = Groq(api_key=api_key)
        prompt = f'Topic: "{topic}"\nQuestion: "{question}"\nIs this question related to the topic? Answer only YES or NO.'
        completion = _groq_client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': 'You are a relevance classifier. Answer only YES or NO.'},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=5,
            temperature=0.0,
        )
        answer = completion.choices[0].message.content.strip().upper()
        return 'YES' in answer
    except Exception: return False
