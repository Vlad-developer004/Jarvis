"""Current weather: the HUD snapshot, the spoken text and the wttr.in fallback. Code tables live in actions/weather_codes.py and place
lookup in actions/weather_geo.py; their names are re-exported here for the callers that import them from this module."""
import time
from core.i18n import get_language
from core.safe import swallow as _swallow
from actions import weather_cache
from actions.weather_codes import (  # noqa: F401  (re-exported)
    _WMO_ICON, _get_wmo_desc, _wttr_desc, DIM_COLOR as _DIM_COLOR,
)
from actions.weather_geo import (  # noqa: F401  (re-exported)
    HEADERS, _ip_geolocation, resolve_location, home_location,
)

_weather_cache = {}
_last_good: dict = {}        # cache key -> {'text', 'ts'}: the last answer that worked, for when the connection is gone
_LAST_GOOD_MAX_AGE_SEC = 6 * 3600
_CACHE_TTL_SEC = 600
_hud_cache: dict = {}
_HUD_TTL_SEC = 600
_OPEN_METEO_URL = ('https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'
                   '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,'
                   'relative_humidity_2m,surface_pressure,cloud_cover,visibility'
                   '&daily=sunrise,sunset,uv_index_max,precipitation_probability_max,temperature_2m_max,temperature_2m_min'
                   '&wind_speed_unit=ms&timezone=auto&past_days=1')


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

def _fetch_snapshot(lat: float, lon: float, city_name: str, lang: str, timeout: float = 5.0) -> dict:
    """One open-meteo request turned into the dict the HUD, the spoken text and the morning briefing all read."""
    import requests
    resp_obj = requests.get(_OPEN_METEO_URL.format(lat=lat, lon=lon), headers=HEADERS, timeout=timeout)
    if resp_obj.status_code != 200:
        raise Exception(f'HTTP {resp_obj.status_code}')
    resp = resp_obj.json()
    w = resp['current']
    code = w['weather_code']
    icon, color = _WMO_ICON.get(code, ('?', '#ffffff'))
    pressure_mmhg = int(round(w.get('surface_pressure', 0) * 0.750064))
    day = resp.get('daily') or {}
    try:
        ti = day['time'].index(str(w.get('time', ''))[:10])      # past_days=1 puts yesterday first
    except Exception:
        ti = 1 if len(day.get('time') or []) > 1 else 0
    try:
        sunrise = day['sunrise'][ti][-5:]
        sunset = day['sunset'][ti][-5:]
    except Exception:
        sunrise = sunset = '—:—'

    def _day(key, i=None):
        try:
            v = day[key][ti if i is None else i]
            return None if v is None else round(float(v), 1)
        except Exception:
            return None
    # how much warmer or colder the whole day is than yesterday (mean of the day's high and low), None when there is no yesterday
    vs_yesterday = None
    if ti > 0 and None not in (_day('temperature_2m_max'), _day('temperature_2m_min'), _day('temperature_2m_max', ti - 1), _day('temperature_2m_min', ti - 1)):
        vs_yesterday = int(round(((_day('temperature_2m_max') + _day('temperature_2m_min')) - (_day('temperature_2m_max', ti - 1) + _day('temperature_2m_min', ti - 1))) / 2))
    vis_m = w.get('visibility')
    extra = {'wind_dir': w.get('wind_direction_10m'), 'gust': None if w.get('wind_gusts_10m') is None else round(w['wind_gusts_10m'], 1), 'clouds': w.get('cloud_cover'),
             'vis_km': None if vis_m is None else round(vis_m / 1000, 1), 'uv': _day('uv_index_max'), 'pop': _day('precipitation_probability_max'),
             'tmax': _day('temperature_2m_max'), 'tmin': _day('temperature_2m_min'), 'vs_yesterday': vs_yesterday}
    return {'ok': True, 'city': city_name, 'lat': lat, 'lon': lon, 'sunrise': sunrise, 'sunset': sunset, **extra,
            'temp': int(round(w['temperature_2m'])), 'feels': int(round(w['apparent_temperature'])), 'desc': _get_wmo_desc(code, lang), 'code': code,
            'icon': icon, 'color': color, 'wind': round(w.get('wind_speed_10m', 0), 1), 'humidity': int(w.get('relative_humidity_2m', 0)),
            'pressure': pressure_mmhg, 'updated_ts': time.time()}

def _air_index(lat: float, lon: float) -> int | None:
    """European air quality index for the HUD; the weather itself must not fail because this one request did."""
    try:
        from actions.weather_extra import fetch_air
        v = fetch_air(lat, lon).get('european_aqi')
        return None if v is None else int(round(v))
    except Exception:
        _swallow()
        return None

