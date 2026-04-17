import time
import concurrent.futures
_weather_cache = {}
_CACHE_TTL_SEC = 600
_hud_cache: dict = {}
_HUD_TTL_SEC = 600
_WMO_ICON = {0: ('☀', '#ffcc00'), 1: ('🌤', '#ffcc00'), 2: ('⛅', '#aabbcc'), 3: ('☁', '#8899aa'), 45: ('🌫', '#8899aa'), 48: ('🌫', '#8899aa'), 51: ('🌦', '#44aaff'), 53: ('🌦', '#44aaff'), 55: ('🌧', '#2288ff'), 61: ('🌧', '#44aaff'), 63: ('🌧', '#2288ff'), 65: ('🌧', '#0066ff'), 71: ('❄', '#aaddff'), 73: ('❄', '#88ccff'), 75: ('❄', '#66bbff'), 80: ('🌦', '#44aaff'), 81: ('🌧', '#2288ff'), 82: ('⛈', '#0044cc'), 95: ('⛈', '#cc44ff')}
_WMO_DESC = {0: 'Ясно', 1: 'Преим. ясно', 2: 'Перем. облачность', 3: 'Пасмурно', 45: 'Туман', 48: 'Иней', 51: 'Моросящий дождь', 53: 'Моросящий дождь', 55: 'Плотный моросящий дождь', 61: 'Небольшой дождь', 63: 'Умеренный дождь', 65: 'Сильный дождь', 71: 'Небольшой снегопад', 73: 'Умеренный снегопад', 75: 'Сильный снегопад', 80: 'Слабый ливень', 81: 'Умеренный ливень', 82: 'Сильный ливень', 95: 'Гроза'}
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
    import requests
    providers = (
        ("ipapi", "https://ipapi.co/json/"),
        ("ipwho", "https://ipwho.is/"),
        ("ipinfo", "https://ipinfo.io/json"),
    )
    def fetch_one(pair: tuple[str, str]) -> tuple[float, float, str] | None:
        name, url = pair
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                return None
            return _parse_geo_json(name, resp.json())
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_one, p) for p in providers]
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=timeout + 1.5):
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
        p = os.path.join('data', 'jarvis_settings.json')
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
        p = os.path.join('data', 'jarvis_settings.json')
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
def get_weather_hud() -> dict:
    cached = _hud_cache.get('data')
    if cached and time.time() - cached['updated_ts'] < _HUD_TTL_SEC:
        return cached
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        last = _load_last_location()
        if last:
            lat, lon, city_name = last
        else:
            geo = _ip_geolocation(headers, timeout=2.0)
            if geo:
                lat, lon, city_name = geo
                _save_last_location(lat, lon, city_name)
            else:
                return {'ok': False, 'city': 'ГЕОЛОКАЦИЯ НЕДОСТУПНА', 'temp': 0, 'feels': 0, 'desc': 'ОШИБКА ГЕО', 'icon': '⚠', 'color': _DIM_COLOR, 'wind': 0, 'humidity': 0, 'pressure': 0, 'sunrise': '—:—', 'sunset': '—:—', 'updated_ts': time.time()}
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m,surface_pressure&daily=sunrise,sunset&wind_speed_unit=ms&timezone=auto'
        resp_obj = requests.get(url, headers=headers, timeout=3)
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
        data = {'ok': True, 'city': city_name, 'lat': lat, 'lon': lon, 'sunrise': sunrise, 'sunset': sunset, 'temp': int(round(w['temperature_2m'])), 'feels': int(round(w['apparent_temperature'])), 'desc': _WMO_DESC.get(code, '—'), 'icon': icon, 'color': color, 'wind': round(w.get('wind_speed_10m', 0), 1), 'humidity': int(w.get('relative_humidity_2m', 0)), 'pressure': pressure_mmhg, 'updated_ts': time.time()}
    except Exception:
        data = {'ok': False, 'city': '—', 'temp': 0, 'feels': 0, 'desc': 'ОШИБКА СЕТИ', 'icon': '⚠', 'color': _DIM_COLOR, 'wind': 0, 'humidity': 0, 'pressure': 0, 'updated_ts': time.time()}
    _hud_cache['data'] = data
    return data
_DIM_COLOR = '#8e98c9'
def is_weather_voice_cached(city: str | None) -> bool:
    key = city.strip().lower() if city else '__auto__'
    c = _weather_cache.get(key)
    return bool(c and time.time() - c['ts'] < _CACHE_TTL_SEC)
def get_weather(city: str | None) -> tuple[bool, str]:
    import requests
    cache_key = city.strip().lower() if city else '__auto__'
    cached = _weather_cache.get(cache_key)
    if cached and time.time() - cached['ts'] < _CACHE_TTL_SEC:
        return (cached['ok'], cached['text'])
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if not city:
            last = _load_last_location()
            if last:
                lat, lon, city_name = last
            else:
                geo = _ip_geolocation(headers, timeout=2.0)
                if not geo:
                    return (False, 'Ошибка при определении местоположения.')
                lat, lon, city_name = geo
                _save_last_location(lat, lon, city_name)
        else:
            city_clean = city.strip().lower()
            if len(city_clean) > 4:
                if city_clean.endswith('е') or city_clean.endswith('и') or city_clean.endswith('а') or city_clean.endswith('у'):
                    city_clean = city_clean[:-1]
            geo_url = f'https://geocoding-api.open-meteo.com/v1/search?name={city_clean}&count=1&language=ru&format=json'
            geo_resp = requests.get(geo_url, headers=headers, timeout=3)
            geo_data = geo_resp.json()
            if not geo_data.get('results'):
                return (False, f'Город {city} не найден.')
            result = geo_data['results'][0]
            lat = result['latitude']
            lon = result['longitude']
            city_name = result.get('name', city)
        weather_url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code&wind_speed_unit=ms'
        w_resp = requests.get(weather_url, headers=headers, timeout=3)
        w_data = w_resp.json()
        current = w_data['current']
        temp = int(round(current['temperature_2m']))
        feels_like = int(round(current['apparent_temperature']))
        code = current['weather_code']
        descriptions = {0: 'Ясно', 1: 'Преимущественно ясно', 2: 'Переменная облачность', 3: 'Пасмурно', 45: 'Туман', 48: 'Иней', 51: 'Легкий моросящий дождь', 53: 'Умеренный моросящий дождь', 55: 'Плотный моросящий дождь', 61: 'Небольшой дождь', 63: 'Умеренный дождь', 65: 'Сильный дождь', 71: 'Небольшой снегопад', 73: 'Умеренный снегопад', 75: 'Сильный снегопад', 80: 'Слабый ливень', 81: 'Умеренный ливень', 82: 'Сильный ливень', 95: 'Гроза'}
        desc = descriptions.get(code, 'Неизвестные условия')
        result_text = f'В городе {city_name} сейчас {desc.lower()}. Температура {temp} градусов, ощущается как {feels_like}.'
        _weather_cache[cache_key] = {'ok': True, 'text': result_text, 'ts': time.time()}
        return (True, result_text)
    except Exception as e:
        return (False, f'Ошибка при получении погоды: {str(e)}')
