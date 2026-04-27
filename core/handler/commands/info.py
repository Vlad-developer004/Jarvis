import threading
def handle_info(handler, cmd, text_lower):
    if cmd == 'currency_rate':
        from actions.currency import get_rate, CURRENCY_ALIASES
        target = 'usd'
        for alias, key in CURRENCY_ALIASES.items():
            if alias in text_lower:
                target = key
                break
        def _rate_task():
            ok, res, url = get_rate(target)
            if ok and url:
                import webbrowser
                webbrowser.open(url)
            handler.speak(res)
        threading.Thread(target=_rate_task, daemon=True).start()
    elif cmd == 'weather':
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
            handler.speak('Секунду, сэр.')
        
        def _w_task():
            ok, res = get_weather(loc_arg, date_offset=offset)
            handler.speak(res)
        threading.Thread(target=_w_task, daemon=True).start()
    elif cmd == 'set_weather_city':
        import re, json, os
        q = text_lower
        for sw in ['установи', 'город', 'запомни', 'смени', 'мой', 'на']:
            q = re.sub(rf'\b{sw}\b', '', q)
        city = q.strip().title()
        if city:
            try:
                settings_path = os.path.join('data', 'jarvis_settings.json')
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
                handler.speak(f"Хорошо, сэр. Теперь я буду показывать погоду для города {city}.")
            except Exception:
                handler.speak("Не удалось сохранить настройки города.")
        else:
            handler.speak("Какой город мне запомнить?")
    elif cmd == 'google_search':
        import webbrowser
        from urllib.parse import quote
        q = text_lower
        for sw in ['найди', 'гугл', 'google', 'поиск', 'ищи']:
            q = q.replace(sw, '')
        q = q.strip()
        if q:
            webbrowser.open(f"https://www.google.com/search?q={quote(q, safe='')}")
            handler.play_response()
        else:
            handler.speak('Что именно мне найти, сэр?')
    elif cmd in ['translate', 'translate_speech']:
        if any(w in text_lower for w in ['это', 'текст', 'выделенное']) or cmd == 'translate':
            from actions.system import translate_selected
            target = 'русский' if ' на русский' in text_lower else 'английский'
            if ' на ' in text_lower:
                target = text_lower.split(' на ')[-1].strip()
            handler.speak(f"Перевожу на {target}")
            def _browser_translate_task():
                ok, msg = translate_selected(target)
                if not ok:
                    handler.speak(f"Проблема с переводом: {msg}")
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
                    if translation: handler.speak(f"Это переводится как: {translation}")
                    else: handler.speak("Не удалось получить перевод.")
                except Exception as e:
                    handler.speak("Произошла ошибка при переводе.")
            threading.Thread(target=_translate_task, daemon=True).start()
        else:
            handler.speak("Я не понял, что именно нужно перевести.")
    elif cmd == 'my_ip':
        from actions.system_control import get_my_ip
        handler.speak("Получаю ваш IP адрес, сэр...")
        def _ip_task():
            handler.speak(get_my_ip())
        threading.Thread(target=_ip_task, daemon=True).start()
    elif cmd == 'system_specs':
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
                    cmd_gpu = 'powershell -command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"'
                    output = subprocess.check_output(cmd_gpu, shell=True, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
                    lines = [l.strip() for l in output.split('\n') if l.strip()]
                    if lines: gpu = lines[0]
                except Exception: pass
                
                res = f"Конфигурация системы: Процессор {cpu}. Оперативная память {ram} гигабайт. Видеокарта {gpu}."
                handler.speak(res)
            except Exception as e:
                handler.speak("Не удалось собрать полные характеристики системы.")
        threading.Thread(target=_specs_task, daemon=True).start()
