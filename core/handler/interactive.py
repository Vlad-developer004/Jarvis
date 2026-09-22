import time
import threading
from core.speech import speak, normalize_for_tts
from core.nlp import _normalize_stt
from core.logging_setup import get_logger as _get_logger
from core.address import get_address as _ga
_log = _get_logger('interactive')
# States that expect an explicit yes/no answer — semantic Layer 0 confirm intercept must be active.
_YES_NO_STATES = frozenset({'game_watcher_suggest', 'game_confirm', 'work_confirm', 'llm_action_confirm'})

_CANCEL_WORDS = ['отмена', 'стоп', 'не надо', 'отбой']
_CANCEL_WORDS_EXT = _CANCEL_WORDS + ['забудь']

def _sem_cmd(text: str, is_waiting_answer: bool = False) -> str:
    """Classify text into an intent string.

    When is_waiting_answer=True the semantic classifier's Layer 0 intercepts
    confirmation words ('да', 'нет', …) before the neural path, returning
    'confirm_yes' / 'confirm_no' / 'confirm_cancel'.
    """
    try:
        from core.engine.recognition import _sem_parse
        parsed = _sem_parse(text, is_waiting_answer=is_waiting_answer)
        if parsed:
            return parsed[0][0] or ''
    except Exception:
        pass
    try:
        from core.nlp.semantic import classify_intent
        return classify_intent(text, is_waiting_answer=is_waiting_answer) or ''
    except Exception:
        pass
    try:
        from core.nlp import match_command
        return match_command(text) or ''
    except Exception:
        return ''

def _check_cancel(handler, text_lower, cancel_words=_CANCEL_WORDS):
    if any(w in text_lower for w in cancel_words):
        handler._set_interactive(None)
        handler.play_response()
        return True
    return False

def _state_work_select(handler, text_lower, words, data, global_cmd):
    if any(w in words for w in ['нет', 'не', 'отмена', 'отбой', 'хватит', 'стоп']):
        handler._set_interactive(None)
        speak(f'Хорошо, {_ga()}.')
        return {'clear_state': True}
    from actions.dev_projects import find_project_by_name, open_project
    from core.responses import spk
    project = find_project_by_name(text_lower)
    if project:
        handler._set_interactive(None)
        ok, err = open_project(project)
        if ok:
            speak(spk('work.open_selected', name=project['name']))
        else:
            speak(spk('work.error'))
            _log.error('open_project failed: %s', err)
        return {'clear_state': True}
    else:
        # Keep state alive — let user try again with correct name
        speak(spk('work.not_found'))
        return {'clear_state': False}

def _state_work_confirm(handler, text_lower, words, data, global_cmd):
    _is_yes = global_cmd == 'confirm_yes' or any(w in words for w in ['да', 'ага', 'давай', 'открой', 'конечно'])
    if _is_yes:
        handler.play_response('loading')
        from actions.system import open_work
        open_work()
    else:
        handler.play_response('work_cancel')
    handler._set_interactive(None)
    return {'clear_state': True}

def _state_llm_action_confirm(handler, text_lower, words, data, global_cmd):
    """Yes/no gate for actions the local LLM resolved via classify_or_chat()
    that are irreversible/disruptive (see ACTION_CONFIRM_REQUIRED) — that
    classification is fuzzier than CANON_SIMPLE/semantic, so we don't act on
    a guess without the user explicitly confirming."""
    yes_words = ['да', 'ага', 'давай', 'конечно', 'точно', 'угу']
    no_words = ['нет', 'не', 'отмена', 'не надо', 'забудь', 'отбой', 'стоп']
    action = data.get('action') if isinstance(data, dict) else None
    _is_yes = global_cmd == 'confirm_yes' or any(w in words for w in yes_words)
    _is_no = global_cmd in ('confirm_no', 'confirm_cancel') or any(w in words for w in no_words)
    handler._set_interactive(None)
    if _is_yes and action:
        handler.handle(action, text_lower)
    else:
        speak(f'Хорошо, отменяю, {_ga()}.')
    return {'clear_state': True}

