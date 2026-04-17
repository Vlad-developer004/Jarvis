from .llm_processor import ask_groq
def search_answer(query: str, raw_query: str='') -> str:
    if not query or len(query) < 2: return ''
    full_q = raw_query if raw_query else query
    try:
        ctx_part, question_part = '', ''
        if ' | ' in full_q:
            parts = full_q.split(' | ', 1)
            ctx_part, question_part = parts[0].strip(), parts[1].strip()
            full_q = ctx_part + ' ' + question_part
        llm_answer = ask_groq(topic=ctx_part, question=full_q)
        if llm_answer: return llm_answer
    except Exception: pass
    return ''
