"""Shared formatting/phrasing helpers for ETS2 voice narration: number
declension, unit formatting, wear-component names, and the RU/UK phrase
picker (_r) used by every event_* function. Split out of the old
phrases.py purely for file size; no behavior change.
"""
import re

def _decline_ru(n: int, f1: str, f2: str, f5: str) -> str:
    last2, last1 = abs(n) % 100, abs(n) % 10
    if 11 <= last2 <= 19: return f5
    if last1 == 1: return f1
    if 2 <= last1 <= 4: return f2
    return f5

def _decline_uk(n: int, f1: str, f2: str, f5: str) -> str:
    last2, last1 = abs(n) % 100, abs(n) % 10
    if 11 <= last2 <= 19: return f5
    if last1 == 1: return f1
    if 2 <= last1 <= 4: return f2
    return f5

def _fmt_km(n: int) -> str:
    return _r(
        [f"{n} {_decline_ru(n, 'килом+етр', 'килом+етра', 'килом+етров')}"],
        [f"{n} {_decline_uk(n, 'кілом+етр', 'кілом+етри', 'кілом+етрів')}"],
    )

def _fmt_min(n: int) -> str:
    return _r(
        [f"{n} {_decline_ru(n, 'мин+уту', 'мин+уты', 'мин+ут')}"],
        [f"{n} {_decline_uk(n, 'хвил+ину', 'хвил+ини', 'хвил+ин')}"],
    )

def _fmt_euro(n: int) -> str:
    try:
        from num2words import num2words
        try:
            from core.i18n import get_speech_language
            lang = get_speech_language()
        except Exception:
            lang = 'ru'
        words = num2words(n, lang='uk' if lang == 'uk' else 'ru')
        return f"{words} {'євро' if lang == 'uk' else 'евро'}"
    except Exception:
        return _r([f"{n} евро"], [f"{n} євро"])

def _fmt_xp(n: int) -> str:
    return _r(
        [f"{n} {_decline_ru(n, 'очко опыта', 'очка опыта', 'очков опыта')}"],
        [f"{n} {_decline_uk(n, 'очко досвіду', 'очки досвіду', 'очок досвіду')}"],
    )

def _transliterate_city(name: str) -> str:
    """Pass city name through as-is — TTS normalizer handles G2P for Latin names."""
    return name

def _resolve_addr(text: str) -> str:
    try:
        from core.address import get_address
        addr = get_address()
        text = re.sub(r'\bсэр\b', addr, text, flags=re.IGNORECASE)
        text = re.sub(r'\bсер\b', addr, text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text

def _addr() -> str:
    """Return the configured address form (e.g. 'сэр', 'командир', 'шеф')."""
    try:
        from core.address import get_address
        return get_address()
    except Exception:
        return 'сэр'

_WEAR_NAMES_UK = {
    "двигатель":       "двигун",
    "коробка передач": "коробка передач",
    "шасси":           "шасі",
    "кабина":          "кабіна",
    "колёса":          "колеса",
}

_WEAR_NAMES_RU_STRESSED = {
    "двигатель":       "дв+игатель",
    "коробка передач": "кор+обка перед+ач",
    "шасси":           "шасс+и",
    "кабина":          "каб+ина",
    "колёса":          "кол+ёса",
}

_WEAR_NAMES_UK_STRESSED = {
    "двигатель":       "двиг+ун",
    "коробка передач": "кор+обка перед+ач",
    "шасси":           "шас+і",
    "кабина":          "каб+іна",
    "колёса":          "кол+еса",
}

def _r(ru: list, uk: list | None = None) -> str:
    """Pick a phrase for the active UI language, without repeating the same
    one until every other option in that specific list has come up (see
    core.responses.pick_response) — plain random.choice() on a short list
    can otherwise pick the same line 2-3 times in a row."""
    from core.responses import pick_response
    try:
        from core.i18n import get_speech_language
        if get_speech_language() == 'uk' and uk:
            return pick_response(tuple(uk), uk)
    except Exception:
        pass
    return pick_response(tuple(ru), ru)

def _pct_str(pct_float: float) -> str:
    """Format a float percentage for TTS without decimals (RU/UK aware)."""
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'

    if pct_float < 1.0:
        return _r(["м+енее одн+ого проц+ента"], ["м+енше одн+ого відс+отка"])
    n = int(round(pct_float))
    last2, last1 = n % 100, n % 10
    if lang == 'uk':
        if 11 <= last2 <= 19:   suffix = "відс+отків"
        elif last1 == 1:         suffix = "відс+оток"
        elif 2 <= last1 <= 4:   suffix = "відс+отки"
        else:                    suffix = "відс+отків"
    else:
        if 11 <= last2 <= 19:   suffix = "проц+ентов"
        elif last1 == 1:         suffix = "проц+ент"
        elif 2 <= last1 <= 4:   suffix = "проц+ента"
        else:                    suffix = "проц+ентов"
    return f"{n} {suffix}"

def _fuel_phrase(km: float) -> str:
    km_int = int(round(km))
    if km_int <= 15:
        return _r(
            ["Т+опливо на исх+оде. Ср+очно найд+ите запр+авку."],
            ["П+аливо закінч+ується. Терм+іново знайд+іть запр+авку."]
        )
    if km_int <= 30:
        return _r(
            [f"Крит+ический +уровень т+оплива. До пуст+ого б+ака {km_int} килом+етров."],
            [f"Крит+ичний р+івень п+алива. До пор+ожнього б+аку {km_int} кілом+етрів."]
        )
    if km_int <= 50:
        return _r(
            [f"Вним+ание, зап+ас х+ода {km_int} килом+етров."],
            [f"Ув+ага, зап+ас х+оду {km_int} кілом+етрів."]
        )
    if km_int <= 100:
        return _r(
            [f"Сэр, рекоменд+ую запр+авиться. Зап+ас х+ода {km_int} килом+етров."],
            [f"Сер, рекоменд+ую запр+авитись. Зап+ас х+оду {km_int} кілом+етрів."]
        )
    if km_int <= 200:
        return _r(
            [f"Сэр, гор+ючего хват+ит ещ+ё на {km_int} килом+етров."],
            [f"Сер, п+ального вистачить ще на {km_int} кілом+етрів."]
        )
    return _r(
        [f"Сэр, зап+ас х+ода — {km_int} килом+етров."],
        [f"Сер, зап+ас х+оду — {km_int} кілом+етрів."]
    )