def _state_video_monitor_select(handler, text_lower, words, data, global_cmd):
    from actions.screenshot import start_video_recording
    state = handler.interactive_state
    with_mic = state.get('with_mic', False) if isinstance(state, dict) else False
    monitors = state.get('monitors', []) if isinstance(state, dict) else []
    handler._set_interactive(None)
    mon_idx = 0
    if any(w in text_lower for w in ['основной', 'главный']):
        mon_idx = next((i for i, m in enumerate(monitors) if m.get('primary')), 0)
    elif any(w in text_lower for w in ['второй', '2']): mon_idx = 1
    elif any(w in text_lower for w in ['третий', '3']): mon_idx = 2
    if any(w in text_lower for w in ['отмена', 'нет']):
        speak(f'Запись отменена, {_ga()}.')
    elif start_video_recording(with_mic, monitor_index=mon_idx)[0]:
        handler.play_response()
    return {'handled': True}

def _state_game_watcher_suggest(handler, text_lower, words, data, global_cmd):
    yes_words = ['да', 'ага', 'давай', 'конечно', 'активируй', 'активирую', 'включай', 'включи', 'угу']
    no_words = ['нет', 'не', 'отмена', 'не надо', 'забудь', 'отбой']
    profile = data.get('profile', '')
    name = data.get('name', '')
    _is_yes = global_cmd == 'confirm_yes' or any(w in words for w in yes_words)
    _is_no = global_cmd in ('confirm_no', 'confirm_cancel') or any(w in words for w in no_words)
    if _is_yes:
        handler._set_interactive(None)
        from .commands.game import apply_game_profile
        apply_game_profile(handler, profile, name)
        return {'clear_state': True}
    elif _is_no:
        handler._set_interactive(None)
        speak(f'Хорошо, {_ga()}.')
        return {'clear_state': True}
    else:
        handler._set_interactive('game_watcher_suggest', data, timeout=30.0)
        return {'new_state': 'game_watcher_suggest', 'new_data': data, 'timeout': 30.0}

def _state_game_confirm(handler, text_lower, words, data, global_cmd):
    from features.gaming import GameInfo
    yes_words = [
        'да', 'ага', 'давай', 'запускай', 'запускаем', 'конечно', 'без проблем',
        'валяй', 'включай', 'активируй', 'активирую', 'джарвис', 'загружай', 'угу'
    ]
    no_words = ['нет', 'не', 'отмена', 'другую', 'не надо', 'забудь', 'отбой', 'ни в коем случае']
    _is_yes = global_cmd == 'confirm_yes' or any(w in words for w in yes_words)
    _is_no = global_cmd in ('confirm_no', 'confirm_cancel') or any(w in words for w in no_words)
    if _is_yes:
        handler._set_interactive(None)
        gi = GameInfo(name=data.get('game_name', ''), launcher='', launch_uri=data.get('game_uri', ''), install_dir=data.get('install_dir', ''))
        handler._launch_game_engine(gi)
        return {'clear_state': True}
    elif _is_no:
        handler._set_interactive('game_specific', {'games': data.get('games', [])})
        speak(f'Хорошо, {_ga()}. Во что именно вы хотите сыграть?')
        return {'clear_state': True}
    else:
        from features.gaming import fuzzy_find_game
        found = fuzzy_find_game(data.get('games', []), text_lower)
        if found:
            handler._set_interactive(None)
            speak(f'Принято, {_ga()}. Запускаю {normalize_for_tts(found.name)}.')
            handler._launch_game_engine(found)
            return {'clear_state': True}
        else:
            speak('К сожалению, я не смог найти такую игру среди установленных.')
            handler._set_interactive(None)
            return {'clear_state': True}

