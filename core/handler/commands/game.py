import os
import subprocess
import threading
import time
from core.system import app_state
from core.speech import speak, normalize_for_tts
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('game')
def apply_game_profile(handler, profile, msg_name):
    from actions.game_input_parts.profile import get_loaded_profile_stem
    if app_state.game_mode and get_loaded_profile_stem() == profile:
        app_state.jarvis_active = True
        app_state.last_command_time = time.time()
        return
    from actions.game_input import load_profile
    ok, msg = load_profile(profile)
    if ok:
        if app_state.game_mode and (app_state.game_profile == msg):
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            return
        app_state.game_mode = True
        app_state.game_profile = msg
        app_state.jarvis_active = True
        app_state.last_command_time = time.time()
        try:
            from core.engine.jarvis import get_engine
            _eng = get_engine()
            if _eng is not None:
                _eng.drain_transcribe_queue(keep=1)
        except Exception:
            pass
        hint = 'Говорите заклинания.' if 'hogwarts' in profile.lower() else 'Говорите команды.'
        speak(f'Игровой режим активирован. Профиль: {msg}. {hint}')
        try: handler.asr.set_vad_mode(True)
        except Exception: pass
        try:
            from actions.game_input import get_hotwords
            hw = get_hotwords() + ['джарвис', 'джервис', 'жарвис', 'джарвиса', 'сэр']
            threading.Thread(target=handler.asr.reload_with_hotwords, args=(hw,), daemon=True).start()
        except Exception: pass
        try:
            from actions.game_audio import game_matcher
            game_matcher.set_profile(profile)
        except Exception: pass
        if 'euro_truck_simulator_2' in profile.lower():
            try:
                from features.ets2 import monitor as ets2_monitor
                ets2_monitor.start()
                _log.debug("[GAME_MODE] ETS2 Monitor started.")
            except Exception as e:
                _log.debug(f"[GAME_MODE] Failed to start ETS2 Monitor: {e}")
        if 'planetbase' in profile.lower():
            try:
                from features.planetbase import monitor as pb_monitor
                pb_monitor.start()
                _log.debug("[GAME_MODE] Planetbase Monitor started.")
            except Exception as e:
                _log.debug(f"[GAME_MODE] Failed to start Planetbase Monitor: {e}")
        if 'farming_simulator_22' in profile.lower():
            try:
                from features.fs22 import monitor as fs22_monitor
                fs22_monitor.start()
                _log.debug("[GAME_MODE] FS22 Monitor started.")
            except Exception as e:
                _log.debug(f"[GAME_MODE] Failed to start FS22 Monitor: {e}")
    else:
        speak(msg)
def start_game_selection_flow(handler, query=None):
    from features.gaming import get_available_launchers, scan_all_games, get_most_recently_played, fuzzy_find_game
    from core.system import get_foreground_process_name
    from features.gaming.watcher import _GAME_EXE_MAP, _QUICK_ALIAS_MAP, is_profile_installed
    fg_name = get_foreground_process_name()
    if fg_name and fg_name in _GAME_EXE_MAP:
        profile_stem, display_name, _ = _GAME_EXE_MAP[fg_name]
        speak(f'Вижу запущенную {normalize_for_tts(display_name)}.')
        apply_game_profile(handler, profile_stem, display_name)
        return
    if query:
        q_low = f' {query.lower()} '
        for alias, profile_stem in _QUICK_ALIAS_MAP.items():
            if alias in q_low or alias.strip() in q_low.strip():
                if is_profile_installed(profile_stem):
                    display_name = profile_stem.replace('_', ' ').title()
                    speak(f'Активирую профиль {normalize_for_tts(display_name)}.')
                    apply_game_profile(handler, profile_stem, display_name)
                    try:
                        games = scan_all_games()
                        wanted = None
                        if profile_stem == 'euro_truck_simulator_2':
                            for g in games:
                                n = (getattr(g, 'name', '') or '').lower()
                                if 'euro truck simulator 2' in n or 'ets2' in n:
                                    wanted = g
                                    break
                        if not wanted:
                            wanted = fuzzy_find_game(games, query)
                        if wanted:
                            speak(f'Запускаю {normalize_for_tts(wanted.name)}.')
                            handler._launch_game_engine(wanted)
                            return
                        if profile_stem == 'euro_truck_simulator_2':
                            try:
                                import os as _os
                                _os.startfile('steam://run/227300')
                                speak('Запускаю Euro Truck Simulator 2 через Steam.')
                                return
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return
                break
        games = scan_all_games()
        found = fuzzy_find_game(games, query)
        if found:
            speak(f'Запускаю {normalize_for_tts(found.name)}.')
            handler._launch_game_engine(found)
            return
        else:
            speak(f'Не нашёл игру по запросу «{query}».')
    launchers = get_available_launchers()
    if len(launchers) > 1:
        names = [normalize_for_tts(n) for n in launchers.keys()]
        l_str = ", ".join(names[:-1]) + " и " + names[-1]
        speak(f'Сэр, обнаружено несколько игровых платформ: {l_str}. Какую выберем?')
        handler._set_interactive('game_launcher_choice', {'launchers': launchers})
    elif len(launchers) == 1:
        name = list(launchers.keys())[0]
        speak(f'Открываю {normalize_for_tts(name)}...')
        lp = launchers[name]
        if lp.startswith('shell:'): subprocess.Popen(['explorer.exe', lp])
        else: subprocess.Popen([lp], creationflags=8)
        def _suggest_delayed():
            from features.gaming import wait_for_launcher_window
            wait_for_launcher_window(name, timeout=15.0)
            time.sleep(1.5)
            speak('Приступаю к анализу вашей библиотеки...')
            all_games = scan_all_games()
            best = get_most_recently_played(all_games)
            if best:
                handler.speak(spk('game.confirm', game=normalize_for_tts(best.name)), wait=True)
                handler._set_interactive('game_confirm', {'game_uri': best.launch_uri, 'game_name': best.name, 'install_dir': best.install_dir, 'games': all_games})
            else: speak('У вас пока нет установленных игр.')
        threading.Thread(target=_suggest_delayed, daemon=True).start()
    else:
        games = scan_all_games()
        best = get_most_recently_played(games)
        if best:
            handler._set_interactive('game_confirm', {'game_uri': best.launch_uri, 'game_name': best.name, 'install_dir': best.install_dir, 'games': games})
            speak(f'Может быть, {normalize_for_tts(best.name)}?')
        else:
            from core.address import get_address as _ga
            speak(f'Похоже, на этом компьютере нет игр, {_ga()}.')
