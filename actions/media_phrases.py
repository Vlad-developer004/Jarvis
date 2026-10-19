"""Spoken phrases about what is playing (RU/UA): "перемотай на 5 минут вперёд", "что сейчас играет", "сколько осталось до конца".

Only the words are understood here; the player side is actions/now_playing.py. `route(text)` is what the recognizer asks first; it answers with one of the
`cinema_*` commands (they sit behind the "cinema" module switch) or None when the phrase is about something else.
"""
from __future__ import annotations

import re
from core.safe import swallow as _swallow

_FLAGS = re.IGNORECASE
_SEEK_VERB = re.compile(r'\b(перемотай\w*|промотай\w*|отмотай\w*|прокрути\w*|мотни\w*|мотай\w*|вернись|верни(?:сь)?|перемотати|промотай|відмотай\w*|перемотай|поверни(?:сь)?|пропусти|пропустити)\b', _FLAGS)
_BACK_WORDS = re.compile(r'\b(назад|отмотай\w*|вернись|відмотай\w*|поверни(?:сь)?|раньше|раніше)\b', _FLAGS)
_FWD_WORDS = re.compile(r'\b(вперед|вперёд|далі|дальше|пропусти\w*)\b', _FLAGS)
_HALF_HOUR = re.compile(r'\b(пол\s?часа|пів\s?години|півгодини)\b', _FLAGS)
_HALF_MIN = re.compile(r'\b(пол\s?минуты|півхвилини|пів\s?хвилини)\b', _FLAGS)
_CLOCK = re.compile(r'(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)')
_AMOUNT = re.compile(r'(\d+(?:[.,]\d+)?)?\s*(час(?:а|ов|у)?|годин[уиа]?|мин(?:ут[уыа]?)?|хвилин[уиа]?|хв|сек(?:унд[уыа]?)?|с)(?![а-яёa-z])', _FLAGS)
_UNIT_SECONDS = (('час', 3600), ('годин', 3600), ('мин', 60), ('хв', 60), ('сек', 1), ('с', 1))
_ABS = re.compile(r'\bна\s+отметку\b|\bна\s+позицию\b|\bна\s+позицію\b|\bна\s+позначку\b', _FLAGS)

_NOW = (re.compile(r'\bчто\s+(?:сейчас|щас|там)?\s*(?:играет|идёт|идет|воспроизводится|включено)\b', _FLAGS), re.compile(r'\bчто\s+(?:это\s+)?(?:за\s+)?(?:видео|серия|фильм|ролик|сериал)\b', _FLAGS),
        re.compile(r'\bчто\s+я\s+смотрю\b', _FLAGS), re.compile(r'\bщо\s+(?:зараз|зараз\s+там)?\s*(?:грає|йде|відтворюється)\b', _FLAGS), re.compile(r'\bщо\s+я\s+дивлюсь\b', _FLAGS))
_MUSIC_WORDS = re.compile(r'песн|пісн|трек|музык|музик|композиц', _FLAGS)           # "что за песня играет" belongs to song recognition
_LEFT = (re.compile(r'\bсколько\b.{0,15}\b(?:осталось|останется)\b.{0,15}\bдо\s+конца\b', _FLAGS), re.compile(r'\bсколько\b.{0,12}\b(?:осталось|останется)\b.{0,20}\b(?:фильма|серии|видео|ролика|сериала)\b', _FLAGS),
         re.compile(r'\bскільки\b.{0,15}\b(?:залишилось|лишилось)\b.{0,15}\bдо\s+кінця\b', _FLAGS), re.compile(r'\bдо\s+конца\s+(?:фильма|серии|видео|ролика)\b', _FLAGS))


def _norm(text: str) -> str:
    try:
        from core.nlp import normalize_numbers
        text = normalize_numbers(text)
    except Exception:
        _swallow()
    return (text or '').lower().replace('ё', 'е')


