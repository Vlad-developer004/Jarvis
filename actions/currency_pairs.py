"""Exchange rates for any supported pair, spoken in the user's own currency ("курс юаня" with the lira as the home currency).

Settings (jarvis_settings.json): `currency_base`, the home currency (default UAH, the earlier fixed behaviour), and `currency_watch`, the list
of currencies the user follows (default dollar and euro). A phrase may name one currency ("курс юаня": that currency in the home one), two
("курс юаня к лире", "сколько стоит доллар в тенге": the first in the second) or none ("мои курсы": every followed currency in turn).
Names and numbers are inflected in Russian and Ukrainian (tables in actions/currency_data.py). actions/currency.py keeps the market feed.
"""
from __future__ import annotations

import json
import re
import time

from actions.currency import _inflect_currency, _inflect_uk, _market_rate, _num_to_ru_words, _num_to_uk_words
from actions.currency_data import CUR as _CUR, FEM_FRAC as _FEM_FRAC, FEM_MAIN as _FEM_MAIN, PHRASES as _PHRASES

DEFAULT_BASE = 'UAH'
DEFAULT_WATCH = ('USD', 'EUR')
MAX_WATCH = 12
_BTC_STEMS = ('биткоин', 'биткойн', 'біткоїн', 'біткойн', 'bitcoin', '=btc')
_PHRASE_RES = [(re.compile(p), t) for p, t in _PHRASES]
_WATCH_RE = re.compile(r'\b(?:мои|мої)\s+курс(?:ы|и)\b|\bкурс(?:ы|и)\s+валют|__PLACEHOLDER__(?:мои|мої)\s+курс(?:ы|и)|курс(?:ы|и)\s+валют', re.IGNORECASE)   # "мои курсы", "курсы валют" (not "курсы английского")
WATCH = 'WATCH'          # marker returned by resolve() for "мои курсы"


def _extra(stem: str) -> int:
    """How many letters a word may add to a stem and still count: case endings ("лир" -> "лирах"), not other words ("лирика")."""
    return 3 if len(stem) >= 5 else 2


def _stems() -> dict:
    """code -> (exact words, prefix stems), for both languages together."""
    out = {}
    for code, row in _CUR.items():
        exact, pre = set(), set()
        for s in row[9] + row[10]:
            if s.startswith('=') or len(s) == 3 and s.isascii():
                exact.add(s.lstrip('='))
            elif len(s) >= 3:
                pre.add(s)
        out[code] = (exact, pre)
    return out


_STEMS = _stems()
_BTC_EXACT = {s.lstrip('=') for s in _BTC_STEMS if s.startswith('=')}
_BTC_PRE = [s for s in _BTC_STEMS if not s.startswith('=')]


def supported(uk: bool = False) -> list[dict]:
    """The currencies with their names; Ukrainian names for the Ukrainian interface."""
    return [{'code': c, 'name': v[1] if uk else v[0]} for c, v in _CUR.items()]


def is_watch_phrase(text: str) -> bool:
    return bool(_WATCH_RE.search(text))


# ---- settings ----

def _read() -> dict:
    from core import settings_io
    return settings_io.read()


def _write(update: dict) -> bool:
    from core import settings_io
    if not settings_io.update(update):
        return False
    _spoken.clear()
    return True


def get_base() -> str:
    code = str(_read().get('currency_base') or '').upper()
    return code if code in _CUR else DEFAULT_BASE


def set_base(code: str) -> bool:
    code = str(code or '').upper()
    return code in _CUR and _write({'currency_base': code})


def clean_watch(codes) -> list[str]:
    out = []
    for c in codes if isinstance(codes, (list, tuple)) else []:
        c = str(c).upper()
        if (c in _CUR or c == 'BTC') and c not in out:
            out.append(c)
    return out[:MAX_WATCH]


def get_watch() -> list[str]:
    raw = _read().get('currency_watch')
    return clean_watch(raw) if isinstance(raw, list) else list(DEFAULT_WATCH)


def set_watch(codes) -> bool:
    return _write({'currency_watch': clean_watch(codes)})


# ---- recognising currencies in a phrase ----

