import time
import re
import queue as _queue_mod
import threading as _threading_mod
from core.system import app_state
_REFUEL_STOP = _threading_mod.Event()
_WAKE_RE = re.compile('\\b(джарвис|джарвиса|джарвису|джарвисе|жарвис|жарвиса|жарвису|шарвис|шарвиса|жорвис|джорвис|жарвист|жаркс|джаркс|жарост|жарност|жарс|жорс|джорс|жорпс|джорпс|джервис|джарвиз|джарвест|джаравис|джарверс|джаверс|бобик)\\b', re.IGNORECASE)
_GAME_ON_VERBS = ('включи', 'активируй', 'запусти', 'подготовь')
_GAME_OFF_VERBS = ('выключи', 'отключи', 'отмени', 'деактивируй', 'выйди', 'закрой', 'завершить', 'закрыть', 'завершить')
_GAME_OFF_EXACT = frozenset({
    'выйди из игрового режима', 'отключи игровой режим', 'отмени игровой режим',
    'отмени режим', 'выключи игровой режим', 'выйди из игры', 'отмени режим игры',
    'конец игры', 'игра окончена', 'верни обычный режим',
    'закрой игру', 'закрыть игру', 'выйти из игры', 'завершить игру',
    'завершить игровой режим', 'выключи режим игры', 'стоп игра',
})
def _is_game_mode_off_phrase(text_norm: str) -> bool:
    if text_norm in _GAME_OFF_EXACT:
        return True
    if any(p in text_norm for p in _GAME_OFF_EXACT if len(p) >= 6):
        return True
    if 'геймод' in text_norm and any(v in text_norm for v in _GAME_OFF_VERBS):
        return True
    has_game = ('игровой' in text_norm) or ('режим игры' in text_norm)
    return has_game and any(v in text_norm for v in _GAME_OFF_VERBS)
_QUICK_GAME_FRAGS = (
    'евро трак', 'евротрак', 'euro truck', 'трак симулятор',
    ' ets', 'etс', 'етс',
    'фарминг', 'farming', ' фс ', ' фс22', ' фс25', ' fs22', ' fs25', 'ферму', 'ферма',
    'хогвартс', 'hogwarts', ' хог',
)
def _is_game_mode_on_phrase(text_norm: str) -> bool:
    if _is_game_mode_off_phrase(text_norm):
        return False
    if 'геймод' in text_norm:
        return True
    has_game = ('игровой' in text_norm) or ('режим игры' in text_norm)
    if has_game and any(v in text_norm for v in _GAME_ON_VERBS):
        return True
    padded = f' {text_norm} '
    _GO_PREFIXES = ('го в ', 'хочу в ', 'запусти ', 'включи ', 'играть в ')
    has_prefix = any(p in padded for p in _GO_PREFIXES)
    has_game_frag = any(frag in padded for frag in _QUICK_GAME_FRAGS)
    return has_prefix and has_game_frag
