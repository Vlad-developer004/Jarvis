"""Guard against destructive commands (shutdown/restart/delete/etc.)
firing on an unrelated or colloquial phrase that merely shares a verb.

Found via this exact test while auditing the matcher: 'выключи музыку'
('turn off the music') and 'выключи свет' ('turn off the light') both
resolved to `shutdown` (power off the PC!), and 'перезагрузи роутер'
('restart the router') resolved to `restart` (reboot Windows). Root cause:
core/nlp/commands.py's fuzzy pattern matcher (_pattern_fuzzy_match) scores
`fuzz.token_set_ratio(text, pattern)` — for a 2-word pattern like "выключи
пк", any "выключи <anything>" scores high purely because the verb overlaps
and "пк" is short, regardless of whether the object word means anything
like a computer. The `keywords`/`verbs` OR-based gate doesn't protect
against this because the fuzzy path only checks the AND-gated
`require_words` list, and shutdown/restart didn't have one.

Fixed by adding `require_words` to shutdown/restart's COMMAND_PATTERNS
entries — this test locks that in and gives future destructive commands a
place to be listed.
"""
from core.nlp.commands import match_command

# Commands where a false-positive match has real-world consequences beyond
# "wrong feature ran" — add to this list whenever a new one is introduced.
DESTRUCTIVE_COMMANDS = frozenset({
    'shutdown', 'restart', 'empty_trash', 'delete_file', 'delete_folder',
    'keyboard_lock',
})

# Phrases that share a verb/keyword with a destructive command but are
# about something else entirely — none of these must ever resolve to one
# of DESTRUCTIVE_COMMANDS.
SAFE_PHRASES = [
    'выключи музыку', 'выключи свет', 'выключи телевизор',
    'выключи вентилятор', 'выключи микрофон', 'выключи камеру',
    'выключись', 'выключи',
    'перезагрузи роутер', 'перезагрузи телефон', 'перезагрузи браузер',
    'очисти стол', 'очисти тарелку', 'очисти голову',
    'удали контакт', 'удали сообщение', 'удали приложение', 'удали историю',
    'отключись', 'отстань', 'помолчи', 'хватит', 'стоп', 'ладно', 'забудь',
]


def test_unrelated_phrases_never_trigger_a_destructive_command():
    offenders = []
    for phrase in SAFE_PHRASES:
        result = match_command(phrase)
        if result in DESTRUCTIVE_COMMANDS:
            offenders.append((phrase, result))
    assert not offenders, f'unrelated phrases matched a destructive command: {offenders}'


def test_the_real_destructive_phrases_still_work():
    # The safety fix must not have collaterally broken the actual commands.
    assert match_command('выключи компьютер') == 'shutdown'
    assert match_command('выключи пк') == 'shutdown'
    assert match_command('перезагрузи компьютер') == 'restart'
    assert match_command('перезагрузи систему') == 'restart'
