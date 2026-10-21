"""Rain over the coming hours, clothes, week and weekend, air quality, saved places, the yesterday comparison, the offline fallback and the
proactive warnings. The analysis functions are pure, so most tests feed them small lists; network calls are stubbed."""
from datetime import date, datetime, timedelta

import pytest

from actions import weather, weather_cache, weather_extra as wx, weather_geo
from core import settings_io
from core.nlp import weather_route


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: path)
    weather._weather_cache.clear()
    weather._hud_cache.clear()
    weather._last_good.clear()
    weather_geo._city_names.clear()
    yield


def _hours(first_hour=10, count=24):
    return [f'2026-10-21T{(first_hour + i) % 24:02d}:00' if first_hour + i < 24 else f'2026-10-22T{(first_hour + i) % 24:02d}:00' for i in range(count)]


# ── phrase routing ────────────────────────────────────────────────────────

@pytest.mark.parametrize('phrase,kind', [
    ('будет ли сегодня дождь', 'rain'), ('возьму зонт', 'rain'), ('нужен ли мне зонт', 'rain'), ('когда закончится дождь', 'rain'),
    ('чи буде дощ', 'rain'), ('що мені вдягнути', 'wear'), ('что надеть', 'wear'), ('как одеться', 'wear'),
    ('какое качество воздуха', 'air'), ('что с воздухом', 'air'), ('якість повітря', 'air'), ('уровень пыльцы', 'air'),
    ('погода на выходные', 'weekend'), ('прогноз на неделю', 'week'), ('погода на неделю в киеве', 'week'),
])
def test_parse_recognises_the_kind(phrase, kind):
    assert weather_route.parse(phrase).kind == kind


@pytest.mark.parametrize('phrase', ['какая погода', 'погода завтра', 'включи звуки дождя', 'открой зонт приложение', 'сколько будет два плюс два', 'включи музыку'])
def test_parse_leaves_other_phrases_alone(phrase):
    assert weather_route.parse(phrase).kind is None


def test_route_only_takes_phrases_without_the_weather_word():
    assert weather_route.route('возьму зонт') == ('weather', 'возьму зонт')
    assert weather_route.route('какое качество воздуха') is not None
    assert weather_route.route('будет ли дождь в погоде') is None       # has "погод": the keyword path handles it
    assert weather_route.route('включи свет') is None


def test_parse_keeps_the_place_name_in_rest():
    q = weather_route.parse('будет ли дождь в берлине')
    assert q.kind == 'rain' and 'берлине' in q.rest and 'дождь' not in q.rest


def test_followup_early_chain_reaches_the_weather_router():
    from core.nlp import followup
    assert followup.early('что надеть')[0] == 'weather'
    assert followup.early('какая погода') is None


@pytest.mark.parametrize('said,want', [('а на выходные', 'погода выходные'), ('а на неделю?', 'погода неделю'), ('и выходные', 'погода выходные')])
def test_week_follow_ups_after_the_weather(said, want):
    from core.nlp import followup
    followup.forget()
    followup.remember('weather', 'какая погода')
    got = followup.resolve(said)
    followup.forget()
    assert got == ('weather', want)
    assert weather_route.parse(want).kind in ('week', 'weekend')


# ── rain ──────────────────────────────────────────────────────────────────

def _rain(prob, mm, temps=None, start=0):
    n = len(prob)
    return wx.rain_window(_hours(10, n), prob, mm, temps or [10] * n, start)


def test_dry_day_needs_no_umbrella():
    r = _rain([0] * 24, [0] * 24)
    assert r['begin'] is None and not r['wet_now']
    assert 'не нужен' in wx.rain_text(r, 'ru')


def test_rain_starting_later_names_the_hour_and_the_end():
    prob = [0] * 5 + [80] * 3 + [0] * 16
    mm = [0] * 5 + [1.0] * 3 + [0] * 16
    r = _rain(prob, mm)
    assert r['begin'] == '15:00' and r['end'] == '18:00'
    text = wx.rain_text(r, 'ru')
    assert '15:00' in text and '18:00' in text and 'зонт' in text.lower()


