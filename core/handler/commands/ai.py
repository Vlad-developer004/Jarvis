import threading
from features.qa import search_answer
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('ai')
def handle_ai(handler, cmd, text_lower, amount):
    if cmd == 'qa_search':
        q = text_lower.replace('джарвис', '').replace('скажи', '').replace('мне', '').strip()
        if not q:
            handler.play_response('wake')
            handler._set_interactive('qa_clarify', {'context': ''}, timeout=30.0)
            return

        handler.play_response('loading')
        try:
            from ui.hud_ai_window import cancel_hide_ai_window
            cancel_hide_ai_window()
        except Exception:
            pass
        # Set interactive state immediately so follow-up questions during TTS playback are caught
        handler._set_interactive('qa_clarify', {'context': q, 'last_ans': ''}, timeout=120.0)
        try:
            from core.speech import warmup_tts
            warmup_tts()
        except Exception:
            pass

        def _task():
            from ui import hud
            has_hud = hud._hud is not None
            
            try:
                # 1. Start streaming
                from features.qa.llm_processor import wrap_llm_stream
                from ui.hud_ai_window import show_ai_window, update_ai_window_text, hide_ai_window
                
                active_subject = [""]
                def _on_sub(sub):
                    active_subject[0] = sub
                    show_ai_window(sub)

                # Show the window immediately with a neutral placeholder title
                # (not the raw question — a long question snapping to a short
                # subject a moment later reads as a visible glitch). The model
                # is asked to prefix its answer with [Subject: ...] (see
                # get_sys_prompt()) so _on_sub can upgrade the title once
                # that's parsed, but it doesn't always do so (especially on
                # short/follow-up answers) — without this call the window
                # simply never appeared for that turn. fetch_image=False since
                # there's nothing meaningful to look up for the placeholder.
                show_ai_window('J.A.R.V.I.S.', fetch_image=False)

                raw_gen = search_answer(q, stream=True)
                gen = wrap_llm_stream(raw_gen, on_subject_found=_on_sub)
                
                full_ans = []
                buffer = ""
                
                # Sentence markers for TTS grouping
                marks = ('.', '!', '?', '\n')
                
                for chunk in gen:
                    if not chunk: continue
                    full_ans.append(chunk)
                    buffer += chunk
                    
                    curr_text = "".join(full_ans).strip()
                    update_ai_window_text(curr_text)
                    
                    # Update HUD (word-by-word/chunk-by-chunk)
                    if has_hud:
                        # Limit HUD text length to avoid overflow, show last ~60 chars if long
                        display_text = curr_text if len(curr_text) < 65 else "..." + curr_text[-62:]
                        hud._hud.root.after(0, lambda t=display_text: hud._hud.show_msg_stream(t))
                    
                    # If buffer is long, allow splitting at commas/semicolons/dashes to speak faster
                    active_marks = marks
                    if len(buffer) > 40:
                        active_marks = marks + (',', ';', '—')
                        
                    if any(m in buffer for m in active_marks):
                        # Find the last mark to split
                        last_mark_pos = -1
                        for m in active_marks:
                            pos = buffer.rfind(m)
                            if pos > last_mark_pos: last_mark_pos = pos
                        
                        if last_mark_pos != -1:
                            sentence = buffer[:last_mark_pos+1].strip()
                            buffer = buffer[last_mark_pos+1:].strip()
                            if sentence:
                                handler.speak(sentence)
                
                # Send remaining buffer
                if buffer.strip():
                    handler.speak(buffer.strip())
                
                final_ans = "".join(full_ans).strip()
                if final_ans:
                    # Finalize visual state
                    if has_hud:
                        hud._hud.root.after(2000, hud._hud.hide_msg_stream)
                    hide_ai_window(delay_ms=5000)
                    # Set up interactive follow-up
                    next_context = active_subject[0] if active_subject[0] else q
                    handler._set_interactive('qa_clarify', {'context': next_context, 'last_ans': final_ans}, timeout=30.0)
                else:
                    handler.speak(spk('ai.no_answer'))
                    if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)
                    hide_ai_window(delay_ms=0)
 
            except Exception as e:
                _log.error(f"[AI_STREAM] Error: {e}")
                handler.speak(spk('ai.error'))
                if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)
                hide_ai_window(delay_ms=0)

        threading.Thread(target=_task, daemon=True).start()
