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
    now = __import__('time').time()
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
_CURRENCIES = {'usd': (lambda: _market_rate('USD', 'UAH'), 'доллара к гривне', 'https://www.google.com/search?q=1+usd+to+uah', False, ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек')), 'eur': (lambda: _market_rate('EUR', 'UAH'), 'евро к гривне', 'https://www.google.com/search?q=1+eur+to+uah', False, ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек')), 'btc': (_btc_usd, 'биткоина в долларах', 'https://www.google.com/search?q=bitcoin+price+in+usd', True, ('доллар', 'доллара', 'долларов'), None), 'gbp': (lambda: _market_rate('GBP', 'UAH'), 'фунта к гривне', 'https://www.google.com/search?q=1+gbp+to+uah', False, ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек')), 'pln': (lambda: _market_rate('PLN', 'UAH'), 'злотого к гривне', 'https://www.google.com/search?q=1+pln+to+uah', False, ('гривна', 'гривны', 'гривен'), ('копейка', 'копейки', 'копеек'))}
CURRENCY_ALIASES = {'доллар': 'usd', 'долларов': 'usd', 'доллара': 'usd', 'долар': 'usd', 'долара': 'usd', 'usd': 'usd', 'евро': 'eur', 'eur': 'eur', 'биткоин': 'btc', 'биткоина': 'btc', 'btc': 'btc', 'bitcoin': 'btc', 'фунт': 'gbp', 'фунта': 'gbp', 'gbp': 'gbp', 'злотый': 'pln', 'злотого': 'pln', 'pln': 'pln'}
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
def get_rate(currency_key: str) -> tuple[bool, str, str]:
    key = currency_key.lower()
    if key not in _CURRENCIES:
        return (False, f'Неизвестная валюта: {currency_key}', '')
    cached = _cache.get(key)
    if cached and time.time() - cached['ts'] < _CACHE_TTL:
        return (True, cached['text'], cached['url'])
    fetch_fn, label, url, is_crypto, main_forms, frac_forms = _CURRENCIES[key]
    try:
        rate = fetch_fn()
        if rate is None:
            return (False, f'Не удалось получить курс {label}.', url)
        if is_crypto:
            rate_int = int(round(rate))
            rate_words = _num_to_ru_words(rate_int)
            unit_word = _inflect_currency(rate_int, *main_forms)
            text = f'Сэр, курс {label} сегодня — {rate_words} {unit_word}.'
        else:
            whole = int(rate)
            frac = round((rate - whole) * 100)
            whole_words = _num_to_ru_words(whole)
            main_unit = _inflect_currency(whole, *main_forms)
            if frac and frac_forms:
                frac_words = _num_to_ru_words(frac)
                frac_unit = _inflect_currency(frac, *frac_forms)
                text = f'Сэр, курс {label} сегодня — {whole_words} {main_unit} {frac_words} {frac_unit}.'
            else:
                text = f'Сэр, курс {label} сегодня — {whole_words} {main_unit}.'
        _cache[key] = {'text': text, 'url': url, 'ts': time.time()}
        return (True, text, url)
    except Exception as e:
        return (False, f'Ошибка при получении курса {label}: {e}', url)
