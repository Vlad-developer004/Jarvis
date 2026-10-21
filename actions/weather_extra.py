"""More than "what is it like now": rain over the coming hours, what to wear, the week and the weekend, air quality and pollen, and the
look-ahead checks behind the proactive warnings. Every answer is one open-meteo request; the analysis is in small pure functions."""
from datetime import date, datetime
from core.i18n import get_language
from core.safe import swallow as _swallow
from actions.weather_codes import _get_wmo_desc
from actions.weather_geo import HEADERS, resolve_location

_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
_AIR_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
_WET_CODES = frozenset({51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99})
_DAYS_RU = ('в понедельник', 'во вторник', 'в среду', 'в четверг', 'в пятницу', 'в субботу', 'в воскресенье')
_DAYS_UK = ('у понеділок', 'у вівторок', 'у середу', 'у четвер', 'у п’ятницю', 'у суботу', 'у неділю')
_POLLEN = {'alder_pollen': ('ольха', 'вільха'), 'birch_pollen': ('берёза', 'береза'), 'grass_pollen': ('злаки', 'злаки'),
           'mugwort_pollen': ('полынь', 'полин'), 'olive_pollen': ('олива', 'олива'), 'ragweed_pollen': ('амброзия', 'амброзія')}
_AIR_LEVELS = ((20, ('хорошее', 'добра')), (40, ('приемлемое', 'прийнятна')), (60, ('умеренное', 'помірна')),
               (80, ('плохое', 'погана')), (100, ('очень плохое', 'дуже погана')), (10 ** 9, ('крайне плохое', 'надзвичайно погана')))


def _t(lang: str, ru: str, uk: str) -> str:
    return uk if lang == 'uk' else ru


def _get(url: str, params: dict, timeout: float = 4.0) -> dict:
    import requests
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code}')
    return resp.json()


def _fail(lang: str) -> str:
    return _t(lang, 'Не удалось получить прогноз.', 'Не вдалося отримати прогноз.')


def _start_index(times: list, now_iso: str) -> int:
    hour = now_iso[:13]
    return next((i for i, t in enumerate(times) if t[:13] >= hour), 0)


# ── rain over the next hours ──────────────────────────────────────────────

def rain_window(times: list, prob: list, mm: list, temps: list, start: int, hours: int = 24) -> dict:
    """Where the next wet spell is. An hour counts as wet with at least 0.2 mm or a 60 percent chance."""
    end = min(start + hours, len(times))
    wet = [((mm[i] or 0) >= 0.2) or ((prob[i] or 0) >= 60) for i in range(start, end)]
    out = {'wet_now': bool(wet and wet[0]), 'begin': None, 'end': None, 'snow': False, 'max_prob': int(max([(prob[i] or 0) for i in range(start, end)] or [0]))}
    first = 0 if out['wet_now'] else next((k for k, w in enumerate(wet) if w), None)
    if first is None:
        return out
    out['snow'] = (temps[start + first] or 0) <= 0.5
    if not out['wet_now']:
        out['begin'] = times[start + first][11:16]
    last = next((k for k in range(first, len(wet)) if not wet[k]), None)
    out['end'] = None if last is None else times[start + last][11:16]
    return out


def rain_text(r: dict, lang: str) -> str:
    what = _t(lang, 'снег', 'сніг') if r['snow'] else _t(lang, 'дождь', 'дощ')
    gear = _t(lang, 'Снег — оденьтесь потеплее.', 'Сніг — вдягніться тепліше.') if r['snow'] else _t(lang, 'Возьмите зонт.', 'Візьміть парасольку.')
    if r['wet_now']:
        if r['end']:
            return _t(lang, f'Сейчас идёт {what}, закончится около {r["end"]}.', f'Зараз іде {what}, закінчиться близько {r["end"]}.')
        return _t(lang, f'Сейчас идёт {what}, и в ближайшие сутки он не закончится. {gear}', f'Зараз іде {what}, і найближчу добу він не закінчиться. {gear}')
    if not r['begin']:
        return _t(lang, 'В ближайшие сутки осадков не ожидается, зонт не нужен.', 'Найближчу добу опадів не очікується, парасолька не потрібна.')
    until = _t(lang, f' и продлится до {r["end"]}', f' і триватиме до {r["end"]}') if r['end'] else ''
    return _t(lang, f'{what.capitalize()} начнётся около {r["begin"]}{until}. {gear}', f'{what.capitalize()} почнеться близько {r["begin"]}{until}. {gear}')


