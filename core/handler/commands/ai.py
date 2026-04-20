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
            from ui import hud
            has_hud = hud._hud is not None
            
            try:
                # 1. Start streaming
                gen = search_answer(q, stream=True)
                full_ans = []
                buffer = ""
                
                # Sentence markers for TTS grouping
                marks = ('.', '!', '?', '\n')
                
                for chunk in gen:
                    if not chunk: continue
                    full_ans.append(chunk)
                    buffer += chunk
                    
                    # Update HUD (word-by-word/chunk-by-chunk)
                    if has_hud:
                        # Cumulative text for visual progress
                        curr_text = "".join(full_ans).strip()
                        # Limit HUD text length to avoid overflow, show last ~60 chars if long
                        display_text = curr_text if len(curr_text) < 65 else "..." + curr_text[-62:]
                        hud._hud.root.after(0, lambda t=display_text: hud._hud.show_msg_stream(t))
                    
                    # If we have a complete sentence, send it to TTS
                    if any(m in buffer for m in marks):
                        # Find the last mark to split
                        last_mark_pos = -1
                        for m in marks:
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
                    # Set up interactive follow-up
                    handler._set_interactive('qa_clarify', {'context': q, 'last_ans': final_ans}, timeout=30.0)
                else:
                    handler.speak('К сожалению, я не смог найти ответ на этот вопрос.')
                    if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)

            except Exception as e:
                print(f"[AI_STREAM] Error: {e}")
                handler.speak('Сэр, возникла ошибка при получении ответа от нейросети.')
                if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)

        threading.Thread(target=_task, daemon=True).start()
