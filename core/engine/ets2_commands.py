"""ETS2 telemetry-driven voice command handling — the fuel/cruise/wipers/
lights/rest-and-wake-up-the-driver logic that only runs while Euro Truck
Simulator 2 telemetry is active in game mode. Split out of
core/engine/recognition.py for file-size only; no behavior change.
"""
import time
import re
import threading as _threading_mod
from core.system import app_state
from core.logging_setup import get_logger as _get_logger
from core.nlp.commands import normalize_numbers

_log = _get_logger('ets2_commands')
_REFUEL_STOP = _threading_mod.Event()
_REST_BASE_HOURS = 9  # ETS2 1.60's rest dialog always opens with the slider on this value

def _confirm_rest_duration(hours: int) -> None:
    """Nudge the rest dialog's slider away from its 9h default to match the
    requested duration, confirm, then hand off to a background watcher that
    waits for the in-game clock to actually reach the wake-up point — the
    dialog fast-forwards time at an unpredictable real-world rate, it doesn't
    jump instantly."""
    from core.speech import speak_async
    from core.nlp.russian import format_duration_russian
    try:
        from actions.game_input import get_binding, press_robust
        from actions.ets2_telemetry import get_game_time
        diff = hours - _REST_BASE_HOURS
        if diff != 0:
            key = get_binding('rest_increase', 'd') if diff > 0 else get_binding('rest_decrease', 'a')
            for _ in range(abs(diff)):
                press_robust(key, duration=0.04)
                time.sleep(0.05)
            time.sleep(0.2)
        start_minutes = get_game_time()
        press_robust(get_binding('action', 'enter'))
        speak_async(f'Принято — отдыхаем {format_duration_russian(hours * 60)}. Спокойной ночи.')
        _threading_mod.Thread(target=_wait_and_wake, args=(start_minutes, hours), daemon=True).start()
    except Exception:
        try:
            import pyautogui as _pag
            _pag.press('enter')
        except Exception:
            pass
        speak_async('Подтверждаю отдых.')

