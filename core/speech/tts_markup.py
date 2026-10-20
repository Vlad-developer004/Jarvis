"""Text tables, transliteration, grapheme-to-phoneme and SSML-tag helpers for core.speech.tts (moved out of tts.py unchanged)."""

import re
import threading

_CYR_LETTERS = {'А': 'а', 'Б': 'бэ', 'В': 'вэ', 'Г': 'гэ', 'Д': 'дэ', 'Е': 'е', 'Ё': 'ё', 'Ж': 'жэ', 'З': 'зэ', 'И': 'и', 'Й': 'й', 'К': 'ка', 'Л': 'эл', 'М': 'эм', 'Н': 'эн', 'О': 'о', 'П': 'пэ', 'Р': 'эр', 'С': 'эс', 'Т': 'тэ', 'У': 'у', 'Ф': 'эф', 'Х': 'ха', 'Ц': 'цэ', 'Ч': 'чэ', 'Ш': 'ша', 'Щ': 'ща', 'Э': 'э', 'Ю': 'ю', 'Я': 'я'}

_CYR_ABBREV  = {'РФ': 'эрэф', 'ООН': 'оон', 'НАТО': 'нато', 'ТАСС': 'тасс', 'МВД': 'эмвэдэ', 'ФСБ': 'эфэсбэ', 'КГБ': 'кэгэбэ', 'ЦРУ': 'цээру', 'ФБР': 'эфбэр', 'МИД': 'мид', 'ВВП': 'вэвэпэ', 'ВВС': 'вэвээс', 'ФНС': 'фээнэс', 'МЧС': 'эмчээс', 'ДТП': 'дэтэпэ', 'СМИ': 'сми', 'НЛО': 'энэло', 'ПК': 'пэка', 'ОС': 'оэс', 'ИП': 'ип', 'ООО': 'ооо', 'ЧС': 'чээс', 'ВМФ': 'вэмэ эф', 'ФСО': 'эфэсэ', 'ГРУ': 'гэрэу', 'СВР': 'эсвээр', 'МГУ': 'эм гэ у', 'РАН': 'ран', 'ВЦИОМ': 'вциом', 'ЦБ': 'цэ бэ', 'ЕС': 'е эс', 'СНГ': 'эс эн гэ', 'БРИКС': 'брикс', 'СССР': 'эс эс эс эр', 'ТВ': 'тэ вэ', 'ДНР': 'дэ эн эр', 'ЛНР': 'эл эн эр'}

_LETTER_NAMES = {'A': 'эй', 'B': 'би', 'C': 'си', 'D': 'ди', 'E': 'и', 'F': 'эф', 'G': 'джи', 'H': 'эйч', 'I': 'ай', 'J': 'джей', 'K': 'кей', 'L': 'эл', 'M': 'эм', 'N': 'эн', 'O': 'оу', 'P': 'пи', 'Q': 'кью', 'R': 'ар', 'S': 'эс', 'T': 'ти', 'U': 'ю', 'V': 'ви', 'W': 'дабл-ю', 'X': 'экс', 'Y': 'вай', 'Z': 'зет'}

