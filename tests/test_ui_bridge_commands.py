import threading
import time

import pytest

from ui_next import bridge
from ui_next.bridge import catalog as cat


@pytest.fixture(scope='module')
def built():
    return cat.build_catalog()


def general(built):
    return [i for i in built['items'] if i['mode'] != 'game']


def test_catalog_items_are_well_formed(built):
    ids = [i['id'] for i in built['items']]
    assert len(ids) == len(set(ids)) > 150
    keys = {c['key'] for c in built['categories']}
    for it in general(built):
        assert it['name'] and it['phrases'], it['id']
        assert it['cat'] in keys, it['id']
        assert it['mode'] in ('run', 'confirm', 'voice')


def test_every_command_has_a_real_name(built):
    # ids without display metadata would show as "Vol set"; all current ids are covered
    assert [i['id'] for i in general(built) if i['id'] not in cat.META] == []


def test_destructive_commands_never_run_without_confirm(built):
    by_id = {i['id']: i for i in built['items']}
    for cid in cat.CONFIRM_IDS:
        if cid in by_id:
            assert by_id[cid]['mode'] in ('confirm', 'voice'), cid


def test_try_phrase_resolves_to_the_same_command(built):
    from core.nlp.commands import match_command
    for it in general(built):
        if it['mode'] != 'voice':
            assert match_command(it['try']) == it['id'], it['id']
        else:
            assert it['try'] is None


def test_insult_command_is_not_listed(built):
    assert 'system_insult' not in {i['id'] for i in built['items']}


def test_display_phrases_skip_mixed_script_typos_and_duplicate_numbers(built):
    by_id = {i['id']: i for i in built['items']}
    assert not any(cat._MIXED_SCRIPT.search(p) for i in general(built) for p in i['phrases'])
    vol = by_id['vol_set']['phrases']
    assert sum('громкость на' in p for p in vol) == 1


class FakeHandler:
    def __init__(self):
        self.calls = []
        self.done = threading.Event()

    def handle(self, cid, text):
        self.calls.append((cid, text))
        self.done.set()


@pytest.fixture
def wired(monkeypatch, built):
    h = FakeHandler()
    monkeypatch.setattr(bridge, '_handler', h)
    monkeypatch.setattr(bridge, '_catalog', built)
    monkeypatch.setattr(bridge, '_hub', None)
    return h


def test_run_executes_the_catalog_phrase_through_the_handler(wired):
    r = bridge.run_command('run', {'id': 'weather'})
    assert r == {'ok': True, 'phrase': 'какая погода'}
    assert wired.done.wait(2) and wired.calls == [('weather', 'какая погода')]


def test_run_ignores_free_text_from_the_ui(wired):
    r = bridge.run_command('run', {'id': 'weather', 'text': 'rm -rf /', 'phrase': 'format c:'})
    assert r['phrase'] == 'какая погода'
    assert wired.done.wait(2) and wired.calls[0][1] == 'какая погода'


def test_run_unknown_or_voice_only_is_refused(wired):
    assert bridge.run_command('run', {'id': 'no_such'}) == {'ok': False, 'error': 'not_runnable'}
    assert bridge.run_command('run', {'id': 'undo'}) == {'ok': False, 'error': 'not_runnable'}
    assert wired.calls == []


def test_run_destructive_requires_explicit_confirm(wired):
    assert bridge.run_command('run', {'id': 'shutdown'}) == {'ok': False, 'error': 'confirm_required'}
    assert bridge.run_command('run', {'id': 'shutdown', 'confirm': 'yes'}) == {'ok': False, 'error': 'confirm_required'}
    assert wired.calls == []
    assert bridge.run_command('run', {'id': 'shutdown', 'confirm': True})['ok'] is True


def test_run_without_handler_or_catalog(monkeypatch, built):
    monkeypatch.setattr(bridge, '_catalog', built)
    monkeypatch.setattr(bridge, '_handler', None)
    assert bridge.run_command('run', {'id': 'weather'}) == {'ok': False, 'error': 'no_handler'}
    monkeypatch.setattr(bridge, '_catalog', None)
    assert bridge.run_command('run', {'id': 'weather'}) == {'ok': False, 'error': 'not_runnable'}


