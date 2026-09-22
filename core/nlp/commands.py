from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
import re
WORDS_TO_NUM = {'ноль': '0', 'один': '1', 'одна': '1', 'одну': '1', 'одно': '1', 'два': '2', 'две': '2', 'три': '3', 'четыре': '4', 'пять': '5', 'шесть': '6', 'семь': '7', 'восемь': '8', 'девять': '9', 'десять': '10', 'одиннадцать': '11', 'двенадцать': '12', 'тринадцать': '13', 'четырнадцать': '14', 'пятнадцать': '15', 'шестнадцать': '16', 'семнадцать': '17', 'восемнадцать': '18', 'девятнадцать': '19', 'двадцать': '20', 'тридцать': '30', 'сорок': '40', 'пятьдесят': '50', 'шестьдесят': '60', 'семьдесят': '70', 'восемьдесят': '80', 'девяносто': '90', 'сто': '100', 'полминуты': '30', 'первую': '1', 'вторую': '2', 'третью': '3', 'четвертую': '4', 'пятую': '5', 'шестую': '6', 'седьмую': '7', 'восьмую': '8', 'девятую': '9', 'последнюю': '9', 'первый': '1', 'второй': '2', 'третий': '3', 'четвертый': '4', 'пятый': '5', 'шестой': '6', 'седьмой': '7', 'восьмой': '8', 'девятый': '9', 'последний': '9', 'первая': '1', 'вторая': '2', 'третья': '3', 'четвертая': '4', 'пятая': '5', 'шестая': '6', 'седьмая': '7', 'восьмая': '8', 'девятая': '9', 'последняя': '9', 'первое': '1', 'второе': '2', 'третье': '3',
    'четвёртую': '4', 'четвёртый': '4', 'четвёртая': '4',
    'десятую': '10', 'десятый': '10', 'десятая': '10',
    'одиннадцатую': '11', 'одиннадцатый': '11', 'одиннадцатая': '11',
    'двенадцатую': '12', 'двенадцатый': '12', 'двенадцатая': '12',
    'тринадцатую': '13', 'тринадцатый': '13', 'тринадцатая': '13',
    'четырнадцатую': '14', 'четырнадцатый': '14', 'четырнадцатая': '14',
    'пятнадцатую': '15', 'пятнадцатый': '15', 'пятнадцатая': '15',
    'шестнадцатую': '16', 'шестнадцатый': '16', 'шестнадцатая': '16',
    'семнадцатую': '17', 'семнадцатый': '17', 'семнадцатая': '17',
    'восемнадцатую': '18', 'восемнадцатый': '18', 'восемнадцатая': '18',
    'девятнадцатую': '19', 'девятнадцатый': '19', 'девятнадцатая': '19',
    'двадцатую': '20', 'двадцатый': '20', 'двадцатая': '20',
    # Ukrainian numerals
    'нуль': '0', 'нульовий': '0',
    'один': '1', 'одна': '1', 'одну': '1', 'одне': '1',
    'два': '2', 'дві': '2', 'двох': '2',
    'три': '3', 'трьох': '3',
    'чотири': '4', 'чотирьох': '4',
    'п\'ять': '5', 'п\'яти': '5',
    'шість': '6', 'шести': '6',
    'сім': '7', 'семи': '7',
    'вісім': '8', 'восьми': '8',
    'дев\'ять': '9', 'дев\'яти': '9',
    'десять': '10', 'десяти': '10',
    'одинадцять': '11', 'дванадцять': '12', 'тринадцять': '13',
    'чотирнадцять': '14', 'п\'ятнадцять': '15', 'шістнадцять': '16',
    'сімнадцять': '17', 'вісімнадцять': '18', 'дев\'ятнадцять': '19',
    'двадцять': '20', 'тридцять': '30', 'сорок': '40',
    'п\'ятдесят': '50', 'шістдесят': '60', 'сімдесят': '70',
    'вісімдесят': '80', 'дев\'яносто': '90', 'сто': '100',
    'перший': '1', 'перша': '1', 'першу': '1', 'першого': '1',
    'другий': '2', 'друга': '2', 'другу': '2', 'другого': '2',
    'третій': '3', 'третя': '3', 'третю': '3', 'третього': '3',
    'четвертий': '4', 'п\'ятий': '5', 'шостий': '6',
    'сьомий': '7', 'восьмий': '8', 'дев\'ятий': '9',
    'останній': '9', 'остання': '9', 'останню': '9',
}
_STT_GLUE_MAP = {
    # ── Typo / STT artefacts ─────────────────────────────────────────────
    'попку': 'папку', 'попки': 'папки', 'попке': 'папке', 'попок': 'папок',
    'создайь': 'создай',
    'джокумент': 'документ',
    'ворддокумент': 'ворд документ', 'вордокумент': 'ворд документ', 'вортдокумент': 'ворд документ',
    # ── Wake-word variants ────────────────────────────────────────────────
    'джаравис': 'джарвис', 'джарверс': 'джарвис', 'джервис': 'джарвис',
    'дарвис': 'джарвис',   'дарвиз': 'джарвис',   'дервис': 'джарвис',
    'джаравиз': 'джарвис', 'джарвиз': 'джарвис',
    # ── Wi-Fi / Bluetooth ─────────────────────────────────────────────────
    'вай фай': 'вайфай', 'ваи фай': 'вайфай', 'ва й фай': 'вайфай',
    'вай фай': 'вайфай',                                       # UK
    'блю туз': 'блютуз', 'блю тус': 'блютуз',
    'блу туз': 'блютуз', 'блу тус': 'блютуз',
    'блу тус': 'блютуз',                                       # UK
    # ── YouTube ───────────────────────────────────────────────────────────
    'ю туб': 'ютуб', 'ютьюб': 'ютуб', 'ю тьюб': 'ютуб',
    'ю туб': 'ютуб',                                           # UK same
    # ── Discord ───────────────────────────────────────────────────────────
    'дис корд': 'дискорд', 'дис кор': 'дискорд',
    'діс корд': 'дискорд', 'діскорд': 'дискорд',              # UK
    # ── Telegram ──────────────────────────────────────────────────────────
    'телеграмм': 'телеграм',
    # ── Instagram ─────────────────────────────────────────────────────────
    'ин стаграм': 'инстаграм', 'инста грам': 'инстаграм',
    'ін стаграм': 'інстаграм', 'інста грам': 'інстаграм',     # UK
    # ── WhatsApp ──────────────────────────────────────────────────────────
    'вацап': 'ватсап', 'уотсап': 'ватсап', 'уотс эп': 'ватсап',
    'вотс ап': 'ватсап', 'вотсап': 'ватсап',                  # UK phonetic
    # ── GitHub ────────────────────────────────────────────────────────────
    'гит хаб': 'github', 'гіт хаб': 'github',                # RU + UK
    'гитхаб': 'github',  'гітхаб': 'github',
    # ── TikTok ────────────────────────────────────────────────────────────
    'тик ток': 'тікток', 'тік ток': 'тікток',
    'тиктак': 'тікток',  'тіктак': 'тікток',
    # ── Spotify ───────────────────────────────────────────────────────────
    'спотифай': 'spotify', 'спотіфай': 'spotify',
    'споти фай': 'spotify', 'споті фай': 'spotify',
    # ── Netflix ───────────────────────────────────────────────────────────
    'нетфликс': 'netflix', 'нетфлікс': 'netflix',
    'нет флікс': 'netflix', 'нет фликс': 'netflix',
    # ── Twitch ────────────────────────────────────────────────────────────
    'твитч': 'twitch', 'твіч': 'twitch', 'твич': 'twitch',
    # ── Viber ─────────────────────────────────────────────────────────────
    'вайбер': 'viber',
    # ── Steam / Epic ──────────────────────────────────────────────────────
    'стим': 'стим',    'стім': 'стим',                        # normalise UK→RU form
    'эпик': 'epic',    'епік': 'epic',
    # ── Figma ─────────────────────────────────────────────────────────────
    'фигма': 'фигма',  'фігма': 'фигма',                      # UK→RU form (used in intents)
    # ── VS Code / OBS ────────────────────────────────────────────────────
    'ви эс код': 'vscode', 'ви ес код': 'vscode',
    'ві ес код': 'vscode', 'ві єс код': 'vscode',             # UK
    'о би эс': 'obs', 'о бі ес': 'obs',                       # UK
    # ── Browsers ──────────────────────────────────────────────────────────
    'хром': 'chrome',
    'файр фокс': 'firefox', 'файрфокс': 'firefox',
    # ── Google ────────────────────────────────────────────────────────────
    'гугол': 'гугл',
    # ── ClipChamp / misc apps ─────────────────────────────────────────────
    'клип чемп': 'клипчемп', 'клип чамп': 'клипчемп',
    'кліп чемп': 'клипчемп', 'кліпчемп': 'клипчемп',         # UK
    # ── Photoshop / Screenshot ───────────────────────────────────────────
    'фото шоп': 'фотошоп',
    'скрин шот': 'скриншот', 'скрін шот': 'скриншот',        # UK
    # ── Paths / folder names ─────────────────────────────────────────────
    'проджектс': 'projects', 'проджетс': 'projects',
    'проекст': 'projects',   'проектс': 'projects',
    'даунлоадс': 'downloads', 'даунлодс': 'downloads',
    'документс': 'documents',
    # ── VPN ───────────────────────────────────────────────────────────────
    'ви пи эн': 'vpn', 'випиэн': 'vpn',
    'ві пі ен': 'vpn', 'ві-пі-ен': 'vpn',                    # UK
    # ── Enter / Tab / OK ─────────────────────────────────────────────────
    'энтер': 'enter', 'ентер': 'enter',                       # RU + UK
    'окей': 'ок',
}
_STT_GLUE_SORTED = sorted(_STT_GLUE_MAP.keys(), key=len, reverse=True)
_RE_DASHES   = re.compile(r'[—–\-]')
_RE_PUNCT    = re.compile(r'[.,!?;:]+')
_RE_SPACES   = re.compile(r'\s+')
_RE_N_TAG    = re.compile(r'\{N\}')
from core.nlp.commands_data import _PS_SHORT, _FIGMA_SHORT, CANON_SIMPLE, CANON_SIMPLE_UK, COMMAND_PATTERNS, _INSULT
def _normalize_stt(text: str) -> str:
    text = text.lower().strip()
    text = _RE_DASHES.sub(' ', text)
    text = _RE_PUNCT.sub('', text)
    text = _RE_SPACES.sub(' ', text).strip()
    for src in _STT_GLUE_SORTED:
        if src in text: text = text.replace(src, _STT_GLUE_MAP[src])
    text = text.replace('игррвой', 'игровой')
    text = text.replace('игрвой', 'игровой')
    text = text.replace('игрровой', 'игровой')
    text = text.replace('игрови', 'игровой')
    text = text.replace('игровй', 'игровой')
    return text
