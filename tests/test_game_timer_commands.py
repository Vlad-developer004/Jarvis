"""Tests for the timer sub-commands in core/handler/commands/game.py
(_timer_set/_timer_add/_timer_status/_timer_cancel) and handle_game_extra's
spell_list — previously untested. The game-launch/profile-activation
functions in this file (apply_game_profile, start_game_selection_flow,
launch_game_engine) have heavy OS/process side effects and are left for a
future pass; this covers the self-contained, easily-isolated timer logic,
including the label-extraction regex that strips duration words out of the
phrase to get the timer's free-text label.
"""
import core.handler.commands.game as game_cmd


class _Speaks(list):
    def __call__(self, text, *a, **k):
        self.append(text)


# ── handle_timer routing ──────────────────────────────────────────────────

def test_handle_timer_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(game_cmd._TIMER_ACTIONS, 'timer_cancel', lambda t: called.append(t))
    game_cmd.handle_timer(None, 'timer_cancel', 'отмени таймер')

    assert called == ['отмени таймер']


def test_timer_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(game_cmd._TIMER_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_TIMER_ACTIONS has non-existent intent keys: {unknown}'


# ── _timer_set ────────────────────────────────────────────────────────────

def test_timer_set_starts_timer_with_parsed_duration(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    captured = []
    monkeypatch.setattr('actions.game_timer.set_timer',
                         lambda secs, label, speak_fn, hud: captured.append((secs, label)) or '10 минут')

    game_cmd._timer_set('поставь таймер на 10 минут')

    assert captured
    secs, label = captured[0]
    assert secs == 600
    assert spoken and '10 минут' in spoken[-1]


def test_timer_set_extracts_label_from_remaining_text(monkeypatch):
    monkeypatch.setattr(game_cmd, 'speak', _Speaks())
    captured = []
    monkeypatch.setattr('actions.game_timer.set_timer',
                         lambda secs, label, speak_fn, hud: captured.append(label) or 'ok')

    game_cmd._timer_set('поставь таймер на 5 минут заварка чая')

    assert captured
    assert 'заварка' in captured[0] and 'чая' in captured[0]


def test_timer_set_without_parseable_duration_asks_instead_of_crashing(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.set_timer',
                         lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not be called')))

    game_cmd._timer_set('поставь таймер')

    assert spoken


# ── _timer_add ────────────────────────────────────────────────────────────

def test_timer_add_adds_parsed_duration(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    captured = []
    monkeypatch.setattr('actions.game_timer.add_time', lambda secs: captured.append(secs) or True)
    monkeypatch.setattr('actions.game_timer.get_status', lambda: 900)

    game_cmd._timer_add('добавь 5 минут')

    assert captured == [300]
    assert spoken


def test_timer_add_speaks_error_when_timer_not_running(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.add_time', lambda secs: False)

    game_cmd._timer_add('добавь 5 минут')

    assert spoken == ['Таймер не запущен.']


def test_timer_add_without_parseable_duration_does_not_call_add_time(monkeypatch):
    monkeypatch.setattr(game_cmd, 'speak', _Speaks())
    monkeypatch.setattr('actions.game_timer.add_time',
                         lambda secs: (_ for _ in ()).throw(AssertionError('must not be called')))

    game_cmd._timer_add('добавь ещё')


# ── _timer_status ─────────────────────────────────────────────────────────

def test_timer_status_no_timer_running(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.get_status', lambda: None)

    game_cmd._timer_status('сколько осталось')

    assert spoken == ['Таймер не запущен.']


def test_timer_status_under_a_minute(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.get_status', lambda: 45)

    game_cmd._timer_status('сколько осталось')

    assert spoken == ['Осталось меньше минуты.']


def test_timer_status_reports_minutes(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.get_status', lambda: 300)

    game_cmd._timer_status('сколько осталось')

    assert spoken and 'Осталось' in spoken[0]


# ── _timer_cancel ─────────────────────────────────────────────────────────

def test_timer_cancel_success(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.cancel_timer', lambda: True)

    game_cmd._timer_cancel('отмени таймер')

    assert spoken == ['Таймер отменён.']


def test_timer_cancel_when_none_running(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_timer.cancel_timer', lambda: False)

    game_cmd._timer_cancel('отмени таймер')

    assert spoken == ['Таймер не был запущен.']


# ── handle_game_extra: spell_list ──────────────────────────────────────────

def test_spell_list_speaks_spells_when_present(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_input.get_spell_list', lambda: ['Люмос', 'Экспеллиармус'])

    game_cmd.handle_game_extra(None, 'spell_list', 'какие у меня заклинания')

    assert spoken and 'Люмос' in spoken[0]


def test_spell_list_speaks_empty_message_when_none(monkeypatch):
    spoken = _Speaks()
    monkeypatch.setattr(game_cmd, 'speak', spoken)
    monkeypatch.setattr('actions.game_input.get_spell_list', lambda: [])

    game_cmd.handle_game_extra(None, 'spell_list', 'какие у меня заклинания')

    assert spoken == ['У вас нет активных заклинаний в этом профиле.']