def get_rain_outlook(city: str | None) -> tuple[bool, str]:
    lang = get_language()
    lat, lon, name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error(name, lang))
    try:
        d = _get(_FORECAST_URL, {'latitude': lat, 'longitude': lon, 'current': 'temperature_2m', 'timezone': 'auto', 'forecast_days': 2,
                                 'hourly': 'temperature_2m,precipitation_probability,precipitation'})
        h = d['hourly']
        start = _start_index(h['time'], d['current']['time'])
        return (True, rain_text(rain_window(h['time'], h['precipitation_probability'], h['precipitation'], h['temperature_2m'], start), lang))
    except Exception:
        _swallow()
        return (False, _fail(lang))


def _location_error(name: str | None, lang: str) -> str:
    from actions.weather import _location_error_text
    return _location_error_text(name, lang)


# ── what to wear ──────────────────────────────────────────────────────────

_OUTFIT = (
    (-15, ('очень тёплый пуховик, шапка, шарф и перчатки', 'дуже теплий пуховик, шапка, шарф і рукавички')),
    (-5, ('зимняя куртка, шапка и перчатки', 'зимова куртка, шапка і рукавички')),
    (5, ('тёплая куртка и шапка', 'тепла куртка і шапка')),
    (12, ('лёгкая куртка или плотная кофта', 'легка куртка або щільна кофта')),
    (18, ('кофта или лёгкая куртка', 'кофта або легка куртка')),
    (24, ('футболка, а на вечер лёгкая кофта', 'футболка, а на вечір легка кофта')),
    (29, ('лёгкая одежда', 'легкий одяг')),
    (10 ** 3, ('самая лёгкая одежда и головной убор', 'найлегший одяг і головний убір')),
)


def outfit_text(feels: float, wind: float, rain: dict, uv: float | None, lang: str) -> str:
    base = _t(lang, *next(v for limit, v in _OUTFIT if feels <= limit))
    extras = []
    if rain['wet_now'] or rain['begin']:
        extras.append(_t(lang, 'тёплая и непромокаемая обувь' if rain['snow'] else 'зонт и непромокаемая обувь',
                         'тепле й непромокальне взуття' if rain['snow'] else 'парасолька і непромокальне взуття'))
    if wind >= 10 and feels > 5:
        extras.append(_t(lang, 'ветровка', 'вітровка'))
    if uv is not None and uv >= 6 and feels > 12:
        extras.append(_t(lang, 'солнцезащитные очки и крем', 'сонцезахисні окуляри і крем'))
    tail = (_t(lang, ' Ещё пригодятся: ', ' Ще стануть у пригоді: ') + ', '.join(extras) + '.') if extras else ''
    return _t(lang, f'На улице ощущается как {int(round(feels))}. Лучше всего: {base}.{tail}', f'На вулиці відчувається як {int(round(feels))}. Найкраще: {base}.{tail}')


def get_outfit(city: str | None) -> tuple[bool, str]:
    lang = get_language()
    lat, lon, name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error(name, lang))
    try:
        d = _get(_FORECAST_URL, {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 2,
                                 'current': 'temperature_2m,apparent_temperature,wind_speed_10m', 'daily': 'uv_index_max',
                                 'hourly': 'temperature_2m,precipitation_probability,precipitation', 'wind_speed_unit': 'ms'})
        h, cur = d['hourly'], d['current']
        start = _start_index(h['time'], cur['time'])
        rain = rain_window(h['time'], h['precipitation_probability'], h['precipitation'], h['temperature_2m'], start, hours=12)
        uv = (d.get('daily') or {}).get('uv_index_max', [None])[0]
        return (True, outfit_text(cur['apparent_temperature'], cur.get('wind_speed_10m') or 0, rain, uv, lang))
    except Exception:
        _swallow()
        return (False, _fail(lang))


# ── week and weekend ──────────────────────────────────────────────────────

def _wet_day(code, precip) -> bool:
    return (precip or 0) >= 1.0 or code in _WET_CODES