def _greeting_for_game_minutes(minutes: int | None) -> str:
    """Pick a time-of-day-correct greeting from the in-game clock — the rest
    can end at any hour, so a hardcoded 'доброе утро' would be wrong half
    the time."""
    if minutes is None:
        return 'С возвращением, сэр.'
    hour = int((minutes % 1440) // 60)
    if 5 <= hour < 11:
        return 'Доброе утро, сэр.'
    if 11 <= hour < 17:
        return 'Добрый день, сэр.'
    if 17 <= hour < 23:
        return 'Добрый вечер, сэр.'
    return 'На улице глубокая ночь, сэр, но отдых окончен.'

def _wait_and_wake(start_minutes: int | None, hours: int) -> None:
    """Poll the telemetry clock until it has actually advanced by the chosen
    rest duration, then bring the truck back to life.

    The clock doesn't jump instantly — it fast-forwards at an unpredictable
    real-world rate while a loading screen briefly takes over. The clock
    keeps ticking normally even right after that load finishes (it's never
    frozen), so we can't detect "control handed back" by waiting for two
    identical readings — that condition never occurs. A short fixed buffer
    after the target is reached is enough to clear the load."""
    from actions.ets2_telemetry import get_game_time
    target = (start_minutes + hours * 60) if start_minutes is not None else None
    deadline = time.time() + min(180.0, max(25.0, hours * 6.0))
    cur = None
    while time.time() < deadline:
        time.sleep(1.0)
        cur = get_game_time()
        if target is not None and cur is not None and cur >= target:
            break
    time.sleep(2.5)
    wake_minutes = get_game_time()
    if wake_minutes is None:
        wake_minutes = cur if cur is not None else target
    _wake_up_truck(hours, wake_minutes)

def _wake_up_truck(slept_hours: int | None, wake_minutes: int | None = None) -> None:
    """Start the engine, release the handbrake and prep lights after a rest stop.
    slept_hours/wake_minutes are known when triggered automatically after
    go_to_sleep; both are None when this still gets called directly."""
    try:
        from core.speech import speak_async
        from actions.ets2_telemetry import get as _tget
        from actions.game_input import get_binding, cast_command, press_robust
        from actions import keysend
        data = _tget()
        engine_key = get_binding('engine', 'e')
        try:
            keysend.key_down(engine_key)
            time.sleep(2.0)
            keysend.key_up(engine_key)
        except Exception:
            press_robust(engine_key, duration=2.0)
        time.sleep(0.5)
        if data and data.get('parkBrake'):
            press_robust(get_binding('handbrake', 'space'))
            time.sleep(0.3)
        if slept_hours is not None:
            from core.nlp.russian import format_duration_russian
            greeting = _greeting_for_game_minutes(wake_minutes)
            speak_async(f'{greeting} Отдохнули знатно — спали {format_duration_russian(slept_hours * 60)}. Заводим тягач и трогаемся.')
        cast_command('подготовь тягач', fuzzy_threshold=0.9)
    except Exception:
        pass
def _handle_telemetry_action(action: str, handler, text: str = '') -> None:
    def _speak(msg: str):
        try:
            from core.speech import speak_async
            speak_async(msg)
        except Exception as _e:
            _log.warning('_speak failed in telemetry action: %s', _e)
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
    except ImportError: return

    print(f"[RECOGNITION] Executing telemetry action: {action!r} (Source text: {text!r})", flush=True)
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
                else:
                    from core.address import get_address as _ga
                    _speak(f'{_ga().capitalize()}, водитель очень устал. До обязательного отдыха {txt}.')
    elif action == 'break_time':
        from core.address import get_address as _ga
        _speak(f'Аварийка включена, ручник затянут, двигатель заглушен. Хорошего отдыха, {_ga()}.')
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
    elif action == 'session_report':
        try:
            from features.ets2 import get_session_report
            _speak(get_session_report())
        except Exception: _speak('Не удалось получить отчёт по сессии.')
    elif action == 'schedule_status':
        try:
            from features.ets2 import get_schedule_status
            _speak(get_schedule_status())
        except Exception: _speak('Не удалось оценить график рейса.')
    elif action == 'cruise_off':
        from actions.ets2_telemetry import get_cruise_active
        if get_cruise_active() is True:
            from actions.game_input import get_binding, press_robust
            press_robust(get_binding('cruise', 'c'))
    elif action == 'cruise_set':
        nums = re.findall(r'\d+', normalize_numbers(text.lower()))
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
        nums = re.findall(r'\d+', normalize_numbers(text.lower()))
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
        # The 'text' argument now contains the clean text_for_game
        t = normalize_numbers(text.lower())

        want: int | None = None

        # Check for specific words first (more robust than numbers)
        if any(w in t for w in ('нейтрал', 'neutral')):
            want = 0
        elif any(w in t for w in ('задн', 'реверс', 'reverse', 'назад', 'задка')):
            want = -1
        else:
            nums = re.findall(r'\d+', t)
            if nums:
                want = int(nums[0])
        
        if want is None:
            _speak('Скажите номер передачи или режим (нейтраль, задний ход).')
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
            _mon.set_auto_cruise(False, by_user=True)
            _speak('Авто-круиз выключен. Управляйте круиз-контролем вручную.')
        except Exception:
            pass
    elif action == 'go_to_sleep':
        # ETS2 1.60: Enter no longer sleeps directly - it opens the "Otdykh" dialog
        # with a duration slider that the game always opens at its 9h default
        # (range 1-24h, step 1h, A/D keys). We adjust relative to that known
        # default instead of guessing the slider's current position.
        t = normalize_numbers(text.lower())
        nums = re.findall(r'\d+', t)
        hours = None
        if nums:
            try:
                hours = max(1, min(24, int(nums[0])))
            except Exception:
                hours = None
        try:
            from actions.ets2_telemetry import get as _tget
            from actions.game_input import get_binding, cast_command, press_robust
            data = _tget()
            if data:
                if not data.get('parkBrake'):
                    press_robust(get_binding('handbrake', 'space'))
                    time.sleep(0.3)
                # Engine must be off before the rest prompt becomes available
                if data.get('engineEnabled'):
                    press_robust(get_binding('engine', 'e'))
                    time.sleep(0.3)
                cast_command('fake_text_for_lights', fuzzy_threshold=1.0)
                from actions.ets2_telemetry import get_lights_low
                if get_lights_low():
                    press_robust(get_binding('lights_main', 'l'))
                    time.sleep(0.1)
                    press_robust(get_binding('lights_main', 'l'))
                time.sleep(0.5)
            # Open the rest dialog (opens with the 9h default already selected)
            press_robust(get_binding('action', 'enter'))
            time.sleep(0.6)
        except Exception:
            try:
                import pyautogui as _pag
                _pag.press('enter')
            except Exception:
                pass
            return
        if hours is None:
            from core.address import get_address as _ga
            _speak(f'Готовлю кабину ко сну, {_ga()}. На сколько часов ставим отдых — оставляем стандартные {_REST_BASE_HOURS}?')
            handler._set_interactive('rest_hours_ask', {}, timeout=15.0)
        else:
            _confirm_rest_duration(hours)
    elif action == 'wake_up':
        _wake_up_truck(None)
    elif action == 'close_game':
        from core.system import app_state as _as
        _as.game_mode = False
        try:
            from actions.game_input import unload_profile
            unload_profile()
        except Exception: pass
        try:
            from features.planetbase import monitor as pb_monitor
            pb_monitor.stop()
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
                from actions import keysend
                from actions.ets2_telemetry import get as _tget
                from actions.game_input import get_binding, press_robust

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
                keysend.key_down(key)
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
                keysend.key_up(key)
                if _REFUEL_STOP.is_set():
                    _speak(f'Заправка остановлена. Бак {int(pct)} процентов.')
                elif pct >= 99.0:
                    _speak('Бак полный. Заправка завершена. Запускаю все системы.')
                    _time.sleep(0.5)
                    # Start engine and prepare truck
                    from actions.game_input import cast_command as _cc
                    _cc('подготовь тягач', fuzzy_threshold=0.9)
                else:
                    _speak(f'Заправка прервана. Бак {int(pct)} процентов.')
            except Exception as _re:
                try:
                    from actions import keysend
                    from actions.game_input import get_binding
                    keysend.key_up(get_binding('refuel', 'r'))
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
            from actions import keysend
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
                    print(f"[INPUT] Pressing key: {hb_key!r} (duration=0.1s)", flush=True)
                    try:
                        keysend.key_down(hb_key)
                        time.sleep(0.1)
                        keysend.key_up(hb_key)
                    except Exception as e:
                        print(f"[INPUT] Error pressing {hb_key!r}: {e}", flush=True)
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
