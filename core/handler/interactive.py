import time
import threading
import subprocess
import os
import win32gui
import win32con
from core.speech import speak, stop_speaking, normalize_for_tts
from core.nlp import match_command, _normalize_stt
def handle_interactive(handler, text: str) -> dict:
    state = handler.interactive_state
    if isinstance(state, dict): state = state.get('type')
    data = handler.interactive_data
    text_lower = text.lower().strip()
    words = text_lower.split()
    global_cmd = match_command(text_lower)
    if global_cmd in ['game_mode_off', 'shutdown', 'guard_on', 'restart', 'guard_off']:
        handler._set_interactive(None)
        handler.handle(global_cmd, text_lower)
        return {'clear_state': True}
    res = {'clear_state': True}
    if state == 'work_confirm':
        if any(w in words for w in ['да', 'ага', 'давай', 'открой', 'конечно']):
            handler.play_response('loading')
            from actions.system import open_work
            open_work()
        elif any(w in words for w in ['нет', 'не', 'отмена', 'отмени', 'хватит']):
            handler.play_response('work_cancel')
        else: handler.play_response('work_cancel')
    elif state == 'video_monitor_select':
        from actions.screenshot import start_video_recording
        with_mic = handler.interactive_state.get('with_mic', False) if isinstance(handler.interactive_state, dict) else False
        monitors = handler.interactive_state.get('monitors', []) if isinstance(handler.interactive_state, dict) else []
        handler._set_interactive(None)
        mon_idx = 0
        if any(w in text_lower for w in ['основной', 'главный']):
            mon_idx = next((i for i, m in enumerate(monitors) if m.get('primary')), 0)
        elif any(w in text_lower for w in ['второй', '2']): mon_idx = 1
        elif any(w in text_lower for w in ['третий', '3']): mon_idx = 2
        if any(w in text_lower for w in ['отмена', 'нет']):
            speak('Запись отменена, сэр.')
        elif start_video_recording(with_mic, monitor_index=mon_idx)[0]:
            handler.play_response()
        return {'handled': True}
    elif state == 'game_watcher_suggest':
        yes_words = ['да', 'ага', 'давай', 'конечно', 'активируй', 'активирую', 'включай', 'включи', 'угу', 'ага']
        no_words = ['нет', 'не', 'отмена', 'не надо', 'забудь', 'отбой']
        profile = data.get('profile', '')
        name = data.get('name', '')
        if any(w in words for w in yes_words):
            handler._set_interactive(None)
            from .commands.game import apply_game_profile
            apply_game_profile(handler, profile, name)
        elif any(w in words for w in no_words):
            handler._set_interactive(None)
            speak('Хорошо, сэр.')
        else:
            res = {'new_state': 'game_watcher_suggest', 'new_data': data, 'timeout': 30.0}
    elif state == 'game_confirm':
        from features.gaming import GameInfo
        yes_words = [
            'да', 'ага', 'давай', 'запускай', 'запускаем', 'конечно', 'без проблем',
            'валяй', 'включай', 'активируй', 'активирую', 'джарвис', 'загружай', 'угу'
        ]
        no_words = ['нет', 'не', 'отмена', 'другую', 'не надо', 'забудь', 'отбой', 'ни в коем случае']
        if any(w in words for w in yes_words):
            handler._set_interactive(None)
            gi = GameInfo(name=data.get('game_name', ''), launcher='', launch_uri=data.get('game_uri', ''), install_dir=data.get('install_dir', ''))
            handler._launch_game_engine(gi)
            return res
        elif any(w in words for w in no_words):
            handler._set_interactive('game_specific', {'games': data.get('games', [])})
            speak('Хорошо, сэр. Во что именно вы хотите сыграть?')
            return res
        else:
            from features.gaming import fuzzy_find_game
            found = fuzzy_find_game(data.get('games', []), text_lower)
            if found:
                handler._set_interactive(None)
                speak(f'Принято, сэр. Запускаю {normalize_for_tts(found.name)}.')
                handler._launch_game_engine(found)
                return res
            else:
                speak('К сожалению, я не смог найти такую игру среди установленных.')
    elif state == 'qa_clarify':
        text_clean = _normalize_stt(text_lower)
        if text_clean.startswith('джарвис'): text_clean = text_clean[7:].strip()
        if text_clean.startswith('скажи'): text_clean = text_clean[5:].strip()
        while text_clean.startswith('а '): text_clean = text_clean[2:].strip()
        if any(w in text_clean.split() for w in ['отмена', 'стоп', 'спасибо']):
            handler.play_response(); return {'clear_state': True}
        if not text_clean or match_command(text_clean) == 'wake':
            handler.play_response('wake')
            return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 30.0}
        cmd = match_command(text_clean)
        if cmd and cmd != 'qa_search':
            handler._set_interactive(None)
            handler.handle(cmd, text_clean)
            return {'clear_state': True}
        from features.qa import search_answer, is_real_question
        context = data.get('context', '')
        last_ans = data.get('last_ans', '')
        if not is_real_question(text_clean):
            return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 30.0}
        handler.play_response('loading')
        try:
            from core.speech import warmup_tts
            warmup_tts()
        except Exception: pass
        # We now pass the user's new question and the previous turn directly.
        # The LLM prompt handles relevance and topic changes automatically.
        def _task():
            from ui import hud
            has_hud = hud._hud is not None
            try:
                gen = search_answer(text_clean, context=context, last_ans=last_ans, stream=True)
                full_ans = []
                buffer = ""
                marks = ('.', '!', '?', '\n')
                
                for chunk in gen:
                    if not chunk: continue
                    full_ans.append(chunk)
                    buffer += chunk
                    
                    if has_hud:
                        curr_text = "".join(full_ans).strip()
                        display_text = curr_text if len(curr_text) < 65 else "..." + curr_text[-62:]
                        hud._hud.root.after(0, lambda t=display_text: hud._hud.show_msg_stream(t))
                    
                    if any(m in buffer for m in marks):
                        last_mark_pos = -1
                        for m in marks:
                            pos = buffer.rfind(m)
                            if pos > last_mark_pos: last_mark_pos = pos
                        if last_mark_pos != -1:
                            sentence = buffer[:last_mark_pos+1].strip()
                            buffer = buffer[last_mark_pos+1:].strip()
                            if sentence: handler.speak(sentence)

                if buffer.strip():
                    handler.speak(buffer.strip())
                
                final_ans = "".join(full_ans).strip()
                if final_ans:
                    if has_hud: hud._hud.root.after(2000, hud._hud.hide_msg_stream)
                    handler._set_interactive('qa_clarify', {'context': text_clean, 'last_ans': final_ans}, timeout=30.0)
                else:
                    speak('Извините, не удалось найти информацию.')
                    if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)
            except Exception as e:
                print(f"[QA_CLARIFY_STREAM] Error: {e}")
                speak('Извините, произошла ошибка.')
                if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)

        threading.Thread(target=_task, daemon=True).start()
        return {'handled': True}
    
    if res.get('clear_state'): handler._set_interactive(None)
    elif 'new_state' in res: handler._set_interactive(res['new_state'], res.get('new_data'), res.get('timeout', 60.0))
    return res
