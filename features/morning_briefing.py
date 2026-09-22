import os
import random
import threading
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from actions.briefing_config import load_briefing_prefs
from core.system import app_state, module_enabled
LOG_DIR  = os.path.join('logs')
LOG_FILE = os.path.join(LOG_DIR, 'last_briefing.txt')
EVENING_LOG_FILE = os.path.join(LOG_DIR, 'last_evening_summary.txt')
MORNING_START = 6
MORNING_END   = 18
EVENING_START = 19
EVENING_END   = 23
_SLOW_TIMEOUT = 8.0
def _read_last_date() -> str:
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''
def _write_today():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(date.today().isoformat())
    except Exception:
        pass
def _read_last_evening_date() -> str:
    try:
        if os.path.exists(EVENING_LOG_FILE):
            with open(EVENING_LOG_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''
def _write_evening_today():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(EVENING_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(date.today().isoformat())
    except Exception:
        pass
def _wait_mixer_idle(timeout: float = 90.0) -> None:
    try:
        from core.speech.tts import wait_for_pygame_mixer_idle
        wait_for_pygame_mixer_idle(timeout=timeout)
    except Exception:
        pass
def _part_greeting(prefs: dict) -> str | None:
    if not prefs.get('include_greeting', True):
        return None
    from core.address import get_address as _ga
    addr = _ga()
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return random.choice([
            f'Доброе утро, {addr}. Все системы функционируют в штатном режиме. Вот краткая сводка.',
            'Доброе утро. Подготовил для вас отчет о состоянии систем и внешней среде.',
            f'С добрым утром, {addr}. Системы в норме. Текущие показатели следующие:',
        ])
    return random.choice([
        f'Добрый день, {addr}. Актуальная статистика по состоянию на текущий момент.',
        'Системы онлайн. Вот актуальный статус ресурсов и окружения.',
        'Добрый день. Все службы работают стабильно. Краткий отчет:',
    ])
def _part_time(prefs: dict) -> str | None:
    if not prefs.get('include_time', True):
        return None
    try:
        from core.nlp import format_time_russian
        now = datetime.now()
        return f'Сейчас {format_time_russian(now.hour, now.minute)}.'
    except Exception:
        return None
def _part_battery(prefs: dict) -> str | None:
    if not prefs.get('include_battery', True):
        return None
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            pct      = int(battery.percent)
            charging = battery.power_plugged
            status   = 'заряжается' if charging else 'работает от батареи'
            return f'Заряд аккумулятора составляет {pct} процентов, система {status}.'
    except Exception:
        pass
    return None
def _part_sysload(prefs: dict) -> str | None:
    if not prefs.get('include_system_load', True):
        return None
    try:
        import psutil
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        if cpu > 80 or ram > 85:
            from core.address import get_address as _ga
            return (f'Внимание, {_ga()}. Наблюдается повышенная нагрузка на ресурсы. '
                    f'Процессор загружен на {int(cpu)} процентов.')
    except Exception:
        pass
    return None
def _part_weather(prefs: dict) -> str | None:
    if not prefs.get('include_weather', True):
        return None
    try:
        from actions.weather import get_weather
        ok, text = get_weather('')
        return text if ok and text else None
    except Exception:
        return None
def _part_weather_calendar_cross(prefs: dict) -> str | None:
    """Warn if the next calendar event falls within a few hours and current
    conditions call for extra clothing/an umbrella — the two facts are useful
    together in a way neither is alone."""
    if not prefs.get('include_weather', True) or not prefs.get('include_calendar', True):
        return None
    if not module_enabled('calendar_ics'):
        return None
    try:
        from actions.calendar_ics import next_event_dt
        ev = next_event_dt()
        if not ev:
            return None
        dt, title = ev
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        hours_until = (dt - now).total_seconds() / 3600
        if not (0 <= hours_until <= 3):
            return None
        from actions.weather import get_current_conditions
        cond = get_current_conditions()
        if not cond:
            return None
        desc = (cond.get('desc') or '').lower()
        temp = cond.get('temp', 0)
        bad = any(k in desc for k in ('дощ', 'дождь', 'сніг', 'снег', 'гроза', 'злив', 'ливен', 'мряк', 'морос'))
        if not (bad or temp <= -5):
            return None
        from core.i18n import get_language
        time_str = dt.astimezone().strftime('%H:%M') if dt.tzinfo else dt.strftime('%H:%M')
        if get_language() == 'uk':
            return f'До речі, до події "{title}" о {time_str} зараз {desc}, одягніться відповідно.'
        return f'Кстати, к событию "{title}" в {time_str} сейчас {desc}, оденьтесь соответственно.'
    except Exception:
        return None
def _part_calendar(prefs: dict) -> str | None:
    if not prefs.get('include_calendar', True):
        return None
    if not module_enabled('calendar_ics'):
        return None
    try:
        from actions.calendar_ics import next_events_summary
        cal = next_events_summary(None, max_events=2)
        return cal if cal and not cal.startswith('Календарь не настроен') else None
    except Exception:
        return None
def _part_mail(prefs: dict) -> str | None:
    if not prefs.get('include_mail_unread', True):
        return None
    if not module_enabled('inbox_digest'):
        return None
    try:
        from actions.inbox_imap import unread_count_voice
        return unread_count_voice() or None
    except Exception:
        return None
def build_briefing_parts(handler=None) -> list[str]:
    prefs = load_briefing_prefs()
    fast_parts = [
        _part_greeting(prefs),
        _part_time(prefs),
        _part_battery(prefs),
        _part_sysload(prefs),
    ]
    slow_fns = {
        'weather':  lambda: _part_weather(prefs),
        'calendar': lambda: _part_calendar(prefs),
        'mail':     lambda: _part_mail(prefs),
        'cross':    lambda: _part_weather_calendar_cross(prefs),
    }
    slow_results: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='briefing') as ex:
        future_map = {ex.submit(fn): key for key, fn in slow_fns.items()}
        for future in as_completed(future_map, timeout=_SLOW_TIMEOUT + 1):
            key = future_map[future]
            try:
                slow_results[key] = future.result(timeout=_SLOW_TIMEOUT)
            except Exception:
                slow_results[key] = None
    ordered_slow = [
        slow_results.get('weather'),
        slow_results.get('cross'),
        slow_results.get('calendar'),
        slow_results.get('mail'),
    ]
    return [p for p in fast_parts + ordered_slow if p]
def speak_daily_summary(handler=None) -> None:
    _wait_mixer_idle()
    parts = build_briefing_parts(handler)
    if not parts:
        from core.speech import speak
        speak('Нет данных для сводки.')
        return
    from core.speech import speak
    speak(' '.join(parts))
def _do_briefing(handler):
    import time
    waited = 0.0
    while getattr(handler, 'is_speaking', False) and waited < 10.0:
        time.sleep(0.1)
        waited += 0.1
    time.sleep(0.4)
    prefs = load_briefing_prefs()
    _prefetch: dict = {}
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='briefing-pre') as ex:
        if prefs.get('include_weather', True):
            _prefetch['weather'] = ex.submit(_part_weather, prefs)
        if prefs.get('include_calendar', True) and module_enabled('calendar_ics'):
            _prefetch['calendar'] = ex.submit(_part_calendar, prefs)
        if prefs.get('include_mail_unread', True) and module_enabled('inbox_digest'):
            _prefetch['mail'] = ex.submit(_part_mail, prefs)
        if prefs.get('include_weather', True) and prefs.get('include_calendar', True) and module_enabled('calendar_ics'):
            _prefetch['cross'] = ex.submit(_part_weather_calendar_cross, prefs)
        _wait_mixer_idle()
        prefetch_results: dict[str, str | None] = {}
        for key, fut in _prefetch.items():
            try:
                prefetch_results[key] = fut.result(timeout=_SLOW_TIMEOUT)
            except Exception:
                prefetch_results[key] = None
    fast = [
        _part_greeting(prefs),
        _part_time(prefs),
        _part_battery(prefs),
        _part_sysload(prefs),
    ]
    slow = [
        prefetch_results.get('weather'),
        prefetch_results.get('cross'),
        prefetch_results.get('calendar'),
        prefetch_results.get('mail'),
    ]
    parts = [p for p in fast + slow if p]
    if not parts:
        _write_today()
        return
    from core.speech import speak
    speak(' '.join(parts))
    _write_today()
