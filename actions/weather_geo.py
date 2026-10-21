"""Where the weather is asked for: a named city, the manual-city setting, the last known location or an IP/Windows lookup.

Split out of actions/weather.py; the HUD, the spoken weather and the forecast all resolve places through this module."""
import concurrent.futures
from core.i18n import get_language
from core.netpolicy import ip_lookup_allowed
from core.safe import swallow as _swallow
from core import settings_io

HEADERS = {'User-Agent': 'Mozilla/5.0'}
_GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
_REVERSE_URL = 'https://api.bigdatacloud.net/data/reverse-geocode-client'
# Endings of a name said in the prepositional case ("в Москве", "в Одессе") that the geocoder only finds without the last letter.
_CASE_ENDINGS = ('е', 'и', 'а', 'у')
_city_names: dict[tuple[float, float, str], str] = {}


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


def _ip_geolocation(headers: dict) -> tuple[float, float, str] | None:
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
                        if not ip_lookup_allowed():
                            return (lat_val, lon_val, city_name)
                        resp = requests.get(f"https://ipwho.is/?lang={lang}", headers=headers, timeout=2.0)
                        if resp.status_code == 200:
                            city_name = resp.json().get('city') or city_name
                    except Exception: _swallow()
                    return (lat_val, lon_val, city_name)
        except Exception:
            _swallow()

    # 2. Fallback to IP Geolocation Providers if Windows Location Service is off/unavailable
    if not ip_lookup_allowed():
        return None
    providers = (      # https only: a plain-http answer can be swapped on the way
        ("ipwho", f"https://ipwho.is/?lang={lang}"),
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
    # No `with` block: its exit waits for the slowest provider even after we
    # already have an answer from the fastest one.
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(providers))
    try:
        futures = [pool.submit(fetch_one, p) for p in providers]
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=10.0):
                try:
                    r = fut.result()
                    if r:
                        return r
                except Exception:
                    _swallow()
        except concurrent.futures.TimeoutError:
            pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return None


def load_last_location() -> tuple[float, float, str] | None:
    loc = settings_io.read().get('last_location')
    if not isinstance(loc, dict):
        return None
    try:
        lat, lon = loc.get('lat'), loc.get('lon')
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon), str(loc.get('city') or 'Ваш город'))
    except (TypeError, ValueError):
        return None


def save_last_location(lat: float, lon: float, city: str) -> None:
    settings_io.update({'last_location': {'lat': float(lat), 'lon': float(lon), 'city': str(city)}})


def _geocode(name: str, lang: str) -> list[dict]:
    import requests
    try:
        resp = requests.get(_GEOCODE_URL, params={'name': name, 'count': 5, 'language': lang, 'format': 'json'}, headers=HEADERS, timeout=2)
        return resp.json().get('results') or []
    except Exception:
        _swallow()
        return []


def _exact(results: list[dict], name: str) -> dict | None:
    want = name.casefold()
    return next((r for r in results if str(r.get('name', '')).casefold() == want), None)


def _as_place(hit: dict, fallback: str) -> tuple[float, float, str]:
    return (hit['latitude'], hit['longitude'], hit.get('name', fallback))


def geocode_city(city: str, lang: str) -> tuple[float, float, str] | None:
    """Looks a spoken city name up. A result whose name equals the query wins, so a nominative "Одесса" is not cut to "Одесс". A name that
    looks prepositional is retried without its last letter; the geocoder's own best guess for the original is the last resort."""
    name = city.strip()
    if not name:
        return None
    first = _geocode(name, lang)
    hit = _exact(first, name)
    if hit:
        return _as_place(hit, city)
    if len(name) > 4 and name.lower().endswith(_CASE_ENDINGS):
        stem = name[:-1]
        second = _geocode(stem, lang)
        hit = _exact(second, stem) or (second[0] if second else None)
        if hit:
            return _as_place(hit, city)
    return _as_place(first[0], city) if first else None


def localized_city(lat: float, lon: float, fallback: str, lang: str) -> str:
    """The place name in the current language. The answer is kept per place and language, so the coordinates go to the lookup service
    once, not on every refresh, and not at all when IP lookups are switched off."""
    key = (round(lat, 2), round(lon, 2), lang)
    if key in _city_names:
        return _city_names[key]
    if not ip_lookup_allowed():
        return fallback
    import requests
    try:
        params = {'latitude': lat, 'longitude': lon, 'localityLanguage': lang}
        resolved = requests.get(_REVERSE_URL, params=params, headers=HEADERS, timeout=2).json().get('city')
        if resolved:
            _city_names[key] = resolved
            return resolved
    except Exception:
        _swallow()
    return fallback


def auto_location(lang: str) -> tuple[float, float, str] | None:
    """Last known location, else Windows/IP geolocation (remembered for next time)."""
    last = load_last_location()
    if last:
        lat, lon, city = last
        return (lat, lon, localized_city(lat, lon, city, lang))
    geo = _ip_geolocation(HEADERS)
    if geo:
        save_last_location(*geo)
    return geo


def home_location(lang: str) -> tuple[float, float, str] | None:
    """Where the user is: the manual-city setting if it can be found, otherwise the automatic location."""
    manual = settings_io.read().get('manual_city')
    if manual:
        hit = geocode_city(str(manual), lang)
        if hit:
            return hit
    return auto_location(lang)


_MAX_PLACES = 20


def get_places() -> dict[str, str]:
    """Named places ("мама" -> "Львов") the user saved by voice."""
    places = settings_io.read().get('weather_places')
    return {str(k): str(v) for k, v in places.items()} if isinstance(places, dict) else {}


def add_place(alias: str, city: str) -> bool:
    alias, city = alias.strip().lower(), city.strip()
    places = get_places()
    if not alias or not city or (alias not in places and len(places) >= _MAX_PLACES):
        return False
    places[alias] = city
    return settings_io.update({'weather_places': places})


def find_place(text: str) -> tuple[str | None, str]:
    """(city, text without the place words) when the phrase names a saved place: "погода у мамы", "а в доме"; the alias is matched by its stem,
    so the case ending does not matter."""
    import re
    for alias, city in sorted(get_places().items(), key=lambda kv: -len(kv[0])):
        stem = re.escape(alias[:-1] if len(alias) > 3 else alias)
        m = re.search(rf'(?:\b(?:у|в|во|для|к|на)\s+)?\b{stem}\w*', text)
        if m:
            return city, f'{text[:m.start()]} {text[m.end():]}'.strip()
    return None, text


def resolve_location(city: str | None, lang: str) -> tuple[float | None, float | None, str | None]:
    """Resolve a city name (or the user's own place when `city` is empty) into (lat, lon, city_name).
    On failure returns (None, None, X) where X is the city name that failed geocoding, or None if it was auto-location that failed —
    callers use that to choose the right localized error message without this function owning any user-facing text itself."""
    if not city:
        manual = settings_io.read().get('manual_city')
        if not manual:
            auto = auto_location(lang)
            return auto if auto else (None, None, None)
        city = str(manual)
    hit = geocode_city(city, lang)
    return hit if hit else (None, None, city)
