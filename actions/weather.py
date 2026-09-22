import time
import concurrent.futures
from core.i18n import get_language
from config_pack.config import get_settings_path

_weather_cache = {}
_CACHE_TTL_SEC = 600
_hud_cache: dict = {}
_HUD_TTL_SEC = 600
_WMO_ICON = {0: ('☀', '#ffcc00'), 1: ('🌤', '#ffcc00'), 2: ('⛅', '#aabbcc'), 3: ('☁', '#8899aa'), 45: ('🌫', '#8899aa'), 48: ('🌫', '#8899aa'), 51: ('🌦', '#44aaff'), 53: ('🌦', '#44aaff'), 55: ('🌧', '#2288ff'), 56: ('🌧', '#88ccff'), 57: ('🌧', '#66bbff'), 61: ('🌧', '#44aaff'), 63: ('🌧', '#2288ff'), 65: ('🌧', '#0066ff'), 66: ('🌧', '#88ccff'), 67: ('🌧', '#66bbff'), 71: ('❄', '#aaddff'), 73: ('❄', '#88ccff'), 75: ('❄', '#66bbff'), 77: ('❄', '#aaddff'), 80: ('🌦', '#44aaff'), 81: ('🌧', '#2288ff'), 82: ('⛈', '#0044cc'), 85: ('❄', '#88ccff'), 86: ('❄', '#66bbff'), 95: ('⛈', '#cc44ff'), 96: ('⛈', '#cc44ff'), 99: ('⛈', '#cc44ff')}

_WMO_DESC_RU = {
    0: 'Ясно', 1: 'Преимущественно ясно', 2: 'Переменная облачность', 3: 'Пасмурно',
    45: 'Туман', 48: 'Иней', 51: 'Моросящий дождь', 53: 'Моросящий дождь',
    55: 'Плотный моросящий дождь', 56: 'Ледяная морось', 57: 'Плотная ледяная морось',
    61: 'Небольшой дождь', 63: 'Умеренный дождь',
    65: 'Сильный дождь', 66: 'Небольшой ледяной дождь', 67: 'Сильный ледяной дождь',
    71: 'Небольшой снегопад', 73: 'Умеренный снегопад',
    75: 'Сильный снегопад', 77: 'Снежные зерна', 80: 'Слабый ливень', 81: 'Умеренный ливень',
    82: 'Сильный ливень', 85: 'Небольшой снежный ливень', 86: 'Сильный снежный ливень',
    95: 'Гроза', 96: 'Гроза с небольшим градом', 99: 'Гроза с сильным градом'
}

_WMO_DESC_UK = {
    0: 'Ясно', 1: 'Переважно ясно', 2: 'Мінлива хмарність', 3: 'Похмуро',
    45: 'Туман', 48: 'Паморозь', 51: 'Мряка', 53: 'Мряка',
    55: 'Густа мряка', 56: 'Льодяна мряка', 57: 'Густа льодяна мряка',
    61: 'Невеликий дощ', 63: 'Помірний дощ',
    65: 'Сильний дощ', 66: 'Невеликий льодяний дощ', 67: 'Сильний льодяний дощ',
    71: 'Невеликий снігопад', 73: 'Помірний снігопад',
    75: 'Сильний снігопад', 77: 'Снігові зерна', 80: 'Слабкий зливовий дощ', 81: 'Помірний зливовий дощ',
    82: 'Сильна злива', 85: 'Невеликий сніговий злив', 86: 'Сильний сніговий злив',
    95: 'Гроза', 96: 'Гроза з невеликим градом', 99: 'Гроза з сильним градом'
}

def _get_wmo_desc(code: int, lang: str) -> str:
    desc_dict = _WMO_DESC_UK if lang == 'uk' else _WMO_DESC_RU
    return desc_dict.get(code, 'неизвестные условия' if lang == 'ru' else 'невідомі умови')
def _parse_geo_json(name: str, data: dict) -> tuple[float, float, str] | None:
    if name == "ipapi":
        lat = data.get('latitude')
        lon = data.get('longitude')
        city = data.get('city') or 'Ваш город'
    elif name == "ipwho":
        if data.get('success') is False:
            return None
        lat = data.get('latitude')
        lon = data.get('longitude')
        city = data.get('city') or 'Ваш город'
    else:
        loc = (data.get('loc') or '').strip()
        if ',' not in loc:
            return None
        lat_s, lon_s = loc.split(',', 1)
        lat = lat_s.strip()
        lon = lon_s.strip()
        city = data.get('city') or 'Ваш город'
    if lat is None or lon is None:
        return None
    return (float(lat), float(lon), str(city))
