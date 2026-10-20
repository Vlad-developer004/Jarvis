"""Spoken-form text normalization for core.speech.tts: numbers, dates, units, stress marks and address forms (moved out of tts.py unchanged)."""

from collections import OrderedDict
import re
import threading
from core.speech.tts_markup import (_ABBREV, _CYR_ABBREV, _CYR_LETTERS, _EXCEPTIONS, _LETTER_NAMES, _PHONETIC_DRIVES, _UNIT_EXPANSIONS, _g2p_word, _protect_ssml_tags, _restore_ssml_tags, _reverse_translit_cyrillic)

_morph_ru = None

_morph_uk = None

_morph_lock = threading.Lock()

_normalize_cache: 'OrderedDict[tuple[str, str], str]' = OrderedDict()

_NORMALIZE_CACHE_MAX = 512

_normalize_cache_lock = threading.Lock()

def _get_morph(lang: str = 'ru'):
    global _morph_ru, _morph_uk
    try:
        import pymorphy3 as _pm3
        if lang == 'uk':
            if _morph_uk is None:
                with _morph_lock:
                    if _morph_uk is None:
                        _morph_uk = _pm3.MorphAnalyzer(lang='uk')
            return _morph_uk
        else:
            if _morph_ru is None:
                with _morph_lock:
                    if _morph_ru is None:
                        _morph_ru = _pm3.MorphAnalyzer()
            return _morph_ru
    except Exception:
        return None

def _get_lang() -> str:
    # Voice/model language — deliberately get_speech_language(), not
    # get_language() (on-screen UI text). See core.i18n.get_speech_language.
    try:
        from core.i18n import get_speech_language
        return get_speech_language()
    except Exception:
        return 'ru'

# ---------------------------------------------------------------------------
# Stress-mark dictionary for Silero v5.
# Format: 'word_lowercase' → 'wо+rd'  where + precedes the stressed vowel.
# Applied case-insensitively; original capitalisation is preserved.
# Add any proper noun or word the model mis-stresses here.
# ---------------------------------------------------------------------------
_STRESS_MAP: dict[str, str] = {
    # Assistant name — stress on А (ДжА́рвис, not ДжарвИ́с)
    'джарвис':  'Дж+арвис',
    'джарвіс':  'Дж+арвіс',
    # Common words that Silero v5 sometimes mis-stresses
    'интерфейс':    'интерф+ейс',
    'центр':        'ц+ентр',
    'включить':     'включ+ить',
    'включи':       'включ+и',
    'включите':     'включ+ите',
    'открыть':      'откр+ыть',
    'открой':       'откр+ой',
    'закрой':       'закр+ой',
    'закрыть':      'закр+ыть',
    'запусти':      'запуст+и',
    'запустить':    'запуст+ить',
    'перезапусти':  'перезапуст+и',
    'выключи':      'выключ+и',
    'выключить':    'выключ+ить',
    'скачать':      'скач+ать',
    'скачай':       'скач+ай',
    'найди':        'найд+и',
    'поищи':        'поищ+и',
    'покажи':       'покаж+и',
    'сорок':        'с+орок',
    'сорока':       'сорок+а',
    # Ukrainian
    'джарвіс':      'Дж+арвіс',
    'інтерфейс':    'інтерф+ейс',
    'увімкни':      'увімкн+и',
    'увімкнути':    'увімкн+ути',
    'вимкни':       'вимкн+и',
    'вимкнути':     'вимкн+ути',
    'відкрий':      'відкр+ий',
    'відкрити':     'відкр+ити',
    'закрий':       'закр+ий',
    'закрити':      'закр+ити',
    'запустити':    'запуст+ити',
    'знайди':       'знайд+и',
    'покажи':       'покаж+и',
    'скачати':      'скач+ати',
}

# Precompile pattern — whole-word, case-insensitive
_STRESS_PAT = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _STRESS_MAP) + r')\b',
    re.IGNORECASE,
)

# Nouns whose dictionary genitive-plural is a regular/suppletive form that
# sounds wrong specifically in the after-a-cardinal counting context, where
# Russian keeps an older invariant form instead ("сто человек", not "сто
# людей"). Keyed by nominative singular as typed; see _fix_noun.
_COUNTING_NOUN_EXCEPTIONS = {
    'человек': 'человек',
}

