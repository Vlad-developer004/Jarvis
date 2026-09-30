"""Automatic pause/emphasis markup for game announcements.

The game phrase banks (Planetbase, ETS2) are plain sentences, which Silero reads
as one flat stream. This adds the same self-closing `<break time="..ms"/>` tags
and `*emphasis*` markers the TTS layer already understands (see the SSML notes
in core/speech/tts.py), so multi-sentence reports breathe and alert keywords
land. Only self-closing tags are used, so sentence chunking can never tear a
tag pair across two audio chunks.

Applied at the game speech entry points only, not to all of Jarvis's speech."""

import re

# Measured against Silero v5 (RU): without markup it already pauses ~400-560 ms
# at every sentence end and colon, but under ~120 ms at commas and dashes, and an
# explicit <break> REPLACES that natural pause rather than adding to it. So the
# sentence break must be longer than the natural pause (a shorter one makes
# speech feel rushed), and the useful additions are at commas and dashes.
_SENTENCE_MS = 620
_DASH_MS = 320
_COMMA_MS = 180
_MAX_SENTENCE_BREAKS = 5
_MAX_COMMA_BREAKS = 4
_MIN_LEN = 25
_COMMA_MIN_TEXT = 70    # only long sentences need comma breathing room
_COMMA_MIN_CLAUSE = 22  # skip short lead-ins like "Сэр,"

# Unicode-aware: \w covers Cyrillic; stress accents (combining marks) are left alone.
_SENTENCE_END = re.compile(r'(?<=[.!?…])[ \t]+(?=[«"“(]?\w)')
_DASH = re.compile(r'[ \t]+[—–][ \t]+(?=\S)')
_COMMA = re.compile(r'(?<=\S,)[ \t]+(?=[^\W\d_])')
_BREAK_TAG = re.compile(r'<break[^>]*/>')

# One emphasis per utterance, on words that carry urgency. Deliberately narrow:
# "тревога" alone would also be stressed in calm "тревога снята".
_EMPHASIS = re.compile(
    r'\b(внимание|критическ\w+|срочно|немедленно|незамедлительно|опасность)\b',
    re.IGNORECASE,
)


def _br(ms: int) -> str:
    return f'<break time="{ms}ms"/>'


def add_pauses(text: str, emphasize: bool = True) -> str:
    """Return `text` with pauses (and one urgency emphasis) added.

    Untouched when the text is short, or already carries markup (LLM narrations
    are prompted to add their own breaks)."""
    if not text or len(text) < _MIN_LEN or '<' in text or '*' in text:
        return text

    out = _breaks(_SENTENCE_END, text, _SENTENCE_MS, _MAX_SENTENCE_BREAKS)
    out = _breaks(_DASH, out, _DASH_MS, _MAX_SENTENCE_BREAKS)
    if len(text) >= _COMMA_MIN_TEXT:
        out = _comma_breaks(out)
    if emphasize:
        out = _EMPHASIS.sub(lambda m: f'*{m.group(0)}*', out, count=1)
    return out


def _breaks(pattern: re.Pattern, text: str, ms: int, limit: int) -> str:
    left = [limit]

    def _do(m: re.Match) -> str:
        if left[0] <= 0:
            return m.group(0)
        left[0] -= 1
        return f' {_br(ms)} '
    return pattern.sub(_do, text)


def _comma_breaks(text: str) -> str:
    """Breath after a comma, but only when the clause before it is long enough
    (never after a short lead-in like "Сэр,")."""
    left = _MAX_COMMA_BREAKS
    parts: list[str] = []
    pos = 0
    clause_start = 0
    for m in _COMMA.finditer(text):
        clause = _BREAK_TAG.sub('', text[clause_start:m.start()])
        clause_start = m.end()
        if left <= 0 or len(clause.strip()) < _COMMA_MIN_CLAUSE:
            continue
        parts.append(text[pos:m.start()])
        parts.append(f' {_br(_COMMA_MS)} ')
        pos = m.end()
        left -= 1
    parts.append(text[pos:])
    return ''.join(parts)
