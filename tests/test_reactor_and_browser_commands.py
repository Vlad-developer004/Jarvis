"""Tests for core/handler/commands/reactor.py (HUD reactor color/pulse
effects) and browser.py (tab management) — previously untested.
"""
import core.handler.commands.reactor as reactor_cmd
import core.handler.commands.browser as browser_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))


class _FakeHud:
    def __init__(self):
        self.queued = []

    class _Queue:
        def __init__(self, outer):
            self._outer = outer

        def put(self, fn):
            self._outer.queued.append(fn)

    def __post_init__(self):
        pass


def _make_hud():
    h = _FakeHud()
    h._hud_queue = _FakeHud._Queue(h)
    h._set_reactor_color = lambda c: h.queued.append(('color', c))
    h._reset_reactor_color = lambda: None
    h._trigger_reactor_pulse = lambda: None
    h._trigger_reactor_glitch = lambda: None
    return h


# ── reactor.py ────────────────────────────────────────────────────────────

def test_reactor_color_command_queues_color_change(monkeypatch):
    import ui.hud as hud_mod
    fake_hud = _make_hud()
    monkeypatch.setattr(hud_mod, '_hud', fake_hud)
    handler = _FakeHandler()

    reactor_cmd.handle_reactor(handler, 'reactor_color_red', 'сделай реактор красным', 0)

    assert len(fake_hud.queued) == 1
    assert handler.play_response_calls


def test_reactor_reset_queues_reset(monkeypatch):
    import ui.hud as hud_mod
    fake_hud = _make_hud()
    monkeypatch.setattr(hud_mod, '_hud', fake_hud)
    handler = _FakeHandler()

    reactor_cmd.handle_reactor(handler, 'reactor_reset', 'сбрось цвет реактора', 0)

    assert len(fake_hud.queued) == 1
    assert handler.play_response_calls


def test_reactor_command_without_hud_running_speaks_error(monkeypatch):
    import ui.hud as hud_mod
    monkeypatch.setattr(hud_mod, '_hud', None)
    handler = _FakeHandler()

    reactor_cmd.handle_reactor(handler, 'reactor_color_red', 'сделай реактор красным', 0)

    assert handler.spoken
    assert handler.play_response_calls == []


def test_reactor_unknown_command_does_nothing(monkeypatch):
    import ui.hud as hud_mod
    fake_hud = _make_hud()
    monkeypatch.setattr(hud_mod, '_hud', fake_hud)
    handler = _FakeHandler()

    reactor_cmd.handle_reactor(handler, 'not_a_reactor_cmd', 'что угодно', 0)

    assert fake_hud.queued == []
    assert handler.play_response_calls == []


# ── browser.py ────────────────────────────────────────────────────────────

def test_handle_browser_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(browser_cmd._BROWSER_ACTIONS, 'close_all_tabs', lambda h, t, a: called.append(t))
    handler = _FakeHandler()

    browser_cmd.handle_browser(handler, 'close_all_tabs', 'закрой все вкладки', 0)

    assert called == ['закрой все вкладки']


def test_browser_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(browser_cmd._BROWSER_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_BROWSER_ACTIONS has non-existent intent keys: {unknown}'


def test_browser_tab_with_number_and_no_new_word_switches_tab(monkeypatch):
    captured = []
    monkeypatch.setattr(browser_cmd, 'goto_tab', lambda n: captured.append(n) or (True, 'ok'))
    handler = _FakeHandler()

    browser_cmd._browser_tab(handler, 'открой вкладку 3', 3)

    assert captured == [3]


def test_browser_tab_with_new_word_opens_new_tab_even_with_number(monkeypatch):
    # 'новую' overrides any parsed number — must open a new tab, not switch
    captured = []
    monkeypatch.setattr(browser_cmd, 'open_new_tab', lambda: captured.append(True) or (True, 'ok'))
    monkeypatch.setattr(browser_cmd, 'goto_tab',
                         lambda n: (_ for _ in ()).throw(AssertionError('must not switch tab')))
    handler = _FakeHandler()

    browser_cmd._browser_tab(handler, 'открой новую вкладку', 3)

    assert captured == [True]


def test_browser_tab_without_number_opens_new_tab(monkeypatch):
    captured = []
    monkeypatch.setattr(browser_cmd, 'open_new_tab', lambda: captured.append(True) or (True, 'ok'))
    handler = _FakeHandler()

    browser_cmd._browser_tab(handler, 'открой вкладку', 0)

    assert captured == [True]


def test_close_tab_n_with_zero_amount_does_nothing(monkeypatch):
    monkeypatch.setattr(browser_cmd, 'close_tab_by_index',
                         lambda n: (_ for _ in ()).throw(AssertionError('must not be called')))
    handler = _FakeHandler()

    browser_cmd._close_tab_n(handler, 'закрой вкладку', 0)

    assert handler.play_response_calls == []


def test_close_tab_n_with_positive_amount_closes_by_index(monkeypatch):
    captured = []
    monkeypatch.setattr(browser_cmd, 'close_tab_by_index', lambda n: captured.append(n) or (True, 'ok'))
    handler = _FakeHandler()

    browser_cmd._close_tab_n(handler, 'закрой вкладку 2', 2)

    assert captured == [2]


def test_context_close_and_close_tab_share_the_same_handler():
    # Regression guard for the fix noted in browser.py: 'context_close'
    # (bare "закрой") must route to the exact same function as 'close_tab'.
    assert browser_cmd._BROWSER_ACTIONS['context_close'] is browser_cmd._BROWSER_ACTIONS['close_tab']