def _part_evening_greeting() -> str:
    from core.address import get_address as _ga
    return random.choice([
        f'Подводим итоги дня, {_ga()}.',
        'Вот краткий итог сегодняшнего дня.',
        f'Добрый вечер, {_ga()}. Коротко о том, как прошёл день.',
    ])
def _part_tomorrow_weather(prefs: dict) -> str | None:
    if not prefs.get('include_weather', True):
        return None
    try:
        from actions.weather import get_weather
        ok, text = get_weather('', date_offset=1)
        return text if ok and text else None
    except Exception:
        return None
def _part_tomorrow_first_event(prefs: dict) -> str | None:
    if not prefs.get('include_calendar', True) or not module_enabled('calendar_ics'):
        return None
    try:
        from actions.calendar_ics import next_event_dt
        ev = next_event_dt()
        if not ev:
            return None
        dt, title = ev
        tomorrow = date.today() + timedelta(days=1)
        ev_date = dt.astimezone().date() if dt.tzinfo else dt.date()
        if ev_date != tomorrow:
            return None
        time_str = (dt.astimezone() if dt.tzinfo else dt).strftime('%H:%M')
        return f'Завтра первым событием в {time_str} — {title}.'
    except Exception:
        return None
def build_evening_parts(handler=None) -> list[str]:
    prefs = load_briefing_prefs()
    fast_parts = [_part_evening_greeting()]
    slow_fns = {
        'weather': lambda: _part_tomorrow_weather(prefs),
        'event':   lambda: _part_tomorrow_first_event(prefs),
        'mail':    lambda: _part_mail(prefs),
    }
    slow_results: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix='evening') as ex:
        future_map = {ex.submit(fn): key for key, fn in slow_fns.items()}
        for future in as_completed(future_map, timeout=_SLOW_TIMEOUT + 1):
            key = future_map[future]
            try:
                slow_results[key] = future.result(timeout=_SLOW_TIMEOUT)
            except Exception:
                slow_results[key] = None
    ordered_slow = [
        slow_results.get('weather'),
        slow_results.get('event'),
        slow_results.get('mail'),
    ]
    return [p for p in fast_parts + ordered_slow if p]
def _do_evening_summary(handler):
    import time
    waited = 0.0
    while getattr(handler, 'is_speaking', False) and waited < 10.0:
        time.sleep(0.1)
        waited += 0.1
    time.sleep(0.4)
    _wait_mixer_idle()
    parts = build_evening_parts(handler)
    _write_evening_today()
    if not parts:
        return
    from core.speech import speak
    speak(' '.join(parts))
def try_evening_summary(handler):
    if not module_enabled('morning_briefing'):
        return
    now = datetime.now()
    if not EVENING_START <= now.hour < EVENING_END:
        return
    last  = _read_last_evening_date()
    today = date.today().isoformat()
    if last == today:
        return
    t = threading.Thread(target=_do_evening_summary, args=(handler,), daemon=True)
    t.start()
def try_morning_briefing(handler):
    if not module_enabled('morning_briefing'):
        return
    now = datetime.now()
    if not MORNING_START <= now.hour < MORNING_END:
        return
    last  = _read_last_date()
    today = date.today().isoformat()
    if last == today:
        return
    t = threading.Thread(target=_do_briefing, args=(handler,), daemon=True)
    t.start()
