"""Commands that only the semantic model knows (core/nlp/intents.py) or that a phrase router finds (actions/media_phrases.py for the
cinema ones): the matcher tables the catalog is built from do not list them, so they get their cards here.

id -> (category, runs from the window). A card runs only when the command is harmless without an argument and with any window in
front; the rest are shown as "voice only"."""
from __future__ import annotations

SEMANTIC_ONLY: dict[str, tuple[str, bool]] = {
    'browser_tab': ('apps', False), 'close_tab_n': ('apps', False), 'close_obs': ('apps', False),
    'session_save': ('apps', False), 'session_restore': ('apps', False), 'session_delete': ('apps', False),
    'cd_folder': ('files', False), 'paste_video': ('files', False), 'clipchamp_last': ('media', False),
    'net_profile_status': ('pc', True), 'net_profile_switch': ('pc', False), 'vpn_reminder': ('pc', False),
    'spell_list': ('games', False),
    'command_save': ('assistant', False), 'command_get': ('assistant', False), 'command_delete': ('assistant', False),
    'calendar_add': ('assistant', False),
    'cinema_watch': ('media', False), 'cinema_continue': ('media', False), 'cinema_later': ('media', False), 'cinema_later_list': ('media', True),
    'cinema_now': ('media', True), 'cinema_left': ('media', True), 'cinema_seek': ('media', False), 'cinema_mode': ('media', False),
    'cinema_when': ('media', False),
}
# Not commands a person says: the fallback for unrecognised text, the hidden insult reply, the "this was a quote" flag.
INTERNAL = {'llm_chat', 'system_insult', 'reported_speech'}
# The Photoshop and Figma voice packs belong to their extensions and are listed with them.
EXTENSION_PREFIXES = ('ps_', 'figma_')


def is_listed_elsewhere(cid: str) -> bool:
    return cid in INTERNAL or cid.startswith(EXTENSION_PREFIXES)