def test_rain_now_says_when_it_stops():
    prob = [90] * 2 + [0] * 22
    r = _rain(prob, [2.0] * 2 + [0] * 22)
    assert r['wet_now'] and r['end'] == '12:00'
    assert 'закончится около 12:00' in wx.rain_text(r, 'ru')


def test_rain_that_never_stops_in_a_day():
    r = _rain([90] * 24, [1.0] * 24)
    assert r['wet_now'] and r['end'] is None
    assert 'не закончится' in wx.rain_text(r, 'ru')


def test_freezing_wet_hours_are_snow_not_rain():
    r = _rain([90] * 24, [1.0] * 24, temps=[-3] * 24)
    assert r['snow'] and 'снег' in wx.rain_text(r, 'ru')


def test_rain_text_in_ukrainian():
    r = _rain([0] * 5 + [80] * 3 + [0] * 16, [0] * 5 + [1.0] * 3 + [0] * 16)
    assert 'Дощ почнеться' in wx.rain_text(r, 'uk')


def test_start_index_skips_hours_already_gone():
    assert wx._start_index(_hours(0, 24), '2026-10-21T07:42') == 7


# ── outfit ────────────────────────────────────────────────────────────────

_DRY = {'wet_now': False, 'begin': None, 'end': None, 'snow': False, 'max_prob': 0}
_WET = {'wet_now': False, 'begin': '15:00', 'end': '17:00', 'snow': False, 'max_prob': 80}


@pytest.mark.parametrize('feels,word', [(-20, 'пуховик'), (-8, 'зимняя куртка'), (2, 'тёплая куртка'), (10, 'лёгкая куртка'), (22, 'футболка'), (35, 'головной убор')])
def test_outfit_follows_the_felt_temperature(feels, word):
    text = wx.outfit_text(feels, 1, _DRY, None, 'ru')
    assert word in text and "'" not in text and '(' not in text


def test_outfit_adds_umbrella_wind_and_sun_extras():
    text = wx.outfit_text(20, 12, _WET, 7, 'ru')
    assert 'зонт' in text and 'ветровка' in text and 'очки' in text


def test_outfit_has_no_extras_on_a_calm_dry_day():
    assert 'пригодятся' not in wx.outfit_text(20, 2, _DRY, 2, 'ru')


# ── week and weekend ──────────────────────────────────────────────────────

def _week(start=date(2026, 10, 19)):       # a Monday
    temps = [(12, 5), (14, 7), (18, 9), (20, 10), (16, 8), (11, 4), (9, 3)]
    return [{'date': start + timedelta(days=i), 'tmax': hi, 'tmin': lo, 'code': 61 if i == 2 else 0, 'precip': 3.0 if i == 2 else 0.0} for i, (hi, lo) in enumerate(temps)]


def test_week_summary_names_warmest_coldest_and_wet_days():
    t = wx.week_text(_week(), 'Киев', 'ru')
    assert 'от 3 до 20' in t and 'Теплее всего в четверг' in t and 'холоднее всего в воскресенье' in t and 'в среду' in t


def test_week_without_rain_says_so():
    days = [dict(d, code=0, precip=0.0) for d in _week()]
    assert 'Заметных осадков не ожидается' in wx.week_text(days, 'Киев', 'ru')


def test_weekend_lists_saturday_and_sunday_only():
    t = wx.week_text(_week(), 'Киев', 'ru', weekend=True)
    assert t.startswith('В городе Киев на выходные. В субботу') and 'В воскресенье' in t and 'среду' not in t


def test_weekend_with_rain_reminds_about_the_umbrella():
    days = [dict(d, code=61) if d['date'].weekday() == 5 else d for d in _week()]
    assert 'зонт' in wx.week_text(days, 'Киев', 'ru', weekend=True)