_PHONETIC_DRIVES = {k: _LETTER_NAMES.get(k, k).capitalize() for k in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'}

_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'

_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'

_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'

_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'

_EXCEPTIONS = {'openai': 'опен эй ай', 'chatgpt': 'чат джи пи ти', 'gpt': 'джи пи ти', 'youtube': 'ютуб', 'discord': 'дискорд', 'twitch': 'твич', 'telegram': 'телеграм', 'whatsapp': 'вотсап', 'instagram': 'инстаграм', 'tiktok': 'тик ток', 'twitter': 'твиттер', 'facebook': 'фейсбук', 'netflix': 'нетфликс', 'spotify': 'спотифай', 'google': 'гугл', 'amazon': 'амазон', 'apple': 'эппл', 'iphone': 'айфон', 'ipad': 'айпэд', 'imac': 'аймак', 'android': 'андроид', 'windows': 'виндовс', 'microsoft': 'майкрософт', 'github': 'гитхаб', 'gitlab': 'гитлаб', 'chrome': 'хром', 'firefox': 'файерфокс', 'safari': 'сафари', 'nvidia': 'энвидиа', 'amd': 'амд', 'intel': 'интел', 'xbox': 'иксбокс', 'playstation': 'плейстейшн', 'nintendo': 'нинтендо', 'steam': 'стим', 'epic': 'эпик', 'games': 'геймс', 'launcher': 'лаунчер', 'euro': 'евро', 'truck': 'трак', 'simulator': 'симулятор', 'ets': 'е т с', 'minecraft': 'майнкрафт', 'cyberpunk': 'киберпанк', 'witcher': 'ведьмак', 'valorant': 'валорант', 'fortnite': 'фортнайт', 'overwatch': 'оверватч', 'hearthstone': 'хёртстон', 'dota': 'дота', 'counter': 'кантер', 'strike': 'страйк', 'planetbase': 'планет бэйс', 'iv': 'четыре', 'iii': 'три', 'ii': 'два', 'v': 'пять', 'exe': 'экзэ', 'dll': 'диэлэл', 'bat': 'бат', 'cmd': 'цээмдэ', 'zip': 'зип', 'rar': 'рар', 'mp3': 'эмпэ три', 'mp4': 'эмпэ четыре', 'pdf': 'пэдээф', 'jpg': 'джыпег', 'jpeg': 'джыпег', 'png': 'пээнг', 'antigravity': 'антигравити', 'gravity': 'гравити', 'anti': 'анти', 'python': 'питон', 'java': 'джава', 'javascript': 'джаваскрипт', 'typescript': 'тайпскрипт', 'react': 'реакт', 'docker': 'докер', 'linux': 'линукс', 'ubuntu': 'убунту', 'bluetooth': 'блютус', 'wifi': 'вайфай', 'wi-fi': 'вайфай', 'browser': 'браузер', 'nuclear': 'нуклеар', 'option': 'опшн', 'iron': 'айрон', 'hearts': 'хёртс', 'c': 'Ц', 'd': 'Д', 'e': 'Е', 'f': 'эф'}

_ABBREV = {'vlc': 'вэ эл си', 'cpu': 'си пи ю', 'gpu': 'джи пи ю', 'ram': 'рэм', 'rom': 'ром', 'ssd': 'эс эс ди', 'hdd': 'эйч ди ди', 'usb': 'ю эс би', 'hdmi': 'эйч ди эм ай', 'fps': 'эф пи эс', 'api': 'эй пи ай', 'url': 'ю эр эл', 'gui': 'джи ю ай', 'ai': 'эй ай', 'pc': 'пи си', 'os': 'оу эс', 'ok': 'окей', 'vpn': 'вэ пэ эн', 'ip': 'ай пи', 'id': 'ай ди', 'vs': 'версус', 'gta': 'гта', 'rpg': 'эрпэгэ', 'ui': 'юай', 'ux': 'юикс', 'tv': 'тиви'}

_UNIT_EXPANSIONS = {'gb': 'гигабайт', 'mb': 'мегабайт', 'kb': 'килобайт', 'km/h': 'километров в час', 'км/ч': 'километров в час', 'kg': 'килограмм', 'cm': 'сантиметров', 'mm': 'миллиметров'}

# English words not in _EXCEPTIONS/_ABBREV are looked up in CMUdict (a
# static ~126k-word pronouncing dictionary, see _g2p_word below) and their
# ARPAbet pronunciation converted straight to Cyrillic — the previous
# g2p_en+nltk pipeline did the same lookup but through nltk's POS tagger and
# runtime data download, which is what actually caused the startup/offline
# fragility (see CLAUDE.md's crash-sensitive-startup rule), not the concept
# of dictionary-based G2P itself. CMUdict ships its data inside the pip
# package (no download, no nltk).
#
# Reverse (Latin -> Cyrillic) transliteration below is the fallback for
# whatever CMUdict doesn't have — in practice, far more often a romanized
# Russian/Ukrainian proper noun (an artist name from Shazam/AudD, see
# actions/song_id.py, a surname, a city) than a genuine unseen English word,
# since CMUdict already covers the common-word case above it.
_CYR_DIGRAPHS = (
    ('shch', 'щ'), ('sch', 'щ'), ('yeah', 'е'),
    ('zh', 'ж'), ('kh', 'х'), ('ts', 'ц'), ('ch', 'ч'), ('sh', 'ш'),
    ('yu', 'ю'), ('ya', 'я'), ('yo', 'ё'), ('ye', 'е'), ('ph', 'ф'),
    ('iy', 'ий'), ('yy', 'ый'), ('ii', 'ий'), ('ck', 'к'), ('qu', 'кв'),
)

_CYR_SINGLE = {
    'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е', 'z': 'з',
    'i': 'и', 'y': 'й', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о',
    'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'f': 'ф', 'h': 'х',
    'c': 'к', 'j': 'й', 'w': 'в', 'x': 'кс', 'q': 'к',
}

# English "silent e" / "magic e" rule: a single vowel followed by a single
# consonant followed by a trailing e usually makes that vowel long
# (site/like/time/name/game/note/live...). The plain per-letter loop above
# reads these short and wrong ("live" -> "ливе" instead of "лайв") because it
# has no notion of the trailing e modifying the preceding vowel — this is
# the main source of genuine English words coming out garbled in a RU/UK
# app whose fallback otherwise targets romanized Russian/Ukrainian proper
# nouns (see the module comment above), which rarely have this shape.
_MAGIC_E_VOWEL = {'a': 'эй', 'i': 'ай', 'o': 'оу', 'u': 'ю'}

_MAGIC_E_PAT = re.compile(r'^([bcdfghjklmnpqrstvwxyz]*)([aiou])([bcdfghjklmnpqrstvwxyz])e$')

# Common short words that fit the vCe shape but don't follow the magic-e
# rule (irregular/unstressed vowel) — looked up before the regex fires.
_MAGIC_E_EXCEPTIONS = {
    'have': 'хэв', 'give': 'гив', 'live': 'лайв', 'love': 'лав',
    'some': 'сам', 'come': 'кам', 'done': 'дан', 'gone': 'гон',
    'none': 'нан', 'one': 'ван', 'move': 'мув', 'lose': 'луз',
    'above': 'абав', 'glove': 'глав', 'use': 'юз', 'whose': 'хуз',
}

def _reverse_translit_cyrillic(word: str) -> str:
    w = word.lower()
    if w in _MAGIC_E_EXCEPTIONS:
        result = _MAGIC_E_EXCEPTIONS[w]
    else:
        m = _MAGIC_E_PAT.match(w)
        if m:
            lead, vowel, cons = m.groups()
            # "ce" is always soft /s/ in English (nice/price/ace), never
            # the hard /k/ that bare 'c' maps to elsewhere (cat, disc).
            cons_cyr = 'с' if cons == 'c' else _CYR_SINGLE.get(cons, cons)
            result = ''.join(_CYR_SINGLE.get(c, c) for c in lead) + _MAGIC_E_VOWEL[vowel] + cons_cyr
        else:
            out = []
            i = 0
            n = len(w)
            while i < n:
                for pat, rep in _CYR_DIGRAPHS:
                    if w.startswith(pat, i):
                        out.append(rep)
                        i += len(pat)
                        break
                else:
                    out.append(_CYR_SINGLE.get(w[i], w[i]))
                    i += 1
            result = ''.join(out)
    return result.capitalize() if word[:1].isupper() and not word.isupper() else result

# ARPAbet (CMUdict's phoneme alphabet) -> Cyrillic. Vowel entries get a
# leading '+' when they carry CMUdict's primary-stress digit (1) — Silero's
# own symbol set supports '+' as an explicit stress mark (see _apply_stress
# above), which is far more reliable than letting its accentor guess stress
# on a synthetic pseudo-Russian spelling it's never seen.
_ARPABET_TO_CYR = {
    'AA': 'а', 'AE': 'э', 'AH': 'а', 'AO': 'о', 'AW': 'ау', 'AY': 'ай',
    'EH': 'э', 'ER': 'ер', 'EY': 'эй', 'IH': 'и', 'IY': 'и', 'OW': 'оу',
    'OY': 'ой', 'UH': 'у', 'UW': 'у', 'B': 'б', 'CH': 'ч', 'D': 'д',
    'DH': 'з', 'F': 'ф', 'G': 'г', 'HH': 'х', 'JH': 'дж', 'K': 'к',
    'L': 'л', 'M': 'м', 'N': 'н', 'NG': 'нг', 'P': 'п', 'R': 'р', 'S': 'с',
    'SH': 'ш', 'T': 'т', 'TH': 'т', 'V': 'в', 'W': 'в', 'Y': 'й', 'Z': 'з',
    'ZH': 'ж',
}

_ARPABET_PHONE_RE = re.compile(r'^([A-Z]+)([0-2])?$')

_CYR_VOWELS = set('аеёиоуыэюя')

_cmudict_data = None

_cmudict_lock = threading.Lock()

_cmudict_load_failed = False

def _get_cmudict():
    """Lazy-loaded, warmed up in the background by warmup_text_models() —
    building the ~126k-word lookup table takes ~2s on first access, so a
    caller reaching this cold (before warmup finishes) blocks on the lock
    instead of re-triggering the load."""
    global _cmudict_data, _cmudict_load_failed
    if _cmudict_data is not None or _cmudict_load_failed:
        return _cmudict_data
    with _cmudict_lock:
        if _cmudict_data is None and not _cmudict_load_failed:
            try:
                import cmudict
                _cmudict_data = cmudict.dict()
            except Exception as e:
                print(f"TTS: cmudict unavailable ({e}), Latin words fall back to letter transliteration.", flush=True)
                _cmudict_load_failed = True
    return _cmudict_data

def _g2p_word(word: str) -> str | None:
    """CMUdict pronunciation -> Cyrillic, or None if the word isn't a known
    English dictionary word (the caller then falls back to
    _reverse_translit_cyrillic, which is what romanized proper nouns need)."""
    d = _get_cmudict()
    if not d:
        return None
    entries = d.get(word.lower())
    if not entries:
        return None
    phones = entries[0]  # first pronunciation is CMUdict's most common one
    out = []
    stress_done = False
    for p in phones:
        m = _ARPABET_PHONE_RE.match(p)
        if not m:
            continue
        cyr = _ARPABET_TO_CYR.get(m.group(1), '')
        if m.group(2) == '1' and cyr and cyr[0] in _CYR_VOWELS and not stress_done:
            cyr = '+' + cyr
            stress_done = True
        out.append(cyr)
    result = ''.join(out)
    if not result:
        return None
    return result.capitalize() if word[:1].isupper() and not word.isupper() else result

# Silero's ssml_text path (see model.save_wav) supports <break time="500ms"/>
# and <break strength="weak|medium|strong|x-strong"/> for pauses, plus
# *word* focus/emphasis markers — used by the cloud QA answers
# (features/qa/llm_processor.get_sys_prompt) to sound less flat. Only
# self-closing <break/> is used (no <prosody>...</prosody> open/close pairs)
# because _chunk_text can split a sentence anywhere .!? occurs, which would
# tear an open/close tag pair across two independently-generated audio
# chunks; a self-closing tag has no punctuation inside it, so it always
# survives sentence splitting intact.
_SSML_TAG_RE = re.compile(r'<[^<>]+>')

_SSML_PLACEHOLDER_BASE = 0xE000  # Unicode Private Use Area — never matches \w or \d

_SSML_PLACEHOLDER_MAX = 0xF8FF - _SSML_PLACEHOLDER_BASE  # PUA block size

def _protect_ssml_tags(text: str) -> tuple[str, list[str]]:
    """Swap <...> tags for single Private-Use-Area codepoints before the
    RU/UA text-normalization regexes run — otherwise words like "break"/
    "time" and numbers inside attribute values (e.g. 500ms) get
    transliterated/spelled out like any other Latin word or number,
    corrupting the tag. A single opaque codepoint (rather than a codepoint
    pair wrapping a decimal index) avoids the digit itself being matched by
    the standalone-number regex further down the pipeline."""
    tags: list[str] = []
    def _stash(m: re.Match) -> str:
        if len(tags) > _SSML_PLACEHOLDER_MAX:
            return m.group(0)  # bail out silently — pathologically many tags
        tags.append(m.group(0))
        return chr(_SSML_PLACEHOLDER_BASE + len(tags) - 1)
    return _SSML_TAG_RE.sub(_stash, text), tags

def _restore_ssml_tags(text: str, tags: list[str]) -> str:
    if not tags:
        return text
    return ''.join(
        tags[ord(c) - _SSML_PLACEHOLDER_BASE] if _SSML_PLACEHOLDER_BASE <= ord(c) < _SSML_PLACEHOLDER_BASE + len(tags) else c
        for c in text
    )

def _needs_ssml_route(text: str) -> bool:
    return '<' in text or '*' in text

def strip_speech_markup(text: str) -> str:
    """Drop <break .../> tags and *emphasis* asterisks for on-screen display
    (AI answer window/HUD) — callers still pass the original, markup-intact
    text to speak()/handler.speak() so TTS keeps the pauses/emphasis."""
    if not text:
        return text
    return _SSML_TAG_RE.sub('', text).replace('*', '')
