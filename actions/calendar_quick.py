"""Natural-language phrase -> calendar event ("завтра в 15:00 встреча с Аней", "в пятницу в 9 утра планёрка каждую неделю").
One parser for the calendar screen (quick add and its preview) and for the voice command "добавь в календарь ...".

Understands Russian and Ukrainian: today / tomorrow / the day after tomorrow, "через N дней/недель/месяцев", a weekday, dd.mm[.yyyy], "12 ноября",
a time ("в 15:30", "в 9 утра", "в 7 вечера", "с 14:00 до 15:30"), and a repeat ("каждый день", "каждую неделю", "каждый понедельник", "ежемесячно").
What is left after cutting those out is the title.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

_WD = {'понедельник': 0, 'понеділок': 0, 'вторник': 1, 'вівторок': 1, 'среду': 2, 'среда': 2, 'середу': 2, 'середа': 2, 'четверг': 3, 'четвер': 3,
       'пятницу': 4, 'пятница': 4, 'пʼятницю': 4, "п'ятницю": 4, 'субботу': 5, 'суббота': 5, 'суботу': 5, 'субота': 5, 'воскресенье': 6, 'неділю': 6, 'неділя': 6}
_WD_RE = '|'.join(sorted(_WD, key=len, reverse=True))
_MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
_MONTHS_UA = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
_MONTH_RE = '|'.join(_MONTHS + _MONTHS_UA)
_NUM = {'один': 1, 'одну': 1, 'одне': 1, 'два': 2, 'две': 2, 'дві': 2, 'три': 3, 'четыре': 4, 'чотири': 4, 'пять': 5, "п'ять": 5, 'шесть': 6, 'шість': 6, 'семь': 7, 'сім': 7, 'десять': 10, 'десять': 10}
_END = r'(?=[\s,.;!?]|$)'
_DAILY = re.compile(r'\s(?:каждый\s+день|ежедневно|кожен\s+день|щодня)' + _END, re.I)
_WEEKLY = re.compile(r'\s(?:каждую\s+неделю|еженедельно|кожен\s+тиждень|щотижня)' + _END, re.I)
_MONTHLY = re.compile(r'\s(?:каждый\s+месяц|ежемесячно|кожен\s+місяць|щомісяця)' + _END, re.I)
_YEARLY = re.compile(r'\s(?:каждый\s+год|ежегодно|кожен\s+рік|щороку)' + _END, re.I)
_EVERY_WD = re.compile(r'\s(?:каждый|каждую|каждое|кожен|кожну|кожного)\s+(' + _WD_RE + r')' + _END, re.I)
_RANGE = re.compile(r'\sс\s*(\d{1,2})[:.](\d{2})\s*(?:до|-|–)\s*(\d{1,2})[:.](\d{2})', re.I)
_RANGE_UA = re.compile(r'\sз\s*(\d{1,2})[:.](\d{2})\s*(?:до|-|–)\s*(\d{1,2})[:.](\d{2})', re.I)
_AT = re.compile(r'\s(?:в|к|на|о|об)\s+(\d{1,2})(?:[:. ]\s?(\d{2}))?\s*(?:час\w*\s*)?(утра|дня|вечера|ночи|ранку|дня|вечора|ночі)?' + _END, re.I)
_CLOCK = re.compile(r'\s(\d{1,2}):(\d{2})()' + _END)
_AFTER = re.compile(r'\sпослезавтра' + _END + r'|\sпіслязавтра' + _END, re.I)
_TOMORROW = re.compile(r'\s(?:завтра)' + _END, re.I)
_TODAY = re.compile(r'\s(?:сегодня|сьогодні)' + _END, re.I)
_IN = re.compile(r'\s(?:через)\s+(?:(\d+|[а-яіїєґʼ\']+)\s+)?(день|дня|дней|дні|днів|неделю|недели|недель|тиждень|тижні|тижнів|месяц|месяца|месяцев|місяць|місяці|місяців)' + _END, re.I)
_ON_WD = re.compile(r'\s(?:в|во|на|у)\s+(' + _WD_RE + r')' + _END, re.I)
_DAY_MONTH = re.compile(r'\s(\d{1,2})\s+(' + _MONTH_RE + r')(?:\s+(\d{4}))?' + _END, re.I)
_DOTTED = re.compile(r'\s(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?=[\s,;!?]|$)')
_LEAD = re.compile(r'^(?:в|на|к|с|до|через|по|о|у|з)\s+', re.I)
_TAIL = re.compile(r'\s+(?:в|на|к|с|до|через|по|о|у|з)$', re.I)


def _month_index(name: str) -> int:
    n = name.lower()
    return _MONTHS.index(n) if n in _MONTHS else _MONTHS_UA.index(n)


def parse_phrase(text: str, today: date | None = None, default_date: date | None = None) -> dict:
    """{title, date ('' when none), time, end_time, repeat, weekdays}. `default_date` is used when only a time or a repeat was said."""
    today = today or date.today()
    s = f' {text or ""} '
    out = {'title': '', 'date': '', 'time': '', 'end_time': '', 'repeat': 'none', 'weekdays': []}

    def take(rx):
        nonlocal s
        m = rx.search(s)
        if m:
            s = s[:m.start()] + ' ' + s[m.end():]
        return m
    if take(_DAILY):
        out['repeat'] = 'daily'
    elif take(_WEEKLY):
        out['repeat'] = 'weekly'
    elif take(_MONTHLY):
        out['repeat'] = 'monthly'
    elif take(_YEARLY):
        out['repeat'] = 'yearly'
    else:
        m = take(_EVERY_WD)
        if m:
            out['repeat'], out['weekdays'] = 'weekly', [_WD[m.group(1).lower()]]
    m = take(_RANGE) or take(_RANGE_UA)
    if m:
        out['time'], out['end_time'] = f'{int(m.group(1)):02d}:{m.group(2)}', f'{int(m.group(3)):02d}:{m.group(4)}'
    else:
        m = take(_AT) or take(_CLOCK)
        if m:
            h, part = int(m.group(1)), (m.group(3) or '').lower()
            if part in ('вечера', 'дня', 'вечора') and h < 12:
                h += 12
            if part in ('ночи', 'ночі') and h == 12:
                h = 0
            if h < 24 and int(m.group(2) or 0) < 60:
                out['time'] = f'{h:02d}:{int(m.group(2) or 0):02d}'
    d = None
    if take(_AFTER):
        d = today + timedelta(days=2)
    elif take(_TOMORROW):
        d = today + timedelta(days=1)
    elif take(_TODAY):
        d = today
    else:
        m = take(_IN)
        if m:
            raw = (m.group(1) or '1').lower()
            n = int(raw) if raw.isdigit() else _NUM.get(raw, 1)
            u = m.group(2).lower()
            if u.startswith(('нед', 'тиж')):
                d = today + timedelta(weeks=n)
            elif u.startswith(('мес', 'міс')):
                m0 = today.month - 1 + n
                year, mon = today.year + m0 // 12, m0 % 12 + 1
                d = today.replace(year=year, month=mon, day=1) + timedelta(days=min(today.day, 28) - 1)
            else:
                d = today + timedelta(days=n)
    if d is None:
        m = take(_ON_WD)
        if m:
            want = _WD[m.group(1).lower()]
            d = today + timedelta(days=((want - today.weekday()) % 7) or 7)
    if d is None:
        m = take(_DAY_MONTH)
        if m:
            try:
                d = date(int(m.group(3)) if m.group(3) else today.year, _month_index(m.group(2)) + 1, int(m.group(1)))
                if not m.group(3) and d < today:
                    d = d.replace(year=d.year + 1)
            except ValueError:
                d = None
    if d is None:
        m = take(_DOTTED)
        if m:
            y = int(m.group(3)) if m.group(3) else today.year
            y = 2000 + y if y < 100 else y
            try:
                d = date(y, int(m.group(2)), int(m.group(1)))
                if not m.group(3) and d < today:
                    d = d.replace(year=d.year + 1)
            except ValueError:
                d = None
    if d is None and out['repeat'] == 'weekly' and out['weekdays']:
        d = today + timedelta(days=(out['weekdays'][0] - today.weekday()) % 7)
    if d is None and (out['time'] or out['repeat'] != 'none'):
        d = default_date or today
    out['date'] = d.isoformat() if d else ''
    title = re.sub(r'\s+', ' ', s).strip(' ,.:;-')
    title = _TAIL.sub('', _LEAD.sub('', title)).strip(' ,.:;-')
    out['title'] = title[:1].upper() + title[1:] if title else ''
    return out


# ---- voice: "добавь в календарь ..." ----
_VERB = r'(?:добавь|добавить|создай|создать|запиши|записать|внеси|поставь|запланируй|запланировать|додай|створи|занеси)'
_ADD = re.compile(r'\b' + _VERB + r'\s+(?:мне\s+|мені\s+)?(?:(?:в|во|у|до)\s+(?:календар\w+|расписани\w+|розклад\w*)|(?P<noun>событие|встречу|подію|зустріч|дело|справу)\b)\s*(?:что\s+|що\s+|:\s*)?', re.I)
_NOUN = {'встречу': 'Встреча', 'зустріч': 'Зустріч', 'событие': '', 'подію': '', 'дело': 'Дело', 'справу': 'Справа'}


def is_add_phrase(text: str) -> bool:
    return bool(_ADD.search(text or ''))


def voice_phrase(text: str) -> str:
    """What follows "добавь в календарь" / "запланируй встречу": the part to parse. A named kind of event ("встречу") stays in the title."""
    m = _ADD.search(text or '')
    if not m:
        return ''
    rest = text[m.end():].strip()
    noun = _NOUN.get((m.group('noun') or '').lower(), '')
    return f'{noun} {rest}'.strip() if noun else rest


def spoken_when(day: str, time: str = '', repeat: str = 'none', today: date | None = None) -> str:
    """"завтра в 15:00", "в пятницу, 23 октября, весь день", "каждую неделю" ... for the confirmation Jarvis says."""
    today = today or date.today()
    d = date.fromisoformat(day)
    diff = (d - today).days
    names = ['в понедельник', 'во вторник', 'в среду', 'в четверг', 'в пятницу', 'в субботу', 'в воскресенье']
    base = {0: 'сегодня', 1: 'завтра', 2: 'послезавтра'}.get(diff) or f'{names[d.weekday()]}, {d.day} {_MONTHS[d.month - 1]}'
    rep = {'daily': ', каждый день', 'weekly': ', каждую неделю', 'monthly': ', каждый месяц', 'yearly': ', каждый год'}.get(repeat, '')
    return f'{base} в {time}{rep}' if time else f'{base}, на весь день{rep}'