def _match(word: str) -> str:
    for code, (exact, pre) in _STEMS.items():
        if word in exact or any(word.startswith(s) and len(word) <= len(s) + _extra(s) for s in pre):
            return code
    if word in _BTC_EXACT or any(word.startswith(s) and len(word) <= len(s) + _extra(s) for s in _BTC_PRE):
        return 'BTC'
    return ''


def mentioned(text: str) -> list[str]:
    """Currency codes named in the phrase, in the order they are spoken (no duplicates)."""
    low = text.lower()
    for rx, token in _PHRASE_RES:
        low = rx.sub(f' {token} ', low)
    out = []
    for w in re.findall(r'[a-zа-яіїєґё]+', low):
        code = _match(w)
        if code and code not in out:
            out.append(code)
    return out


def resolve(text: str) -> tuple[str, str]:
    """(target, base) for a phrase: what to price and in what. "мои курсы" -> (WATCH, home). Nothing named -> dollar in the home currency."""
    found = mentioned(text)
    base = get_base()
    if len(found) >= 2:
        return found[0], found[1]
    if not found and is_watch_phrase(text):
        return WATCH, base
    target = found[0] if found else 'USD'
    if target == 'BTC':
        return 'BTC', base
    if target == base:                                        # "курс гривны" with the hryvnia as home: price it in dollars (or euro)
        return target, 'EUR' if target == 'USD' else 'USD'
    return target, base


def build_pattern() -> str:
    """Regex alternation of every stem, for the recognizer's "this is a currency question" shortcut."""
    parts = set()
    for code, (exact, pre) in _STEMS.items():
        parts |= {re.escape(w) + r'\b' for w in exact}
        parts |= {re.escape(s) + r'\w{0,%d}\b' % _extra(s) for s in pre}
    parts |= {re.escape(w) + r'\b' for w in _BTC_EXACT}
    parts |= {re.escape(s) + r'\w{0,%d}\b' % _extra(s) for s in _BTC_PRE}
    return '|'.join(sorted(parts, key=len, reverse=True))


# ---- rates and speech ----

_spoken: dict = {}
_TTL = 300


def _btc_usd() -> float | None:
    from actions.currency import _btc_usd as f
    return f()


def rate(target: str, base: str) -> float | None:
    """Units of `base` for one `target` (bitcoin included), or None when the feed has no answer."""
    if target == 'BTC':
        usd = _btc_usd()
        if usd is None or base == 'USD':
            return usd
        to_base = _market_rate('USD', base)
        return None if to_base is None else usd * to_base
    return _market_rate(target, base)


def _pick_amount(value: float, has_frac: bool) -> tuple[int, float]:
    """How many units to price so the answer is a readable number: one unit, or 100 / 1000 / ... for weak currencies."""
    for m in (1, 100, 1000, 10000, 100000):
        v = value * m
        if (v >= 1 if has_frac else round(v) >= 1):
            return m, v
    return 100000, value * 100000


def _words(uk: bool):
    return (_num_to_uk_words, _inflect_uk) if uk else (_num_to_ru_words, _inflect_currency)


def _fem(words: str, uk: bool) -> str:
    """Feminine form of the last numeral word: один/два -> одна/две (дві)."""
    head, _, last = words.rpartition(' ')
    last = {'один': 'одна', 'два': 'дві' if uk else 'две'}.get(last, last)
    return f'{head} {last}'.strip()


def _money(value: float, main, frac, uk: bool, fem_main: bool = False, fem_frac: bool = False) -> str:
    num, infl = _words(uk)
    whole = int(value)
    cents = round((value - whole) * 100) if frac else 0
    if cents >= 100:
        whole, cents = whole + 1, 0
    if not frac:
        whole = int(round(value))
    parts = []
    if whole or not cents:
        w = num(whole)
        parts.append(f'{_fem(w, uk) if fem_main else w} {infl(whole, *main)}')
    if cents:
        c = num(cents)
        parts.append(f'{_fem(c, uk) if fem_frac else c} {infl(cents, *frac)}')
    return ' '.join(parts)


