import time

import pytest

from actions import scenarios as sc


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(sc.settings_io, 'read', lambda: dict(data))
    monkeypatch.setattr(sc.settings_io, 'update', lambda ch: data.update(ch) or True)
    return data


def test_save_validates_and_keeps_names_and_phrases_unique(store):
    sc.save('', 'Работа', 'режим работы', 'открой хром\nгромкость тридцать')
    assert store['scenarios'][0]['steps'] == ['открой хром', 'громкость тридцать']
    for args, code in ((('', '', 'x', 'a'), 'required'), (('', 'A', 'x', ''), 'bad_steps'), (('', 'раБота', 'другая', 'a'), 'exists'),
                       (('', 'B', 'Режим, работы!', 'a'), 'exists'), (('', 'C', 'x', ['a'] * 13), 'bad_steps')):
        with pytest.raises(sc.ScenarioError) as e:
            sc.save(*args)
        assert e.value.code == code
    sc.save('Работа', 'Работа', 'режим работы', 'a')       # editing keeps its own name and phrase
    assert [s['steps'] for s in sc.load()] == [['a']]
    assert sc.delete('Работа') == [] and store['scenarios'] == []


def test_match_whole_phrase_with_few_extra_words_or_close_spelling(store):
    sc.save('', 'Кино', 'режим кино', 'выключи свет')
    sc.save('', 'Работа', 'режим работы', 'открой хром')
    assert sc.match('Джарвис, режим работы')['name'] == 'Работа'
    assert sc.match('включи режим кино')['name'] == 'Кино'
    assert sc.match('режим кина')['name'] == 'Кино'
    assert sc.match('включи режим работы и поставь таймер на десять минут пожалуйста') is None
    assert sc.match('открой браузер') is None and sc.match('') is None


def test_run_executes_steps_in_order_with_pause_and_confirms(store, monkeypatch):
    calls = []
    monkeypatch.setattr(sc.time, 'sleep', lambda s: calls.append(('sleep', s)))

    class H:
        silent_mode = False

        def handle(self, c, s):
            calls.append((c, s))

        def play_response(self, kind, override_silent=False):
            calls.append(('say', kind, override_silent))

    scenario = {'name': 'N', 'phrase': 'p', 'steps': ['громче', 'пауза 3', 'пауза 99', 'тише']}
    table = {'громче': [('vol_up', 'громче')], 'тише': [('vol_down', 'тише'), ('wake', 'x')]}
    h = H()
    sc.run(h, scenario, lambda t: table.get(t, []))
    for _ in range(200):
        if ('say', 'confirm', True) in calls:
            break
        time.sleep(0.01)
    assert [c for c in calls if c[0] != 'sleep'] == [('vol_up', 'громче'), ('vol_down', 'тише'), ('say', 'confirm', True)]
    assert ('sleep', 3) in calls and ('sleep', 10) in calls and h.silent_mode is False