def _apply_stress(text: str) -> str:
    """Replace known mis-stressed words with stress-marked variants."""
    def _repl(m: re.Match) -> str:
        word = m.group(0)
        key  = word.lower()
        replacement = _STRESS_MAP.get(key, word)
        # Preserve original capitalisation (first letter)
        if word[0].isupper() and not replacement[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        return replacement
    return _STRESS_PAT.sub(_repl, text)

_normalize_nlp_deps = None

def _get_normalize_nlp_deps():
    """Lazily import+cache the (get_russian_plural, num2words) pair used by
    several pipeline steps — done once, not on every normalize_for_tts() call."""
    global _normalize_nlp_deps
    if _normalize_nlp_deps is None:
        from core.nlp import get_russian_plural
        from num2words import num2words
        _normalize_nlp_deps = (get_russian_plural, num2words)
    return _normalize_nlp_deps

_CASE_TAG = {'gen': 'gent', 'prep': 'loct', 'nom': 'nomn', 'dat': 'datv', 'acc': 'accs'}

def _inflect_last(morph, phrase: str, tags: set, prefer_pos: tuple = ('ADJF',)) -> str:
    """Inflect the last word of a phrase to given morphological tags.

    prefer_pos restricts the first pass to parses of that part of speech.
    This matters because pymorphy3 returns every homonym reading for a
    spelling, sorted by corpus frequency, not by which reading actually
    fits here — e.g. "сто" also parses as an indeclinable abbreviation noun
    (score-tied with its real NUMR reading), and that noun reading
    "successfully" inflects to itself unchanged, so an unfiltered first
    pass silently returns "сто" instead of the genitive "ста". Ordinal
    callers want ADJF ("пятый" is grammatically an adjective);
    _expand_standalone_numbers passes prefer_pos=('NUMR',) for cardinals.
    """
    if morph is None: return phrase
    words = phrase.strip().split()
    if not words: return phrase
    last = words[-1]
    parses = morph.parse(last)
    # Build fallback tag sets: try most-specific first, then relax constraints
    tag_variants = []
    for drop in (set(), {'sing'}, {'masc', 'femn', 'neut'}, {'masc', 'femn', 'neut', 'sing'}):
        t = tags - drop
        if t and t not in tag_variants:
            tag_variants.append(t)
    for strict in (True, False):
        for p in parses:
            if strict and p.tag.POS not in prefer_pos:
                continue
            for tv in tag_variants:
                infl = p.inflect(tv)
                if infl:
                    return (' '.join(words[:-1]) + ' ' + infl.word).strip()
    return phrase

def _ordinal_case(morph, nw_lang: str, phrase: str, case: str, gender: str = 'masc') -> str:
    """Inflect ordinal phrase to requested case and gender."""
    if case == 'nom': return phrase
    ct = _CASE_TAG.get(case, 'gent')
    # Ukrainian loct: prefer dative form — same meaning, more common than archaic '-ім'
    if nw_lang == 'uk' and ct == 'loct':
        r = _inflect_last(morph, phrase, {'datv', gender, 'sing'})
        if r != phrase: return r
    return _inflect_last(morph, phrase, {ct, gender, 'sing'})

def _expand_drive_letters(text: str) -> str:
    return re.sub(
        r'\b([A-Za-z]):\\',
        lambda m: f'диск {_PHONETIC_DRIVES.get(m.group(1).upper(), m.group(1).upper())} ',
        text)

def _expand_units_and_currency(text: str, lang: str) -> str:
    km_word = 'кілометрів' if lang == 'uk' else 'километров'
    gb_word = 'гігабайт' if lang == 'uk' else 'гигабайт'
    kb_word = 'кілобайт' if lang == 'uk' else 'килобайт'
    all_units = {**_UNIT_EXPANSIONS, 'км': km_word, 'гб': gb_word, 'мб': 'мегабайт', 'кб': kb_word}
    text = re.sub(
        r'\b(ГБ|МБ|КБ|км/ч|км/час|кг|см|мм|км)\b',
        lambda m: all_units.get(m.group(0).lower(), m.group(0)),
        text, flags=re.IGNORECASE)
    return text.replace('€', 'євро' if lang == 'uk' else 'евро')

def _expand_minus_sign(text: str, nw_lang: str) -> str:
    # -5 → минус 5 (before any number conversion)
    minus = 'мінус ' if nw_lang == 'uk' else 'минус '
    return re.sub(r'(?<!\d)(?<!\w)-(\d)', lambda m: minus + m.group(1), text)

def _expand_degrees(text: str, nw_lang: str) -> str:
    # 20°C, -5°, 20° → spoken form with proper pluralization
    minus = 'мінус ' if nw_lang == 'uk' else 'минус '

    def _degree_repl(m: re.Match) -> str:
        n = int(m.group(1))
        abs_n = abs(n)
        sign = minus if n < 0 else ''
        last2, last1 = abs_n % 100, abs_n % 10
        if 11 <= last2 <= 19:   form = 'градусів' if nw_lang == 'uk' else 'градусов'
        elif last1 == 1:         form = 'градус'
        elif 2 <= last1 <= 4:   form = 'градуси' if nw_lang == 'uk' else 'градуса'
        else:                    form = 'градусів' if nw_lang == 'uk' else 'градусов'
        return f"{sign}{abs_n} {form}"
    return re.sub(r'(-?\d+)\s*°[CcFfСс]?', _degree_repl, text)

def _expand_percentages(text: str, lang: str, num2words, get_russian_plural) -> str:
    def _uk_pct_word(n: int) -> str:
        last2, last1 = n % 100, n % 10
        if 11 <= last2 <= 19: return 'відсотків'
        if last1 == 1: return 'відсоток'
        if 2 <= last1 <= 4: return 'відсотки'
        return 'відсотків'
    if lang == 'uk':
        return re.sub(
            r'(\d+)\s*%',
            lambda m: f"{num2words(int(m.group(1)), lang='uk')} {_uk_pct_word(int(m.group(1)))}",
            text)
    return re.sub(
        r'(\d+)\s*%',
        lambda m: f"{num2words(int(m.group(1)), lang='ru')} {get_russian_plural(int(m.group(1)), ['процент', 'процента', 'процентов'])}",
        text)

_RATIO_PREP = {'ru': 'из', 'uk': 'із'}

def _expand_fractions(text: str, nw_lang: str, morph, num2words) -> str:
    # "10/10" (a rating/score) read as bare digits was coming out as
    # "десять десять" — no separator — because _expand_standalone_numbers
    # matches each side of the "/" independently. Say it as "N из M"
    # (genitive on M) instead, before the standalone-number pass ever sees
    # the digits.
    def _ratio(m: re.Match) -> str:
        word_a = num2words(int(m.group(1)), lang=nw_lang)
        word_b = num2words(int(m.group(2)), lang=nw_lang)
        if morph is not None:
            infl = _inflect_last(morph, word_b, {'gent'}, prefer_pos=('NUMR',))
            if infl != word_b:
                word_b = infl
        return f'{word_a} {_RATIO_PREP[nw_lang]} {word_b}'
    return re.sub(r'(?<!\w)(\d+)\s*/\s*(\d+)(?!\w)', _ratio, text)

def _expand_years(text: str, lang: str, nw_lang: str, morph, num2words) -> str:
    if lang == 'uk':
        # Ukrainian: рік (nom), року (gen/date), році (prep), -го, -му, -й
        def _year_uk(m: re.Match) -> str:
            try:
                y = int(m.group('year'))
                suf = (m.group('suf') or '').strip().rstrip('.').lower()
                ordy = num2words(y, lang='uk', to='ordinal')
                if suf in ('року', 'р'):    return _ordinal_case(morph, nw_lang, ordy, 'gen') + ' року'
                if suf == 'році':           return _ordinal_case(morph, nw_lang, ordy, 'prep') + ' році'
                if suf in ('рік', 'р.'):    return ordy + ' рік'
                if suf == '-го':            return _ordinal_case(morph, nw_lang, ordy, 'gen')
                if suf in ('-му', '-м'):    return _ordinal_case(morph, nw_lang, ordy, 'prep')
                return num2words(y, lang='uk')
            except Exception: return m.group(0)
        text = re.sub(
            r'\b(?P<year>19\d{2}|20\d{2})\s*(?P<suf>року|році|рік|р\.|р\b|-го|-му|-м\b)',
            _year_uk, text, flags=re.IGNORECASE)
        # Standalone years in Ukrainian year range "2020-2023" → cardinal both
        return re.sub(
            r'\b(19\d{2}|20\d{2})\s*[-–]\s*(19\d{2}|20\d{2})\b',
            lambda m: f"{num2words(int(m.group(1)), lang='uk')} — {num2words(int(m.group(2)), lang='uk')}",
            text)

    # Russian: год (nom), года (gen), году (prep), -го, -м, -й
    def _year_ru(m: re.Match) -> str:
        try:
            y = int(m.group('year'))
            suf = (m.group('suf') or '').strip().rstrip('.').lower()
            ordy = num2words(y, lang='ru', to='ordinal')
            if suf == 'года':           return _ordinal_case(morph, nw_lang, ordy, 'gen') + ' года'
            if suf == 'году':           return _ordinal_case(morph, nw_lang, ordy, 'prep') + ' году'
            if suf in ('год', 'г'):     return ordy + ' год'
            if suf in ('-го', 'го'):    return _ordinal_case(morph, nw_lang, ordy, 'gen')
            if suf in ('-м', 'м', '-й'): return _ordinal_case(morph, nw_lang, ordy, 'prep')
            return num2words(y, lang='ru')
        except Exception: return m.group(0)
    text = re.sub(
        r'\b(?P<year>19\d{2}|20\d{2})\s*(?P<suf>года\b|году\b|год\b|г\.|г\b|-го\b|(?<!\w)го\b|-м\b|-й\b)',
        _year_ru, text, flags=re.IGNORECASE)
    # Year range "2020-2023"
    return re.sub(
        r'\b(19\d{2}|20\d{2})\s*[-–]\s*(19\d{2}|20\d{2})\b',
        lambda m: f"{num2words(int(m.group(1)), lang='ru')} — {num2words(int(m.group(2)), lang='ru')}",
        text)

def _expand_dates(text: str, lang: str, nw_lang: str, morph, num2words) -> str:
    # Day + month, e.g. "5 марта" → "пятого марта"
    if lang == 'uk':
        return re.sub(
            r'\b(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\b',
            lambda m: _ordinal_case(morph, nw_lang, num2words(int(m.group(1)), lang='uk', to='ordinal'), 'gen') + ' ' + m.group(2),
            text, flags=re.IGNORECASE)
    return re.sub(
        r'\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b',
        lambda m: _ordinal_case(morph, nw_lang, num2words(int(m.group(1)), lang='ru', to='ordinal'), 'gen') + ' ' + m.group(2),
        text, flags=re.IGNORECASE)

def _expand_ordinal_shorthand(text: str, nw_lang: str, morph, num2words) -> str:
    # 1-й, 2-й, 3-го, 2-му etc. Optional capture of following Cyrillic word
    # for gender/case agreement.
    def _ordinal_short(m: re.Match) -> str:
        try:
            n = int(m.group(1))
            suf = m.group(2).lower().lstrip('-')
            following_ws = m.group(3) or ''
            following = following_ws.strip()
            ordy = num2words(n, lang=nw_lang, to='ordinal')
            if suf in ('го', 'ого', 'його', 'его'):
                return _ordinal_case(morph, nw_lang, ordy, 'gen') + following_ws
            if suf in ('м', 'ом', 'ем', 'му', 'ому'):
                return _ordinal_case(morph, nw_lang, ordy, 'prep') + following_ws
            # Ambiguous suffix (-й/-ій/-я/-е/-є): agree with following noun
            if following and morph is not None:
                parses = morph.parse(following.lower())
                if parses:
                    cmap = {'nomn': 'nom', 'gent': 'gen', 'datv': 'dat',
                            'accs': 'acc', 'ablt': 'prep', 'loct': 'prep'}
                    # Prefer loct > datv > gent > ablt over nomn/accs (ordinals
                    # before nouns are usually in oblique context, not nom-plural)
                    oblique_pref = ('loct', 'datv', 'gent', 'ablt')
                    best = next(
                        (p for pref in oblique_pref
                         for p in parses if str(p.tag.case) == pref),
                        parses[0]
                    )
                    gender = str(best.tag.gender) if best.tag.gender else 'masc'
                    case = cmap.get(str(best.tag.case) if best.tag.case else 'nomn', 'nom')
                    return _ordinal_case(morph, nw_lang, ordy, case, gender) + following_ws
            return ordy + following_ws
        except Exception:
            return m.group(0)
    return re.sub(
        r'\b(\d+)(-?(?:й|ій|я|є|е|го|ого|його|его|му|ому|м|ом|ем))(\s+[А-Яа-яЁёІіЇїЄє]+)?',
        _ordinal_short, text, flags=re.IGNORECASE)

def _expand_year_ranges_with_prep(text: str, nw_lang: str, morph, num2words) -> str:
    # "с 1939 по 1945" / "від 1939 до 1945" — no digit suffix to key off, so
    # this runs separately from _expand_years, keyed on the governing prepositions.
    prep_start = r'(?:с|от|із|з|від|за)\s+'
    prep_end = r'\s+(?:по|до|—|-)\s+'

    def _year_range_repl(m: re.Match) -> str:
        try:
            y = int(m.group('ry'))
            return m.group('pre') + _ordinal_case(morph, nw_lang, num2words(y, lang=nw_lang, to='ordinal'), 'gen') + m.group('sep')
        except Exception: return m.group(0)
    return re.sub(
        r'(?P<pre>' + prep_start + r')(?P<ry>19\d{2}|20\d{2})(?P<sep>' + prep_end + r')',
        _year_range_repl, text, flags=re.IGNORECASE)

def _fix_number_noun_agreement(text: str, nw_lang: str, morph) -> str:
    # "5 метр" → "5 метров" etc.
    if morph is None:
        return text

    def _fix_noun(m: re.Match) -> str:
        try:
            n = int(m.group(1))
            noun = m.group(2)
            parses = morph.parse(noun.lower())
            noun_p = next((p for p in parses if 'NOUN' in str(p.tag)), None)
            if noun_p is None: return m.group(0)
            abs_n = abs(n)
            last2, last1 = abs_n % 100, abs_n % 10
            if 11 <= last2 <= 19:   req = ('gent', 'plur')
            elif last1 == 1:         req = ('nomn', 'sing')
            elif 2 <= last1 <= 4:   req = ('gent', 'sing')
            else:                    req = ('gent', 'plur')
            cur_case = str(noun_p.tag.case) if noun_p.tag.case else ''
            cur_num = str(noun_p.tag.number) if noun_p.tag.number else ''
            if cur_case == req[0] and cur_num == req[1]:
                return m.group(0)  # already correct
            # pymorphy3's dictionary genitive-plural for these nouns is the
            # regular declined form ("человек" -> "людей"), but after a
            # cardinal number Russian keeps the invariant counting form
            # ("сто человек", never "сто людей") — a lexical exception,
            # not something the inflector can derive from tags alone.
            if nw_lang == 'ru' and req == ('gent', 'plur'):
                exc = _COUNTING_NOUN_EXCEPTIONS.get(noun.lower())
                if exc:
                    return m.group(1) + ' ' + exc
            infl = noun_p.inflect({req[0], req[1]})
            if infl:
                return m.group(1) + ' ' + infl.word
        except Exception:
            pass
        return m.group(0)
    return re.sub(r'\b(\d+)\s+([А-Яа-яЁёІіЇїЄє]{3,})\b', _fix_noun, text)

def _expand_abbreviations_and_latin(text: str) -> str:
    text = re.sub(
        r'(?<![А-ЯЁа-яёa-zA-Z])[А-ЯЁ]{2,6}(?![А-ЯЁа-яёa-zA-Z])',
        lambda m: _CYR_ABBREV.get(m.group(0), ' '.join(_CYR_LETTERS.get(c, c) for c in m.group(0))),
        text)
    return re.sub(r"[a-zA-Z]+(?:['-][a-zA-Z]+)*", _transliterate_word, text)

_GEN_GOV_PREPS = {
    'ru': ('до', 'от', 'с', 'около', 'свыше', 'выше', 'ниже'),
    'uk': ('до', 'від', 'з', 'близько', 'понад', 'вище', 'нижче'),
}

def _expand_standalone_numbers(text: str, nw_lang: str, morph, num2words) -> str:
    # Remaining standalone numbers, with genitive agreement after
    # case-governing prepositions ("до 19 градусов" → "до девятнадцати
    # градусов", not the bare nominative "до девятнадцать").
    def _standalone_number(m: re.Match) -> str:
        word = num2words(int(m.group('num')), lang=nw_lang)
        prep = (m.group('prep') or '').lower()
        if morph is not None and prep in _GEN_GOV_PREPS.get(nw_lang, ()):
            infl = _inflect_last(morph, word, {'gent'}, prefer_pos=('NUMR',))
            if infl != word:
                word = infl
        return (m.group('prep') + ' ' if m.group('prep') else '') + word
    preps_alt = '|'.join(_GEN_GOV_PREPS.get(nw_lang, ()))
    return re.sub(
        rf'(?:\b(?P<prep>{preps_alt})\s+)?(?<!\w)(?P<num>\d+)(?!\w)',
        _standalone_number, text, flags=re.IGNORECASE)

def _apply_address_form(text: str) -> str:
    # Replace hardcoded "сэр"/"сер" with the user-configured address form,
    # then add a comma after it (Сэр/Джарвис/Леди/custom) for TTS prosody.
    # Both steps need the same configured value, fetched once.
    try:
        from core.address import get_address
        addr_value = get_address()
        if addr_value.lower() not in ('сэр', 'сер'):
            text = re.sub(r'\bсэр\b', addr_value, text, flags=re.IGNORECASE)
            text = re.sub(r'\bсер\b', addr_value, text, flags=re.IGNORECASE)
        addr_esc = re.escape(addr_value)
        cyr = r'[а-яёА-ЯЁіїєІЇЄ]'
        text = re.sub(rf'^({addr_esc})\s+({cyr})', r'\1, \2', text, flags=re.IGNORECASE)
        text = re.sub(rf'([.!?])\s+({addr_esc})\s+({cyr})', r'\1 \2, \3', text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text

def normalize_for_tts(text: str) -> str:
    if not text:
        return ''
    lang = _get_lang()
    key = (text, lang)
    with _normalize_cache_lock:
        cached = _normalize_cache.get(key)
        if cached is not None:
            _normalize_cache.move_to_end(key)
            return cached

    text, ssml_tags = _protect_ssml_tags(text)
    # Convert phrase pause markers to sentence boundaries so Silero pauses naturally
    text = re.sub(r'\s+\.\.\.\s+', '. ', text)

    get_russian_plural, num2words = _get_normalize_nlp_deps()
    nw_lang = 'uk' if lang == 'uk' else 'ru'
    morph = _get_morph(nw_lang)

    text = _expand_drive_letters(text)
    text = _expand_units_and_currency(text, lang)
    text = _expand_minus_sign(text, nw_lang)
    text = _expand_degrees(text, nw_lang)
    text = _expand_percentages(text, lang, num2words, get_russian_plural)
    text = _expand_years(text, lang, nw_lang, morph, num2words)
    text = _expand_dates(text, lang, nw_lang, morph, num2words)
    text = _expand_ordinal_shorthand(text, nw_lang, morph, num2words)
    text = _expand_year_ranges_with_prep(text, nw_lang, morph, num2words)
    text = _fix_number_noun_agreement(text, nw_lang, morph)
    text = _expand_abbreviations_and_latin(text)
    text = _expand_fractions(text, nw_lang, morph, num2words)
    text = _expand_standalone_numbers(text, nw_lang, morph, num2words)
    # Runs after number expansion (not before, as originally), so dictionary
    # entries for number-words themselves (e.g. "сорок") actually match —
    # num2words only produces that Cyrillic text on this line, and matching
    # it before expansion was a no-op since the source text still held "40".
    text = _apply_stress(text)
    text = _apply_address_form(text)

    if ssml_tags:
        text = _restore_ssml_tags(text, ssml_tags)
    result = text.strip()
    with _normalize_cache_lock:
        _normalize_cache[key] = result
        _normalize_cache.move_to_end(key)
        while len(_normalize_cache) > _NORMALIZE_CACHE_MAX:
            _normalize_cache.popitem(last=False)  # evict oldest, not everything
    return result

def _transliterate_word(m: re.Match) -> str:
    word = m.group(0); lower = word.lower()
    if lower in _EXCEPTIONS:
        val = _EXCEPTIONS[lower]
        return val.capitalize() if word[0].isupper() and (not word.isupper()) else val
    if word.isupper():
        if lower in _ABBREV: return _ABBREV[lower]
        if len(word) <= 6: return ' '.join((_LETTER_NAMES.get(c, c) for c in word))
    parts = re.sub('([a-z])([A-Z])', '\\1 \\2', word)
    parts = re.sub('([A-Z]+)([A-Z][a-z])', '\\1 \\2', parts).split()
    if len(parts) > 1:
        result = []
        for p in parts:
            pl = p.lower()
            if pl in _EXCEPTIONS: result.append(_EXCEPTIONS[pl])
            elif p.isupper() and pl in _ABBREV: result.append(_ABBREV[pl])
            elif p.isupper() and len(p) <= 4: result.append(' '.join((_LETTER_NAMES.get(c, c) for c in p)))
            else: result.append((p.islower() and _g2p_word(p)) or _reverse_translit_cyrillic(p))
        return ' '.join(result)
    # CMUdict lookup only for lowercase words — a capitalized word is almost
    # always a proper noun, and CMUdict's coverage of common Russian first
    # names (Sasha, Vladimir, Nikita...) in their ANGLICIZED pronunciation
    # would otherwise mis-read a Russian name that happens to also be a
    # CMUdict entry.
    return (word.islower() and _g2p_word(word)) or _reverse_translit_cyrillic(word)
