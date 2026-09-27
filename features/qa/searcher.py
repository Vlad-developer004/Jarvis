from .llm_processor import ask_llm

def search_answer(query: str, raw_query: str='', context: str='', last_ans: str='', stream: bool = False,
                   history: list[dict] = None):
    if not query or len(query) < 2:
        if stream: return iter([])
        return ''

    # Check if this is an old call with piped context
    # (fallback for safety though we removed this from interactive.py)
    full_q = raw_query if raw_query else query
    if not context and ' | ' in full_q:
        parts = full_q.split(' | ', 1)
        context, query = parts[0].strip(), parts[1].strip()

    try:
        return ask_llm(topic=context, question=query, last_ans=last_ans, stream=stream, history=history)
    except Exception: pass
    
    if stream: return iter([])
    return ''
