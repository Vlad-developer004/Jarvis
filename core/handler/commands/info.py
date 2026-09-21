import threading
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('info')

def _currency_rate(handler, cmd, text_lower):
    from actions.currency import get_rate, CURRENCY_ALIASES
    target = 'usd'
    # sort longest first to avoid 'btc' matching before 'bitcoin'
    for alias in sorted(CURRENCY_ALIASES, key=len, reverse=True):
        if alias in text_lower:
            target = CURRENCY_ALIASES[alias]
            break
    _log.debug('currency: text=%r → target=%s', text_lower, target)
    def _rate_task():
        ok, res, url = get_rate(target)
        if ok and url:
            import webbrowser
            webbrowser.open(url)
        handler.speak(res)
    threading.Thread(target=_rate_task, daemon=True).start()

def _weather(handler, cmd, text_lower):
    from actions.weather import get_weather, is_weather_voice_cached, extract_date_offset
    import re
    offset, q = extract_date_offset(text_lower)
    fillers = ['какая', 'какую', 'будет', 'узнай', 'скажи', 'сейчас', 'погода', 'погоду', 'в', 'городе', 'сегодня', 'на', 'улице', 'там', 'же', 'а']
    for sw in fillers:
        q = re.sub(rf'\b{sw}\b', '', q)
    loc = q.strip()
    loc_arg = loc if loc else None

    cache_key = loc_arg if loc_arg else f"__auto___{offset}"
    if not is_weather_voice_cached(cache_key):
        city_display = loc_arg if loc_arg else '(текущее местоположение)'
        handler.speak(spk('weather.fetching', city=city_display), wait=True)

    def _w_task():
        ok, res = get_weather(loc_arg, date_offset=offset)
        handler.speak(res)
    threading.Thread(target=_w_task, daemon=True).start()

def _set_weather_city(handler, cmd, text_lower):
    import re, json, os
    q = text_lower
    for sw in ['установи', 'город', 'запомни', 'смени', 'мой', 'на']:
        q = re.sub(rf'\b{sw}\b', '', q)
    city = q.strip().title()
    if city:
        try:
            from config_pack.config import get_settings_path
            settings_path = get_settings_path()
            s = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    s = json.load(f)
            s['manual_city'] = city
            # Clear HUD cache to force refresh
            from actions.weather import _hud_cache
            _hud_cache.clear()
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            handler.speak(spk('weather.city_saved', city=city))
        except Exception:
            handler.speak(spk('weather.city_save_error'))
    else:
        handler.speak(spk('weather.ask_city'))
        handler._set_interactive('weather_city_ask', {}, timeout=20.0)

def _google_search(handler, cmd, text_lower):
    import webbrowser
    from urllib.parse import quote
    q = text_lower
    for sw in ['найди в гугле', 'найди в google', 'загугли', 'гугли',
               'найди', 'гугле', 'гугла', 'гуглу', 'гугл', 'google',
               'поиске', 'поиска', 'поиск', 'ищи']:
        q = q.replace(sw, '')
    q = ' '.join(w for w in q.split() if len(w) > 1)
    q = q.strip()
    if q:
        webbrowser.open(f"https://www.google.com/search?q={quote(q, safe='')}")
        handler.play_response()
    else:
        handler.speak(spk('search.ask_query'))
        handler._set_interactive('google_ask', {}, timeout=20.0)

