import json
from pathlib import Path

import pytest

from ui_next import bridge
from ui_next.bridge import profiles

ETS = {
    'game': 'Euro Truck Simulator 2',
    'bindings': {'engine': 'e', 'horn': 'h'},
    'spells': [
        {'name': 'Запуск двигателя', 'variants': ['заведи'], 'sequence': [{'binding': 'engine'}, {'wait': 0.8}, {'binding': 'engine'}]},
        {'name': 'Камера (вид)', 'variants': ['камера'], 'key': '8'},
        {'name': 'Ручник', 'variants': ['ручник'], 'key': 'space', 'sequence': [{'key': 'MACRO'}]},
        {'name': 'Мышь', 'variants': ['клик'], 'mouse': 'left'},
        {'name': 'Круиз', 'variants': ['круиз'], 'telemetry_action': 'cruise_set'},
    ],
}
HOG = {
    'game': 'Hogwarts Legacy',
    'spells': [{'name': 'Ревелио', 'variants': ['ревелио'], 'key': 'r'}, {'name': 'Протего', 'variants': ['протего']}, {'name': 'Выстрел', 'variants': ['бей'], 'mouse': 'left'}],
}


@pytest.fixture
def prof(tmp_path, monkeypatch):
    for name, d in (('euro_truck_simulator_2', ETS), ('hogwarts_legacy', HOG)):
        (tmp_path / f'{name}.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    import actions.game_input as gi
    monkeypatch.setattr(gi, 'PROFILES_DIR', Path(tmp_path))
    monkeypatch.setattr(profiles, '_lang_uk', lambda: False)
    monkeypatch.setattr(profiles, '_installed_ids', lambda: {'game_ets2', 'game_hogwarts'})
    return tmp_path


def _saved(prof, stem='euro_truck_simulator_2'):
    return json.loads((prof / f'{stem}.json').read_text(encoding='utf-8'))


def test_list_and_get(prof):
    assert [g['short'] for g in profiles.list_games()] == ['ETS 2', 'HOGWARTS']
    d = profiles.get_game('Euro Truck Simulator 2')
    ids = {r['id']: r for r in d['rows']}
    assert ids['b:engine']['key'] == 'e' and ids['b:engine']['label'] == 'Двигатель'
    assert ids['s:1']['label'] == 'Камера' and ids['s:1']['key'] == '8'     # direct-key spell, bracket text trimmed
    assert ids['s:2']['macro'] is True                                      # key + macro sequence
    assert 's:3' not in ids and 's:4' not in ids                            # mouse and telemetry-only entries are not key rows
    assert [m['name'] for m in d['macros']] == ['Запуск двигателя']


def test_set_key_validates_and_drops_macro(prof):
    assert profiles.set_key('Euro Truck Simulator 2', 'b:engine', 'f5') == {'ok': True}
    assert _saved(prof)['bindings']['engine'] == 'f5'
    assert profiles.set_key('Euro Truck Simulator 2', 'b:engine', 'ctrl+alt+del;')['error'] == 'bad_key'
    assert profiles.set_key('Euro Truck Simulator 2', 's:2', 'x') == {'ok': True}
    assert 'sequence' not in _saved(prof)['spells'][2] and _saved(prof)['spells'][2]['key'] == 'x'
    assert profiles.set_key('Euro Truck Simulator 2', 'b:engine', '') == {'ok': True} and _saved(prof)['bindings']['engine'] == ''
    assert profiles.set_key('Euro Truck Simulator 2', 'b:nope', 'a')['error'] == 'unknown_row'
    assert profiles.set_key('No Game', 'b:engine', 'a')['error'] == 'unknown_game'


def test_macro_roundtrip_and_validation(prof):
    g = 'Euro Truck Simulator 2'
    got = profiles.macro_get(g, 0)
    assert got['sequence'][0] == {'binding': 'engine'}
    seq = [{'binding': 'engine'}, {'wait': 99}, {'key': 'F', 'hold': 0.2}, {'wait': 1, '_disabled': True}]
    assert profiles.macro_save(g, 0, seq, ['Заведи', ' ']) == {'ok': True}
    saved = _saved(prof)['spells'][0]
    assert saved['sequence'] == [{'binding': 'engine'}, {'wait': 60.0}, {'key': 'f', 'hold': 0.2}, {'wait': 1.0, '_disabled': True}]
    assert saved['variants'] == ['заведи']
    assert profiles.macro_save(g, 0, [{'binding': 'rocket'}])['error'] == 'bad_sequence'
    assert profiles.macro_save(g, 0, [{'key': 'a b c'}])['error'] == 'bad_sequence'
    assert profiles.macro_save(g, 0, 'x')['error'] == 'bad_sequence'


def test_macro_create_and_delete(prof):
    g = 'Euro Truck Simulator 2'
    assert profiles.macro_create(g, ' ', [], '')['error'] == 'no_name'
    res = profiles.macro_create(g, 'Подготовь тягач', ['Заведи', 'поехал'], 'engine')
    assert res['ok'] and _saved(prof)['spells'][res['idx']] == {'name': 'Подготовь тягач', 'variants': ['заведи', 'поехал'], 'sequence': [{'binding': 'engine'}]}
    assert profiles.macro_delete(g, res['idx']) == {'ok': True}
    assert all(s['name'] != 'Подготовь тягач' for s in _saved(prof)['spells'])


def test_hogwarts_grid_moves_spells_between_slots(prof):
    g = 'Hogwarts Legacy'
    assert profiles.grid_set(g, 1, 1, 'Протего') == {'ok': True}
    assert profiles.grid_set(g, 2, 3, 'Протего') == {'ok': True}              # same spell, another slot
    d = profiles.get_game(g)
    assert d['grid']['2']['3'] == 'Протего' and d['grid']['1'] == {}
    assert profiles.grid_set(g, 2, 3, '—') == {'ok': True} and profiles.get_game(g)['grid']['2'] == {}
    assert profiles.grid_set(g, 5, 1, 'Протего')['error'] == 'bad_slot'
    assert profiles.grid_set(g, 1, 1, 'Выстрел')['error'] == 'unknown_spell'   # mouse actions cannot take a slot
    assert profiles.grid_set('Euro Truck Simulator 2', 1, 1, 'Ручник')['error'] == 'unknown_game'


def test_command_routing(prof):
    assert bridge.run_command('profile', {'op': 'games'})['ok'] is True
    assert bridge.run_command('profile', {'op': 'get', 'game': 'Nope'}) == {'ok': False, 'error': 'unknown_game'}
    assert bridge.run_command('profile', {'op': 'zzz'})['error'] == 'bad_op'
