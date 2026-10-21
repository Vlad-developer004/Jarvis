"""A time of day in a timer phrase: "поставь таймер на 13 15", "таймер до тринадцати пятнадцати", "таймер на 8:30 вечера".

extract_duration_seconds() only knows lengths ("15 минут"), so "на 13 15" used to give nothing. Here the clock time is turned into the seconds
left until its next occurrence (today, or tomorrow when it has already passed)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_HM = re.compile(r'(?<![\d:.])(\d{1,2})\s*[:.]\s*(\d{2})(?![\d:.])'            # 13:15, 13.15
                 r'|(?<![\d:.])(\d{1,2})\s+0\s+(\d)(?![\d:])'                       # 13 0 5 = 13:05
                 r'|(?<![\d:.])(\d{1,2})\s+(\d{2}|0)(?![\d:])')                       # 13 15, 13 0
_UNITS = re.compile(r'час|минут|секунд|хвилин|годин')
_PART = (('вечера', 12), ('дня', 12), ('утра', 0), ('ночи', 0))


def parse_clock(text: str) -> tuple[int, int] | None:
    """(hour, minute) of a clock time spoken without length units, or None. "13 15", "13:15", "тринадцать ноль пять" (13:05), "8 30 вечера" (20:30)."""
    from core.nlp.commands import normalize_numbers
    t = normalize_numbers(text.lower().replace('ё', 'е'))
    if _UNITS.search(t):
        return None                  # "13 часов 15 минут" is a length, not a time of day
    m = _HM.search(t)
    if not m:
        return None
    if m.group(1):
        h, mi = int(m.group(1)), int(m.group(2))
    elif m.group(3):
        h, mi = int(m.group(3)), int(m.group(4))
    else:
        h, mi = int(m.group(5)), int(m.group(6))
    for word, shift in _PART:
        if re.search(rf'\b{word}\b', t):
            if shift and h < 12:
                h += shift
            elif not shift and h == 12:
                h = 0
            break
    return (h, mi) if 0 <= h <= 23 and 0 <= mi <= 59 else None


def seconds_until(hm: tuple[int, int], now: datetime | None = None) -> int:
    now = now or datetime.now()
    target = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds())
