"""Question detection, system prompt, message building and history trimming for features.qa.llm_processor (moved out unchanged)."""

from core.safe import swallow as _swallow
import re as _re

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
    'найди', 'объясни', 'поищи', 'расскажи', 'подробнее', 'почему',
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
    try:
        from features.planetbase.knowledge import prompt_context
        game_ctx = prompt_context()
    except Exception:
        game_ctx = ''
    return game_ctx + (
        f'Ты — J.A.R.V.I.S., лаконичный и остроумный ИИ-ассистент Тони Старка. '
        f'Отвечай на языке: {lang_name}, кратко (1-3 предложения), по существу, вежливо и уверенно. '
        f'Если новый вопрос не связан с прошлой темой разговора — игнорируй прошлый контекст.\n'
        f'Формат ответа: первая строка "[Subject: <тема ВОПРОСА НИЖЕ, именительный падеж, '
        f'{lang_name}>]", затем с новой строки — сам ответ (тема в этом шаблоне условная, '
        f'не копируй её, бери тему из реального вопроса).\n'
        f'Для TTS изредка можно: *слово* — выделить одно слово в предложении (не больше '
        f'одного на предложение), <break time="300ms"/> — одна пауза на весь ответ. '
        f'Больше никакой разметки (markdown, теги, списки).'
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

def _build_messages(topic: str, question: str, last_ans: str, history: list[dict] = None) -> list[dict]:
    if history:
        return history + [{'role': 'user', 'content': question}]
    if topic and last_ans:
        return [
            {'role': 'user', 'content': topic},
            {'role': 'assistant', 'content': last_ans},
            {'role': 'user', 'content': question},
        ]
    prompt = f'Тема: «{topic}». Вопрос: «{question}»' if topic and question else (question or topic)
    return [{'role': 'user', 'content': prompt}]

# ---------------------------------------------------------------------------
# Follow-up conversation history — real multi-turn memory for the qa_search /
# qa_clarify flow (core/handler/interactive.py's _state_qa_clarify), instead
# of the single-previous-turn topic/last_ans reconstruction above (kept only
# as a fallback for callers that don't pass history). Bounded to 85% of the
# current model's own context window rather than a fixed turn count, since
# that window ranges from ~4k (a small local model) to 100k+ (cloud) — a
# fixed cap would either waste most of a big model's window or overflow a
# small one.
# ---------------------------------------------------------------------------
_DEFAULT_CTX_TOKENS = 8192  # unknown model (not in the cached catalog) — conservative

_HISTORY_BUDGET_FRACTION = 0.85

def _estimate_tokens(text: str) -> int:
    return max(1, len(text or '') // 4)  # rough chars/4 heuristic, no tokenizer dependency

def _parse_ctx_tokens(ctx_str: str) -> int | None:
    """Reverses model_fetcher._fmt_ctx's '131.1k'/'2M'/'4096' formatting back
    to an integer token count."""
    if not ctx_str:
        return None
    s = ctx_str.strip().lower()
    try:
        if s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        return int(s)
    except ValueError:
        return None

def _get_model_ctx_tokens(provider: str, model: str) -> int:
    try:
        from features.qa.model_fetcher import _cache_path, _load_json
        cache = _load_json(_cache_path())
        for m in cache.get(provider, {}).get('models', []):
            if m.get('id') == model:
                return _parse_ctx_tokens(m.get('ctx', '')) or _DEFAULT_CTX_TOKENS
    except Exception:
        _swallow()
    return _DEFAULT_CTX_TOKENS

def _trim_history(history: list[dict], provider: str, model: str, question: str,
                   sys_prompt: str, reply_budget: int) -> list[dict]:
    """Drops the oldest (user, assistant) turns until the estimated prompt
    size fits _HISTORY_BUDGET_FRACTION of the model's context window, leaving
    room for the new question and the reply. Always keeps at least the most
    recent turn, even if that alone doesn't fit — better than answering with
    zero memory of a conversation that's clearly still going."""
    if not history:
        return history
    budget = int(_get_model_ctx_tokens(provider, model) * _HISTORY_BUDGET_FRACTION)
    reserved = _estimate_tokens(sys_prompt) + _estimate_tokens(question) + reply_budget
    trimmed = list(history)
    while len(trimmed) > 2:
        used = reserved + sum(_estimate_tokens(m['content']) for m in trimmed)
        if used <= budget:
            break
        trimmed = trimmed[2:]  # drop the oldest (user, assistant) pair
    return trimmed

def _max_tokens(question: str) -> int:
    # Previously 220/140 — a factual "расскажи про X" answer about anything
    # with actual substance (a public figure, a historical event) routinely
    # ran past 140-220 tokens despite the system prompt asking for 1-3
    # sentences, so the reply got hard-cut mid-word rather than mid-thought.
    q_low = (question or '').lower()
    return 380 if any(p in q_low for p in _QUESTION_PHRASES) else 220