def _seconds_in(text: str) -> float | None:
    """Total seconds named in the phrase ("1 час 20 минут" -> 4800, "полчаса" -> 1800), None when there is no amount."""
    total, found = 0.0, False
    if _HALF_HOUR.search(text):
        total, found = total + 1800, True
        text = _HALF_HOUR.sub(' ', text)
    if _HALF_MIN.search(text):
        total, found = total + 30, True
        text = _HALF_MIN.sub(' ', text)
    for m in _AMOUNT.finditer(text):
        unit = m.group(2).lower()
        mult = next((v for k, v in _UNIT_SECONDS if unit.startswith(k)), None)
        if mult is None:
            continue
        num = m.group(1)
        if num is None and unit == 'с':
            continue                                    # a lone "с" is the preposition, not seconds
        total += (float(num.replace(',', '.')) if num else 1.0) * mult
        found = True
    return total if found and total > 0 else None


def parse_seek(text: str) -> dict | None:
    """{'mode': 'by'|'to', 'seconds': n} for a rewind phrase, else None. "by" is relative (negative = back), "to" is a position from the start."""
    t = _norm(text)
    if not _SEEK_VERB.search(t):
        return None
    clock = _CLOCK.search(t)
    if clock and (_ABS.search(t) or re.search(r'\bна\s+' + re.escape(clock.group(0)), t)):
        h, mi, s = (int(clock.group(1)), int(clock.group(2)), int(clock.group(3) or 0)) if clock.group(3) else (0, int(clock.group(1)), int(clock.group(2)))
        return {'mode': 'to', 'seconds': float(h * 3600 + mi * 60 + s)}
    sec = _seconds_in(_CLOCK.sub(' ', t))
    if sec is None:
        return None
    if _ABS.search(t):
        return {'mode': 'to', 'seconds': sec}
    back = bool(_BACK_WORDS.search(t)) and not (_FWD_WORDS.search(t) and not re.search(r'\bназад\b', t))
    return {'mode': 'by', 'seconds': -sec if back else sec}


def is_now(text: str) -> bool:
    t = _norm(text)
    return not _MUSIC_WORDS.search(t) and any(p.search(t) for p in _NOW)


def is_left(text: str) -> bool:
    t = _norm(text)
    return any(p.search(t) for p in _LEFT)


# ---- "включи фильм X", "найди сериал X сезон 2 серия 3", "где посмотреть X" ----
_WATCH_VERB = r'(?:включи|включить|поставь|поставить|найди|найти|покажи|показать|запусти|запустить|открой|хочу\s+посмотреть|давай\s+посмотрим|посмотреть|смотреть|'               r'увімкни|постав|знайди|покажи|запусти|відкрий|хочу\s+подивитися|давай\s+подивимось|подивитися|дивитися|подивитись)'
_WATCH_WHERE = r'(?:где\s+(?:можно\s+)?(?:посмотреть|смотреть)|де\s+(?:можна\s+)?(?:подивитися|дивитися|дивитись))'
_MEDIA_NOUN = r'(?P<noun>мультсериал\w*|сериал\w*|серіал\w*|фильм\w*|фільм\w*|кино|кіно|мультфильм\w*|мультфільм\w*|мультик\w*|аниме|аніме|шоу)'
_WATCH_RE = re.compile(r'^\W*(?:(?:' + _WATCH_VERB + r')\s+(?:мне\s+|нам\s+)?' + _MEDIA_NOUN + r'|(?P<where>' + _WATCH_WHERE + r'))\s*(?P<rest>.*)$', _FLAGS)
_SEASON_RE = re.compile(r'(?:сезон\w*|season)\s*(\d+)|(\d+)\s*(?:-?й\s*)?(?:сезон\w*)', _FLAGS)
_EPISODE_RE = re.compile(r'(?:сери[яюи]|серія|серію|эпизод\w*|епізод\w*)\s*(\d+)|(\d+)\s*(?:-?я\s*)?(?:сери[яюи]|серія|эпизод\w*|епізод\w*)', _FLAGS)
_TAIL_RE = re.compile(r'\s+(?:онлайн|безкоштовно|бесплатно|в\s+хорошем\s+качестве|в\s+хорошій\s+якості)\s*$', _FLAGS)
_SERIES_NOUN = re.compile(r'сериал|серіал', _FLAGS)