def launch_game_engine(handler, game_info):
    _log.debug('launch: name=%r uri=%r dir=%r', game_info.name, game_info.launch_uri, game_info.install_dir)
    threading.Thread(target=_do_launch, args=(handler, game_info), daemon=True).start()
def _do_launch(handler, game_info):
    from features.gaming import find_game_executable
    from features.gaming.watcher import is_profile_installed
    from actions.system import activate_game_mode
    handler.play_response('game'); time.sleep(0.3)
    try: activate_game_mode()
    except Exception: pass
    exe_path = find_game_executable(game_info.install_dir, game_info.name)
    _log.debug('_do_launch exe_path=%r', exe_path)
    if exe_path: subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), creationflags=8)
    else:
        _log.debug('_do_launch fallback startfile uri=%r', game_info.launch_uri)
        os.startfile(game_info.launch_uri)
    profile_stem = game_info.name.lower().replace(' ', '_')
    if is_profile_installed(profile_stem):
        apply_game_profile(handler, profile_stem, game_info.name)
def handle_game_extra(handler, cmd, text_lower):
    if cmd == 'spell_list':
        from actions.game_input import get_spell_list
        spells = get_spell_list()
        if spells:
            speak("Ваши текущие заклинания: " + ", ".join(spells))
        else:
            speak("У вас нет активных заклинаний в этом профиле.")

def _timer_set(text_lower):
    from core.nlp import extract_duration_seconds
    from actions.game_timer import set_timer
    import re
    secs = extract_duration_seconds(text_lower)
    if secs <= 0:
        speak('Скажите продолжительность, например: таймер на тридцать минут.')
        return
    from core.nlp.commands import normalize_numbers
    text_norm = normalize_numbers(text_lower)
    label_raw = re.sub(
        r'(засеки|дай|поставь|таймер|на|постав|год[иі]ну|час\w*|хвилин\w*|минут\w*|секунд\w*|\d+)',
        '', text_norm
    ).strip()
    label = label_raw if len(label_raw) > 2 else ''
    hud = getattr(app_state, 'hud', None)
    duration_str = set_timer(secs, label, speak, hud)
    speak(f'Таймер запущен на {duration_str}. Предупрежу заблаговременно.')

def _timer_add(text_lower):
    from core.nlp import extract_duration_seconds, format_duration_russian
    from actions.game_timer import add_time, get_status
    secs = extract_duration_seconds(text_lower)
    if secs <= 0:
        speak('Скажите сколько добавить, например: добавь пятнадцать минут.')
        return
    if add_time(secs):
        remaining = get_status()
        if remaining and remaining >= 60:
            speak(f'Добавлено. Осталось {format_duration_russian(remaining // 60)}.')
        else:
            speak('Добавлено.')
    else:
        speak('Таймер не запущен.')

def _timer_status(text_lower):
    from actions.game_timer import get_status
    from core.nlp import format_duration_russian
    remaining = get_status()
    if remaining is None:
        speak('Таймер не запущен.')
    elif remaining < 60:
        speak('Осталось меньше минуты.')
    else:
        speak(f'Осталось {format_duration_russian(remaining // 60)}.')

def _timer_cancel(text_lower):
    from actions.game_timer import cancel_timer
    if cancel_timer():
        speak('Таймер отменён.')
    else:
        speak('Таймер не был запущен.')

_TIMER_ACTIONS = {
    'timer_set': _timer_set,
    'timer_add': _timer_add,
    'timer_status': _timer_status,
    'timer_cancel': _timer_cancel,
}

def handle_timer(handler, cmd, text_lower):
    action = _TIMER_ACTIONS.get(cmd)
    if action:
        action(text_lower)