def _ip_geolocation(headers: dict, timeout: float = 2.0) -> tuple[float, float, str] | None:
    import requests, subprocess, os
    lang = get_language()
    
    # 1. Try native Windows Geolocation Service (highly precise Wi-Fi/cellular triangulation)
    if os.name == 'nt':
        try:
            ps_script = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.Device') | Out-Null; "
                "$watcher = New-Object System.Device.Location.GeoCoordinateWatcher; "
                "$watcher.Start(); Start-Sleep -Milliseconds 600; "
                "$pos = $watcher.Position.Location; "
                "if (!$pos.IsUnknown) { Write-Output \"$($pos.Latitude),$($pos.Longitude)\" }"
            )
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            out = subprocess.check_output(
                ['powershell', '-NoProfile', '-Command', ps_script],
                startupinfo=startupinfo, timeout=2.5, shell=False,
            ).decode('utf-8', errors='ignore').strip()
            if out and ',' in out:
                lat_s, lon_s = out.split(',', 1)
                lat_val = float(lat_s.strip())
                lon_val = float(lon_s.strip())
                if lat_val != 0.0 and lon_val != 0.0:
                    # Fetch nearest beautiful town name from a quick IP API fallback
                    city_name = 'Ваша локація' if lang == 'uk' else 'Ваша локация'
                    try:
                        resp = requests.get(f"https://ipwho.is/?lang={lang}", headers=headers, timeout=2.0)
                        if resp.status_code == 200:
                            city_name = resp.json().get('city') or city_name
                    except Exception: pass
                    return (lat_val, lon_val, city_name)
        except Exception:
            pass

    # 2. Fallback to IP Geolocation Providers if Windows Location Service is off/unavailable
    providers = (
        ("ipwho", f"https://ipwho.is/?lang={lang}"),
        ("ip-api", f"http://ip-api.com/json/?lang={lang}"),
        ("ipapi", "https://ipapi.co/json/"),
    )
    def fetch_one(pair: tuple[str, str]) -> tuple[float, float, str] | None:
        name, url = pair
        try:
            resp = requests.get(url, headers=headers, timeout=5.0)
            if resp.status_code != 200:
                return None
            return _parse_geo_json(name, resp.json())
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_one, p) for p in providers]
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=10.0):
                try:
                    r = fut.result()
                    if r:
                        return r
                except Exception:
                    pass
        except TimeoutError:
            pass
    return None
def _load_last_location() -> tuple[float, float, str] | None:
    try:
        import json, os
        p = get_settings_path()
        if not os.path.exists(p):
            return None
        with open(p, 'r', encoding='utf-8') as f:
            s = json.load(f)
        loc = s.get('last_location')
        if not isinstance(loc, dict):
            return None
        lat = loc.get('lat')
        lon = loc.get('lon')
        city = loc.get('city') or 'Ваш город'
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon), str(city))
    except Exception:
        return None