def _handle_telemetry_action(action: str, handler, text: str = '') -> None:
    def _speak(msg: str):
        try:
            from core.speech import speak_async
            speak_async(msg)
        except Exception: pass
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
    except ImportError: return
    if action == 'telemetry_diag':
        from actions.ets2_telemetry import is_available as _ia, _read_raw as _rr
        if not _ia():
            _speak('Модуль телеметрии не установлен. Запустите инсталлятор плагина.')
            return
        raw = _rr()
        if raw is None:
            _speak('Телеметрия недоступна. Убедитесь что ETS2 запущена и плагин активен. Подробности — в файле logs/telemetry_debug.log.')
            return
        spd = float(raw.get('speed', 0)) * 3.6
        sdk = raw.get('sdkActive', '?')
        _speak(f'Телеметрия работает. Скорость {int(spd)} км/ч. SDK активен: {sdk}.')
    elif action == 'fuel_status':
        if data:
            f_range = int(round(float(data.get('fuelRange', 0))))
            cap = float(data.get('fuelCapacity') or 1)
            f_pct = int(round(float(data.get('fuel', 0)) / cap * 100))
            _speak(f'Запас хода {f_range} километров, топлива в баке {f_pct} процентов.')
        else: _speak('Телеметрия недоступна.')
    elif action == 'truck_status':
        if data:
            f_range = int(round(float(data.get('fuelRange', 0))))
            engine = 'двигатель работает' if data.get('engineEnabled') else 'двигатель заглушен'
            brake = 'ручник поднят' if data.get('parkBrake') else 'ручник снят'
            _speak(f'Статус тягача: {engine}, {brake}. Запас хода {f_range} километров.')
        else: _speak('Телеметрия недоступна.')
    elif action == 'route_status':
        if data:
            dist = float(data.get('routeDistance', 0))
            dist_km = int(round(dist / 1000)) if dist > 1000 else int(round(dist))
            unit = 'километров' if dist > 1000 else 'метров'
            mins = int(round(float(data.get('routeTime', 0)) / 60))
            from core.nlp import format_duration_russian
            _speak(f'До пункта назначения {dist_km} {unit}. Расчётное время в пути — {format_duration_russian(mins)}.')
        else: _speak('Телеметрия недоступна.')
    elif action == 'rest_status':
        if data:
            rest = int(data.get('restStop', -1))
            if rest <= 0: _speak('Данные об усталости недоступны.')
            else:
                from core.nlp import format_duration_russian
                txt = format_duration_russian(rest)
                h = rest // 60
                if h >= 3: _speak(f'Водитель в норме. До обязательного отдыха {txt}.')
                elif h >= 1: _speak(f'До обязательного отдыха {txt}. Рекомендую планировать остановку.')
                else: _speak(f'Сэр, водитель очень устал. До обязательного отдыха {txt}.')
    elif action == 'break_time': _speak('Аварийка включена, ручник затянут, двигатель заглушен. Хорошего отдыха, сэр.')
    elif action == 'night_mode':
        try:
            from actions.game_input import press_robust
            if not data.get('lightsBeamLow'): press_robust('l'); time.sleep(0.15)
            if not data.get('lightsBeamHigh'): press_robust('k')
            _speak('Ночной режим. Ближний и дальний свет включены.')
        except Exception: _speak('Не удалось переключить освещение.')
    elif action == 'morning_mode':
        try:
            from actions.game_input import press_robust
            if data.get('lightsBeamHigh'): press_robust('k'); time.sleep(0.15)
            if data.get('lightsBeamLow'): press_robust('l')
            _speak('Утренний режим. Освещение выключено.')
        except Exception: _speak('Не удалось переключить освещение.')
    elif action == 'diagnostic_report':
        try:
            from features.ets2 import get_wear_report
            _speak(get_wear_report())
        except Exception: _speak('Не удалось получить данные диагностики.')
    elif action == 'cruise_off':
        from actions.ets2_telemetry import get_cruise_active
        if get_cruise_active() is True:
            from actions.game_input import get_binding, press_robust
            press_robust(get_binding('cruise', 'c'))
    elif action == 'cruise_set':
        import re as _re
        from core.nlp.commands import normalize_numbers as _nn
        nums = _re.findall(r'\d+', _nn(text.lower()))
        if not nums:
            _speak('Скажите целевую скорость, например: круиз контроль восемьдесят.')
            return
        target_kmh = max(30, min(160, int(nums[0])))
        try:
            from actions.ets2_telemetry import get_cruise_speed_kmh as _cruise_kmh, get_speed_kmh as _spd_kmh, get_cruise_active as _ca
            active = _ca()
            current_target = _cruise_kmh()
            truck_spd = _spd_kmh()
            
            # Use current cruise target for comparison if active, otherwise use truck speed
            base_for_compare = current_target if (active and current_target and current_target > 0) else truck_spd
            if base_for_compare is None: base_for_compare = 30.0
            
            if target_kmh == int(round(base_for_compare / 5.0) * 5.0):
                _speak(f'Круиз уже настроен на {target_kmh} км/ч.')
                return
            
            current_kmh = base_for_compare
        except Exception:
            current_kmh = 30.0
            
        # Check and disable auto-cruise if active
        try:
            from features.ets2 import monitor as _mon
            if getattr(_mon, '_auto_cruise', False):
                _mon.set_auto_cruise(False)
                _speak(f'Сэр, устанавливаю {target_kmh}. Авто-круиз отключён.')
            else:
                direction = 'Повышаю' if target_kmh > current_kmh else 'Снижаю'
                _speak(f'{direction} круиз до {target_kmh} км/ч.')
        except Exception:
            pass

        from actions.game_input import cruise_set_speed as _css
        ok, actual = _css(target_kmh, current_kmh)
        if not ok:
            # Only speak error if it failed completely
            pass
    elif action == 'cruise_adjust':
        import re as _re
        from core.nlp.commands import normalize_numbers as _nn
        nums = _re.findall(r'\d+', _nn(text.lower()))
        delta_kmh = int(nums[0]) if nums else 5
        delta_kmh = max(5, (round(delta_kmh / 5.0)) * 5)
        _UP   = ('увеличь', 'прибавь', 'добавь', 'повысь', 'ускорь', 'подними', 'больше')
        _DOWN = ('уменьши', 'убери',   'снизь',   'замедли', 'сбрось', 'опусти', 'меньше')
        text_low = text.lower()
        is_down = any(w in text_low for w in _DOWN)
        if is_down:
            delta_kmh = -delta_kmh
        try:
            from actions.ets2_telemetry import get_cruise_speed_kmh as _ckm, get_speed_kmh as _spd
            base = _ckm()
            if base is None or base < 5.0:
                base = _spd() or 60.0
        except Exception:
            base = 60.0
        base_snapped = round(base / 5.0) * 5.0
        target = max(30, min(160, int(base_snapped + delta_kmh)))
        
        # Check and disable auto-cruise if active
        try:
            from features.ets2 import monitor as _mon
            if getattr(_mon, '_auto_cruise', False):
                _mon.set_auto_cruise(False)
                _speak(f'Корректирую до {target}. Авто-круиз отключён.')
            else:
                direction_text = 'Увеличиваю' if delta_kmh > 0 else 'Снижаю'
                _speak(f'{direction_text} круиз до {target} км/ч.')
        except Exception:
            pass
            
        from actions.game_input import cruise_set_speed as _css
        ok, actual = _css(target, base_snapped)
        if not ok:
            pass
    elif action == 'cruise_limit':
        try:
            from actions.ets2_telemetry import get_speed_limit_kmh as _lim, get_cruise_speed_kmh as _ckm, get_speed_kmh as _spd
            limit = _lim()
            if limit is None or limit < 10:
                _speak('Данные об ограничении скорости недоступны.')
                return
            target_kmh = int(round(limit / 5.0) * 5.0)
            current = _ckm()
            if current is None:
                current = _spd() or 30.0
            from actions.game_input import cruise_set_speed as _css
            ok, actual = _css(target_kmh, current)
            if ok:
                _speak(f'Круиз установлен по ограничению: {actual} км/ч.')
            else:
                _speak('Не удалось установить круиз по ограничению.')
        except Exception as _e:
            _speak(f'Ошибка: {_e}')
    elif action == 'gear_set':
        import re as _re
        from core.nlp.commands import normalize_numbers as _nn
        t = _nn(text.lower())
        nums = _re.findall(r'\d+', t)
        want: int | None = None
        if any(w in t for w in ('нейтрал', 'нейтраль', 'neutral')):
            want = 0
        elif any(w in t for w in ('задний', 'заднюю', 'задняя', 'реверс', 'reverse', 'назад', 'реверсивный', 'задка')):
            want = -1
        elif nums:
            want = int(nums[0])
        if want is None:
            _speak('Скажите номер передачи, например: поставь двенадцатую передачу, или скажите: задний ход.')
            return
        try:
            from actions.ets2_telemetry import get_gear as _get_gear
            cur = _get_gear()
        except Exception:
            cur = None
        if cur is None:
            _speak('Не вижу текущую передачу по телеметрии. Включите телеметрию ETS2 и проверьте плагин.')
            return
        try:
            from actions.game_input import set_gear as _set_gear
            ok, actual = _set_gear(int(want), int(cur))
            if ok:
                if actual == -1:
                    _speak('Задний ход.')
                elif actual == 0:
                    _speak('Нейтраль.')
                else:
                    _speak(f'Передача {actual}.')
            else:
                _speak('Не удалось переключить передачу. Проверьте биндинги и режим коробки.')
        except Exception:
            _speak('Не удалось переключить передачу.')
    elif action == 'auto_cruise_on':
        try:
            from features.ets2 import monitor as _mon
            _mon.set_auto_cruise(True)
            _speak('Авто-круиз включён. Буду следить за ограничением скорости и корректировать круиз-контроль.')
            # Engage cruise control immediately if possible
            try:
                from actions.ets2_telemetry import get_speed_kmh, get_speed_limit_kmh, get_cruise_active
                if get_cruise_active() is False:
                    speed = get_speed_kmh()
                    limit = get_speed_limit_kmh()
                    if speed and speed >= 30.0:
                        target = limit if (limit and limit > 30) else speed
                        from actions.game_input_parts.driving import cruise_set_speed
                        cruise_set_speed(int(target), speed, auto_mode=False)
            except Exception: pass
        except Exception:
            _speak('Не удалось включить авто-круиз.')
    elif action == 'auto_cruise_off':
        try:
            from features.ets2 import monitor as _mon
            _mon.set_auto_cruise(False)
            _speak('Авто-круиз выключен. Управляйте круиз-контролем вручную.')
        except Exception:
            pass
    elif action == 'go_to_sleep':
        try:
            from actions.ets2_telemetry import get as _tget
            from actions.game_input import get_binding, cast_command
            import pydirectinput as _pdi
            _pdi.PAUSE = 0
            data = _tget()
            if data:
                from actions.game_input import press_robust
                if not data.get('parkBrake'):
                    press_robust(get_binding('handbrake', 'space'))
                    time.sleep(0.3)
                if data.get('engineEnabled'):
                    press_robust(get_binding('engine', 'e'))
                    time.sleep(0.3)
                cast_command('fake_text_for_lights', fuzzy_threshold=1.0)
                from actions.ets2_telemetry import get_lights_parking, get_lights_low
                if get_lights_low():
                    press_robust(get_binding('lights_main', 'l'))
                    time.sleep(0.1)
                    press_robust(get_binding('lights_main', 'l'))
                time.sleep(0.5)
            from actions.game_input import press_robust
            press_robust(get_binding('action', 'enter'))
        except Exception:
            try:
                import pyautogui as _pag
                _pag.press('enter')
            except Exception: pass
    elif action == 'wake_up':
        try:
            from actions.ets2_telemetry import get as _tget
            from actions.game_input import get_binding, cast_command
            import pydirectinput as _pdi
            _pdi.PAUSE = 0
            try:
                from actions.game_input import press_robust
                press_robust(get_binding('action', 'enter'))
                time.sleep(0.25)
            except Exception:
                pass
            data = _tget()
            engine_key = get_binding('engine', 'e')
            from actions.game_input import press_robust
            # Start engine with a long hold for reliability
            try:
                import pydirectinput as _pdi
                _pdi.keyDown(engine_key)
                time.sleep(2.0)
                _pdi.keyUp(engine_key)
            except Exception:
                press_robust(engine_key, duration=2.0)
            time.sleep(0.5)
            if data and data.get('parkBrake'):
                from actions.game_input import press_robust
                press_robust(get_binding('handbrake', 'space'))
                time.sleep(0.3)
            cast_command('подготовь тягач', fuzzy_threshold=0.9)
        except Exception:
            pass
    elif action == 'close_game':
        from core.system import app_state as _as
        _as.game_mode = False
        try:
            from actions.game_input import unload_profile
            unload_profile()
        except Exception: pass
        try:
            import pyautogui as _pag
            _pag.hotkey('alt', 'f4')
        except Exception:
            try:
                import subprocess
                subprocess.Popen(['taskkill', '/F', '/IM', 'eurotrucks2.exe'],
                                 creationflags=0x08000000)
            except Exception: pass
    elif action == 'refuel_start':
        import threading as _threading
        import time as _time
        _REFUEL_STOP.set()
        _time.sleep(0.15)
        _REFUEL_STOP.clear()
        def _refuel_loop():
            try:
                import pydirectinput as _pdi
                from actions.ets2_telemetry import get as _tget
                from actions.game_input import get_binding, press_robust
                
                _pdi.PAUSE = 0
                d = _tget()
                if not d:
                    _speak('Телеметрия недоступна — не могу контролировать заправку.')
                    return

                # 1. Prepare: Stop engine and set handbrake
                if d.get('engineEnabled'):
                    _speak('Глушу двигатель для заправки.')
                    press_robust(get_binding('engine', 'e'))
                    _time.sleep(1.2)
                
                if not d.get('parkBrake'):
                    press_robust(get_binding('handbrake', 'space'))
                    _time.sleep(0.3)

                # 2. Refuel: Hold Action key (Enter)
                key = get_binding('action', 'enter')
                cap = float(d.get('fuelCapacity') or 0)
                if cap <= 0:
                    _speak('Нет данных о ёмкости бака. Заправляйте вручную.')
                    return
                
                pct = float(d.get('fuel', 0)) / cap * 100
                if pct >= 99.0:
                    _speak('Бак уже полный.')
                    return
                
                _speak(f'Начинаю заправку. Удерживаю клавишу.')
                _pdi.keyDown(key)
                max_sec = 360
                poll_sec = 1.0
                elapsed = 0.0
                last_pct = pct
                while elapsed < max_sec and not _REFUEL_STOP.is_set():
                    _time.sleep(poll_sec)
                    elapsed += poll_sec
                    d = _tget()
                    if not d: break
                    pct = float(d.get('fuel', 0)) / cap * 100
                    for milestone in (50, 75, 90, 95):
                        if last_pct < milestone <= pct:
                            _speak(f'Бак {milestone} процентов.')
                            break
                    last_pct = pct
                    if pct >= 99.5:
                        break
                _pdi.keyUp(key)
                if _REFUEL_STOP.is_set():
                    _speak(f'Заправка остановлена. Бак {int(pct)} процентов.')
                elif pct >= 99.0:
                    _speak('Бак полный. Заправка завершена.')
                else:
                    _speak(f'Заправка прервана. Бак {int(pct)} процентов.')
            except Exception as _re:
                try:
                    import pydirectinput as _pdi
                    from actions.game_input import get_binding
                    _pdi.keyUp(get_binding('refuel', 'r'))
                except Exception:
                    pass
                _speak(f'Ошибка заправки: {_re}')
        _threading.Thread(target=_refuel_loop, daemon=True, name='ets2-refuel').start()
    elif action == 'refuel_stop':
        _REFUEL_STOP.set()
    elif action == 'unload_cargo':
        try:
            from actions.ets2_telemetry import get as _tget
            from actions.game_input import get_binding
            import pydirectinput as _pdi
            _pdi.PAUSE = 0
            data = _tget() or {}
            hb_key = get_binding('handbrake', 'space')
            eng_key = get_binding('engine', 'e')
            wip_key = get_binding('wipers', 'p')
            lights_key = get_binding('lights_main', 'l')
            high_key = get_binding('lights_high', 'k')
            trailer_key = get_binding('trailer', 't')
            action_key = get_binding('action', 'enter')
            from actions.game_input import press_robust
            try:
                if not bool(data.get('parkBrake')):
                    press_robust(hb_key)
                    time.sleep(0.25)
            except Exception:
                pass
            try:
                from actions.ets2_telemetry import get_wipers as _gw
                for _ in range(3):
                    if _gw() is not True:
                        break
                    press_robust(wip_key)
                    time.sleep(0.15)
            except Exception:
                pass
            try:
                from actions.ets2_telemetry import get_lights_parking as _gp, get_lights_low as _gl, get_lights_high as _gh
                if _gh() is True:
                    press_robust(high_key)
                    time.sleep(0.15)
                if _gl() is True:
                    press_robust(lights_key)
                elif _gp() is True:
                    press_robust(lights_key)
                    time.sleep(0.10)
                    press_robust(lights_key)
            except Exception:
                pass
            try:
                if bool(data.get('engineEnabled')):
                    press_robust(eng_key)
                    time.sleep(0.25)
            except Exception:
                pass
            try:
                press_robust(action_key)
                time.sleep(0.25)
                press_robust(action_key)
            except Exception:
                pass
            try:
                press_robust(trailer_key)
            except Exception:
                pass
            _speak('Рейс завершён. Тягач заглушен, свет и дворники выключены. Груз передан.')
        except Exception:
            _speak('Не удалось выполнить сценарий завершения рейса.')
    elif action == 'install_plugin':
        try:
            from actions.ets2_telemetry_installer import run_installer
            from ui import hud
            run_installer(tk_root=hud._hud.root if hud._hud else None)
        except Exception: pass