def week_text(days: list[dict], city: str, lang: str, weekend: bool = False) -> str:
    """days: [{'date': date, 'tmax', 'tmin', 'code', 'precip'}], today first."""
    names = _DAYS_UK if lang == 'uk' else _DAYS_RU
    if weekend:
        picked = [x for x in days if x['date'].weekday() >= 5]
        if not picked:
            return _t(lang, 'Прогноза на выходные пока нет.', 'Прогнозу на вихідні поки немає.')
        parts = [f'{names[x["date"].weekday()].capitalize()} {_get_wmo_desc(x["code"], lang).lower()}, '
                 + _t(lang, f'от {int(round(x["tmin"]))} до {int(round(x["tmax"]))}', f'від {int(round(x["tmin"]))} до {int(round(x["tmax"]))}')
                 for x in picked]
        head = _t(lang, f'В городе {city} на выходные. ', f'У місті {city} на вихідні. ')
        umbrella = _t(lang, ' Не забудьте зонт.', ' Не забудьте парасольку.') if any(_wet_day(x['code'], x['precip']) for x in picked) else ''
        return head + '. '.join(parts) + '.' + umbrella
    hottest = max(days, key=lambda x: x['tmax'])
    coldest = min(days, key=lambda x: x['tmin'])
    wet = [names[x['date'].weekday()] for x in days if _wet_day(x['code'], x['precip'])]
    lo, hi = int(round(min(x['tmin'] for x in days))), int(round(max(x['tmax'] for x in days)))
    text = _t(lang, f'В городе {city} на ближайшую неделю от {lo} до {hi} градусов. Теплее всего {names[hottest["date"].weekday()]}, до {int(round(hottest["tmax"]))}, '
                    f'холоднее всего {names[coldest["date"].weekday()]}, около {int(round(coldest["tmin"]))}.',
              f'У місті {city} на найближчий тиждень від {lo} до {hi} градусів. Найтепліше {names[hottest["date"].weekday()]}, до {int(round(hottest["tmax"]))}, '
              f'найхолодніше {names[coldest["date"].weekday()]}, близько {int(round(coldest["tmin"]))}.')
    if wet:
        text += _t(lang, f' Осадки ожидаются: {", ".join(wet)}.', f' Опади очікуються: {", ".join(wet)}.')
    else:
        text += _t(lang, ' Заметных осадков не ожидается.', ' Помітних опадів не очікується.')
    return text


def get_week(city: str | None, weekend: bool = False) -> tuple[bool, str]:
    lang = get_language()
    lat, lon, name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error(name, lang))
    try:
        d = _get(_FORECAST_URL, {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 7,
                                 'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum'})['daily']
        days = [{'date': date.fromisoformat(d['time'][i]), 'tmax': d['temperature_2m_max'][i], 'tmin': d['temperature_2m_min'][i],
                 'code': d['weather_code'][i], 'precip': d['precipitation_sum'][i]} for i in range(len(d['time']))
                if d['temperature_2m_max'][i] is not None and d['temperature_2m_min'][i] is not None]
        return (True, week_text(days, name, lang, weekend)) if days else (False, _fail(lang))
    except Exception:
        _swallow()
        return (False, _fail(lang))


# ── air quality and pollen ────────────────────────────────────────────────

def air_level(aqi: float, lang: str) -> str:
    return _t(lang, *next(v for limit, v in _AIR_LEVELS if aqi <= limit))


def air_text(cur: dict, city: str, lang: str) -> str:
    aqi = cur.get('european_aqi')
    if aqi is None:
        return _t(lang, 'Данных о качестве воздуха для этого места нет.', 'Даних про якість повітря для цього місця немає.')
    text = _t(lang, f'В городе {city} качество воздуха {air_level(aqi, lang)}, индекс {int(round(aqi))}.',
              f'У місті {city} якість повітря {air_level(aqi, lang)}, індекс {int(round(aqi))}.')
    if aqi > 60:
        text += _t(lang, ' Лучше сократить время на улице и проветривать реже.', ' Краще скоротити час надворі й провітрювати рідше.')
    pollen = sorted(((cur[k], v) for k, v in _POLLEN.items() if (cur.get(k) or 0) >= 10), reverse=True)
    if pollen:
        names = ', '.join(_t(lang, *v) for _, v in pollen[:3])
        text += _t(lang, f' Пыльца в воздухе: {names}. Аллергикам стоит быть осторожнее.', f' Пилок у повітрі: {names}. Алергікам варто бути обережнішими.')
    return text


