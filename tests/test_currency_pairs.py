import pytest

from actions import currency_pairs as cp


@pytest.fixture
def home(monkeypatch):
    """Home currency and market feed under test control."""
    state = {'base': 'UAH', 'rates': {}}
    monkeypatch.setattr(cp, 'get_base', lambda: state['base'])
    monkeypatch.setattr(cp, '_market_rate', lambda t, b: state['rates'].get((t, b)))
    monkeypatch.setattr(cp, '_btc_usd', lambda: 100000.0)
    monkeypatch.setattr(cp, '_spoken', {})
    import core.i18n as i18n
    monkeypatch.setattr(i18n, 'get_speech_language', lambda: 'ru')
    return state


@pytest.mark.parametrize('text, expected', [
    ('курс юаня', ['CNY']),
    ('курс юаня к лире', ['CNY', 'TRY']),
    ('сколько стоит доллар в тенге', ['USD', 'KZT']),
    ('какой курс евро', ['EUR']),
    ('курс гривен в лирах', ['UAH', 'TRY']),
    ('курс иены', ['JPY']),
    ('курс европы', []),                 # "евро" is matched as a whole word only
    ('курс лирики', []),                 # a stem is not a prefix of any longer word
    ('скільки коштує долар', ['USD']),
    ('курс биткоина', ['BTC']),
])
def test_mentioned(text, expected):
    assert cp.mentioned(text) == expected


def test_resolve_uses_home_currency_and_avoids_same_pair(home):
    home['base'] = 'TRY'
    assert cp.resolve('курс юаня') == ('CNY', 'TRY')
    assert cp.resolve('курс юаня к рублю') == ('CNY', 'RUB')
    assert cp.resolve('какой курс') == ('USD', 'TRY')           # nothing named: dollar in the home currency
    assert cp.resolve('курс лиры') == ('TRY', 'USD')            # the home currency itself is priced in dollars
    home['base'] = 'USD'
    assert cp.resolve('курс доллара') == ('USD', 'EUR')
    assert cp.resolve('курс биткоина') == ('BTC', 'USD')


def test_spoken_rate_in_home_currency(home):
    home['rates'][('CNY', 'TRY')] = 5.6
    ok, text, url = cp.get_rate_pair('CNY', 'TRY')
    assert ok and text == 'Сэр, курс юаня к лире сегодня — пять лир шестьдесят курушей.'
    assert url.endswith('1+cny+to+try')


def test_weak_currency_is_priced_per_hundred(home):
    home['rates'][('JPY', 'UAH')] = 0.2755
    ok, text, _ = cp.get_rate_pair('JPY', 'UAH')
    assert ok and text == 'Сэр, сто иен сегодня стоят — двадцать семь гривен пятьдесят пять копеек.'


def test_base_without_fraction(home):
    home['rates'][('USD', 'JPY')] = 151.4
    ok, text, _ = cp.get_rate_pair('USD', 'JPY')
    assert ok and text == 'Сэр, курс доллара к иене сегодня — сто пятьдесят одна иена.'


def test_rounding_carries_into_whole_units(home):
    home['rates'][('USD', 'UAH')] = 41.996
    assert cp.get_rate_pair('USD', 'UAH')[1] == 'Сэр, курс доллара к гривне сегодня — сорок две гривны.'


def test_bitcoin_in_home_currency(home):
    home['base'] = 'UAH'
    home['rates'][('USD', 'UAH')] = 40.0
    ok, text, _ = cp.get_rate_pair('BTC', 'UAH')
    assert ok and text.startswith('Сэр, биткоин сегодня стоит — четыре миллиона гривен')


def test_feed_failure_is_reported(home):
    ok, text, _ = cp.get_rate_pair('CNY', 'TRY')
    assert not ok and 'Не удалось' in text
    assert cp.get_rate_pair('XXX', 'TRY')[0] is False


def test_ukrainian_phrasing(home, monkeypatch):
    import core.i18n as i18n
    monkeypatch.setattr(i18n, 'get_speech_language', lambda: 'uk')
    home['rates'][('USD', 'UAH')] = 41.5
    assert cp.get_rate_pair('USD', 'UAH')[1] == 'Курс долара до гривні сьогодні — сорок одна гривня п\'ятдесят копійок.'