def test_week_text_in_ukrainian():
    assert 'Найтепліше у четвер' in wx.week_text(_week(), 'Київ', 'uk')


# ── air ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('aqi,word', [(10, 'хорошее'), (35, 'приемлемое'), (55, 'умеренное'), (75, 'плохое'), (95, 'очень плохое'), (150, 'крайне')])
def test_air_levels(aqi, word):
    assert word in wx.air_level(aqi, 'ru')


def test_air_text_warns_when_bad_and_lists_pollen():
    t = wx.air_text({'european_aqi': 70, 'birch_pollen': 120, 'grass_pollen': 15, 'olive_pollen': 2}, 'Киев', 'ru')
    assert 'индекс 70' in t and 'сократить' in t and 'берёза' in t and 'злаки' in t and 'олива' not in t


def test_air_text_without_data():
    assert 'нет' in wx.air_text({}, 'Киев', 'ru')


# ── look-ahead warnings ───────────────────────────────────────────────────

def _outlook(temps=None, rain=None, gusts=None, tmax=(15, 15)):
    n = 24
    return wx.analyze_outlook(_hours(10, n), temps or [8] * n, rain or [0] * n, gusts or [3] * n, list(tmax), '2026-10-21T10:20', 'ru')


def test_quiet_outlook_has_no_warnings():
    assert _outlook() == []


def test_frost_warning_when_it_drops_below_zero_tonight():
    keys = [k for k, _ in _outlook(temps=[8, 6, 4, 3, 2, 1, 0, -1, -3] + [-3] * 15)]
    assert keys == ['frost']


def test_no_frost_warning_when_it_already_is_freezing():
    assert _outlook(temps=[-2] * 24) == []


def test_sharp_change_tomorrow():
    assert [k for k, _ in _outlook(tmax=(18, 8))] == ['drop']
    assert [k for k, _ in _outlook(tmax=(8, 18))] == ['rise']
    assert _outlook(tmax=(18, 12)) == []


def test_strong_wind_and_downpour():
    keys = [k for k, _ in _outlook(gusts=[3, 4, 18] + [3] * 21, rain=[0, 4, 4, 4] + [0] * 20)]
    assert keys == ['wind', 'downpour']


# ── saved places ──────────────────────────────────────────────────────────

def test_saved_place_is_found_in_any_case_form():
    assert weather_geo.add_place('Мама', 'Львов')
    assert weather_geo.find_place('погода у мамы') == ('Львов', 'погода')
    assert weather_geo.find_place('погода в маме')[0] == 'Львов'
    assert weather_geo.find_place('погода в берлине') == (None, 'погода в берлине')


def test_places_are_capped():
    for i in range(weather_geo._MAX_PLACES):
        assert weather_geo.add_place(f'место{i}', 'Киев')
    assert not weather_geo.add_place('лишнее', 'Киев')
    assert weather_geo.add_place('место0', 'Одесса')          # renaming an existing one is not growth


class _Handler:
    def __init__(self):
        self.said = []

    def speak(self, text, **kw):
        self.said.append(text)


def test_voice_command_saves_a_place():
    from core.handler.commands import info
    h = _Handler()
    info._set_weather_city(h, 'set_weather_city', 'запомни город львов как мама')
    assert weather_geo.get_places() == {'мама': 'Львов'}
    assert 'manual_city' not in settings_io.read()
    assert h.said and 'мама' in h.said[0]


def test_voice_command_without_the_place_form_still_sets_the_home_city():
    from core.handler.commands import info
    h = _Handler()
    info._set_weather_city(h, 'set_weather_city', 'установи город берлин')
    assert settings_io.read()['manual_city'] == 'Берлин'


# ── yesterday and the single snapshot request ─────────────────────────────

