from core import i18n


def test_default_language_is_russian():
    assert i18n.get_language() == 'ru'


def test_set_language_switches_translations():
    i18n.set_language('ru')
    ru_text = i18n.tr('extensions.win_title')
    i18n.set_language('uk')
    uk_text = i18n.tr('extensions.win_title')
    assert ru_text != uk_text
    assert i18n.get_language() == 'uk'


def test_tr_falls_back_to_key_when_missing():
    assert i18n.tr('this.key.does.not.exist') == 'this.key.does.not.exist'


def _parse_deck_cmd_meta():
    # CMD_META lives inside open_deck()'s function body (not a module-level
    # name), so it can't be imported directly — parse it out of the source
    # with ast instead, the same way it was audited when the "БАЗА КОМАНД"
    # discoverability gap (auto-generated English-ish titles) was fixed.
    import ast
    import pathlib
    src = pathlib.Path('ui/dialogs/deck.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == 'CMD_META':
                return ast.literal_eval(node.value)
    raise AssertionError('CMD_META assignment not found in ui/dialogs/deck.py')


def test_deck_command_titles_are_non_empty():
    # Regression guard for the "БАЗА КОМАНД" discoverability fix: every
    # CMD_META entry needs a real Russian title, not a blank placeholder.
    cmd_meta = _parse_deck_cmd_meta()
    assert cmd_meta, 'CMD_META parsed empty'
    for cmd_id, (title, _desc, _example) in cmd_meta.items():
        assert title, f'{cmd_id} has an empty title'


def test_deck_command_titles_match_registered_commands():
    # deck.py resolves a command's card from CMD_META keyed by ids sourced
    # from *either* COMMAND_PATTERNS or CANON_SIMPLE (see open_deck()) —
    # an id in neither is metadata left behind after a rename/removal.
    from core.nlp.commands import COMMAND_PATTERNS, CANON_SIMPLE
    cmd_meta = _parse_deck_cmd_meta()
    known_ids = {p['id'] for p in COMMAND_PATTERNS} | set(CANON_SIMPLE.values())
    stale = set(cmd_meta) - known_ids
    assert not stale, f'CMD_META has entries for commands that no longer exist: {stale}'
