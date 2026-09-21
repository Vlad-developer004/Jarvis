import time
_cache: dict = {}
_CACHE_TTL = 300
def _open_url(url: str):
    import os
    os.startfile(url)
_er_cache: dict = {}
_ER_TTL = 300
def _market_rate(base: str, target: str) -> float | None:
    import requests
    now = time.time()
    cache_key = f'{base}_{target}'
    cached = _er_cache.get(cache_key)
    if cached and now - cached['ts'] < _ER_TTL:
        return cached['rate']
    url = f'https://open.er-api.com/v6/latest/{base}'
    r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
    data = r.json()
    if data.get('result') == 'success':
        rate = float(data['rates'][target])
        _er_cache[cache_key] = {'rate': rate, 'ts': now}
        return rate
    return None
def _btc_usd() -> float | None:
    import requests
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'
    r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
    return float(r.json()['bitcoin']['usd'])
# (fetch_fn, label_ru, url, is_crypto, ru_main_forms, ru_frac_forms, uk_label, uk_main_forms, uk_frac_forms)
_CURRENCIES = {
    'usd': (lambda: _market_rate('USD', 'UAH'), 'доллара к гривне', 'https://www.google.com/search?q=1+usd+to+uah', False,
            ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек'),
            'долара до гривні', ('гривня', 'гривні', 'гривень'), ('копійка', 'копійки', 'копійок')),
    'eur': (lambda: _market_rate('EUR', 'UAH'), 'евро к гривне', 'https://www.google.com/search?q=1+eur+to+uah', False,
            ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек'),
            'євро до гривні', ('гривня', 'гривні', 'гривень'), ('копійка', 'копійки', 'копійок')),
    'btc': (_btc_usd, 'биткоина в долларах', 'https://www.google.com/search?q=bitcoin+price+in+usd', True,
            ('доллар', 'доллара', 'долларов'), None,
            'біткоїна в доларах', ('долар', 'долари', 'доларів'), None),
    'gbp': (lambda: _market_rate('GBP', 'UAH'), 'фунта к гривне', 'https://www.google.com/search?q=1+gbp+to+uah', False,
            ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек'),
            'фунта до гривні', ('гривня', 'гривні', 'гривень'), ('копійка', 'копійки', 'копійок')),
    'pln': (lambda: _market_rate('PLN', 'UAH'), 'злотого к гривне', 'https://www.google.com/search?q=1+pln+to+uah', False,
            ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек'),
            'злотого до гривні', ('гривня', 'гривні', 'гривень'), ('копійка', 'копійки', 'копійок')),
}
CURRENCY_ALIASES = {
    # Russian
    'доллар': 'usd', 'долларов': 'usd', 'доллара': 'usd',
    'евро': 'eur',
    'биткоин': 'btc', 'биткоина': 'btc',
    'фунт': 'gbp', 'фунта': 'gbp',
    'злотый': 'pln', 'злотого': 'pln',
    # Ukrainian
    'долар': 'usd', 'долара': 'usd', 'долару': 'usd', 'доларів': 'usd',
    'євро': 'eur',
    'біткоїн': 'btc', 'біткоїна': 'btc', 'біткойн': 'btc', 'біткойну': 'btc',
    'фунт': 'gbp', 'фунта': 'gbp', 'фунту': 'gbp',
    'злотий': 'pln', 'злотого': 'pln',
    # Symbols / tickers
    'usd': 'usd', 'eur': 'eur', 'btc': 'btc', 'bitcoin': 'btc', 'gbp': 'gbp', 'pln': 'pln',
}
def _num_to_uk_words(n: int) -> str:
    if n == 0: return 'нуль'
    ones = ['', 'один', 'два', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять',
            'десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 'п\'ятнадцять',
            'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять']
    ones_f = ['', 'одна', 'дві', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять',
              'десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 'п\'ятнадцять',
              'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять']
    tens = ['', '', 'двадцять', 'тридцять', 'сорок', 'п\'ятдесят', 'шістдесят', 'сімдесят', 'вісімдесят', 'дев\'яносто']
    hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', 'п\'ятсот', 'шістсот', 'сімсот', 'вісімсот', 'дев\'ятсот']
    def _chunk(num, fem=False):
        parts = []
        if num >= 100: parts.append(hundreds[num // 100]); num %= 100
        if num >= 20: parts.append(tens[num // 10]); num %= 10
        if num > 0: parts.append((ones_f if fem else ones)[num])
        return ' '.join(p for p in parts if p)
    parts = []
    billions = n // 1_000_000_000; n %= 1_000_000_000
    millions = n // 1_000_000; n %= 1_000_000
    thousands = n // 1000; n %= 1000
    if billions:
        b = billions % 10
        s = 'мільярдів' if b in (0, 5, 6, 7, 8, 9) or (billions % 100 in range(11, 20)) else ('мільярд' if b == 1 else 'мільярди')
        parts.append(f'{_chunk(billions)} {s}')
    if millions:
        m = millions % 10
        s = 'мільйонів' if m in (0, 5, 6, 7, 8, 9) or (millions % 100 in range(11, 20)) else ('мільйон' if m == 1 else 'мільйони')
        parts.append(f'{_chunk(millions)} {s}')
    if thousands:
        t = thousands % 10
        s = 'тисяч' if t in (0, 5, 6, 7, 8, 9) or (thousands % 100 in range(11, 20)) else ('тисяча' if t == 1 else 'тисячі')
        parts.append(f'{_chunk(thousands, fem=True)} {s}')
    if n: parts.append(_chunk(n))
    return ' '.join(parts)

def _inflect_uk(n: int, form1: str, form2: str, form5: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19: return form5
    n %= 10
    if n == 1: return form1
    if 2 <= n <= 4: return form2
    return form5

def _num_to_ru_words(n: int) -> str:
    if n == 0:
        return 'ноль'
    ones = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
    tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
    hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
    def _chunk(num: int) -> str:
        parts = []
        if num >= 100:
            parts.append(hundreds[num // 100])
            num %= 100
        if num >= 20:
            parts.append(tens[num // 10])
            num %= 10
        if num > 0:
            parts.append(ones[num])
        return ' '.join((p for p in parts if p))
    parts = []
    billions = n // 1000000000
    n %= 1000000000
    millions = n // 1000000
    n %= 1000000
    thousands = n // 1000
    remainder = n % 1000
    if billions:
        b = billions % 10
        suffix = 'миллиардов'
        if b == 1 and billions % 100 != 11:
            suffix = 'миллиард'
        elif b in (2, 3, 4) and billions % 100 not in (12, 13, 14):
            suffix = 'миллиарда'
        parts.append(f'{_chunk(billions)} {suffix}')
    if millions:
        m = millions % 10
        suffix = 'миллионов'
        if m == 1 and millions % 100 != 11:
            suffix = 'миллион'
        elif m in (2, 3, 4) and millions % 100 not in (12, 13, 14):
            suffix = 'миллиона'
        parts.append(f'{_chunk(millions)} {suffix}')
    if thousands:
        t = thousands % 10
        chunk_t = _chunk(thousands).replace('один ', 'одна ').replace('два ', 'две ')
        if chunk_t in ('один', 'одна'):
            chunk_t = 'одна'
        elif chunk_t in ('два', 'две'):
            chunk_t = 'две'
        suffix = 'тысяч'
        if t == 1 and thousands % 100 != 11:
            suffix = 'тысяча'
        elif t in (2, 3, 4) and thousands % 100 not in (12, 13, 14):
            suffix = 'тысячи'
        parts.append(f'{chunk_t} {suffix}')
    if remainder:
        parts.append(_chunk(remainder))
    return ' '.join(parts)
def _inflect_currency(n: int, form1: str, form2: str, form5: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return form5
    n %= 10
    if n == 1:
        return form1
    if 2 <= n <= 4:
        return form2
    return form5
_CURRENCIES_UK = {
    'usd': 'долара до гривні',
    'eur': 'євро до гривні',
    'btc': 'біткоїна в доларах',
    'gbp': 'фунта до гривні',
    'pln': 'злотого до гривні',
}

def get_rate(currency_key: str) -> tuple[bool, str, str]:
    from core.i18n import get_speech_language
    lang = get_speech_language()
    key = currency_key.lower()
    if key not in _CURRENCIES:
        err = f'Невідома валюта: {currency_key}' if lang == 'uk' else f'Неизвестная валюта: {currency_key}'
        return (False, err, '')
    cached = _cache.get(f'{key}_{lang}')
    if cached and time.time() - cached['ts'] < _CACHE_TTL:
        return (True, cached['text'], cached['url'])
    row = _CURRENCIES[key]
    fetch_fn, label_ru, url, is_crypto = row[0], row[1], row[2], row[3]
    if lang == 'uk':
        label    = row[6]
        main_f   = row[7]
        frac_f   = row[8]
        num_fn   = _num_to_uk_words
        infl_fn  = _inflect_uk
    else:
        label    = label_ru
        main_f   = row[4]
        frac_f   = row[5]
        num_fn   = _num_to_ru_words
        infl_fn  = _inflect_currency
    try:
        rate = fetch_fn()
        if rate is None:
            err = f'Не вдалося отримати курс {label}.' if lang == 'uk' else f'Не удалось получить курс {label}.'
            return (False, err, url)
        if is_crypto:
            rate_int = int(round(rate))
            rate_words = num_fn(rate_int)
            unit_word = infl_fn(rate_int, *main_f)
            text = f'Курс {label} сьогодні — {rate_words} {unit_word}.' if lang == 'uk' else f'Сэр, курс {label} сегодня — {rate_words} {unit_word}.'
        else:
            whole = int(rate)
            frac = round((rate - whole) * 100)
            whole_words = num_fn(whole)
            main_unit = infl_fn(whole, *main_f)
            if frac and frac_f:
                frac_words = num_fn(frac)
                frac_unit = infl_fn(frac, *frac_f)
                text = f'Курс {label} сьогодні — {whole_words} {main_unit} {frac_words} {frac_unit}.' if lang == 'uk' else f'Сэр, курс {label} сегодня — {whole_words} {main_unit} {frac_words} {frac_unit}.'
            else:
                text = f'Курс {label} сьогодні — {whole_words} {main_unit}.' if lang == 'uk' else f'Сэр, курс {label} сегодня — {whole_words} {main_unit}.'
        _cache[f'{key}_{lang}'] = {'text': text, 'url': url, 'ts': time.time()}
        return (True, text, url)
    except Exception as e:
        err = f'Помилка при отриманні курсу {label}: {e}' if lang == 'uk' else f'Ошибка при получении курса {label}: {e}'
        return (False, err, url)
