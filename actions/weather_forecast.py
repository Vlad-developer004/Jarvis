"""Multi-day and time-of-day forecast — split out of actions/weather.py to
keep that file under the project's ~600-line ceiling. Shares geocoding via
actions.weather.resolve_location instead of duplicating it."""
import re
import time
from core.i18n import get_language
from actions.weather import resolve_location, _location_error_text, _get_wmo_desc, _inflect_degree

_PERIODS: dict[str, list[int]] = {
    'утро': list(range(6, 12)), 'утром': list(range(6, 12)),
    'день': list(range(12, 18)), 'днем': list(range(12, 18)), 'днём': list(range(12, 18)),
    'вечер': list(range(18, 23)), 'вечером': list(range(18, 23)),
    'ночь': [23, 0, 1, 2, 3, 4, 5], 'ночью': [23, 0, 1, 2, 3, 4, 5],
}
_PERIOD_WORD_RU = {
    'утро': 'утром', 'утром': 'утром', 'день': 'днём', 'днем': 'днём', 'днём': 'днём',
    'вечер': 'вечером', 'вечером': 'вечером', 'ночь': 'ночью', 'ночью': 'ночью',
}
_PERIOD_WORD_UK = {
    'утро': 'вранці', 'утром': 'вранці', 'день': 'вдень', 'днем': 'вдень', 'днём': 'вдень',
    'вечер': 'ввечері', 'вечером': 'ввечері', 'ночь': 'вночі', 'ночью': 'вночі',
}


def extract_date_offset(text: str) -> tuple[int, str]:
    """Extracts date offset and removes temporal keywords from text."""
    text = text.lower()
    offset = 0
    if 'послезавтра' in text:
        offset = 2
        text = text.replace('послезавтра', '')
    elif 'завтра' in text:
        offset = 1
        text = text.replace('завтра', '')

    match = re.search(r'через\s+(один|два|три|четыре|пять|шесть|семь|\d+)\s+(?:день|дня|дней)?', text)
    if match:
        val = match.group(1)
        num_map = {'один': 1, 'два': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7}
        val_int = num_map.get(val) or (int(val) if val.isdigit() else 0)
        if val_int > 0:
            offset = val_int
            text = text.replace(match.group(0), '')

    return offset, text.strip()


def extract_period(text: str) -> tuple[str | None, str]:
    """Finds a time-of-day word ("утром"/"днём"/"вечером"/"ночью") in text
    and strips it out, so it doesn't leak into a city-name guess downstream."""
    for word in _PERIODS:
        if re.search(rf'\b{word}\b', text):
            return word, re.sub(rf'\b{word}\b', '', text).strip()
    return None, text