def _save_last_location(lat: float, lon: float, city: str) -> None:
    try:
        import json, os
        p = get_settings_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        s = {}
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    s = json.load(f)
            except Exception:
                s = {}
        if not isinstance(s, dict):
            s = {}
        s['last_location'] = {'lat': float(lat), 'lon': float(lon), 'city': str(city)}
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
# wttr.in uses WWO codes (differ from WMO). Maps to (ru_desc, uk_desc, icon, color).
_WTTR_CODE_MAP: dict[int, tuple[str, str, str, str]] = {
    113: ('Ясно',                    'Ясно',                     '☀',  '#ffcc00'),
    116: ('Переменная облачность',   'Мінлива хмарність',        '🌤', '#ffcc00'),
    119: ('Облачно',                 'Хмарно',                   '⛅', '#aabbcc'),
    122: ('Пасмурно',                'Похмуро',                  '☁',  '#8899aa'),
    143: ('Туман',                   'Туман',                    '🌫', '#8899aa'),
    176: ('Местами дождь',           'Місцями дощ',              '🌦', '#44aaff'),
    179: ('Местами снег',            'Місцями сніг',             '🌨', '#aaddff'),
    182: ('Мокрый снег',             'Мокрий сніг',              '🌨', '#88ccff'),
    185: ('Ледяная морось',          'Льодяна мряка',            '🌧', '#66bbff'),
    200: ('Грозы поблизости',        'Грози поблизу',            '⛈', '#cc44ff'),
    227: ('Метель',                  'Хуртовина',                '❄',  '#aaddff'),
    230: ('Вьюга',                   'Завірюха',                 '❄',  '#66bbff'),
    248: ('Туман',                   'Туман',                    '🌫', '#8899aa'),
    260: ('Ледяной туман',           'Льодяний туман',           '🌫', '#8899aa'),
    263: ('Небольшая морось',        'Невелика мряка',           '🌦', '#44aaff'),
    266: ('Морось',                  'Мряка',                    '🌦', '#44aaff'),
    281: ('Ледяная морось',          'Льодяна мряка',            '🌧', '#44aaff'),
    284: ('Сильная ледяная морось',  'Сильна льодяна мряка',     '🌧', '#2288ff'),
    293: ('Небольшой дождь',         'Невеликий дощ',            '🌦', '#44aaff'),
    296: ('Небольшой дождь',         'Невеликий дощ',            '🌧', '#44aaff'),
    299: ('Умеренный дождь',         'Помірний дощ',             '🌧', '#2288ff'),
    302: ('Умеренный дождь',         'Помірний дощ',             '🌧', '#2288ff'),
    305: ('Сильный дождь',           'Сильний дощ',              '🌧', '#0066ff'),
    308: ('Сильный дождь',           'Сильний дощ',              '🌧', '#0044cc'),
    311: ('Ледяной дождь',           'Льодяний дощ',             '🌧', '#66bbff'),
    314: ('Сильный ледяной дождь',   'Сильний льодяний дощ',     '🌧', '#44aaff'),
    317: ('Мокрый снег',             'Мокрий сніг',              '🌨', '#88ccff'),
    320: ('Сильный мокрый снег',     'Сильний мокрий сніг',      '🌨', '#66bbff'),
    323: ('Небольшой снег',          'Невеликий снігопад',       '❄',  '#aaddff'),
    326: ('Небольшой снег',          'Невеликий снігопад',       '❄',  '#aaddff'),
    329: ('Умеренный снег',          'Помірний снігопад',        '❄',  '#88ccff'),
    332: ('Умеренный снег',          'Помірний снігопад',        '❄',  '#88ccff'),
    335: ('Сильный снег',            'Сильний снігопад',         '❄',  '#66bbff'),
    338: ('Сильный снег',            'Сильний снігопад',         '❄',  '#66bbff'),
    350: ('Ледяная крупа',           'Льодяна крупа',            '🌨', '#88ccff'),
    353: ('Слабый ливень',           'Слабка злива',             '🌦', '#44aaff'),
    356: ('Умеренный ливень',        'Помірна злива',            '🌧', '#2288ff'),
    359: ('Проливной дождь',         'Зливовий дощ',             '🌧', '#0044cc'),
    362: ('Ливень со снегом',        'Злива зі снігом',          '🌨', '#66bbff'),
    365: ('Сильный ливень со снегом','Сильна злива зі снігом',   '🌨', '#44aaff'),
    368: ('Слабый снегопад',         'Слабкий снігопад',         '❄',  '#aaddff'),
    371: ('Умеренный снегопад',      'Помірний снігопад',        '❄',  '#88ccff'),
    374: ('Ледяная крупа',           'Льодяна крупа',            '🌨', '#88ccff'),
    377: ('Сильная ледяная крупа',   'Сильна льодяна крупа',     '🌨', '#66bbff'),
    386: ('Гроза с дождём',          'Гроза з дощем',            '⛈', '#cc44ff'),
    389: ('Гроза с сильным дождём',  'Гроза з сильним дощем',    '⛈', '#cc44ff'),
    392: ('Гроза со снегом',         'Гроза зі снігом',          '⛈', '#aa44ff'),
    395: ('Гроза с сильным снегом',  'Гроза з сильним снігом',   '⛈', '#aa44ff'),
}