def _open_meteo_reply(today_max=20, today_min=10, yest_max=14, yest_min=8):
    return {'current': {'time': '2026-10-21T14:00', 'temperature_2m': 17.2, 'apparent_temperature': 16.0, 'weather_code': 3, 'wind_speed_10m': 3.0,
                        'relative_humidity_2m': 60, 'surface_pressure': 1000, 'wind_gusts_10m': 6, 'wind_direction_10m': 90, 'cloud_cover': 50, 'visibility': 10000},
            'daily': {'time': ['2026-10-20', '2026-10-21', '2026-10-22'], 'sunrise': ['2026-10-20T07:10', '2026-10-21T07:12', '2026-10-22T07:14'],
                      'sunset': ['2026-10-20T18:00', '2026-10-21T17:58', '2026-10-22T17:56'], 'uv_index_max': [2, 3, 3],
                      'precipitation_probability_max': [10, 20, 30], 'temperature_2m_max': [yest_max, today_max, 12], 'temperature_2m_min': [yest_min, today_min, 6]}}


class _Resp:
    status_code = 200

    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


def test_snapshot_uses_todays_column_and_compares_with_yesterday(monkeypatch):
    import requests
    seen = []
    monkeypatch.setattr(requests, 'get', lambda url, **k: seen.append(url) or _Resp(_open_meteo_reply()))
    snap = weather._fetch_snapshot(50.0, 30.0, 'Киев', 'ru')
    assert 'past_days=1' in seen[0]
    assert snap['tmax'] == 20 and snap['tmin'] == 10 and snap['sunrise'] == '07:12' and snap['uv'] == 3
    assert snap['vs_yesterday'] == 4          # mean 15 today against mean 11 yesterday


def test_format_says_warmer_or_colder_than_yesterday_only_above_the_threshold():
    warm = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru', vs_yesterday=4)
    cold = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru', vs_yesterday=-3)
    same = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru', vs_yesterday=1)
    none = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru')
    assert 'на 4 градусов теплее, чем вчера' in warm or 'теплее, чем вчера' in warm
    assert 'холоднее, чем вчера' in cold
    assert 'вчера' not in same and 'вчера' not in none


def test_any_city_gets_the_comparison_and_nothing_is_stored(monkeypatch):
    monkeypatch.setattr(weather, 'resolve_location', lambda city, lang: (1.0, 2.0, city))
    monkeypatch.setattr(weather, '_fetch_snapshot', lambda *a, **k: {'desc': 'Ясно', 'temp': 20, 'feels': 20, 'wind': 1.0, 'vs_yesterday': 5})
    ok, text = weather.get_weather('Берлин')
    assert ok and 'теплее, чем вчера' in text
    assert 'weather_yesterday' not in settings_io.read()


# ── offline: the last good answer ─────────────────────────────────────────

def test_voice_weather_falls_back_to_the_last_good_answer(monkeypatch):
    monkeypatch.setattr(weather, 'resolve_location', lambda city, lang: (1.0, 2.0, 'Киев'))
    monkeypatch.setattr(weather, '_fetch_snapshot', lambda *a, **k: {'desc': 'Ясно', 'temp': 20, 'feels': 20, 'wind': 1.0})
    ok, first = weather.get_weather('Киев')
    assert ok
    weather._weather_cache.clear()

    def _down(*a, **k):
        raise ConnectionError('offline')
    monkeypatch.setattr(weather, '_fetch_snapshot', _down)
    ok, text = weather.get_weather('Киев')
    assert ok and 'Нет связи, это данные на' in text and first in text


def test_voice_weather_gives_up_when_the_last_answer_is_too_old(monkeypatch):
    monkeypatch.setattr(weather, 'resolve_location', lambda city, lang: (1.0, 2.0, 'Киев'))
    weather._last_good['киев_0'] = {'text': 'старое', 'ts': 0}

    def _down(*a, **k):
        raise ConnectionError('offline')
    monkeypatch.setattr(weather, '_fetch_snapshot', _down)
    ok, text = weather.get_weather('Киев')
    assert not ok and 'старое' not in text


