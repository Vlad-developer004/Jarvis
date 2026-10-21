"""data/game_profiles/*.json: every profile must be internally consistent, the RU and UK copies must not drift apart, and the runtime pieces the
profiles rely on ("when" steps, "assign" spells, "alert_sound") must do what the profiles expect."""
import glob
import json
import os
import time
from collections import defaultdict

import pytest

from actions.game_input_parts import runtime
from actions.keysend_parts.keymap import _STR_TO_VK

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FILES = sorted(glob.glob(os.path.join(ROOT, 'data', 'game_profiles', '*.json')))
WHEN_FIELDS = {'engineEnabled', 'parkBrake', 'lightsHazards', 'lightsBeamHigh', 'lightsBeamLow'}
ACTIONS = ('key', 'keys', 'mouse', 'sequence', 'lights_target', 'wiper_target', 'response', 'telemetry_action', 'binding', 'hold_start', 'hold_end', 'assign')


def _profile(name):
    with open(os.path.join(ROOT, 'data', 'game_profiles', name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def _ids(paths):
    return [os.path.basename(p) for p in paths]


def _steps(spell):
    return [st for st in spell.get('sequence') or [] if isinstance(st, dict)]


def _keys(spell):
    out = [spell['key']] if spell.get('key') not in (None, '', 'MACRO') else []
    out += spell.get('keys') or []
    out += [spell[k] for k in ('hold_start', 'hold_end') if spell.get(k)]
    for st in _steps(spell):
        out += ([st['key']] if st.get('key') else []) + list(st.get('keys') or [])
    return out


def _sig(spell):
    return json.dumps({k: v for k, v in spell.items() if k not in ('name', 'variants', 'response')}, sort_keys=True, ensure_ascii=False)


@pytest.mark.parametrize('path', FILES, ids=_ids(FILES))
def test_profile_is_consistent(path):
    data = _profile(os.path.splitext(os.path.basename(path))[0])
    bindings, spells = data.get('bindings', {}), data['spells']
    owner = defaultdict(set)
    for s in spells:
        norm = [v.strip().lower() for v in s['variants']]
        assert len(norm) == len(set(norm)), f"{s['name']}: a variant is listed twice"
        for v in norm:
            owner[v].add(s['name'])
        refs = ([s['binding']] if s.get('binding') else []) + [st['binding'] for st in _steps(s) if 'binding' in st]
        assert all(r in bindings for r in refs), f"{s['name']}: binding {refs} is not in the profile's bindings"
        assert all(str(k).lower() in _STR_TO_VK for k in _keys(s)), f"{s['name']}: unknown key name in {_keys(s)}"
        assert all(set(st.get('when', {})) <= WHEN_FIELDS for st in _steps(s)), f"{s['name']}: unknown telemetry field in a step condition"
        assert any(s.get(k) for k in ACTIONS), f"{s['name']}: no action, the loader would drop it"
    assert not {v: sorted(n) for v, n in owner.items() if len(n) > 1}, 'the same spoken phrase is listed in several spells'
    for n, k in bindings.items():
        assert str(k).lower() in _STR_TO_VK, f'binding {n}: unknown key {k}'


def test_every_ets2_telemetry_action_has_a_handler():
    with open(os.path.join(ROOT, 'core', 'engine', 'ets2_commands.py'), encoding='utf-8') as f:
        src = f.read()
    for name in ('euro_truck_simulator_2', 'euro_truck_simulator_2_uk'):
        for s in _profile(name)['spells']:
            if s.get('telemetry_action'):
                assert f"'{s['telemetry_action']}'" in src, f"{s['name']}: nothing handles {s['telemetry_action']}"


@pytest.mark.parametrize('game', ['euro_truck_simulator_2', 'farming_simulator_22', 'hogwarts_legacy'])
def test_uk_copy_has_the_same_commands_as_the_ru_profile(game):
    ru, uk = _profile(game), _profile(game + '_uk')
    assert uk.get('bindings') == ru.get('bindings')
    assert [_sig(s) for s in uk['spells']] == [_sig(s) for s in ru['spells']]
    for r, u in zip(ru['spells'], uk['spells']):    # a UK spell may add phrases but never loses the RU ones
        assert set(r['variants']) <= set(u['variants']), f"{r['name']}: the UK copy lost RU phrases"


def test_ets2_engine_commands_never_toggle_blindly():
    spells = {s['name']: s for s in _profile('euro_truck_simulator_2')['spells']}
    for name in ('Запуск двигателя', 'Остановка двигателя', 'Подготовка к рейсу', 'Продолжить движение'):
        engine = [st for st in _steps(spells[name]) if st.get('binding') == 'engine']
        assert len(engine) == 1 and 'engineEnabled' in engine[0].get('when', {}), f'{name}: the engine key must be pressed once, and only when needed'
    assert spells['Запуск двигателя']['sequence'][0]['when'] == {'engineEnabled': False}
    assert spells['Остановка двигателя']['sequence'][0]['when'] == {'engineEnabled': True}


def test_ets2_light_flash_and_rain_mode_use_sensible_lights():
    spells = {s['name']: s for s in _profile('euro_truck_simulator_2')['spells']}
    assert [st.get('binding') for st in spells['Поморгать фарами']['sequence'] if 'binding' in st] == ['lights_high', 'lights_high']
    assert spells['Режим: Дождь']['lights_target'] == 'low_on'     # high beams in the rain blind oncoming drivers


# ---- runtime pieces the profiles rely on ----
@pytest.fixture
def pressed(monkeypatch):
    log = []
    monkeypatch.setattr(runtime.keysend, 'key_down', lambda k: log.append(('down', k)))
    monkeypatch.setattr(runtime.keysend, 'key_up', lambda k: log.append(('up', k)))
    monkeypatch.setattr(runtime, 'press_robust', lambda k, **kw: log.append(('press', k)))
    monkeypatch.setattr(runtime.time, 'sleep', lambda s: None)
    return log


def _telemetry(monkeypatch, frame):
    import actions.ets2_telemetry as tel
    monkeypatch.setattr(tel, 'get', lambda: frame)


def test_a_step_with_when_runs_only_in_that_state(monkeypatch, pressed):
    step = {'key': 'e', 'hold': 0.1, 'when': {'engineEnabled': False}}
    _telemetry(monkeypatch, {'engineEnabled': True})
    runtime._execute_sequence([step])
    assert pressed == []                                     # the engine is already running: do not toggle it off
    _telemetry(monkeypatch, {'engineEnabled': False})
    runtime._execute_sequence([step])
    assert pressed == [('down', 'e'), ('up', 'e')]


def test_a_step_with_when_runs_when_the_state_is_unknown(monkeypatch, pressed):
    _telemetry(monkeypatch, None)
    runtime._execute_sequence([{'key': 'e', 'when': {'engineEnabled': False}}])
    assert pressed == [('press', 'e')]


@pytest.fixture
def one_entry(monkeypatch):
    spoken = []
    monkeypatch.setattr(runtime, '_speak_response', spoken.append)
    monkeypatch.setattr(runtime, '_last_cast', {})

    def put(**kw):
        runtime._last_cast.clear()
        runtime._flat[:] = [('x', {'name': 'Спелл', 'variants': ['x'], **kw}, 'x', 1)]
    yield put, spoken
    runtime._flat[:] = []


def test_an_unassigned_spell_says_so_instead_of_staying_silent(one_entry, pressed):
    put, spoken = one_entry
    put(assign=True)
    result = runtime.cast_command('x')
    deadline = time.monotonic() + 5     # the line is spoken from a daemon thread; a loaded machine can take over a second
    while not spoken and time.monotonic() < deadline:
        time.sleep(0.01)
    assert result == (True, 'Спелл', None)
    assert spoken and 'не назначено' in spoken[0]
    assert not pressed


def test_the_red_alert_sound_belongs_to_the_spell_not_to_key_3(one_entry, pressed, monkeypatch):
    put, _ = one_entry
    played = []
    import core.speech.sound as sound
    monkeypatch.setattr(sound, 'play_alert_sound', played.append)
    put(key='3')
    runtime.cast_command('x')
    assert played == []                                      # "Вид сверху" (key 3) in ETS2 used to play the red alert
    put(key='3', alert_sound='red_alert')
    runtime.cast_command('x')
    assert played == ['red_alert']