def _forms(code: str, uk: bool):
    r = _CUR[code]
    return (r[7], r[8]) if uk else (r[4], r[5])                  # unit forms (1, 2-4, 5+) and fraction forms


def _label(code: str, uk: bool, after_to: bool = False) -> str:
    """Name for "курс <genitive> к <dative>" (Ukrainian "до" takes the genitive for both)."""
    r = _CUR[code]
    return r[6] if uk else r[3] if after_to else r[2]


def _price(target: str, base: str, uk: bool):
    """(units priced, spoken amount) of `target` in `base`, or None when the feed has no rate."""
    value = rate(target, base)
    if value is None:
        return None
    main, frac = _forms(base, uk)
    if target == 'BTC':
        return 1, _money(value, main, None, uk, base in _FEM_MAIN)
    m, v = _pick_amount(value, frac is not None)
    return m, _money(v, main, frac, uk, base in _FEM_MAIN, base in _FEM_FRAC)


def _units(target: str, m: int, uk: bool) -> str:
    """"сто иен" / "тысяча тенге" / "доллар": what is being priced."""
    main = _CUR[target][7 if uk else 4]
    if m == 1:
        return main[0]
    num, infl = _words(uk)
    return f'{num(m)} {infl(m, *main)}'.replace('одна тысяча', 'тысяча').replace('одна тисяча', 'тисяча')


def get_rate_pair(target: str, base: str) -> tuple[bool, str, str]:
    """(ok, spoken sentence, web page with the same rate)."""
    from core.i18n import get_speech_language
    uk = get_speech_language() == 'uk'
    target, base = target.upper(), base.upper()
    if base not in _CUR or (target not in _CUR and target != 'BTC'):
        return False, ('Невідома валюта.' if uk else 'Неизвестная валюта.'), ''
    url = f'https://www.google.com/search?q=1+{target.lower()}+to+{base.lower()}'
    key = f'{target}_{base}_{uk}'
    hit = _spoken.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return True, hit[1], url
    try:
        priced = _price(target, base, uk)
    except Exception as e:
        return False, (f'Помилка при отриманні курсу: {e}' if uk else f'Ошибка при получении курса: {e}'), url
    if priced is None:
        return False, ('Не вдалося отримати курс.' if uk else 'Не удалось получить курс.'), url
    m, amount = priced
    if target == 'BTC':
        text = f'Біткоїн сьогодні коштує — {amount}.' if uk else f'Сэр, биткоин сегодня стоит — {amount}.'
    elif m == 1:
        t_label, b_label = _label(target, uk), _label(base, uk, True)
        text = f'Курс {t_label} до {b_label} сьогодні — {amount}.' if uk else f'Сэр, курс {t_label} к {b_label} сегодня — {amount}.'
    else:
        many = _units(target, m, uk)
        text = f'{many.capitalize()} сьогодні коштують — {amount}.' if uk else f'Сэр, {many} сегодня стоят — {amount}.'
    _spoken[key] = (time.time(), text)
    return True, text, url


def get_watch_summary(base: str) -> tuple[bool, str, str]:
    """One sentence with every followed currency priced in `base` ("мои курсы")."""
    from core.i18n import get_speech_language
    uk = get_speech_language() == 'uk'
    items = [c for c in get_watch() if c != base]
    if not items:
        return False, ('Список валют порожній: додайте їх у розділі «Команди».' if uk else 'Список валют пуст: добавьте их в разделе «Команды».'), ''
    parts = []
    for code in items:
        try:
            priced = _price(code, base, uk)
        except Exception:
            priced = None
        if priced is None:
            continue
        m, amount = priced
        name = 'біткоїн' if code == 'BTC' and uk else 'биткоин' if code == 'BTC' else _units(code, m, uk)
        parts.append(f'{name} — {amount}')
    if not parts:
        return False, ('Не вдалося отримати курси.' if uk else 'Не удалось получить курсы.'), ''
    b_label = _label(base, uk, True)
    head = f'Курси до {b_label}: ' if uk else f'Сэр, курсы к {b_label}: '
    return True, head + '; '.join(parts) + '.', ''
