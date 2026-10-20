"""Catalog of voice commands for the "Commands" screen, built from the same tables the matcher uses
(core.nlp.commands.COMMAND_PATTERNS / CANON_SIMPLE), plus display metadata (commands_meta.META).

Each item: id, name, desc, cat, phrases (what to say), mode:
  'run'    - the UI may run it with a button (an example phrase without arguments that the matcher maps to this id);
  'confirm'- same, but destructive: the UI asks first and the core insists on confirm=true;
  'voice'  - needs a spoken argument or acts on the active window, so it is shown without a run button;
  'game'   - a voice command of a game profile (data/game_profiles): works in game mode while that game runs.
"""
from __future__ import annotations

import logging
import re

from .commands_meta import META
from .commands_meta_uk import CATEGORIES_UK, META_UK

_log = logging.getLogger(__name__)

# (key, title, hint) in display order
CATEGORIES = [
    ('assistant', 'Помощник', 'Время, погода, вопросы, почта'),
    ('timers', 'Таймеры и заметки', 'Напоминания, диктовка, перевод'),
    ('media', 'Видео и музыка', 'YouTube, пауза, запись экрана'),
    ('sound', 'Звук и экран', 'Громкость, яркость, скриншоты'),
    ('apps', 'Приложения и окна', 'Открыть, закрыть, раскладка'),
    ('files', 'Файлы и папки', 'Найти, открыть последний, создать'),
    ('pc', 'Компьютер', 'Питание, сеть, диски, уборка'),
    ('games', 'Игры и мышь', 'Игровой режим, охрана, мышь'),
    ('ui', 'Сам Jarvis', 'Окна и настройки ассистента'),
]
_CAT_IDS = {
    'assistant': 'wake listen_on listen_off show_help open_deck how_are_you praise thanks qa_search time_now today_summary calendar_next calendar_add weather set_weather_city currency_rate calc nasa_apod song_id jarvis_exit inbox_unread mail_compose',
    'timers': 'timer_set timer_add timer_sub timer_cancel timer_status reminder cancel_reminder note_save dictation_on ocr_screen ocr_last translate translate_speech work_session',
    'media': 'cinema_watch cinema_continue cinema_when cinema_mode cinema_later cinema_later_list cinema_now cinema_left cinema_seek play_yt open_youtube yt_channel yt_bwd yt_fwd yt_full yt_next yt_prev yt_last_watched media_pause media_pause_browser media_pause_youtube media_play media_play_browser media_play_youtube open_last_video download_video save_video open_saved start_video stop_video',
    'sound': 'vol_down vol_up vol_max vol_mute vol_unmute vol_set vol_zero audio_switch brightness_down brightness_up brightness_set screenshot screenshot_site screenshot_terminal move_monitor',
    'files': 'create_folder create_word_doc delete_file delete_folder paste_file explorer_go_up explorer_goto find_doc find_file find_sheet recent_any recent_any_prev recent_doc recent_doc_prev recent_pres recent_pres_prev recent_sheet recent_sheet_prev empty_trash',
    'pc': 'shutdown shutdown_timer restart lock_pc sleep_pc cancel_timer economy_on economy_off system_cleanup system_cleanup_deep system_status system_specs internet_speed my_ip health_disks wifi_toggle bluetooth_toggle bt_connect bt_disconnect bt_list keyboard_lock keyboard_unlock',
    'games': 'game_mode_on game_mode_off exit_game guard_on guard_off mouse_click mouse_dblclick mouse_down mouse_faster mouse_left mouse_right mouse_slower mouse_up',
    'ui': 'show_hud min_win open_settings open_keybinds open_extensions open_perf restart_jarvis reactor_color_amber reactor_color_cyan reactor_color_green reactor_color_magenta reactor_color_red reactor_color_white reactor_glitch reactor_pulse reactor_reset',
}
_CAT_OF = {cid: cat for cat, ids in _CAT_IDS.items() for cid in ids.split()}
_CAT_PREFIX = (('open_', 'apps'), ('close_', 'apps'), ('win_', 'apps'), ('clip_', 'apps'), ('ps_', 'apps'), ('figma_', 'apps'), ('yt_', 'media'), ('media_', 'media'), ('vol_', 'sound'), ('recent_', 'files'))
_APPS_EXTRA = 'max_win min_all min_other_win unmin_win close_win context_close change_layout press_enter undo redo select_all git_commit google_search open_browser open_task_manager close_tab close_all_tabs close_all_win close_other_win'.split()
_CAT_OF.update({cid: 'apps' for cid in _APPS_EXTRA})