def _wttr_desc(code: int, lang: str) -> tuple[str, str, str]:
    """Return (description, icon, color) for a WWO weather code."""
    entry = _WTTR_CODE_MAP.get(code)
    if entry:
        desc = entry[0] if lang != 'uk' else entry[1]
        return desc, entry[2], entry[3]
    return ('—', '?', '#ffffff')

def _to_24h(t: str) -> str:
    try:
        from datetime import datetime
        return datetime.strptime(t.strip(), '%I:%M %p').strftime('%H:%M')
    except Exception:
        return '—:—'

def _fetch_wttr(lat: float, lon: float, city_name: str, lang: str, headers: dict) -> dict:
    import requests
    url = f'https://wttr.in/{lat},{lon}?format=j1&lang={lang}'
    resp = requests.get(url, headers=headers, timeout=5.0)
    if resp.status_code != 200:
        raise Exception(f'wttr HTTP {resp.status_code}')
    j = resp.json()
    cur = j['current_condition'][0]
    temp = int(cur['temp_C'])
    feels = int(cur['FeelsLikeC'])
    humidity = int(cur.get('humidity', 0))
    wind_ms = round(float(cur.get('windspeedKmph', 0)) / 3.6, 1)
    pressure_mmhg = int(round(float(cur.get('pressure', 0)) * 0.750064))
    code = int(cur.get('weatherCode', 0))
    desc, icon, color = _wttr_desc(code, lang)
    try:
        astro = j['weather'][0]['astronomy'][0]
        sunrise = _to_24h(astro['sunrise'])
        sunset = _to_24h(astro['sunset'])
    except Exception:
        sunrise = sunset = '—:—'
    return {'ok': True, 'city': city_name, 'lat': lat, 'lon': lon,
            'sunrise': sunrise, 'sunset': sunset,
            'temp': temp, 'feels': feels, 'desc': desc, 'icon': icon, 'color': color,
            'wind': wind_ms, 'humidity': humidity, 'pressure': pressure_mmhg,
            'updated_ts': time.time()}

def get_weather_hud() -> dict:
    lang = get_language()
    cache_key = f'data_{lang}'
    cached = _hud_cache.get(cache_key)
    if cached and time.time() - cached['updated_ts'] < _HUD_TTL_SEC:
        return cached
    try:
        import requests, json, os
        headers = {'User-Agent': 'Mozilla/5.0'}

        manual_city = None
        settings_path = get_settings_path()
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                s = json.load(f)
                manual_city = s.get('manual_city')

        lat, lon, city_name = (None, None, None)
        lang = get_language()

        if manual_city:
            city_clean = manual_city.strip()
            geo_url = 'https://geocoding-api.open-meteo.com/v1/search'
            params = {'name': city_clean, 'count': 1, 'language': lang, 'format': 'json'}
            try:
                geo_resp = requests.get(geo_url, params=params, headers=headers, timeout=2)
                geo_data = geo_resp.json()
                if geo_data.get('results'):
                    res = geo_data['results'][0]
                    lat, lon, city_name = res['latitude'], res['longitude'], res.get('name', manual_city)
            except Exception:
                pass

        if lat is None:
            last = _load_last_location()
            if last:
                lat, lon, city_name = last
                # Re-fetch city name in current language via reverse geocoding
                try:
                    rev_url = f'https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage={lang}'
                    rev_resp = requests.get(rev_url, headers=headers, timeout=2)
                    resolved = rev_resp.json().get('city')
                    if resolved:
                        city_name = resolved
                except Exception:
                    pass
            else:
                geo = _ip_geolocation(headers, timeout=1.5)
                if geo:
                    lat, lon, city_name = geo
                    _save_last_location(lat, lon, city_name)
                else:
                    raise Exception("Location not found")

        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m,surface_pressure&daily=sunrise,sunset&wind_speed_unit=ms&timezone=auto'
        resp_obj = requests.get(url, headers=headers, timeout=5.0)
        if resp_obj.status_code != 200:
            raise Exception(f'HTTP {resp_obj.status_code}')
        resp = resp_obj.json()
        w = resp['current']
        code = w['weather_code']
        icon, color = _WMO_ICON.get(code, ('?', '#ffffff'))
        pressure_hpa = w.get('surface_pressure', 0)
        pressure_mmhg = int(round(pressure_hpa * 0.750064))
        try:
            sunrise = resp['daily']['sunrise'][0][-5:]
            sunset = resp['daily']['sunset'][0][-5:]
        except Exception:
            sunrise = sunset = '—:—'
        data = {'ok': True, 'city': city_name, 'lat': lat, 'lon': lon, 'sunrise': sunrise, 'sunset': sunset, 'temp': int(round(w['temperature_2m'])), 'feels': int(round(w['apparent_temperature'])), 'desc': _get_wmo_desc(code, lang), 'icon': icon, 'color': color, 'wind': round(w.get('wind_speed_10m', 0), 1), 'humidity': int(w.get('relative_humidity_2m', 0)), 'pressure': pressure_mmhg, 'updated_ts': time.time()}
    except Exception:
        # open-meteo failed — try wttr.in as fallback
        if lat is not None:
            try:
                data = _fetch_wttr(lat, lon, city_name or '—', lang, headers)
                _hud_cache[cache_key] = data
                return data
            except Exception:
                pass
        # Both APIs failed — return stale cache rather than showing error
        stale = _hud_cache.get(cache_key)
        if stale and stale.get('ok'):
            return stale
        err_msg = 'ПОМИЛКА МЕРЕЖІ' if lang == 'uk' else 'ОШИБКА СЕТИ'
        data = {'ok': False, 'city': '—', 'temp': 0, 'feels': 0, 'desc': err_msg, 'icon': '⚠', 'color': _DIM_COLOR, 'wind': 0, 'humidity': 0, 'pressure': 0, 'updated_ts': time.time()}
    _hud_cache[cache_key] = data
    return data