_ALL_PATTERN_STRINGS = []
# Pre-compile clean patterns + word sets + lengths for each command at load time.
# This eliminates all _RE_N_TAG.sub() calls inside hot fuzzy loops.
for _cp in COMMAND_PATTERNS:
    _cp['_clean_patterns'] = []
    _cp['_pat_word_sets'] = []   # set of words in each clean pattern (for intersection filter)
    _cp['_pat_plens'] = []       # word-count of each clean pattern
    # Build a union of all unique words across all this command's keywords+verbs+patterns
    _kv_words: set = set(_cp.get('keywords', [])) | set(_cp.get('verbs', []))
    for _s in _cp['patterns']:
        _clean = _RE_N_TAG.sub('', _s).strip()
        if _clean:
            _ALL_PATTERN_STRINGS.append(_clean)
            _cp['_clean_patterns'].append(_clean)
            _ws = set(re.findall(r'\b\w+\b', _clean))
            _cp['_pat_word_sets'].append(_ws)
            _cp['_pat_plens'].append(len(_clean.split()))
            _kv_words |= _ws
    _cp['_all_words'] = _kv_words   # quick pre-filter: if text shares none of these, skip
_CANON_SIMPLE_KEYS = sorted(CANON_SIMPLE.keys(), key=len, reverse=True)
_CANON_SUBSTR_KEYS = [k for k in _CANON_SIMPLE_KEYS if len(k) >= 4]
_CANON_UK_KEYS = sorted(CANON_SIMPLE_UK.keys(), key=len, reverse=True)
_CANON_UK_SUBSTR_KEYS = [k for k in _CANON_UK_KEYS if len(k) >= 4]
_SPLIT_PATTERN = re.compile('\\s+(?:и|а потом|потом|затем|після чого|після|потім)\\s+')
_ORDINALS_MAP = {'первый': '1', 'второй': '2', 'третий': '3', 'первая': '1', 'вторая': '2', 'третья': '3', 'первую': '1', 'вторую': '2', 'третью': '3', 'первое': '1', 'втовое': '2', 'третье': '3', 'первого': '1', 'второго': '2', 'третьего': '3', 'первом': '1', 'втором': '2', 'третьем': '3'}
_TENS_VAL = {'двадцать': 20, 'тридцать': 30, 'сорок': 40, 'пятьдесят': 50, 'шестьдесят': 60, 'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90}
_UNITS_VAL = {'один': 1, 'одна': 1, 'одну': 1, 'одно': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9}

# -----------------------------------------------------------------------
# ADAPTIVE CONVERSATIONAL FILTER
# Built automatically from COMMAND_PATTERNS — no hardcoded lists.
# Any new command added to COMMAND_PATTERNS automatically expands this set.
# -----------------------------------------------------------------------
_COMMAND_VERBS: set = set()
for _cp in COMMAND_PATTERNS:
    _COMMAND_VERBS.update(_cp.get('verbs', []))
# Add common standalone imperative forms not always present in pattern verbs
_COMMAND_VERBS.update({
    'напомни', 'запомни', 'расскажи', 'объясни', 'стоп', 'хватит',
    'откройте', 'закройте', 'сверните', 'включите', 'выключите',
    # Infinitives commonly used as commands in Russian
    'открыть', 'закрыть', 'создать', 'сделать', 'найти', 'включить', 'выключить',
    'запустить', 'удалить', 'сохранить', 'отправить', 'скачать', 'загрузить',
    'подключить', 'отключить', 'перезагрузить', 'выключиться',
})
_COMMAND_VERBS.discard('')  # safety

# Russian question-starter words (interrogative pronouns/adverbs)
_QUESTION_STARTERS = frozenset({
    'что', 'чего', 'зачем', 'почему', 'как', 'каким', 'какой', 'какая', 'какое', 'какие',
    'когда', 'где', 'кто', 'кому', 'кого', 'чем', 'чему', 'сколько'
})

# Russian 2nd-person present-tense verb endings ("ты пишешь", "ты делаешь" etc.)
_RE_2ND_PERSON_VERB = re.compile(r'\b\w+(ешь|ёшь|ишь|аешь|яешь|уешь|оешь)\b')

# Russian 1st-person present-tense verb endings short form ("я делаю", "я хочу")
_RE_1ST_PERSON_VERB = re.compile(r'^\bя\b\s+\w+(ю|аю|яю|ею|иваю|ываю|уваю)\s*$')

def _is_conversational(text: str) -> bool:
    """
    Detects if the phrase is a conversational utterance rather than a command.
    Uses Russian grammar rules + the dynamically-built _COMMAND_VERBS set.

    Rules (all without any hardcoded phrase lists):
    1. Phrase starts with a question word AND contains no known command verb.
    2. Phrase contains "ты" + a 2nd-person present-tense verb AND no command verb.
    3. Short phrase "я + [1st-person verb]" AND no command verb.

    NOTE: Exact matches in CANON_SIMPLE already bypass this function entirely
    (they return before this is called). So "что ты умеешь" still works as show_help.
    """
    t = text.lower().strip()
    words = t.split()
    if len(words) < 2:
        return False

    has_cmd_verb = any(w in _COMMAND_VERBS for w in words)
    if has_cmd_verb:
        return False  # Has a real command verb — let it through

    # Rule 1: starts with question word, no command verb
    if words[0] in _QUESTION_STARTERS:
        return True

    # Rule 2: contains "ты" + 2nd-person present-tense verb
    if 'ты' in words and _RE_2ND_PERSON_VERB.search(t):
        return True

    # Rule 3: short "я + [1st-person verb]" phrase
    if words[0] == 'я' and len(words) <= 4 and _RE_1ST_PERSON_VERB.match(t):
        return True

    return False


_NOISE_WORDS = {
    'открой', 'закрой', 'удали', 'создай', 'сделай', 'покажи', 'найди', 'найти', 'запусти', 'включи', 'выключи',
    'переключи', 'смени', 'поменяй', 'установи', 'поставь', 'сверни', 'разверни', 'выполни',
    'что', 'как', 'почему', 'зачем', 'где', 'когда', 'кто', 'какой', 'какая', 'какое', 'какие',
    'сколько', 'один', 'два', 'три', 'четыре', 'пять', 'первый', 'второй', 'третий', 'это', 'тут', 'здесь', 'сейчас'
}
class WakeWordsStrictSet:
    def __contains__(self, item: str) -> bool:
        if not item: return False
        from rapidfuzz.distance import Levenshtein
        il = item.lower()
        for base in ('джарвис', 'джарвіс'):
            dist = Levenshtein.distance(il, base)
            limit = 1 if len(il) <= 5 else 2
            if dist <= limit:
                return True
        return False

_WAKE_WORDS_STRICT = WakeWordsStrictSet()
_FILLERS_STRICT = {'пожалуйста', 'плиз', 'ну', 'давай', 'хочу', 'мне', 'эту', 'тут', 'здесь', 'плиз', 'сэр', 'слушай'}

# Grammatical pattern: "что ты [verb 2nd person present]" or "ты [verb -ешь/-ишь/-ёшь]"
# These are conversational questions about what Jarvis is CURRENTLY doing — never a command.
# Русская грамматика: глагол 2 лица наст. времени оканчивается на -ешь, -ёшь, -ишь.
_RE_CONVO_QUESTION = re.compile(
    r'^(что|чего|зачем|почему|как)?\s*ты\s+\w*(ешь|ёшь|ишь|аешь|яешь|уешь|оешь)\s*$'
)
# "я [verb -ю/-аю/-яю/-ею]" — user talks about themselves, never a command.
_RE_SELF_STATEMENT = re.compile(
    r'^я\s+\w+(ю|аю|яю|ею|иваю|ываю|уваю)\s*$'
)

_NOISE_SINGLE_VERBS = frozenset({
    'открой', 'запусти', 'удали', 'закрой', 'создай', 'сделай',
    'покажи', 'найди', 'найти', 'установи', 'поставь'
})

def _is_noise_phrase(text: str) -> bool:
    t = text.lower().strip()
    if not t: return True
    if t in _WAKE_WORDS_STRICT: return True
    if t in _FILLERS_STRICT: return True
    if t in _NOISE_SINGLE_VERBS: return True          # O(1) frozenset lookup
    if _RE_CONVO_QUESTION.match(t): return True
    if _RE_SELF_STATEMENT.match(t): return True
    return False

def normalize_numbers(text: str) -> str:
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        w = words[i]
        if w in _TENS_VAL and i + 1 < len(words) and (words[i + 1] in _UNITS_VAL):
            result.append(str(_TENS_VAL[w] + _UNITS_VAL[words[i + 1]]))
            i += 2
        elif w in WORDS_TO_NUM:
            result.append(WORDS_TO_NUM[w])
            i += 1
        else:
            result.append(w); i += 1
    return ' '.join(result)

_NEGATIVE_KEYWORDS = {
    'вкладку': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win', 'min_all', 'min_other_win', 'unmin_win', 'win_snap_left', 'win_snap_right', 'win_snap_top_left', 'win_snap_top_right', 'win_snap_bottom_left', 'win_snap_bottom_right', 'explorer_goto', 'cd_folder'},
    'вкладки': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win', 'min_all', 'min_other_win', 'unmin_win'},
    'вкладка': {'close_win', 'close_all_win', 'close_other_win', 'min_win', 'max_win'},
    'окно': {'close_tab', 'close_tab_n', 'close_all_tabs', 'browser_tab', 'context_close'},
    'окна': {'close_tab', 'close_tab_n', 'close_all_tabs', 'browser_tab', 'context_close'},
    # An AI-question verb anywhere in the phrase means it's a question for the
    # assistant to answer (qa_search), not a request for the local help screen —
    # blocks the bare 'что ты умеешь'/'что ты можешь'/'что ты знаешь' canon
    # substring match from pre-empting e.g. "скажи что ты знаешь про эресонский мост".
    'скажи': {'show_help'}, 'расскажи': {'show_help'}, 'объясни': {'show_help'}, 'ответь': {'show_help'},
    'розкажи': {'show_help'}, 'поясни': {'show_help'}, 'відповідай': {'show_help'},
}

_CREATE_FILE_COMPLETION_MARKERS = (
    'папке', 'папку', 'папка', 'каталог', 'проект', 'имен', 'назван', 'новый', 'новая', 'новое', 'пустой',
    'ворд', 'word', 'excel', 'эксель', 'эксел', 'таблиц', 'презентац', 'powerpoint', 'ppt',
    'python', 'пайтон', 'питон', 'текстов', 'markdown', 'маркдаун',
    'javascript', 'typescript', 'jsx', 'tsx', 'react', 'html', 'json',
    'vue', 'svelte', 'css', 'scss', 'sass', 'js', 'ts', 'php', 'node',
    'документ', 'модул', 'скрипт', 'класс', 'интерфейс', 'компонент',
)

def _create_file_phrase_complete_enough(text_lower: str) -> bool:
    t = (text_lower or '').strip()
    if not t:
        return False
    if any(m in t for m in _CREATE_FILE_COMPLETION_MARKERS):
        return True
    if re.search(r'\.(py|ts|js|tsx|jsx|md|txt|json|html|css|sql|rs|go|java|cs|kt)\b', t):
        return True
    if re.match(r'^(джарвис|джервис|жарвис)\s+(создай|сделай|создать|сделать)\s+файл\s*$', t):
        return False
    return True

def _is_blocked_by_negative_kw(text_words: set, candidate_id: str) -> bool:
    for neg_word, blocked_ids in _NEGATIVE_KEYWORDS.items():
        if neg_word in text_words and candidate_id in blocked_ids: return True
    return False
def _keyword_verb_startswith_match(text: str, text_lower: str, text_words: set) -> str:
    """Combined keyword/verb + startswith pass — single loop over COMMAND_PATTERNS."""
    for pat in COMMAND_PATTERNS:
        pat_id = pat['id']
        bw = pat.get('block_words')
        if bw and any(b in w for b in bw for w in text_words): continue
        if _is_blocked_by_negative_kw(text_words, pat_id): continue
        rw = pat.get('require_words')
        if rw and not any(r in text_words for r in rw): continue

        # --- startswith check (fast, no fuzzy) ---
        for cp in pat.get('_clean_patterns', []):
            if text.startswith(cp):
                if pat_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
                    break
                return pat_id

        # --- keyword/verb check ---
        k_found = [kw for kw in pat.get('keywords', []) if kw in text_words]
        v_found = [v for v in pat.get('verbs', []) if v in text_words]
        e_found = []
        for e in pat.get('extras', []):
            if ' ' in e:
                if e in text_lower: e_found.append(e)
            elif e in text_words: e_found.append(e)
        if (k_found and v_found) or (k_found and e_found) or (v_found and e_found):
            matched_words = set(k_found) | set(v_found)
            for e in e_found: matched_words.update(e.split())
            if len(matched_words) >= 2:
                if pat_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
                    continue
                return pat_id
    return ''

def _pattern_fuzzy_match(text: str, text_words_set: set | None = None) -> tuple[str, int]:
    """
    Fuzzy match against COMMAND_PATTERNS.
    Optimizations:
    - Uses pre-compiled _clean_patterns (no _RE_N_TAG.sub at runtime)
    - Uses pre-built _all_words per command for O(1) intersection pre-filter
    - Pre-built _pat_plens avoids len(split()) per iteration
    - Early exit when score >= 95 (near-perfect match)
    - Accepts text_words_set to avoid recomputing it if already available
    """
    best_id, best_score, best_len = '', 0, 0
    if text_words_set is None:
        text_words_set = set(re.findall(r'\b\w+\b', text.lower()))
    text_words = len(text.split())
    text_lower = text.lower()
    for pat in COMMAND_PATTERNS:
        pat_id = pat['id']
        # Word-intersection pre-filter: if text shares NO word with this command's
        # entire vocabulary (keywords + verbs + pattern words), fuzzy cannot match.
        if not (text_words_set & pat['_all_words']): continue
        bw = pat.get('block_words')
        if bw and any(b in w for b in bw for w in text_words_set): continue
        if _is_blocked_by_negative_kw(text_words_set, pat_id): continue
        rw = pat.get('require_words')
        if rw and not any(r in text_words_set for r in rw): continue
        for cp, pws, plen in zip(pat['_clean_patterns'], pat['_pat_word_sets'], pat['_pat_plens']):
            # Skip if no word overlap between text and this specific pattern
            if not (text_words_set & pws): continue
            score = fuzz.token_set_ratio(text_lower, cp)
            if text_words < plen: score *= (text_words / plen) ** 0.5
            elif plen < text_words: score *= max(plen / text_words, 0.6)
            if score >= pat['min_score']:
                if score > best_score or (score == best_score and plen > best_len):
                    best_score, best_len, best_id = score, plen, pat_id
                    if best_score >= 95:
                        break  # near-perfect, no need to check remaining patterns
        if best_score >= 95:
            break
    if best_id == 'create_word_doc' and not _create_file_phrase_complete_enough(text_lower):
        return ('', 0)
    return (best_id, best_score)
_match_cache: dict[str, str] = {}
_ext_manager_cache = None

def _get_ext_manager():
    global _ext_manager_cache
    if _ext_manager_cache is None:
        try:
            from core.extensions import ExtensionManager
            _ext_manager_cache = ExtensionManager()
        except Exception:
            pass
    return _ext_manager_cache
def match_command(text: str, threshold: int=75) -> str:
    text = _normalize_stt(text)
    if not text: return ''
    _cached = _match_cache.get(text)
    if _cached is not None: return _cached
    result = _match_command_inner(text, threshold)
    if len(_match_cache) > 512:
        _match_cache.clear()
    _match_cache[text] = result
    return result
def _match_command_inner(text: str, threshold: int) -> str:
    from core.i18n import get_language
    lang = get_language()
    canon = CANON_SIMPLE_UK if lang == 'uk' else CANON_SIMPLE
    canon_keys = _CANON_UK_KEYS if lang == 'uk' else _CANON_SIMPLE_KEYS
    canon_substr_keys = _CANON_UK_SUBSTR_KEYS if lang == 'uk' else _CANON_SUBSTR_KEYS

    text_norm = normalize_numbers(text)

    # --- Exact CANON lookup (O(1)) ---
    _game_kw = {'игр', 'геймод', 'гра', 'граю', 'запусти', 'включи', 'хочу', 'game', 'играть', 'играй'} if lang == 'ru' else {'гра', 'граю', 'запусти', 'включи', 'хочу', 'game'}
    for t in (text, text_norm):
        cmd0 = canon.get(t)
        if cmd0:
            if cmd0 == 'game_mode_on' and not any(kw in t for kw in _game_kw):
                return ''
            if cmd0 == 'reminder' and 'напомн' not in t and 'напомин' not in t and 'напомин' not in t:
                return ''
            return cmd0

    # --- Insult detection ---
    try:
        words = set(re.findall(r'\b\w+\b', text_norm))
        has_jarvis = bool(words & {'джарвис', 'джервис', 'жарвис'})
        directed = has_jarvis or (text_norm.startswith('ты ') and len(words) <= 4)
        if directed and any(k in text_norm for k in (
            'туп', 'дурак', 'дура', 'идиот', 'дебил', 'кретин', 'тормоз',
            'заткни', 'замолчи', 'молчи', 'завали', 'закройся',
            'отвали', 'проваливай', 'уйди', 'пошел', 'пошёл', 'нахер',
        )):
            return _INSULT
    except Exception:
        pass

    # --- App-context shortcuts (PS / Figma) — cached ExtensionManager ---
    try:
        from core.system import get_foreground_process_name
        ext = _get_ext_manager()
        if ext:
            proc = (get_foreground_process_name() or '').lower()
            if proc:
                if 'photoshop' in proc and ext.has_feature('photoshop_voice'):
                    cmd = _PS_SHORT.get(text_norm) or _PS_SHORT.get(text)
                    if cmd: return cmd
                if ext.has_feature('figma_voice') and any(k in proc for k in ('figma', 'chrome', 'brave', 'msedge')):
                    cmd = _FIGMA_SHORT.get(text_norm) or _FIGMA_SHORT.get(text)
                    if cmd: return cmd
    except Exception:
        pass

    # Compute once — reused across all sub-functions
    is_noise = _is_noise_phrase(text_norm)
    if is_noise:
        return ''

    text_lower = text_norm.lower()
    text_words_set = set(re.findall(r'\b\w+\b', text_lower))
    
    # Strip wake words and exact fillers to avoid length penalties and fix startswith
    _stripped_lower = text_lower
    _stripped_words_set = set(text_words_set)
    for w in list(_stripped_words_set):
        if w in _WAKE_WORDS_STRICT:
            _stripped_lower = re.sub(r'\b' + re.escape(w) + r'\b', '', _stripped_lower).strip()
            _stripped_words_set.discard(w)
    for w in _FILLERS_STRICT:
        if w in _stripped_words_set:
            _stripped_lower = re.sub(r'\b' + re.escape(w) + r'\b', '', _stripped_lower).strip()
            _stripped_words_set.discard(w)

    if not _stripped_lower:
        return ''

    # --- CANON substring scan ---
    for key in canon_substr_keys:
        if key in _stripped_lower and re.search(r'\b' + re.escape(key) + r'\b', _stripped_lower):
            cmd_id = canon[key]
            # A short canon entry like 'закрой' is meant for the bare verb said
            # alone — but as a substring match it would also fire inside
            # "закрой окно"/"закрой вкладку" etc., pre-empting the more specific
            # COMMAND_PATTERNS rule for that object word before it gets a
            # chance to run. Same _NEGATIVE_KEYWORDS table already used below.
            if _is_blocked_by_negative_kw(_stripped_words_set, cmd_id):
                continue
            return cmd_id

    # --- Keyword/verb + startswith — single pass over COMMAND_PATTERNS ---
    kv_result = _keyword_verb_startswith_match(_stripped_lower, _stripped_lower, _stripped_words_set)
    if kv_result: return kv_result

    # --- Fuzzy pattern match against COMMAND_PATTERNS ---
    # Pass text_words_set to avoid recomputing it inside
    pat_id, _ = _pattern_fuzzy_match(_stripped_lower, _stripped_words_set)
    if pat_id: return pat_id

    # --- Conversational gate (before expensive fallbacks) ---
    if _is_conversational(text_norm):
        return ''

    # --- Levenshtein fallback (typo correction, tight threshold) ---
    best_lev_match, best_lev_dist = None, float('inf')
    for key in canon_keys:
        max_len = max(len(key), len(_stripped_lower))
        if max_len == 0: continue
        dist = Levenshtein.distance(_stripped_lower, key)
        if dist / max_len <= 0.2 and dist < best_lev_dist:
            best_lev_dist, best_lev_match = dist, key
    if best_lev_match:
        _lev_cmd = canon[best_lev_match]
        # 'мне' is a stripped filler (see _FILLERS_STRICT above), so "напомни
        # мне" collapses to "напомни" — which is Levenshtein-distance 1 from
        # 'запомни' (note_save's canon key), well inside this 20% typo
        # threshold, even though these are two different real words, not an
        # ASR misspelling of the same one. Same guard already exists for the
        # exact-CANON lookup path above; needed here too since this fallback
        # runs independently of it.
        if not (_lev_cmd == 'note_save' and 'напомн' in _stripped_lower and 'запомн' not in _stripped_lower):
            return _lev_cmd

    # --- Final fuzzy token_set_ratio on CANON ---
    best_match, best_score, best_len = None, 0, 0
    tlen = len(_stripped_lower.split())
    for key in canon_keys:
        score = fuzz.token_set_ratio(_stripped_lower, key)
        if score >= threshold:
            klen = len(key.split())
            if tlen == 1 and klen > 1:
                if score < 100: continue
                if _stripped_lower in _NOISE_WORDS or _stripped_lower.isdigit(): continue
                if klen > 2: continue
            # Short text (≤2 words) matching a much longer key is likely a false positive.
            # Require near-perfect score unless all words of the text are actually in the key.
            if tlen <= 2 and klen > tlen:
                text_words_set2 = set(_stripped_lower.split())
                key_words_set = set(key.split())
                if not text_words_set2.issubset(key_words_set) and score < 92:
                    continue
            # Mirror of the guard above: a longer phrase matching a SHORTER
            # key is likely a false positive too — token_set_ratio can hit
            # the threshold purely off one shared generic verb (e.g. both
            # "открой обс" and "открой автор эффектс" share "открой"), even
            # though the key's actual content word ("обс") never appears in
            # the phrase at all. Require the key's own words to genuinely be
            # present as tokens unless the score is near-perfect.
            if klen < tlen:
                key_words_set2 = set(key.split())
                text_words_set3 = set(_stripped_lower.split())
                if not key_words_set2.issubset(text_words_set3) and score < 92:
                    continue
            if score > best_score or (score == best_score and klen > best_len):
                best_score, best_len, best_match = score, klen, key
    if best_match:
        return canon[best_match]
    return ''
def extract_all_commands(text: str) -> list[tuple[str, str]]:
    from core.i18n import get_language
    lang = get_language()
    text = _normalize_stt(text)
    if not text: return []
    if lang == 'uk':
        if 'крім ' in text:
            idx = text.find('крім ')
            text = text[:idx] + text[idx:].replace(' і ', ' та ')
    else:
        if 'кроме ' in text:
            idx = text.find('кроме ')
            text = text[:idx] + text[idx:].replace(' и ', ' да ')
    segments = _SPLIT_PATTERN.split(text)
    results = []
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
        cmd = match_command(seg)
        if cmd: results.append((cmd, seg))
    if not results:
        cmd = match_command(text)
        if cmd: results.append((cmd, text))
        return results
    if len(results) == 1 and len(segments) > 1:
        full_cmd = match_command(text)
        if full_cmd == results[0][0]: return [(full_cmd, text)]
    return results
def extract_amount(text: str) -> int:
    text_norm = normalize_numbers(text.lower())
    nums = re.findall('\\d+', text_norm)
    return sum((int(n) for n in nums)) if nums else 5
def extract_duration_seconds(text: str) -> int:
    text_lower = text.lower()
    # Exact half-unit words — checked against the raw text, since
    # normalize_numbers() maps 'полминуты' to the digit token '30' via
    # WORDS_TO_NUM, which would make this \bполминуты\b check unreachable.
    if re.search(r'\bполчаса\b', text_lower): return 1800
    if re.search(r'\bполминуты\b', text_lower): return 30
    text_norm = normalize_numbers(text_lower)
    total, found = 0, False
    _UNIT_MULT = [('час', 3600), ('минут', 60), ('секунд', 1)]
    # "полтора/полторы {unit}" = 1.5 × unit
    for unit, mult in _UNIT_MULT:
        if re.search(rf'\bполтор[аы]\s+{unit}', text_norm):
            total += int(1.5 * mult); found = True
    # "{N} с половиной {unit}" = (N + 0.5) × unit
    for m in re.finditer(r'(\d+)\s+с\s+половиной\s+(час|минут|секунд)', text_norm):
        n, uw = int(m.group(1)), m.group(2)
        mult = next(mu for u, mu in _UNIT_MULT if uw.startswith(u[:3]))
        total += int((n + 0.5) * mult); found = True
    # Standard "{N} {unit}"
    for unit, mult in _UNIT_MULT:
        m = re.search(f'(\\d+)\\s*{unit}', text_norm)
        if m: total += int(m.group(1)) * mult; found = True
    # Bare unit words without number
    if not re.search(r'\d+\s*час', text_norm) and not re.search(r'полтор[аы]\s+час', text_norm) \
            and re.search(r'\bчас(?:а|ов)?\b', text_norm):
        total += 3600; found = True
    if not re.search(r'\d+\s*минут', text_norm) and not re.search(r'полтор[аы]\s+минут', text_norm) \
            and re.search(r'\bминут(?:у|ы|е)?\b', text_norm):
        total += 60; found = True
    if not re.search(r'\d+\s*секунд', text_norm) and re.search(r'\bсекунд(?:у|ы|е)?\b', text_norm):
        total += 1; found = True
    if found: return total
    # No explicit duration wording at all (no number, no час/минут/секунд) —
    # return 0 rather than borrowing extract_amount()'s volume-style "no
    # number means 5" default, which used to defeat every `if delay <= 0`
    # guard in reminder/timer/shutdown_timer call sites (e.g. an incomplete
    # "выключи компьютер через" would silently shut down in 5 seconds).
    return 0