def _state_play_yt_ask(handler, text_lower, words, data, global_cmd):
    from core.nlp.commands import _WAKE_WORDS_STRICT
    if _check_cancel(handler, text_lower, _CANCEL_WORDS_EXT):
        return {'clear_state': True}
    # ignore bare wake-word utterances, keep waiting
    if text_lower.strip() in _WAKE_WORDS_STRICT:
        handler._set_interactive('play_yt_ask', data, timeout=20.0)
        return {'new_state': 'play_yt_ask', 'new_data': data, 'timeout': 20.0}
    query = text_lower.strip()
    is_music = data.get('is_music', False) if data else False
    is_video = data.get('is_video', False) if data else False
    if not query:
        handler._set_interactive('play_yt_ask', data, timeout=20.0)
        return {'new_state': 'play_yt_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    _bg = data.get('background', False) if data else False
    from core.handler.yt_play import resolve_and_play_youtube
    threading.Thread(
        target=resolve_and_play_youtube,
        args=(handler, query, is_music, is_video, _bg),
        daemon=True,
    ).start()
    return {'clear_state': True}

def _state_yt_channel_ask(handler, text_lower, words, data, global_cmd):
    from actions.youtube import open_youtube_channel
    if _check_cancel(handler, text_lower, _CANCEL_WORDS_EXT):
        return {'clear_state': True}
    q = text_lower.strip()
    if not q:
        handler._set_interactive('yt_channel_ask', data, timeout=20.0)
        return {'new_state': 'yt_channel_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    _bg = data.get('background', False) if data else False
    threading.Thread(
        target=lambda: (open_youtube_channel(q, background=_bg), handler.play_response()),
        daemon=True,
    ).start()
    return {'clear_state': True}

# RU/UK ordinal words -> 0-based index, for picking a card in the YouTube
# disambiguation picker (ui/dialogs/yt_picker_dlg.py) by voice. Capped at 5
# since that's the picker's candidate limit (see actions.youtube.search_youtube_candidates).
_YT_PICK_ORDINALS = {
    'первое': 0, 'первый': 0, 'первую': 0, 'один': 0, '1': 0,
    'второе': 1, 'второй': 1, 'вторую': 1, 'два': 1, '2': 1,
    'третье': 2, 'третий': 2, 'третью': 2, 'три': 2, '3': 2,
    'четвертое': 3, 'четвёртое': 3, 'четвертый': 3, 'четвёртый': 3, 'четыре': 3, '4': 3,
    'пятое': 4, 'пятый': 4, 'пять': 4, '5': 4,
    'перше': 0, 'перший': 0, 'першу': 0,
    'друге': 1, 'другий': 1, 'другу': 1,
    'третє': 2, 'третій': 2, 'третю': 2,
    'четверте': 3, 'четвертий': 3,
    "п'яте": 4, "п'ятий": 4,
}

def _parse_yt_pick_ordinal(words: list[str], fuzzy_threshold: int = 82) -> int | None:
    """Exact match first, then a fuzzy fallback for STT mishearing a less
    common ordinal word (e.g. "третье" transcribed as "третьи"/"третие") —
    'первое'/'второе' are common enough that STT rarely mangles them, but
    the project's own ASR is tuned on frequent vocabulary, and rarer words
    further down the list are more likely to come through slightly off.
    The rest of this codebase's NLU (core/nlp/commands.py) already leans on
    rapidfuzz for exactly this kind of tolerance; a bare `in` dict lookup
    here had none."""
    for w in words:
        if w in _YT_PICK_ORDINALS:
            return _YT_PICK_ORDINALS[w]
    from rapidfuzz import fuzz
    best_idx, best_score = None, 0
    for w in words:
        if len(w) < 3:
            continue  # too short to fuzzy-match reliably
        for key, idx in _YT_PICK_ORDINALS.items():
            if key.isdigit():
                continue
            score = fuzz.ratio(w, key)
            if score > best_score:
                best_score, best_idx = score, idx
    return best_idx if best_score >= fuzzy_threshold else None

def _state_yt_pick_ask(handler, text_lower, words, data, global_cmd):
    from ui.dialogs.yt_picker_dlg import select_index, cancel_picker, is_picker_open
    if not is_picker_open():
        # The window already resolved itself (click or its own timeout) —
        # nothing left for this state to do, stop waiting on more voice input.
        handler._set_interactive(None)
        return {'clear_state': True}
    if _check_cancel(handler, text_lower, _CANCEL_WORDS_EXT):
        cancel_picker()
        return {'clear_state': True}
    idx = _parse_yt_pick_ordinal(words)
    if idx is None:
        handler._set_interactive('yt_pick_ask', data, timeout=20.0)
        return {'new_state': 'yt_pick_ask', 'new_data': data, 'timeout': 20.0}
    if select_index(idx):
        handler._set_interactive(None)
        return {'clear_state': True}
    speak('Такого варианта нет.')
    handler._set_interactive('yt_pick_ask', data, timeout=20.0)
    return {'new_state': 'yt_pick_ask', 'new_data': data, 'timeout': 20.0}

def _state_cinema_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    title = text_lower.strip()
    if not title:
        handler._set_interactive('cinema_ask', data, timeout=20.0)
        return {'new_state': 'cinema_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    is_series = data.get('is_series', False) if data else False
    season = data.get('season', 1) if data else 1
    episode = data.get('episode', 1) if data else 1
    handler.play_response('loading')
    def _cinema(t=title, s=is_series, sn=season, ep=episode):
        from features.cinema import watch_media
        from core.responses import spk as _spk
        mtype = 'сериал' if s else 'фильм'
        handler.speak(_spk('cinema.searching', type=mtype, title=t))
        ok, url = watch_media(t, s, sn, ep)
        if not ok:
            handler.speak(_spk('cinema.not_found', type=mtype, title=t))
    threading.Thread(target=_cinema, daemon=True).start()
    return {'clear_state': True}

def _state_note_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    note = text_lower.strip()
    if not note:
        handler._set_interactive('note_ask', data, timeout=30.0)
        return {'new_state': 'note_ask', 'new_data': data, 'timeout': 30.0}
    handler._set_interactive(None)
    from actions.notes import save_note
    if save_note(note): handler.play_response()
    return {'clear_state': True}

def _state_google_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    q = text_lower.strip()
    if not q:
        handler._set_interactive('google_ask', data, timeout=20.0)
        return {'new_state': 'google_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    import webbrowser
    from urllib.parse import quote
    webbrowser.open(f'https://www.google.com/search?q={quote(q, safe="")}')
    handler.play_response()
    return {'clear_state': True}

def _state_translate_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    import re as _re
    m = _re.search(r'(.+?)\s+на\s+(\w+)$', text_lower.strip())
    query = m.group(1).strip() if m else text_lower.strip()
    target_lang = m.group(2).strip() if m else 'английский'
    if not query:
        handler._set_interactive('translate_ask', data, timeout=30.0)
        return {'new_state': 'translate_ask', 'new_data': data, 'timeout': 30.0}
    handler._set_interactive(None)
    def _translate(q=query, lang=target_lang):
        from actions.system import LANG_MAP
        from core.responses import spk as _spk
        import requests
        lang_code = LANG_MAP.get(lang.lower(), 'en')
        try:
            url = f'https://api.mymemory.translated.net/get?q={requests.utils.quote(q)}&langpair=ru|{lang_code}'
            r = requests.get(url, timeout=5)
            t = r.json().get('responseData', {}).get('translatedText', '')
            handler.speak(_spk('translate.result_v2', text=t) if t else _spk('translate.fetch_error'))
        except Exception:
            handler.speak(_spk('translate.generic_error'))
    threading.Thread(target=_translate, daemon=True).start()
    return {'clear_state': True}

def _state_weather_city_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    city = text_lower.strip().title()
    if not city:
        handler._set_interactive('weather_city_ask', data, timeout=20.0)
        return {'new_state': 'weather_city_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    import json, os
    from core.responses import spk as _spk
    try:
        from config_pack.config import get_settings_path
        from actions.weather import _hud_cache
        sp = get_settings_path()
        s = {}
        if os.path.exists(sp):
            with open(sp, 'r', encoding='utf-8') as f: s = json.load(f)
        s['manual_city'] = city
        _hud_cache.clear()
        with open(sp, 'w', encoding='utf-8') as f: json.dump(s, f, ensure_ascii=False, indent=2)
        handler.speak(_spk('weather.city_saved', city=city))
    except Exception:
        handler.speak(_spk('weather.city_save_error'))
    return {'clear_state': True}

def _state_cd_folder_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    name = text_lower.strip()
    if not name:
        handler._set_interactive('cd_folder_ask', data, timeout=20.0)
        return {'new_state': 'cd_folder_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    from pathlib import Path
    from actions.filesystem import goto_folder
    ctx = Path(data.get('ctx', '')) if data and data.get('ctx') else None
    ok, r = goto_folder(ctx, name)
    if ok: handler.play_response()
    else: handler.speak(r)
    return {'clear_state': True}

def _state_find_file_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    query = text_lower.strip()
    if not query:
        handler._set_interactive('find_file_ask', data, timeout=20.0)
        return {'new_state': 'find_file_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    file_type = data.get('file_type', 'any') if data else 'any'
    from core.responses import spk as _spk
    handler.speak(_spk('files.searching', query=query))
    def _search(q=query, ft=file_type):
        from actions.recent import search_and_open_file
        ok, r = search_and_open_file(q, ft)
        if ok: handler.play_response()
        else: handler.speak(r)
    threading.Thread(target=_search, daemon=True).start()
    return {'clear_state': True}

def _state_net_profile_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    if not text_lower.strip():
        handler._set_interactive('net_profile_ask', data, timeout=20.0)
        return {'new_state': 'net_profile_ask', 'new_data': data, 'timeout': 20.0}
    handler._set_interactive(None)
    from actions.network_profiles import parse_profile_target, set_active_profile
    key = parse_profile_target(text_lower)
    if key:
        ok, msg = set_active_profile(key)
        handler.speak(msg)
    else:
        from core.responses import spk as _spk
        handler.speak(_spk('net.ask_profile_v2'))
    return {'clear_state': True}

def _state_reminder_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    if not text_lower.strip():
        handler._set_interactive('reminder_ask', data, timeout=30.0)
        return {'new_state': 'reminder_ask', 'new_data': data, 'timeout': 30.0}
    handler._set_interactive(None)
    from core.nlp import extract_duration_seconds
    from core.responses import spk as _spk
    delay = extract_duration_seconds(text_lower)
    if delay > 0:
        from features.reminder import schedule_reminder
        from core.handler.commands.system import _fmt_delay
        from core.system import app_state
        hud = getattr(app_state, 'hud', None)
        schedule_reminder(delay, 'о чём-то', handler.speak, hud)
        handler.speak(_spk('reminder.set_ok', delay=_fmt_delay(delay)))
    else:
        handler.speak(_spk('reminder.ask_time'))
        handler._set_interactive('reminder_ask', {}, timeout=30.0)
    return {'clear_state': True}

def _state_qa_clarify(handler, text_lower, words, data, global_cmd):
    text_clean = _normalize_stt(text_lower)
    if text_clean.startswith('джарвис'): text_clean = text_clean[7:].strip()
    if text_clean.startswith('скажи'): text_clean = text_clean[5:].strip()
    while text_clean.startswith('а '): text_clean = text_clean[2:].strip()
    if any(w in text_clean.split() for w in ['отмена', 'стоп', 'спасибо']):
        handler._set_interactive(None)
        handler.play_response()
        return {'clear_state': True}
    if not text_clean or _sem_cmd(text_clean) == 'wake':
        handler._set_interactive('qa_clarify', data, timeout=30.0)
        handler.play_response('wake')
        return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 30.0}
    cmd = _sem_cmd(text_clean)
    if cmd and cmd not in ('qa_search', 'reported_speech'):
        handler._set_interactive(None)
        handler.handle(cmd, text_clean)
        return {'clear_state': True}
    from features.qa import search_answer, is_real_question
    context = data.get('context', '')
    last_ans = data.get('last_ans', '')
    if not is_real_question(text_clean):
        handler._set_interactive('qa_clarify', data, timeout=30.0)
        return {'new_state': 'qa_clarify', 'new_data': data, 'timeout': 30.0}
    handler.play_response('loading')
    try:
        from ui.hud_ai_window import cancel_hide_ai_window
        cancel_hide_ai_window()
    except Exception:
        pass
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
            from features.qa.llm_processor import wrap_llm_stream
            from ui.hud_ai_window import show_ai_window, update_ai_window_text, hide_ai_window

            active_subject = [context]
            def _on_sub(sub):
                active_subject[0] = sub
                show_ai_window(sub)

            raw_gen = search_answer(text_clean, context=context, last_ans=last_ans, stream=True)
            gen = wrap_llm_stream(raw_gen, on_subject_found=_on_sub)

            full_ans = []
            buffer = ""
            marks = ('.', '!', '?', '\n')

            for chunk in gen:
                if not chunk: continue
                full_ans.append(chunk)
                buffer += chunk

                curr_text = "".join(full_ans).strip()
                update_ai_window_text(curr_text)

                if has_hud:
                    display_text = curr_text if len(curr_text) < 65 else "..." + curr_text[-62:]
                    hud._hud.root.after(0, lambda t=display_text: hud._hud.show_msg_stream(t))

                # If buffer is long, allow splitting at commas/semicolons/dashes to speak faster
                active_marks = marks
                if len(buffer) > 40:
                    active_marks = marks + (',', ';', '—')

                if any(m in buffer for m in active_marks):
                    last_mark_pos = -1
                    for m in active_marks:
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
                hide_ai_window(delay_ms=8000)
                next_context = active_subject[0] if active_subject[0] else text_clean
                handler._set_interactive('qa_clarify', {'context': next_context, 'last_ans': final_ans}, timeout=30.0)
            else:
                speak('Извините, не удалось найти информацию.')
                if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)
                hide_ai_window(delay_ms=0)
        except Exception as e:
            _log.error(f"[QA_CLARIFY_STREAM] Error: {e}")
            speak('Извините, произошла ошибка.')
            if has_hud: hud._hud.root.after(0, hud._hud.hide_msg_stream)
            hide_ai_window(delay_ms=0)

    threading.Thread(target=_task, daemon=True).start()
    return {'handled': True}

def _state_rest_hours_ask(handler, text_lower, words, data, global_cmd):
    if _check_cancel(handler, text_lower):
        return {'clear_state': True}
    from core.nlp.commands import normalize_numbers
    import re as _re3
    t = normalize_numbers(text_lower)
    nums = _re3.findall(r'\d+', t)
    handler._set_interactive(None)
    hours = 9
    if nums:
        try:
            hours = max(1, min(24, int(nums[0])))
        except Exception:
            hours = 9
    from core.engine.ets2_commands import _confirm_rest_duration
    threading.Thread(target=_confirm_rest_duration, args=(hours,), daemon=True).start()
    return {'clear_state': True}

_STATE_HANDLERS = {
    'work_select': _state_work_select,
    'work_confirm': _state_work_confirm,
    'video_monitor_select': _state_video_monitor_select,
    'game_watcher_suggest': _state_game_watcher_suggest,
    'game_confirm': _state_game_confirm,
    'play_yt_ask': _state_play_yt_ask,
    'yt_channel_ask': _state_yt_channel_ask,
    'yt_pick_ask': _state_yt_pick_ask,
    'cinema_ask': _state_cinema_ask,
    'note_ask': _state_note_ask,
    'google_ask': _state_google_ask,
    'translate_ask': _state_translate_ask,
    'weather_city_ask': _state_weather_city_ask,
    'cd_folder_ask': _state_cd_folder_ask,
    'find_file_ask': _state_find_file_ask,
    'net_profile_ask': _state_net_profile_ask,
    'reminder_ask': _state_reminder_ask,
    'qa_clarify': _state_qa_clarify,
    'rest_hours_ask': _state_rest_hours_ask,
    'llm_action_confirm': _state_llm_action_confirm,
}

def handle_interactive(handler, text: str) -> dict:
    state = handler.interactive_state
    if isinstance(state, dict): state = state.get('type')
    data = handler.interactive_data
    text_lower = text.lower().strip()
    words = text_lower.split()
    # Pass is_waiting_answer=True for yes/no confirmation states so that
    # the semantic Layer 0 intercept properly handles 'да'/'нет' etc.
    _waiting = state in _YES_NO_STATES
    global_cmd = _sem_cmd(text_lower, is_waiting_answer=_waiting)
    if global_cmd in ['game_mode_off', 'shutdown', 'guard_on', 'restart', 'guard_off']:
        handler._set_interactive(None)
        handler.handle(global_cmd, text_lower)
        return {'clear_state': True}
    fn = _STATE_HANDLERS.get(state)
    if fn is None:
        handler._set_interactive(None)
        return {'clear_state': True}
    return fn(handler, text_lower, words, data, global_cmd)