def test_hud_shows_the_snapshot_from_disk_when_everything_is_down(monkeypatch):
    import time
    weather_cache.save_snapshot({'ok': True, 'city': 'Киев', 'temp': 7, 'feels': 5, 'desc': 'Пасмурно', 'updated_ts': time.time() - 3600})
    monkeypatch.setattr(weather, 'home_location', lambda lang: None)
    data = weather.get_weather_hud()
    assert data['ok'] and data['temp'] == 7


def test_snapshot_on_disk_expires():
    import time
    weather_cache.save_snapshot({'ok': True, 'temp': 1, 'updated_ts': time.time() - 13 * 3600})
    assert weather_cache.load_snapshot() is None


def test_successful_hud_fetch_is_saved_with_the_air_index(monkeypatch):
    monkeypatch.setattr(weather, 'home_location', lambda lang: (1.0, 2.0, 'Киев'))
    monkeypatch.setattr(weather, '_fetch_snapshot', lambda *a, **k: {'ok': True, 'city': 'Киев', 'temp': 9, 'updated_ts': __import__('time').time()})
    monkeypatch.setattr(wx, 'fetch_air', lambda lat, lon, timeout=3.0: {'european_aqi': 42.4})
    data = weather.get_weather_hud()
    assert data['aqi'] == 42 and weather_cache.load_snapshot()['temp'] == 9


def test_hud_survives_a_failing_air_request(monkeypatch):
    monkeypatch.setattr(weather, 'home_location', lambda lang: (1.0, 2.0, 'Киев'))
    monkeypatch.setattr(weather, '_fetch_snapshot', lambda *a, **k: {'ok': True, 'city': 'Киев', 'temp': 9, 'updated_ts': __import__('time').time()})

    def _boom(*a, **k):
        raise TimeoutError
    monkeypatch.setattr(wx, 'fetch_air', _boom)
    data = weather.get_weather_hud()
    assert data['ok'] and data['aqi'] is None


# ── command wiring ────────────────────────────────────────────────────────

def _run_weather_command(monkeypatch, phrase, answers):
    from core.handler.commands import info
    import core.speech as speech
    monkeypatch.setattr(speech, 'run_speaking_task', lambda fn, **k: fn())
    monkeypatch.setattr(wx, 'answer', lambda kind, city: answers.append((kind, city)) or (True, 'ответ'))
    h = _Handler()
    info._weather(h, 'weather', phrase)
    return h


def test_command_sends_rain_questions_to_the_rain_answer(monkeypatch):
    calls = []
    h = _run_weather_command(monkeypatch, 'будет ли дождь в берлине', calls)
    assert calls == [('rain', 'берлине')] and h.said[-1] == 'ответ'


def test_command_resolves_a_saved_place(monkeypatch):
    weather_geo.add_place('мама', 'Львов')
    calls = []
    _run_weather_command(monkeypatch, 'что надеть у мамы', calls)
    assert calls == [('wear', 'Львов')]


def test_command_week_and_air_without_a_city(monkeypatch):
    calls = []
    _run_weather_command(monkeypatch, 'погода на неделю', calls)
    _run_weather_command(monkeypatch, 'какое качество воздуха', calls)
    assert calls == [('week', None), ('air', None)]


def test_command_plain_weather_does_not_use_the_extra_answers(monkeypatch):
    calls = []
    monkeypatch.setattr(weather, 'get_weather', lambda city, date_offset=0: (True, f'plain {city} {date_offset}'))
    h = _run_weather_command(monkeypatch, 'какая погода завтра в киеве', calls)
    assert calls == [] and h.said[-1] == 'plain киеве 1'


# ── proactive warnings ────────────────────────────────────────────────────

