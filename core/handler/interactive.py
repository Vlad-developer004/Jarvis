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
        while text_clean.startswith('а '): text_clean = text_clean[2:].strip()
        if any(w in text_clean.split() for w in ['отмена', 'стоп', 'спасибо']):
            handler.play_response(); return {'clear_state': True}
        if not text_clean or match_command(text_clean) == 'wake':
            handler.play_response('wake')
            return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 25.0}
        cmd = match_command(text_clean)
        if cmd and cmd != 'qa_search':
            handler._set_interactive(None)
            handler.handle(cmd, text_clean)
            return {'clear_state': True}
        from features.qa import search_answer, is_real_question, check_relevance
        context = data.get('context', '')
        if not is_real_question(text_clean):
            return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 20.0}
        is_independent = False
        prefixes = ['что такое', 'кто такой', 'расскажи о', 'почему', 'как', 'где', 'когда']
        for p in prefixes:
            if text_clean.startswith(p):
                is_independent = True; break
        if not is_independent and context:
            if not check_relevance(context, text_clean): is_independent = True
        query = text_clean if is_independent else context
        raw_query = text_clean if is_independent else f"{context} | {text_clean}"
        handler.play_response('loading')
        answer = search_answer(query, raw_query=raw_query)
        if answer:
            handler.speak(answer)
            res = {'new_state': 'qa_clarify', 'new_data': {'context': text_clean if is_independent else context}, 'timeout': 20.0}
        else:
            speak('Извините, не удалось найти информацию.')
    if res.get('clear_state'): handler._set_interactive(None)
    elif 'new_state' in res: handler._set_interactive(res['new_state'], res.get('new_data'), res.get('timeout', 60.0))
    return res