# Destructive or hard to undo: the UI asks first, the core refuses without confirm.
CONFIRM_IDS = set('shutdown shutdown_timer restart sleep_pc restart_jarvis jarvis_exit empty_trash delete_file delete_folder system_cleanup system_cleanup_deep git_commit close_win close_all_win close_all_tabs close_other_win exit_game keyboard_lock wifi_toggle bluetooth_toggle bt_disconnect'.split())
# Act on the focused window or need a spoken target: running them from the Jarvis window would hit the wrong thing.
VOICE_ONLY_IDS = set('clip_copy clip_cut clip_paste clip_paste_last clip_paste_prev clip_history undo redo select_all press_enter context_close close_tab close_all_tabs yt_bwd yt_fwd yt_full yt_next yt_prev mouse_click mouse_dblclick mouse_down mouse_faster mouse_left mouse_right mouse_slower mouse_up figma_auto_layout figma_group ps_brush ps_eraser ps_save win_snap_left win_snap_right max_win min_win move_monitor paste_file explorer_go_up dictation_on translate translate_speech note_save screenshot_site screenshot_terminal download_video save_video find_doc find_file find_sheet create_folder create_word_doc delete_file delete_folder media_play_youtube media_pause_youtube media_play_browser media_pause_browser'.split())
HIDDEN_IDS = {'system_insult'}
# A first-visit shortlist: things worth trying right away.
STARTERS = 'timer_set weather vol_set play_yt song_id reminder google_search screenshot game_mode_on open_browser'.split()

# Extensions that must be installed for some general commands to work (ids from data/extensions_catalog.json).
_NEEDS_PREFIX = (('ps_', 'feature_photoshop_voice'), ('figma_', 'feature_figma_voice'), ('guard_', 'feature_guard_cam'))
_NEEDS_IDS = {'inbox_unread': 'feature_mail_client', 'mail_compose': 'feature_mail_client', 'calendar_next': 'feature_calendar_ics', 'calendar_add': 'feature_calendar_ics', 'today_summary': 'feature_calendar_ics'}
# game profile file stem -> extension id (to tell whether the profile is installed)
_GAME_EXT = {'euro_truck_simulator_2': 'game_ets2', 'farming_simulator_22': 'game_fs22', 'hogwarts_legacy': 'game_hogwarts', 'planetbase': 'game_planetbase'}
_PLACEHOLDER = re.compile(r'\{[^}]*\}|\[[^\]]*\]')
_MAX_PHRASES = 3
_MIXED_SCRIPT = re.compile(r'\b(?=\w*[a-z])(?=\w*[а-яё])\w+', re.I)   # typo variants like "etс" (latin + cyrillic in one word)


def _category(cid: str) -> str:
    cat = _CAT_OF.get(cid)
    if cat:
        return cat
    for prefix, c in _CAT_PREFIX:
        if cid.startswith(prefix):
            return c
    return 'assistant'


def _clean(p: str) -> str:
    return re.sub(r'\{N\}', '[число]', str(p)).strip()


def _all_phrases(example: str, patterns: list, canon: list) -> list[str]:
    seen, out = set(), []
    for p in [example] + list(patterns) + sorted(canon, key=len):
        p = _clean(p)
        key = p.lower()
        if p and key not in seen and not _MIXED_SCRIPT.search(p):
            seen.add(key)
            out.append(p)
    return out


def _interface_is_uk() -> bool:
    try:
        from core import i18n
        return i18n.get_language() == 'uk'
    except Exception:
        return False


def _ukrainian_first(phrases: list[str]) -> list[str]:
    """For the Ukrainian interface: phrases with Ukrainian letters first, those only Russian have last (the order inside each group is kept)."""
    def rank(p: str) -> int:
        return 0 if re.search(r'[іїєґ]', p, re.I) else 2 if re.search(r'[ыэъё]', p, re.I) else 1
    return sorted(phrases, key=rank)


