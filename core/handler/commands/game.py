import os
import subprocess
import threading
import time
from core.system import app_state
from core.speech import speak, normalize_for_tts
def apply_game_profile(handler, profile, msg_name):
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
                print("[GAME_MODE] ETS2 Monitor started.")
            except Exception as e:
                print(f"[GAME_MODE] Failed to start ETS2 Monitor: {e}")
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
                handler.speak(f'Смею предположить, вы хотите сыграть в {normalize_for_tts(best.name)}? Запускаем?', wait=True)
                handler._set_interactive('game_confirm', {'game_uri': best.launch_uri, 'game_name': best.name, 'install_dir': best.install_dir, 'games': all_games})
            else: speak('У вас пока нет установленных игр.')
        threading.Thread(target=_suggest_delayed, daemon=True).start()
    else:
        games = scan_all_games()
        best = get_most_recently_played(games)
        if best:
            handler._set_interactive('game_confirm', {'game_uri': best.launch_uri, 'game_name': best.name, 'install_dir': best.install_dir, 'games': games})
            speak(f'Может быть, {normalize_for_tts(best.name)}?')
        else: speak('Похоже, на этом компьютере нет игр, сэр.')
def launch_game_engine(handler, game_info):
    print(f'[launch_game_engine] name={game_info.name!r} uri={game_info.launch_uri!r} dir={game_info.install_dir!r}', flush=True)
    threading.Thread(target=_do_launch, args=(handler, game_info), daemon=True).start()
def _do_launch(handler, game_info):
    from features.gaming import find_game_executable
    from features.gaming.watcher import is_profile_installed
    from actions.system import activate_game_mode
    handler.play_response('game'); time.sleep(0.3)
    try: activate_game_mode()
    except Exception: pass
    exe_path = find_game_executable(game_info.install_dir, game_info.name)
    print(f'[_do_launch] exe_path={exe_path!r}', flush=True)
    if exe_path: subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), creationflags=8)
    else:
        print(f'[_do_launch] falling back to os.startfile uri={game_info.launch_uri!r}', flush=True)
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
