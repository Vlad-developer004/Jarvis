import threading
from features.qa import search_answer
def handle_ai(handler, cmd, text_lower, amount):
    if cmd == 'qa_search':
        q = text_lower.replace('джарвис', '').replace('скажи', '').replace('мне', '').strip()
        if not q:
            handler.play_response('wake')
            handler._set_interactive('qa_clarify', {'context': ''}, timeout=30.0)
            return
        handler.play_response('loading')
        try:
            from core.speech import warmup_tts
            warmup_tts()
        except Exception:
            pass
        def _task():
            ans = search_answer(q)
            if ans:
                handler.speak(ans)
                handler._set_interactive('qa_clarify', {'context': q}, timeout=30.0)
            else:
                handler.speak('К сожалению, я не смог найти ответ на этот вопрос.')
        threading.Thread(target=_task, daemon=True).start()