_DIM_COLOR = '#8e98c9'
def _weather_advice(desc: str, temp: int, wind: float, lang: str) -> str:
    """Short practical tip based on already-resolved description/temp/wind.
    Keyed off keywords in `desc` rather than raw WMO/WWO codes so it works the
    same regardless of which weather API/code space resolved the description."""
    d = desc.lower()
    tips: list[str] = []
    if lang == 'uk':
        if 'гроза' in d:
            tips.append('Можлива гроза, краще побути вдома.')
        elif any(k in d for k in ('дощ', 'злив', 'мряк')):
            tips.append('Візьміть парасольку.')
        if any(k in d for k in ('сніг', 'хуртовин', 'завірюх', 'крупа')):
            tips.append('Будьте обережні на дорозі — сніг.')
        if temp <= -5:
            tips.append('Дуже холодно, одягніться тепліше.')
        elif temp >= 28:
            tips.append('Дуже спекотно, не забудьте воду.')
        if wind >= 10:
            tips.append('Сильний вітер, тримайте капелюх.')
    else:
        if 'гроза' in d:
            tips.append('Возможна гроза, лучше остаться дома.')
        elif any(k in d for k in ('дождь', 'ливен', 'морос')):
            tips.append('Возьмите зонт.')
        if any(k in d for k in ('снег', 'метель', 'вьюг', 'крупа')):
            tips.append('Будьте осторожны на дороге — снег.')
        if temp <= -5:
            tips.append('Очень холодно, оденьтесь теплее.')
        elif temp >= 28:
            tips.append('Очень жарко, не забудьте воду.')
        if wind >= 10:
            tips.append('Сильный ветер, держите шапку.')
    return ' '.join(tips)
def _load_yesterday_temp() -> tuple[str, int] | None:
    try:
        import json, os
        p = get_settings_path()
        if not os.path.exists(p):
            return None
        with open(p, 'r', encoding='utf-8') as f:
            s = json.load(f)
        snap = s.get('weather_yesterday')
        if not isinstance(snap, dict) or 'date' not in snap or 'temp' not in snap:
            return None
        return (str(snap['date']), int(snap['temp']))
    except Exception:
        return None