def test_base_setting_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"x": 1}', encoding='utf-8')
    import core.settings_io as sio
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    assert cp.get_base() == 'UAH'
    assert cp.set_base('try') is True and cp.get_base() == 'TRY'
    assert cp.set_base('xxx') is False and cp.get_base() == 'TRY'
    import json
    assert json.loads(path.read_text(encoding='utf-8')) == {'x': 1, 'currency_base': 'TRY'}


def test_recognizer_routes_currency_questions():
    from core.engine.recognition import _CURRENCY_RE
    assert _CURRENCY_RE.search('курс юаня к лире') and _CURRENCY_RE.search('сколько стоит доллар')
    assert not _CURRENCY_RE.search('курс лекций по математике')


@pytest.mark.parametrize('text, expected', [
    ('курс канадского доллара', ['CAD']),
    ('курс датской кроны к шведской кроне', ['DKK', 'SEK']),
    ('курс крон', ['CZK']),
    ('сколько стоит рупия', ['INR']),
    ('курс белорусского рубля', ['BYN']),
    ('курс молдавского лея', ['MDL']),
    ('курс лея', ['RON']),
    ('курс бата', ['THB']),
    ('курс батона', []),
    ('курс шекеля в гривнах', ['ILS', 'UAH']),
    ('курс вони', ['KRW']),
])
def test_more_currencies(text, expected):
    assert cp.mentioned(text) == expected


def test_every_currency_can_be_spoken_both_ways(home, monkeypatch):
    """Data integrity: each code works as target and as home currency in both languages (no missing form, no crash)."""
    import core.i18n as i18n
    for lang in ('ru', 'uk'):
        monkeypatch.setattr(i18n, 'get_speech_language', lambda l=lang: l)
        for code in cp._CUR:
            home['rates'][(code, 'UAH')] = 12.34
            home['rates'][('USD', code)] = 12.34
            ok, text, _ = cp.get_rate_pair(code, 'UAH') if code != 'UAH' else cp.get_rate_pair('USD', 'UAH')
            assert ok and text.endswith('.') and '  ' not in text, (lang, code, text)
            ok, text, _ = cp.get_rate_pair('USD', code)
            assert ok and '  ' not in text, (lang, code, text)
            assert len(cp._CUR[code]) == 11 and cp._CUR[code][0] and cp._CUR[code][1]


def test_watch_list_setting(tmp_path, monkeypatch):
    path = tmp_path / 's.json'
    import core.settings_io as sio
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    assert cp.get_watch() == ['USD', 'EUR']                         # default before anything is saved
    assert cp.set_watch(['cny', 'TRY', 'xxx', 'CNY', 'btc']) is True
    assert cp.get_watch() == ['CNY', 'TRY', 'BTC']
    assert cp.set_watch([]) is True and cp.get_watch() == []
    assert len(cp.clean_watch(list(cp._CUR) * 2)) == cp.MAX_WATCH


def test_my_rates_phrase_reads_the_watch_list(home, monkeypatch):
    monkeypatch.setattr(cp, 'get_watch', lambda: ['USD', 'CNY', 'UAH', 'JPY'])
    home['rates'].update({('USD', 'UAH'): 41.5, ('CNY', 'UAH'): 5.8, ('JPY', 'UAH'): 0.27})
    assert cp.resolve('мои курсы') == (cp.WATCH, 'UAH') and cp.resolve('курсы валют') == (cp.WATCH, 'UAH')
    assert cp.resolve('курсы английского') == ('USD', 'UAH')       # plain "courses" is not a currency question
    ok, text, _ = cp.get_watch_summary('UAH')
    assert ok and text == ('Сэр, курсы к гривне: доллар — сорок одна гривна пятьдесят копеек; юань — пять гривен восемьдесят копеек; '
                           'сто иен — двадцать семь гривен.')


def test_empty_watch_list(home, monkeypatch):
    monkeypatch.setattr(cp, 'get_watch', lambda: [])
    ok, text, _ = cp.get_watch_summary('UAH')
    assert not ok and 'пуст' in text