def parse_watch(text: str) -> dict | None:
    """A request to watch something: {'type': 'movie'|'series'|'unknown', 'title', 'season', 'episode', 'hint'}; None for any other phrase.
    `season`/`episode` are None unless said; `hint` is the phrase without the leading verb, for finding a named service ("... на Netflix")."""
    t = _norm(text).strip()
    m = _WATCH_RE.match(t)
    if not m:
        return None
    rest = (m.group('rest') or '').strip()
    noun = (m.group('noun') or '').lower()
    season = episode = None
    sm = _SEASON_RE.search(rest)
    if sm:
        season = int(sm.group(1) or sm.group(2))
        rest = (rest[:sm.start()] + ' ' + rest[sm.end():]).strip()
    em = _EPISODE_RE.search(rest)
    if em:
        episode = int(em.group(1) or em.group(2))
        rest = (rest[:em.start()] + ' ' + rest[em.end():]).strip()
    hint = rest
    rest = re.sub(r'\s+(?:на|в|у|во)\s+[\w+.\- ]{2,25}$', lambda mm: '' if _looks_like_service(mm.group(0)) else mm.group(0), rest).strip()
    rest = _TAIL_RE.sub('', rest).strip(' ,.-')
    kind = 'series' if (_SERIES_NOUN.search(noun) or season or episode) else ('movie' if noun else 'unknown')
    return {'type': kind, 'title': rest, 'season': season, 'episode': episode, 'hint': hint}


def _looks_like_service(tail: str) -> bool:
    """True when the "на X" at the end of a request names a viewing service (so it is not part of the title)."""
    try:
        from actions import cinema_services as cs
        pool = [{'id': p['id'], 'name': p['name'], 'domain': p['domain']} for p in cs.PRESETS]
        return cs.find_service(pool, tail) is not None
    except Exception:
        return False


# ---- "продолжи сериал X", "продолжи смотреть X", "включи следующую серию X" (the user's own files) ----
_CONTINUE_RE = re.compile(r'^\W*(?:(?:продолжи|продолжить|продовж\w*)\s+(?:смотреть|просмотр|сериал\w*|серіал\w*|дивитися|дивитись|перегляд)|'
                          r'(?:включи|увімкни|поставь|постав)\s+(?:следующую|наступну)\s+(?:серию|серію))\s*(?P<rest>.*)$', _FLAGS)


def parse_continue(text: str) -> dict | None:
    """{'title': str} for "continue the series" (title may be empty: the last watched one); None for any other phrase."""
    m = _CONTINUE_RE.match(_norm(text).strip())
    if not m:
        return None
    title = re.sub(r'^(?:сериал\w*|серіал\w*|про|у|в)\s+', '', (m.group('rest') or '').strip())
    return {'title': title.strip(' ,.-')}


# ---- "когда выйдет следующая серия X" (dates from TVmaze, see actions/tv_info.py) ----
_WHEN_RE = re.compile(r'^\W*(?:когда|коли)\s+(?:(?:будет|выйдет|выходит|появится)|(?:буде|вийде|виходить|з.явиться))\s+(?:следующая|новая|очередная|наступна|нова|чергова)\s+(?:серия|серія|серию)\s*(?P<rest>.*)$', _FLAGS)


def parse_when(text: str) -> dict | None:
    """{'title': str} for "when is the next episode of X" (title may be empty: the last series from the library); None for any other phrase."""
    m = _WHEN_RE.match(_norm(text).strip())
    if not m:
        return None
    title = re.sub(r'^(?:сериала?|серіалу?|у|в|для|про)\s+', '', (m.group('rest') or '').strip())
    return {'title': title.strip(' ,.-?')}