def get_weather_hud() -> dict:
    lang = get_language()
    cache_key = f'data_{lang}'
    cached = _hud_cache.get(cache_key)
    if cached and time.time() - cached['updated_ts'] < _HUD_TTL_SEC:
        return cached
    # Bound before the try so the except fallback can never hit a NameError.
    lat, lon, city_name = (None, None, None)
    try:
        loc = home_location(lang)
        if not loc:
            raise Exception('Location not found')
        lat, lon, city_name = loc
        data = _fetch_snapshot(lat, lon, city_name, lang)
        data['aqi'] = _air_index(lat, lon)
        weather_cache.save_snapshot(data)
    except Exception:
        _swallow()
        # open-meteo failed — try wttr.in as fallback
        if lat is not None:
            try:
                data = _fetch_wttr(lat, lon, city_name or '—', lang, HEADERS)
                _hud_cache[cache_key] = data
                return data
            except Exception:
                _swallow()
        # Both APIs failed — return stale cache rather than showing error
        stale = _hud_cache.get(cache_key) or weather_cache.load_snapshot()
        if stale and stale.get('ok'):
            return stale
        err_msg = 'ПОМИЛКА МЕРЕЖІ' if lang == 'uk' else 'ОШИБКА СЕТИ'
        data = {'ok': False, 'city': '—', 'temp': 0, 'feels': 0, 'desc': err_msg, 'icon': '⚠', 'color': _DIM_COLOR, 'wind': 0, 'humidity': 0, 'pressure': 0, 'updated_ts': time.time()}
    _hud_cache[cache_key] = data
    return data

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
def _format_current_weather_text(city_name: str, desc: str, temp: int, feels: int, lang: str, wind: float = 0.0,
                                 vs_yesterday: int | None = None) -> str:
    """`vs_yesterday`: degrees the whole day is warmer (positive) or colder than yesterday, from the forecast service; a small
    difference is not worth saying."""
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
    if vs_yesterday is not None and abs(vs_yesterday) >= 2:
        n = abs(vs_yesterday)
        if lang == 'uk':
            text += f' Це на {n} градусів {"тепліше" if vs_yesterday > 0 else "холодніше"}, ніж учора.'
        else:
            text += f' Это на {n} градусов {"теплее" if vs_yesterday > 0 else "холоднее"}, чем вчера.'
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
def is_weather_voice_cached(city: str | None, date_offset: int = 0, period: str | None = None) -> bool:
    """True when get_weather() would answer from its text cache; the key is built the same way. Part-of-day answers are never cached."""
    if period:
        return False
    key = f"{city.strip().lower() if city else '__auto__'}_{date_offset}"
    c = _weather_cache.get(key)
    return bool(c and time.time() - c['ts'] < _CACHE_TTL_SEC)
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
    # — reuse a still-fresh HUD fetch instead of making a second network
    # round-trip for the same conditions.
    if not city and date_offset == 0:
        hud_cached = _hud_cache.get(f'data_{lang}')
        if hud_cached and hud_cached.get('ok') and time.time() - hud_cached.get('updated_ts', 0) < _HUD_TTL_SEC:
            text = _format_current_weather_text(hud_cached['city'], hud_cached['desc'], hud_cached['temp'], hud_cached['feels'], lang, hud_cached.get('wind', 0.0), hud_cached.get('vs_yesterday'))
            _weather_cache[cache_key] = {'ok': True, 'text': text, 'ts': time.time()}
            return (True, text)

    if date_offset != 0:
        from actions.weather_forecast import get_forecast
        try:
            ok, text = get_forecast(city, date_offset)
        except Exception:
            _swallow()
            return (False, 'Помилка при отриманні прогнозу.' if lang == 'uk' else 'Ошибка при получении прогноза.')
        if ok:
            _weather_cache[cache_key] = {'ok': True, 'text': text, 'ts': time.time()}
        return (ok, text)

    try:
        lat, lon, city_name = resolve_location(city, lang)
        if lat is None:
            return (False, _location_error_text(city_name, lang))
        snap = _fetch_snapshot(lat, lon, city_name, lang, timeout=2.5)
        result_text = _format_current_weather_text(city_name, snap['desc'], snap['temp'], snap['feels'], lang, snap['wind'], snap.get('vs_yesterday'))
        _weather_cache[cache_key] = {'ok': True, 'text': result_text, 'ts': time.time()}
        _last_good[cache_key] = {'text': result_text, 'ts': time.time()}
        return (True, result_text)
    except Exception:
        _swallow()
        old = _last_good.get(cache_key)
        if old and time.time() - old['ts'] < _LAST_GOOD_MAX_AGE_SEC:
            at = time.strftime('%H:%M', time.localtime(old['ts']))
            note = f'Немає зв’язку, це дані на {at}.' if lang == 'uk' else f'Нет связи, это данные на {at}.'
            return (True, f'{note} {old["text"]}')
        return (False, 'Не вдалося отримати погоду.' if lang == 'uk' else 'Не удалось получить погоду.')

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