def test_mic_command_sets_ignore_mode_under_the_state_lock(monkeypatch):
    from core.system import app_state
    monkeypatch.setattr(app_state, 'ignore_mode', False)
    assert bridge.run_command('mic', {'on': False}) == {'ok': True, 'muted': True}
    assert app_state.ignore_mode is True
    assert bridge.run_command('mic', {'on': True}) == {'ok': True, 'muted': False}
    assert app_state.ignore_mode is False


def test_game_profiles_become_game_items(tmp_path, monkeypatch):
    import json

    import config_pack.config as cfg
    (tmp_path / 'demo_game.json').write_text(json.dumps({'game': 'Demo Game', 'spells': [
        {'name': 'Запуск двигателя', 'variants': ['заведи', 'Заведи', 'запусти', 'мотор', 'двигатель'], 'key': 'e'},
        {'name': 'Пустая', 'variants': []},
    ]}), encoding='utf-8')
    (tmp_path / 'demo_game_uk.json').write_text(json.dumps({'game': 'Demo Game_uk', 'spells': [{'name': 'x', 'variants': ['y']}]}), encoding='utf-8')
    monkeypatch.setattr(cfg, 'get_data_dir', lambda name: str(tmp_path))
    from core import i18n
    monkeypatch.setattr(i18n, 'get_language', lambda: 'ru')
    groups, items = cat.game_catalog({})
    assert groups == [{'key': 'game:demo_game', 'title': 'Demo Game', 'count': 1, 'installed': None}]
    assert len(items) == 1 and items[0]['mode'] == 'game' and items[0]['try'] is None
    assert items[0]['phrases'] == ['заведи', 'запусти', 'мотор'] and items[0]['more'] == 1


def test_game_items_are_never_runnable(wired, built):
    games = [i for i in built['items'] if i['mode'] == 'game']
    assert games
    for it in games:
        assert it['try'] is None and it['cat'].startswith('game:')
    assert bridge.run_command('run', {'id': games[0]['id']}) == {'ok': False, 'error': 'not_runnable'}
    assert wired.calls == []


def test_extension_dependent_commands_are_marked(built):
    needs = {i['id']: i['needs'] for i in built['items'] if i.get('needs')}
    assert needs.get('ps_brush') == 'feature_photoshop_voice'
    assert needs.get('guard_on') == 'feature_guard_cam'


def test_timer_command_validates_and_drives_the_game_timer(monkeypatch):
    import types

    from actions import game_timer
    calls = []
    monkeypatch.setattr(game_timer, 'set_timer', lambda secs, label, speak, hud=None: calls.append(('start', secs, label)) or 'x')
    monkeypatch.setattr(game_timer, 'add_time', lambda secs: calls.append(('add', secs)) or True)
    monkeypatch.setattr(game_timer, 'cancel_timer', lambda: calls.append(('cancel',)) or True)
    monkeypatch.setattr(bridge, '_handler', types.SimpleNamespace(speak=lambda t: None))
    assert bridge.run_command('timer', {'op': 'start', 'seconds': 600, 'label': ' чай '}) == {'ok': True}
    assert bridge.run_command('timer', {'op': 'add', 'seconds': 60})['ok'] is True
    assert bridge.run_command('timer', {'op': 'cancel'})['ok'] is True
    assert calls == [('start', 600, 'чай'), ('add', 60), ('cancel',)]
    for bad in (0, -5, 10 ** 7, 'abc', None):
        assert bridge.run_command('timer', {'op': 'start', 'seconds': bad})['ok'] is False
    assert bridge.run_command('timer', {'op': 'nope', 'seconds': 5})['ok'] is False