def _translate(handler, cmd, text_lower):
    if any(w in text_lower for w in ['это', 'текст', 'выделенное']) or cmd == 'translate':
        from actions.system import translate_selected
        target = 'русский' if ' на русский' in text_lower else 'английский'
        if ' на ' in text_lower:
            target = text_lower.split(' на ')[-1].strip()
        handler.speak(spk('translate.translating_v2', lang=target))
        def _browser_translate_task():
            ok, msg = translate_selected(target)
            if not ok:
                handler.speak(spk('translate.problem', msg=msg))
        threading.Thread(target=_browser_translate_task, daemon=True).start()
        return
    import re
    m = re.search(r'(?:слово|фраза|предложение)\s+(.+?)(?:\s+на\s+(\w+))?$', text_lower)
    if not m: m = re.search(r'переведи\s+(.+?)(?:\s+на\s+(\w+))?$', text_lower)
    if m:
        query = m.group(1).strip()
        target_lang = m.group(2).strip() if m.group(2) else 'английский'
        def _translate_task():
            from actions.system import LANG_MAP
            import requests
            lang_code = LANG_MAP.get(target_lang.lower(), 'en')
            try:
                url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(query)}&langpair=ru|{lang_code}"
                r = requests.get(url, timeout=5)
                data = r.json()
                translation = data.get('responseData', {}).get('translatedText', '')
                if translation: handler.speak(spk("translate.result_v2", text=translation))
                else: handler.speak(spk("translate.fetch_error"))
            except Exception as e:
                handler.speak(spk("translate.generic_error"))
        threading.Thread(target=_translate_task, daemon=True).start()
    else:
        handler.speak(spk("translate.ask_text"))
        handler._set_interactive('translate_ask', {}, timeout=30.0)

def _my_ip(handler, cmd, text_lower):
    from actions.system_control import get_my_ip
    handler.speak(spk("ip.fetching"))
    def _ip_task():
        handler.speak(get_my_ip())
    threading.Thread(target=_ip_task, daemon=True).start()

def _nasa_apod(handler, cmd, text_lower):
    from actions.nasa import get_apod
    handler.speak(spk('nasa.fetching'), wait=True)
    def _apod_task():
        r = get_apod()
        if not r['ok']:
            handler.speak(r['error'])
            return
        # NASA's title/explanation are English-only — shown as text, never
        # spoken (see actions/nasa.py's module docstring for why).
        display_text = f"{r['title']}\n\n{r['explanation']}"
        try:
            from ui.hud_ai_window import show_ai_window, update_ai_window_text, set_ai_window_image, set_ai_window_video, hide_ai_window
            show_ai_window('NASA · Картинка дня', fetch_image=False)
            update_ai_window_text(display_text)
            if r['media_type'] == 'video':
                if r.get('video_path'):
                    set_ai_window_video(r['video_path'])
                handler.speak(spk('nasa.ready_video'))
            else:
                if r.get('image_path'):
                    set_ai_window_image(r['image_path'])
                handler.speak(spk('nasa.ready'))
            hide_ai_window(delay_ms=8000)
        except Exception:
            handler.speak(spk('nasa.ready'))
    threading.Thread(target=_apod_task, daemon=True).start()

def _system_specs(handler, cmd, text_lower):
    def _specs_task():
        import platform
        import psutil
        import os
        try:
            cpu = platform.processor() or "Неизвестный процессор"
            ram = round(psutil.virtual_memory().total / (1024**3), 1)

            # Try to get GPU via WMI (Windows)
            gpu = "Неизвестная видеокарта"
            try:
                import subprocess
                output = subprocess.check_output(
                    ['powershell', '-NoProfile', '-Command',
                     'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'],
                    shell=False, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                ).decode('utf-8', errors='ignore')
                lines = [l.strip() for l in output.split('\n') if l.strip()]
                if lines: gpu = lines[0]
            except Exception: pass

            res = f"Конфигурация системы: Процессор {cpu}. Оперативная память {ram} гигабайт. Видеокарта {gpu}."
            handler.speak(res)
        except Exception as e:
            handler.speak(spk("specs.error"))
    threading.Thread(target=_specs_task, daemon=True).start()

_INFO_ACTIONS = {
    'currency_rate': _currency_rate,
    'weather': _weather,
    'set_weather_city': _set_weather_city,
    'google_search': _google_search,
    'translate': _translate,
    'translate_speech': _translate,
    'my_ip': _my_ip,
    'system_specs': _system_specs,
    'nasa_apod': _nasa_apod,
}

def handle_info(handler, cmd, text_lower):
    action = _INFO_ACTIONS.get(cmd)
    if action:
        action(handler, cmd, text_lower)