def get_forecast(city: str | None, date_offset: int) -> tuple[bool, str]:
    import requests
    lang = get_language()
    lat, lon, city_name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error_text(city_name, lang))

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        weather_url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,temperature_2m_min,rain_sum,snowfall_sum,wind_speed_10m_max&timezone=auto&wind_speed_unit=ms'
        w_data = requests.get(weather_url, headers=headers, timeout=2.5).json()
        daily = w_data['daily']
        if date_offset >= len(daily['time']):
            err_long = "Прогноз на такий тривалий термін недоступний. Я можу зазирнути максимум на тиждень вперед." if lang == 'uk' else "Прогноз на такой долгий срок недоступен. Я могу заглянуть максимум на неделю вперед."
            return (False, err_long)

        t_max = int(round(daily['temperature_2m_max'][date_offset]))
        t_min = int(round(daily['temperature_2m_min'][date_offset]))
        code = daily['weather_code'][date_offset]
        desc = _get_wmo_desc(code, lang)

        if lang == 'uk':
            day_str = "завтра" if date_offset == 1 else ("післязавтра" if date_offset == 2 else f"через {date_offset} дні")
            if date_offset >= 5: day_str = f"через {date_offset} днів"
            result_text = f'У місті {city_name} {day_str} очікується {desc.lower()}. '
            result_text += f'Вночі буде близько {_inflect_degree(t_min, lang)}, а вдень температура підніметься до {_inflect_degree(t_max, lang)}. '
        else:
            day_str = "завтра" if date_offset == 1 else ("послезавтра" if date_offset == 2 else f"через {date_offset} дня")
            if date_offset >= 5: day_str = f"через {date_offset} дней"
            result_text = f'В городе {city_name} {day_str} ожидается {desc.lower()}. '
            result_text += f'Ночью будет около {_inflect_degree(t_min, lang)}, а днём температура поднимется до {_inflect_degree(t_max, lang)}. '

        rain = daily.get('rain_sum', [0] * 10)[date_offset]
        snow = daily.get('snowfall_sum', [0] * 10)[date_offset]
        wind = daily.get('wind_speed_10m_max', [0] * 10)[date_offset]

        if lang == 'uk':
            if rain > 1.0: result_text += f'Можливий дощ до {int(rain)} міліметрів. '
            if snow > 1.0: result_text += f'Очікується сніг. '
            if wind > 8.0: result_text += f'Буде вітряно, пориви до {int(wind)} метрів на секунду. '
            if 'гроза' in desc.lower(): result_text += 'Можлива гроза, краще побути вдома. '
            if t_min <= -5: result_text += 'Вночі буде дуже холодно, одягніться тепліше. '
            if t_max >= 28: result_text += 'Вдень буде дуже спекотно, не забудьте воду.'
        else:
            if rain > 1.0: result_text += f'Возможен дождь до {int(rain)} миллиметров. '
            if snow > 1.0: result_text += f'Ожидается снег. '
            if wind > 8.0: result_text += f'Будет ветрено, порывы до {int(wind)} метров в секунду. '
            if 'гроза' in desc.lower(): result_text += 'Возможна гроза, лучше остаться дома. '
            if t_min <= -5: result_text += 'Ночью будет очень холодно, оденьтесь теплее. '
            if t_max >= 28: result_text += 'Днём будет очень жарко, не забудьте воду.'

        return (True, result_text)
    except Exception as e:
        return (False, f'Помилка при отриманні прогнозу: {str(e)}' if lang == 'uk' else f'Ошибка при получении прогноза: {str(e)}')


def get_weather_period(city: str | None, period: str) -> tuple[bool, str]:
    """Forecast for a specific part of today (утро/день/вечер/ночь) instead
    of just 'right now' or 'as a full day'."""
    import requests
    hours = _PERIODS.get(period)
    if not hours:
        return (False, '')
    lang = get_language()
    lat, lon, city_name = resolve_location(city, lang)
    if lat is None:
        return (False, _location_error_text(city_name, lang))

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability,weather_code&timezone=auto&forecast_days=1'
        resp = requests.get(url, headers=headers, timeout=2.5).json()
        hourly = resp['hourly']
        times = hourly['time']
        temps = hourly['temperature_2m']
        precip = hourly.get('precipitation_probability', [0] * len(times))
        codes = hourly['weather_code']
        idxs = [i for i, t in enumerate(times) if int(t[11:13]) in hours]
        if not idxs:
            return (False, 'Немає даних на цей період.' if lang == 'uk' else 'Нет данных на этот период.')

        t_vals = [temps[i] for i in idxs]
        p_vals = [precip[i] for i in idxs]
        c_vals = [codes[i] for i in idxs]
        t_min, t_max = int(round(min(t_vals))), int(round(max(t_vals)))
        max_precip = max(p_vals)
        # Worst (highest) WMO code in the window is a reasonable stand-in for
        # "what should I expect" — codes broadly escalate in severity within
        # each precipitation family (see _WMO_DESC_RU/_UK in actions.weather).
        worst_code = max(c_vals)
        desc = _get_wmo_desc(worst_code, lang)
        p_word = (_PERIOD_WORD_UK if lang == 'uk' else _PERIOD_WORD_RU).get(period, period)

        if lang == 'uk':
            text = f'У місті {city_name} {p_word} очікується {desc.lower()}, температура від {_inflect_degree(t_min, lang)} до {_inflect_degree(t_max, lang)}.'
            if max_precip >= 40:
                text += f' Ймовірність опадів до {int(max_precip)} відсотків, візьміть парасольку.'
        else:
            text = f'В городе {city_name} {p_word} ожидается {desc.lower()}, температура от {_inflect_degree(t_min, lang)} до {_inflect_degree(t_max, lang)}.'
            if max_precip >= 40:
                text += f' Вероятность осадков до {int(max_precip)} процентов, возьмите зонт.'
        return (True, text)
    except Exception as e:
        return (False, f'Помилка при отриманні прогнозу: {str(e)}' if lang == 'uk' else f'Ошибка при получении прогноза: {str(e)}')
