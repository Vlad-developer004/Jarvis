"""Short follow-ups that only make sense after the previous command: "а завтра?" after the weather, "ещё пять минут" after a timer,
"ещё" after "громче". The recognizer asks here only when nothing else matched the phrase."""
from __future__ import annotations

import re
import threading
import time

TTL = 120.0     # seconds after the previous command during which a follow-up still refers to it
_lock = threading.Lock()
_last: tuple[str, str, float] | None = None

_DAY = r'(?:сегодня|завтра|послезавтра|утром|днём|днем|вечером|ночью|через\s+\w+\s+дн\w+|на\s+выходные|на\s+неделю|выходные|неделю)'
_WEATHER_DAY = re.compile(rf'^(?:а|и|ну|а как|а что)?\s*(?:там\s+)?(?:на\s+)?({_DAY})$')
_WEATHER_CITY = re.compile(r'^(?:а|и)\s+(?:в|во)\s+([а-яёіїєґa-z][а-яёіїєґa-z\- ]{1,29})$')
_TIMER_MORE = re.compile(r'^(?:и\s+|а\s+)?(?:ещё|еще)\s+(.+)$')
_AGAIN = {'ещё', 'еще', 'ещё немного', 'еще немного', 'ещё чуть', 'еще чуть', 'ещё чуть-чуть', 'еще чуть-чуть', 'ещё раз', 'еще раз', 'и ещё', 'и еще',
          'давай ещё', 'давай еще', 'продолжай'}
_REPEATABLE = ('vol_up', 'vol_down', 'brightness_up', 'brightness_down')
_TIMER_CMDS = ('timer_set', 'timer_add', 'timer_sub')


def early(text: str) -> tuple[str, str] | None:
    """Phrases that are unambiguous on their own and must not wait for the semantic model: spoken arithmetic, also a continuation of the last
    calculator answer ("и плюс сто тридцать три"). Asked before the normal parse."""
    from core.nlp import calc, weather_route
    return calc.route(text) or weather_route.route(text)


def remember(cmd: str, segment: str) -> None:
    """Called for every command that was executed (not for a bare wake word)."""
    global _last
    with _lock:
        _last = (cmd, segment, time.time())


def forget() -> None:
    global _last
    with _lock:
        _last = None


def resolve(text: str, now: float | None = None) -> tuple[str, str] | None:
    """The (command, segment) a follow-up phrase stands for, or None when it is not one or the previous command is too old."""
    with _lock:
        prev = _last
    if prev is None:
        return None
    cmd, seg, ts = prev
    if (time.time() if now is None else now) - ts > TTL:
        return None
    t = re.sub(r'\s+', ' ', text.lower().replace('?', ' ').replace('!', ' ').replace(',', ' ')).strip()
    if not t or len(t) > 40:
        return None
    if cmd == 'weather':
        m = _WEATHER_DAY.match(t)
        if m:
            return 'weather', f'погода {m.group(1)}'
        m = _WEATHER_CITY.match(t)
        if m:
            return 'weather', f'погода в {m.group(1).strip()}'
    if cmd in _TIMER_CMDS:
        m = _TIMER_MORE.match(t)
        if m:
            from core.nlp import extract_duration_seconds
            if extract_duration_seconds(m.group(1)) > 0:
                return 'timer_add', f'добавь {m.group(1)}'
    if cmd in _REPEATABLE and t in _AGAIN:
        return cmd, seg
    return None