def _save_today_temp(temp: int) -> None:
    try:
        import json, os
        from datetime import date
        p = get_settings_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        s = {}
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    s = json.load(f)
            except Exception:
                s = {}
        if not isinstance(s, dict):
            s = {}
        today = date.today().isoformat()
        existing = s.get('weather_yesterday')
        # Only overwrite once per day so "yesterday" stays yesterday's temp
        # for the whole current day instead of drifting with every re-check.
        if not (isinstance(existing, dict) and existing.get('date') == today):
            s['weather_yesterday'] = {'date': today, 'temp': int(temp)}
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
def _yesterday_compare_text(temp: int, lang: str) -> str:
    from datetime import date, timedelta
    snap = _load_yesterday_temp()
    _save_today_temp(temp)
    if not snap:
        return ''
    snap_date, snap_temp = snap
    if snap_date != (date.today() - timedelta(days=1)).isoformat():
        return ''
    delta = temp - snap_temp
    if abs(delta) < 2:
        return ''
    if lang == 'uk':
        return f'Це на {abs(delta)} градусів {"тепліше" if delta > 0 else "холодніше"}, ніж учора.'
    return f'Это на {abs(delta)} градусов {"теплее" if delta > 0 else "холоднее"}, чем вчера.'
def _format_current_weather_text(city_name: str, desc: str, temp: int, feels: int, lang: str, wind: float = 0.0) -> str:
    import random
    # Feels-like only adds something when it actually differs — repeating the
    # same number twice ("20 градусов, ощущается как 20") reads as robotic.
    feels_diff = abs(feels - temp) >= 2
    # City name comes from the geocoder in nominative form and isn't declined
    # elsewhere in this codebase, so every variant keeps the safe "в городе X"
    # wrapper instead of guessing a case ending ("в Киеве" vs "в Москве" etc.)
    if lang == 'uk':
        openers = [
            f'У місті {city_name} зараз {desc.lower()}.',
            f'Наразі у місті {city_name} {desc.lower()}.',
            f'У місті {city_name} на цей момент {desc.lower()}.',
        ]
        temp_part = f'{_inflect_degree(temp, lang)}'
        if feels_diff:
            temp_part += f', відчувається як {_inflect_degree(feels, lang)}'
        text = f'{random.choice(openers)} {temp_part.capitalize()}.'
    else:
        openers = [
            f'В городе {city_name} сейчас {desc.lower()}.',
            f'Сейчас в городе {city_name} {desc.lower()}.',
            f'В городе {city_name} на данный момент {desc.lower()}.',
        ]
        temp_part = f'{_inflect_degree(temp, lang)}'
        if feels_diff:
            temp_part += f', ощущается как {_inflect_degree(feels, lang)}'
        text = f'{random.choice(openers)} {temp_part.capitalize()}.'
    compare = _yesterday_compare_text(temp, lang)
    if compare:
        text = f'{text} {compare}'
    advice = _weather_advice(desc, temp, wind, lang)
    return f'{text} {advice}'.strip() if advice else text
def get_current_conditions() -> dict | None:
    """Latest cached HUD weather snapshot (desc/temp/wind), no network call.
    Returns None if nothing fresh is cached — callers should treat that as
    'skip', not fall back to a blocking fetch."""
    lang = get_language()
    d = _hud_cache.get(f'data_{lang}')
    if d and d.get('ok') and time.time() - d.get('updated_ts', 0) < _HUD_TTL_SEC:
        return d
    return None
def is_weather_voice_cached(city: str | None) -> bool:
    key = city.strip().lower() if city else '__auto__'
    c = _weather_cache.get(key)
    return bool(c and time.time() - c['ts'] < _CACHE_TTL_SEC)