def test_reminder_command_schedules_and_cancels(monkeypatch):
    from features import reminder
    seen = []
    monkeypatch.setattr(reminder, 'schedule_reminder', lambda secs, msg, speak, hud=None: seen.append((secs, msg)))
    assert bridge.run_command('reminder', {'seconds': 300, 'text': ' позвонить '}) == {'ok': True}
    assert seen == [(300, 'позвонить')]
    assert bridge.run_command('reminder', {'seconds': 300, 'text': '  '})['ok'] is False
    assert bridge.run_command('reminder', {'seconds': 0, 'text': 'a'})['ok'] is False
    assert bridge.run_command('reminder', {'op': 'cancel', 'id': 'x'})['ok'] is False
    assert bridge.run_command('reminder', {'op': 'cancel', 'id': 99999})['ok'] is False


def test_library_scan_payload_and_launch_by_id(monkeypatch):
    import types

    from features.gaming import scanner
    from ui_next.bridge import library
    games = [scanner.GameInfo('Old Game', 'Steam', 'steam://a', 100), scanner.GameInfo('New Game', 'Epic Games', 'epic://b', 900), scanner.GameInfo('New Game', 'Epic Games', 'epic://dup', 5)]
    monkeypatch.setattr(scanner, 'scan_all_games', lambda force=False: games)
    rows = library.scan()
    assert [r['name'] for r in rows] == ['New Game', 'Old Game']          # duplicates folded, most recently played first
    gid = rows[0]['id']
    launched = []
    monkeypatch.setattr(bridge, '_handler', types.SimpleNamespace(_launch_game_engine=lambda g: launched.append(g.name)))
    assert bridge.run_command('game_launch', {'id': gid}) == {'ok': True, 'name': 'New Game'}
    assert launched == ['New Game']
    assert bridge.run_command('game_launch', {'id': 'nope'})['ok'] is False
    assert bridge.run_command('game_launch', {'id': r'C:\Windows\notepad.exe'})['ok'] is False   # only library ids, never paths
    assert launched == ['New Game']


def test_library_scan_async_publishes_and_refuses_parallel_scan(monkeypatch):
    import threading

    from ui_next.bridge import library
    gate, done, out = threading.Event(), threading.Event(), []
    monkeypatch.setattr(library, 'scan', lambda force=False: gate.wait(2) and [])
    monkeypatch.setattr(library, '_scanning', False)
    assert library.scan_async(lambda t, p: (out.append((t, p)), done.set())) is True
    assert library.scan_async(lambda t, p: None) is False
    gate.set()
    assert done.wait(3) and out == [('library', {'games': [], 'scanning': False})]


def test_extension_command_installs_simple_and_refuses_setup_flows(monkeypatch):
    from core.extensions import ExtensionManager
    from ui_next.bridge import extensions as ext
    calls = []
    mgr = ExtensionManager()
    monkeypatch.setattr(mgr, 'install', lambda i: calls.append(('install', i)) or True)
    monkeypatch.setattr(mgr, 'uninstall', lambda i: calls.append(('uninstall', i)) or True)
    monkeypatch.setattr(ext, 'publish_extensions', lambda publish, only_if_changed=False: None)
    monkeypatch.setattr(bridge, '_publish_catalog_async', lambda: None)
    assert bridge.run_command('extension', {'id': 'game_hogwarts', 'on': True}) == {'ok': True}
    assert bridge.run_command('extension', {'id': 'game_hogwarts', 'on': False}) == {'ok': True}
    assert calls == [('install', 'game_hogwarts'), ('uninstall', 'game_hogwarts')]
    for needs_setup in ('feature_mail_client', 'game_ets2', 'game_planetbase', 'feature_calendar_ics', 'feature_guard_cam', 'nope'):
        assert bridge.run_command('extension', {'id': needs_setup, 'on': True}) == {'ok': False, 'error': 'needs_setup'}
    assert len(calls) == 2


def test_extensions_payload_matches_the_catalog():
    from ui_next.bridge.extensions import SIMPLE, extensions_payload
    rows = extensions_payload()
    assert rows and all({'id', 'name', 'installed', 'simple', 'category'} <= set(r) for r in rows)
    assert {r['id'] for r in rows if r['simple']} == SIMPLE & {r['id'] for r in rows}