# ---- cinema mode and the watch-later list ----
_MODE_RE = re.compile(r'\bрежим\w*\s+(?:кино|кіно|кинотеатр\w*|кінотеатр\w*)\b', _FLAGS)
_MODE_OFF = re.compile(r'\b(?:выключи|отключи|отмени|закончи|заверши|выйди|вылезь|вимкни|скасуй|закінчи|вийди)\w*', _FLAGS)
_LATER_ADD = re.compile(r'^\W*(?:добавь|добавить|занеси|запиши|додай)\s+(?:(?P<noun>фильм|сериал|фільм|серіал)\s+)?(?P<t>.+?)\s+(?:в|у|до)\s+(?:список|списку)\s+(?:просмотра|просмотр|желаемого|перегляду|бажаного|посмотреть)\W*$', _FLAGS)
_LATER_SOON = re.compile(r'^\W*(?:посмотрю|подивлюсь|посмотрим|подивимось)\s+(?:позже|пізніше|потом|потім)\s+(?:(?P<noun>фильм|сериал|фільм|серіал)\s+)?(?P<t>.+?)\W*$', _FLAGS)
_LATER_LIST = re.compile(r'\bчто\s+(?:у\s+меня\s+)?в\s+списке\s+(?:просмотра|желаемого)\b|\bщо\s+(?:у\s+мене\s+)?в\s+списку\s+(?:перегляду|бажаного)\b|\bчто\s+я\s+хотел\s+посмотреть\b|\bщо\s+я\s+хотів\s+подивитися\b', _FLAGS)


def parse_mode(text: str) -> str | None:
    """'on' / 'off' for "режим кино" phrases ("включи режим кино", "выключи режим кино"), else None."""
    t = _norm(text)
    if not _MODE_RE.search(t):
        return None
    return 'off' if _MODE_OFF.search(t) else 'on'


def parse_later(text: str) -> dict | None:
    """{'title', 'kind'} for "добавь Дюна в список просмотра" / "посмотрю позже Дюна", else None."""
    t = _norm(text).strip()
    m = _LATER_ADD.match(t) or _LATER_SOON.match(t)
    if not m or len(m.group('t').strip()) < 2:
        return None
    title = m.group('t').strip(' ,.-')
    return {'title': title[:1].upper() + title[1:], 'kind': 'series' if (m.group('noun') or '').startswith(('сериал', 'серіал')) else 'movie'}


def is_later_list(text: str) -> bool:
    return bool(_LATER_LIST.search(_norm(text)))


def route(text: str) -> str | None:
    """The `cinema_*` command for a phrase about the running media or about finding something to watch, or None."""
    if parse_seek(text) is not None:
        return 'cinema_seek'
    if is_left(text):
        return 'cinema_left'
    if is_now(text):
        return 'cinema_now'
    if parse_mode(text) is not None:
        return 'cinema_mode'
    if parse_later(text) is not None:
        return 'cinema_later'
    if is_later_list(text):
        return 'cinema_later_list'
    if parse_when(text) is not None:
        return 'cinema_when'
    if parse_continue(text) is not None:
        return 'cinema_continue'
    if parse_watch(text) is not None:
        return 'cinema_watch'
    return None


def spoken_duration(sec: float) -> str:
    """"5 минут", "1 час 20 минут", "45 секунд" (Russian forms; the Ukrainian voice reads the same digits)."""
    sec = int(round(abs(sec)))
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)

    def plural(n: int, one: str, few: str, many: str) -> str:
        return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
    parts = []
    if h:
        parts.append(f"{h} {plural(h, 'час', 'часа', 'часов')}")
    if m:
        parts.append(f"{m} {plural(m, 'минута', 'минуты', 'минут')}")
    if s and not h:
        parts.append(f"{s} {plural(s, 'секунда', 'секунды', 'секунд')}")
    return ' '.join(parts) or '0 секунд'