@pytest.fixture
def alerts(tmp_path, monkeypatch):
    from features import weather_alerts
    monkeypatch.setattr(weather_alerts, 'LOG_DIR', str(tmp_path))
    monkeypatch.setattr(weather_alerts, 'OUTLOOK_FILE', str(tmp_path / 'outlook.json'))
    monkeypatch.setattr(weather_alerts, 'LOG_FILE', str(tmp_path / 'alert.txt'))
    weather_alerts._announced_events.clear()
    weather.get_current_conditions  # noqa: B018  (imported lazily by the steps)
    monkeypatch.setattr(weather, 'get_current_conditions', lambda: {'lat': 1.0, 'lon': 2.0, 'desc': 'Ясно', 'temp': 10, 'wind': 2})

    class _Dt(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 21, 12, 0, tzinfo=tz)
    monkeypatch.setattr(weather_alerts, 'datetime', _Dt)
    return weather_alerts


def test_outlook_warning_is_spoken_once_per_day(alerts, monkeypatch):
    monkeypatch.setattr(wx, 'check_outlook', lambda lat, lon, lang: [('frost', 'Ночью заморозки.')])
    h = _Handler()
    alerts._outlook_step(h)
    alerts._outlook_step(h)
    assert len(h.said) == 1 and 'заморозки' in h.said[0]


def test_outlook_warning_is_silent_at_night(alerts, monkeypatch):
    from datetime import datetime as real

    class _Night(real):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 21, 3, 0, tzinfo=tz)
    monkeypatch.setattr(alerts, 'datetime', _Night)
    monkeypatch.setattr(wx, 'check_outlook', lambda lat, lon, lang: [('frost', 'x')])
    h = _Handler()
    alerts._outlook_step(h)
    assert h.said == []


def test_new_kinds_are_added_to_the_ones_already_said(alerts, monkeypatch):
    seq = iter([[('frost', 'Заморозки.')], [('frost', 'Заморозки.'), ('wind', 'Ветер.')]])
    monkeypatch.setattr(wx, 'check_outlook', lambda lat, lon, lang: next(seq))
    h = _Handler()
    alerts._outlook_step(h)
    alerts._outlook_step(h)
    assert len(h.said) == 2 and 'Ветер' in h.said[1] and 'Заморозки' not in h.said[1]


def _event(monkeypatch, alerts, minutes):
    ev = (datetime(2026, 10, 21, 12, 0) + timedelta(minutes=minutes), 'Встреча')
    monkeypatch.setattr('core.system.module_enabled', lambda name: True)
    monkeypatch.setattr(alerts, 'module_enabled', lambda name: True)
    import actions.calendar_ics as ics
    monkeypatch.setattr(ics, 'next_event_dt', lambda settings=None: ev)


def test_event_in_the_rain_gets_a_warning_once(alerts, monkeypatch):
    _event(monkeypatch, alerts, 60)
    monkeypatch.setattr(wx, 'rain_chance_at', lambda lat, lon, when: (80, 1.5))
    h = _Handler()
    alerts._event_step(h)
    alerts._event_step(h)
    assert len(h.said) == 1 and 'Встреча' in h.said[0] and '13:00' in h.said[0] and 'дождь' in h.said[0]


def test_event_with_dry_weather_is_silent(alerts, monkeypatch):
    _event(monkeypatch, alerts, 60)
    monkeypatch.setattr(wx, 'rain_chance_at', lambda lat, lon, when: (10, 0.0))
    h = _Handler()
    alerts._event_step(h)
    assert h.said == []


@pytest.mark.parametrize('minutes', [10, 200])
def test_event_outside_the_window_is_ignored(alerts, monkeypatch, minutes):
    _event(monkeypatch, alerts, minutes)
    monkeypatch.setattr(wx, 'rain_chance_at', lambda *a: pytest.fail('checked outside the window'))
    h = _Handler()
    alerts._event_step(h)
    assert h.said == []