def _display(all_phrases: list[str]) -> list[str]:
    """Up to _MAX_PHRASES variants; the same sentence with different numbers counts once, the placeholder form wins."""
    out, seen = [], set()
    for p in sorted(all_phrases, key=lambda x: 0 if '[' in x else 1):   # stable: placeholder forms first
        key = re.sub(r'\d+|\[[^\]]*\]', '#', p.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    order = {p: i for i, p in enumerate(all_phrases)}
    return sorted(out, key=lambda x: order[x])[:_MAX_PHRASES]


def _needs(cid: str) -> str | None:
    if cid in _NEEDS_IDS:
        return _NEEDS_IDS[cid]
    return next((ext for prefix, ext in _NEEDS_PREFIX if cid.startswith(prefix)), None)


def _extensions() -> dict[str, dict]:
    """{ext id: {name, installed}} from the extension manager; empty when it is unavailable."""
    try:
        from core.extensions import ExtensionManager
        mgr = ExtensionManager()
        return {e['id']: {'name': e.get('name', e['id']), 'installed': mgr.is_installed(e['id'])} for e in mgr._catalog}
    except Exception:
        _log.debug('extension catalog unavailable', exc_info=True)
        return {}


def game_catalog(exts: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Voice commands of the game profiles (ru or uk files, like the keybind editor): (groups, items)."""
    import json
    from pathlib import Path
    try:
        from config_pack.config import get_data_dir
        from core import i18n
        is_uk = i18n.get_language() == 'uk'
        folder = Path(get_data_dir('game_profiles'))
        files = sorted(folder.glob('*.json'))
    except Exception:
        _log.debug('game profiles unavailable', exc_info=True)
        return [], []
    groups, items = [], []
    for f in files:
        if f.stem.endswith('_uk') != is_uk:
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
        except Exception:
            continue
        stem = f.stem[:-3] if f.stem.endswith('_uk') else f.stem
        key = 'game:' + stem
        ext = exts.get(_GAME_EXT.get(stem, ''))
        count = 0
        for sp in data.get('spells') or []:
            name = str(sp.get('name') or '').strip()
            variants = []
            for v in sp.get('variants') or []:
                v = str(v).strip()
                if v and v.lower() not in {x.lower() for x in variants}:
                    variants.append(v)
            if not name or not variants:
                continue
            items.append({'id': f'{key}:{count}', 'name': name, 'desc': '', 'cat': key, 'phrases': variants[:_MAX_PHRASES], 'more': max(0, len(variants) - _MAX_PHRASES), 'mode': 'game', 'try': None})
            count += 1
        if count:
            groups.append({'key': key, 'title': str(data.get('game') or stem).removesuffix('_uk'), 'count': count, 'installed': None if ext is None else ext['installed']})
    return groups, items


def build_catalog() -> dict:
    """Builds the catalog payload. Needs core.nlp.commands (already loaded in the running app)."""
    from core.nlp.commands import CANON_SIMPLE, COMMAND_PATTERNS
    patterns = {p['id']: p.get('patterns', []) for p in COMMAND_PATTERNS}
    canon: dict[str, list] = {}
    for phrase, cid in CANON_SIMPLE.items():
        canon.setdefault(cid, []).append(phrase)
    items = []
    uk = _interface_is_uk()
    for cid in sorted(set(patterns) | set(canon)):
        if cid in HIDDEN_IDS:
            continue
        name, desc, example = META.get(cid, (cid.replace('_', ' ').capitalize(), '', ''))
        if uk and cid in META_UK:
            name, desc = META_UK[cid]
        every = _all_phrases(example, patterns.get(cid, []), canon.get(cid, []))
        if uk:
            every = _ukrainian_first(every)
        phrases = _display(every)
        mode = 'voice' if cid in VOICE_ONLY_IDS else 'confirm' if cid in CONFIRM_IDS else 'run'
        items.append({'id': cid, 'name': name, 'desc': desc, 'cat': _category(cid), 'phrases': phrases, 'mode': mode, '_every': every})
    # a command is runnable only if some phrase without arguments really resolves to it through the matcher
    from core.nlp.commands import match_command
    for it in items:
        every = it.pop('_every')
        it['try'] = None
        if it['mode'] != 'voice':
            it['try'] = run_phrase_for(every, it['id'], match_command)
            if it['try'] is None:
                it['mode'] = 'voice'
    exts = _extensions()
    for it in items:
        need = _needs(it['id'])
        if need and need in exts:
            it['needs'] = need
    groups, game_items = game_catalog(exts)
    return {'categories': [{'key': k, 'title': (CATEGORIES_UK.get(k) or (t, h))[0] if uk else t, 'hint': (CATEGORIES_UK.get(k) or (t, h))[1] if uk else h} for k, t, h in CATEGORIES], 'items': items + game_items, 'games': groups, 'ext': {k: v for k, v in exts.items() if k in {i.get('needs') for i in items}},
            'starters': [s for s in STARTERS if any(i['id'] == s for i in items)]}


def run_phrase_for(phrases: list[str], cid: str, match_command) -> str | None:
    """First phrase without placeholders that the matcher resolves to ``cid``."""
    for p in phrases:
        if _PLACEHOLDER.search(p):
            continue
        try:
            if match_command(p) == cid:
                return p
        except Exception:
            _log.debug('match_command failed for %r', p, exc_info=True)
    return None