def handle_recognized_text(text: str, handler):
    from core.speech import stop_speaking, is_speaking
    from core.nlp import extract_all_commands, _normalize_stt
    
    # Only interrupt if we are NOT in interactive state AND we heard a wake word or a command
    text_low = text.lower().strip()
    is_wake = bool(_WAKE_RE.search(text_low))
    parsed_cmds = None
    
    if is_speaking():
        if is_wake or (handler.interactive_state and len(text_low) > 3):
            stop_speaking()
            time.sleep(0.1)
    text = text.strip()
    if not text: return
    try:
        from ui.voice_prompt_bridge import try_consume_voice_prompt
        if try_consume_voice_prompt(text):
            return
    except Exception:
        pass
    if app_state.game_mode:
        app_state.jarvis_active = True
        app_state.last_command_time = time.time()
    if handler.interactive_state:
        if handler.is_speaking: stop_speaking(); time.sleep(0.1)
        app_state.last_command_time = time.time()
        handler.handle_interactive(text); return
    if app_state.game_mode:
        text_norm = _normalize_stt(text)
        if _is_game_mode_off_phrase(text_norm):
            handler.handle('game_mode_off', text); return
        from actions.game_input import cast_command, match_command as _gi_match
        _fuzzy = 0.75
        ok, _ = cast_command(text, fuzzy_threshold=_fuzzy)
        print(f'[GAME_MODE] text={text!r} cast_ok={ok}', flush=True)
        if ok:
            match = _gi_match(text, threshold=_fuzzy)
            if match and match[0].get('telemetry_action'):
                _handle_telemetry_action(match[0]['telemetry_action'], handler, text=text)
            return
        if _is_game_mode_on_phrase(text_norm):
            handler.handle('game_mode_on', text); return
    if app_state.dictation_mode:
        from actions.dictation import handle_dictation_text
        res = handle_dictation_text(text)
        if res['stop']:
            app_state.dictation_mode = False; handler.play_response()
        return
    text_lower = text.lower().strip()
    is_wake = bool(_WAKE_RE.search(text_lower))
    parsed_cmds = None
    if not is_wake:
        parsed_cmds = extract_all_commands(text)
        is_wake = any((c == 'wake' for c, _ in parsed_cmds))
    if not app_state.jarvis_active:
        cmds_early = parsed_cmds if parsed_cmds is not None else extract_all_commands(text)
        early_allowed = {'show_hud', 'show_help', 'mail_compose'}
        early = [(c, s) for c, s in cmds_early if c in early_allowed]
        if early:
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            for c, seg in early:
                handler.handle(c, seg)
                time.sleep(0.05)
            return
        if handler.interactive_state:
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            handler.handle_interactive(text)
            return
        if getattr(app_state, 'ignore_mode', False):
            cmds_ign = parsed_cmds if parsed_cmds is not None else extract_all_commands(text)
            cmds_listen = [(c, s) for c, s in cmds_ign if c == 'listen_on']
            if cmds_listen:
                app_state.jarvis_active = True
                app_state.last_command_time = time.time()
                for c, seg in cmds_listen:
                    handler.handle(c, seg)
                    time.sleep(0.05)
            return
        elif is_wake:
            app_state.jarvis_active = True; app_state.last_command_time = time.time()
            rest = _WAKE_RE.sub('', text_lower, count=1).strip().strip(',').strip()
            cmds = extract_all_commands(rest) if rest else []
            real = [m for m in cmds if m[0] != 'wake']
            if not real:
                if getattr(app_state, 'ignore_mode', False):
                    return
                handler.handle('wake', 'джарвис')
            else:
                handler.silent_mode = len(real) > 1
                for c, seg in real:
                    handler.handle(c, seg); time.sleep(0.1)
                if handler.silent_mode:
                    handler.silent_mode = False; handler.play_response('confirm', override_silent=True)
    else:
        try:
            from actions.meetings import match_meeting, open_meeting
            matched = match_meeting(text_lower)
            if matched:
                app_state.last_command_time = time.time()
                if open_meeting(matched):
                    handler.speak(f'Открываю — {matched.get("name", "")}.')
                return
        except Exception:
            pass
        cmds = parsed_cmds if parsed_cmds is not None else extract_all_commands(text)
        if getattr(app_state, 'ignore_mode', False) and cmds:
            cmds = [(c, s) for c, s in cmds if c == 'listen_on']
            if not cmds:
                return
        if cmds:
            app_state.last_command_time = time.time()
            has_real = any((c != 'wake' for c, _ in cmds))
            filtered = [(c, seg) for c, seg in cmds if not (has_real and c == 'wake')]
            handler.silent_mode = len(filtered) > 1
            for c, seg in filtered:
                if c == 'dictation_on':
                    from actions.dictation import start_dictation
                    start_dictation(); app_state.dictation_mode = True
                    if not handler.silent_mode: handler.play_response()
                else: handler.handle(c, seg)
                time.sleep(0.1)
            if handler.silent_mode:
                handler.silent_mode = False; handler.play_response('confirm', override_silent=True)
def flush_final(asr, handler, transcribe_queue: _queue_mod.Queue):
    from config_pack.config import RATE as _RATE
    audio = bytes(asr._audio_buffer)
    asr.reset()
    if not audio or not transcribe_queue:
        return
    item = (audio, handler)
    evicted = 0
    while evicted < 200:
        try:
            transcribe_queue.put_nowait(item)
            if evicted:
                try:
                    from core.voice_debug_log import voice_event
                    voice_event(f'QUEUE_EVICT oldest x{evicted} sec={len(audio) / 2 / _RATE:.2f}')
                except Exception:
                    pass
            return
        except _queue_mod.Full:
            try:
                transcribe_queue.get_nowait()
                evicted += 1
            except _queue_mod.Empty:
                break
    try:
        transcribe_queue.put_nowait(item)
    except _queue_mod.Full:
        try:
            from core.voice_debug_log import voice_event
            voice_event(f'QUEUE_FULL dropped sec={len(audio) / 2 / _RATE:.2f} evicted={evicted}')
        except Exception:
            pass