def fetch_air(lat: float, lon: float, timeout: float = 3.0) -> dict:
    return _get(_AIR_URL, {'latitude': lat, 'longitude': lon, 'timezone': 'auto',
                           'current': 'european_aqi,pm2_5,pm10,ozone,' + ','.join(_POLLEN)}, timeout)['current']


def get_air(city: str | None) -> tuple[bool, str]:
    lang = get_language()
    lat, lon, name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error(name, lang))
    try:
        return (True, air_text(fetch_air(lat, lon, 4.0), name, lang))
    except Exception:
        _swallow()
        return (False, _fail(lang))


# ── look-ahead for the proactive warnings ─────────────────────────────────

def analyze_outlook(times: list, temps: list, rain_mm: list, gusts: list, tmax: list, now_iso: str, lang: str) -> list[tuple[str, str]]:
    """[(key, spoken warning)] for the next hours: frost, a sharp change from today to tomorrow, strong wind, a downpour."""
    s = _start_index(times, now_iso)
    out = []
    nxt = [x for x in temps[s:s + 12] if x is not None]
    if nxt and temps[s] is not None and temps[s] > 2 and min(nxt) <= 0:
        out.append(('frost', _t(lang, f'Ночью ожидаются заморозки, до {int(round(min(nxt)))} градусов.', f'Вночі очікуються заморозки, до {int(round(min(nxt)))} градусів.')))
    if len(tmax) > 1 and tmax[0] is not None and tmax[1] is not None:
        delta = tmax[1] - tmax[0]
        if delta <= -8:
            out.append(('drop', _t(lang, f'Завтра резко похолодает: на {int(round(-delta))} градусов ниже, чем сегодня.', f'Завтра різко похолодає: на {int(round(-delta))} градусів нижче, ніж сьогодні.')))
        elif delta >= 8:
            out.append(('rise', _t(lang, f'Завтра заметно потеплеет: на {int(round(delta))} градусов выше, чем сегодня.', f'Завтра помітно потепліє: на {int(round(delta))} градусів вище, ніж сьогодні.')))
    g = max([x for x in gusts[s:s + 12] if x is not None] or [0])
    if g >= 17:
        out.append(('wind', _t(lang, f'Ожидается сильный ветер, порывы до {int(round(g))} метров в секунду.', f'Очікується сильний вітер, пориви до {int(round(g))} метрів на секунду.')))
    if sum(x or 0 for x in rain_mm[s:s + 6]) >= 10:
        out.append(('downpour', _t(lang, 'В ближайшие часы ожидается ливень.', 'Найближчими годинами очікується злива.')))
    return out


def _outlook_data(lat: float, lon: float) -> dict:
    return _get(_FORECAST_URL, {'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 2, 'wind_speed_unit': 'ms', 'current': 'temperature_2m',
                                'hourly': 'temperature_2m,precipitation,wind_gusts_10m,precipitation_probability', 'daily': 'temperature_2m_max'})


def check_outlook(lat: float, lon: float, lang: str) -> list[tuple[str, str]]:
    d = _outlook_data(lat, lon)
    h = d['hourly']
    return analyze_outlook(h['time'], h['temperature_2m'], h['precipitation'], h['wind_gusts_10m'], d['daily']['temperature_2m_max'], d['current']['time'], lang)


def rain_chance_at(lat: float, lon: float, when: datetime) -> tuple[int, float] | None:
    """(chance in percent, millimetres) for the hour of `when`, local time of the place."""
    h = _outlook_data(lat, lon)['hourly']
    key = when.strftime('%Y-%m-%dT%H')
    i = next((k for k, t in enumerate(h['time']) if t[:13] == key), None)
    return None if i is None else (int(h['precipitation_probability'][i] or 0), float(h['precipitation'][i] or 0))


_ANSWERS = {
    'rain': get_rain_outlook,
    'wear': get_outfit,
    'air': get_air,
    'week': lambda city: get_week(city, False),
    'weekend': lambda city: get_week(city, True),
}


def answer(kind: str, city: str | None) -> tuple[bool, str]:
    """The spoken answer for a weather_route kind; never raises."""
    try:
        return _ANSWERS[kind](city)
    except Exception:
        _swallow()
        return (False, _fail(get_language()))