def resolve_location(city: str | None, lang: str) -> tuple[float | None, float | None, str | None]:
    """Resolve a city name (or auto-detect via manual-city setting / last known
    location / IP geolocation) into (lat, lon, city_name).
    On failure returns (None, None, X) where X is the city name that failed
    geocoding, or None if it was auto-location that failed — callers use that
    to choose the right localized error message without this function owning
    any user-facing text itself (shared by get_weather and weather_forecast)."""
    import json, os, requests
    headers = {'User-Agent': 'Mozilla/5.0'}
    lat, lon, city_name = None, None, None

    if not city:
        settings_path = get_settings_path()
        manual_city = None
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                manual_city = json.load(f).get('manual_city')

        if manual_city:
            city = manual_city
        else:
            last = _load_last_location()
            if last:
                lat, lon, city_name = last
            else:
                geo = _ip_geolocation(headers, timeout=2.0)
                if not geo:
                    return (None, None, None)
                lat, lon, city_name = geo
                _save_last_location(lat, lon, city_name)

    if city and (lat is None):
        city_clean = city.strip()
        query_name = city_clean
        if len(query_name) > 4 and query_name.lower() not in ('kyiv', 'київ'):
            if query_name.lower().endswith(('е', 'и', 'а', 'у')): query_name = query_name[:-1]

        geo_url = 'https://geocoding-api.open-meteo.com/v1/search'
        params = {'name': query_name, 'count': 1, 'language': lang, 'format': 'json'}
        try:
            geo_resp = requests.get(geo_url, params=params, headers=headers, timeout=2)
            geo_data = geo_resp.json()
            if geo_data.get('results'):
                result = geo_data['results'][0]
                lat, lon, city_name = result['latitude'], result['longitude'], result.get('name', city)
        except Exception:
            pass

        if lat is None:
            return (None, None, city)

    return (lat, lon, city_name)
def _location_error_text(city_name: str | None, lang: str) -> str:
    if city_name:
        return f'Місто {city_name} не знайдено.' if lang == 'uk' else f'Город {city_name} не найден.'
    return 'Помилка при визначенні місця розташування.' if lang == 'uk' else 'Ошибка при определении местоположения.'
def get_weather(city: str | None, date_offset: int = 0) -> tuple[bool, str]:
    cache_key = f"{city.strip().lower() if city else '__auto__'}_{date_offset}"
    cached = _weather_cache.get(cache_key)
    if cached and time.time() - cached['ts'] < _CACHE_TTL_SEC:
        return (cached['ok'], cached['text'])

    lang = get_language()
    # "What's the weather" (no city, today) is the common case, and the HUD
    # widget already polls this exact same default location every 10 minutes
    # (see ui/hud_weather.py) — reuse a still-fresh HUD fetch instead of making
    # a second network round-trip for the same conditions.
    if not city and date_offset == 0:
        hud_cached = _hud_cache.get(f'data_{lang}')
        if hud_cached and hud_cached.get('ok') and time.time() - hud_cached.get('updated_ts', 0) < _HUD_TTL_SEC:
            text = _format_current_weather_text(hud_cached['city'], hud_cached['desc'], hud_cached['temp'], hud_cached['feels'], lang, hud_cached.get('wind', 0.0))
            _weather_cache[cache_key] = {'ok': True, 'text': text, 'ts': time.time()}
            return (True, text)

    if date_offset != 0:
        from actions.weather_forecast import get_forecast
        try:
            ok, text = get_forecast(city, date_offset)
        except Exception as e:
            return (False, f'Ошибка при получении прогноза: {str(e)}')
        if ok:
            _weather_cache[cache_key] = {'ok': True, 'text': text, 'ts': time.time()}
        return (ok, text)

    try:
        import requests
        lat, lon, city_name = resolve_location(city, lang)
        if lat is None:
            return (False, _location_error_text(city_name, lang))

        headers = {'User-Agent': 'Mozilla/5.0'}
        weather_url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&wind_speed_unit=ms'
        w_data = requests.get(weather_url, headers=headers, timeout=2.5).json()
        current = w_data['current']
        temp, feels, code = int(round(current['temperature_2m'])), int(round(current['apparent_temperature'])), current['weather_code']
        wind = current.get('wind_speed_10m', 0.0)
        desc = _get_wmo_desc(code, lang)
        result_text = _format_current_weather_text(city_name, desc, temp, feels, lang, wind)

        _weather_cache[cache_key] = {'ok': True, 'text': result_text, 'ts': time.time()}
        return (True, result_text)
    except Exception as e:
        return (False, f'Ошибка при получении погоды: {str(e)}')

def _inflect_degree(n: int, lang: str = 'ru') -> str:
    abs_n = abs(n)
    if 11 <= (abs_n % 100) <= 19:
        return f"{n} градусів" if lang == 'uk' else f"{n} градусов"
    last_digit = abs_n % 10
    if last_digit == 1:
        return f"{n} градус"
    if 2 <= last_digit <= 4:
        return f"{n} градуси" if lang == 'uk' else f"{n} градуса"
    return f"{n} градусів" if lang == 'uk' else f"{n} градусов"
