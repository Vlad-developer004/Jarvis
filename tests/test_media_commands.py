"""Tests for core/handler/commands/media.py — YouTube control and
volume/app-volume commands. Previously untested; covers the level-selection
logic (vol_max/vol_zero/vol_set) and the app-name extraction regex in
_app_vol(), which strips filler words and numbers from the raw utterance to
find which app the user meant.
"""
import core.handler.commands.media as media_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []
        self.interactive_state = None
        self.interactive_data = None

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))

    def _set_interactive(self, state, data=None, timeout=60.0):
        self.interactive_state = state
        self.interactive_data = data


# ── handle_yt_control / handle_volume routing ────────────────────────────

def test_handle_yt_control_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(media_cmd._YT_ACTIONS, 'yt_next', lambda h, c, t: called.append(c))
    handler = _FakeHandler()

    media_cmd.handle_yt_control(handler, 'yt_next', 'следующее видео')

    assert called == ['yt_next']


def test_handle_volume_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(media_cmd._VOL_ACTIONS, 'vol_mute', lambda h, c, t, a: called.append(c))
    handler = _FakeHandler()

    media_cmd.handle_volume(handler, 'vol_mute', 'выключи звук', 0)

    assert called == ['vol_mute']


def test_yt_actions_and_vol_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    # app_vol_* commands are produced by dedicated regexes in
    # core/engine/recognition.py (_APP_VOL_SET_RE/_UP_RE/_DOWN_RE), not via
    # the semantic-classifier INTENTS registry — a different, legitimate
    # NLU path, not dead code.
    regex_routed = {'app_vol_up', 'app_vol_down', 'app_vol_set'}
    unknown_yt = set(media_cmd._YT_ACTIONS.keys()) - set(INTENTS.keys())
    unknown_vol = set(media_cmd._VOL_ACTIONS.keys()) - set(INTENTS.keys()) - regex_routed
    assert not unknown_yt, f'_YT_ACTIONS has non-existent intent keys: {unknown_yt}'
    assert not unknown_vol, f'_VOL_ACTIONS has non-existent intent keys: {unknown_vol}'


# ── yt fwd/bwd duration parsing ──────────────────────────────────────────

def test_yt_fwd_uses_parsed_duration(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.youtube.control_youtube',
                         lambda action, amount=None: captured.append((action, amount)))
    handler = _FakeHandler()

    media_cmd._yt_fwd(handler, 'yt_fwd', 'перемотай на 30 секунд')

    assert captured == [('forward', 30)]


def test_yt_fwd_defaults_to_five_seconds_when_unparseable(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.youtube.control_youtube',
                         lambda action, amount=None: captured.append((action, amount)))
    handler = _FakeHandler()

    media_cmd._yt_fwd(handler, 'yt_fwd', 'перемотай вперёд')

    assert captured == [('forward', 5)]


# ── yt_channel ────────────────────────────────────────────────────────────

def test_yt_channel_with_name_opens_directly(monkeypatch):
    opened = []
    monkeypatch.setattr('actions.youtube.open_youtube_channel',
                         lambda q, background=False: opened.append(q))
    handler = _FakeHandler()

    # Callers always pass already-lowercased text (see recognition.py's
    # text_lower convention) — match that here.
    media_cmd._yt_channel(handler, 'yt_channel', 'открой канал аркадий опять')

    assert opened == ['аркадий опять']
    assert handler.play_response_calls


def test_yt_channel_without_name_asks(monkeypatch):
    handler = _FakeHandler()

    media_cmd._yt_channel(handler, 'yt_channel', 'открой канал')

    assert handler.interactive_state == 'yt_channel_ask'
    assert handler.spoken


# ── volume level selection (_vol_set_like) ───────────────────────────────

def test_vol_max_command_sets_full_volume(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.volume.set_volume_level', lambda level: captured.append(level))
    handler = _FakeHandler()

    media_cmd._vol_set_like(handler, 'vol_max', 'сделай звук на максимум', 0)

    assert captured == [1.0]


def test_vol_zero_command_sets_zero_volume(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.volume.set_volume_level', lambda level: captured.append(level))
    handler = _FakeHandler()

    media_cmd._vol_set_like(handler, 'vol_zero', 'сделай звук на минимум', 0)

    assert captured == [0.0]


def test_vol_set_uses_explicit_amount(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.volume.set_volume_level', lambda level: captured.append(level))
    handler = _FakeHandler()

    media_cmd._vol_set_like(handler, 'vol_set', 'поставь громкость на 40', 40)

    assert captured == [0.4]


def test_vol_set_recognizes_maximum_keyword_in_text_without_vol_max_cmd(monkeypatch):
    # cmd is 'vol_set' (generic), but the phrase itself says "максимум"
    captured = []
    monkeypatch.setattr('actions.volume.set_volume_level', lambda level: captured.append(level))
    handler = _FakeHandler()

    media_cmd._vol_set_like(handler, 'vol_set', 'сделай максимально громко', 0)

    assert captured == [1.0]


# ── _app_vol name extraction ──────────────────────────────────────────────

def test_app_vol_extracts_app_name_and_direction(monkeypatch):
    captured = []
    monkeypatch.setattr('actions.volume.set_app_volume',
                         lambda name, direction, amount: captured.append((name, direction, amount)) or (True, 'ok'))
    handler = _FakeHandler()

    media_cmd._app_vol(handler, 'app_vol_up', 'сделай громкость дискорда громче', 0)

    assert captured
    name, direction, amount = captured[0]
    assert 'дискорд' in name
    assert direction == 'up'


def test_app_vol_falls_back_to_system_volume_when_name_empty(monkeypatch):
    monkeypatch.setattr('actions.volume.set_app_volume', lambda name, direction, amount: (False, 'not found'))
    fallback_calls = []
    monkeypatch.setattr(media_cmd, 'handle_volume', lambda h, c, t, a: fallback_calls.append((c, a)))
    handler = _FakeHandler()

    media_cmd._app_vol(handler, 'app_vol_up', 'сделай громче', 0)

    assert fallback_calls == [('vol_up', 0)]


def test_app_vol_speaks_error_when_app_name_present_but_not_found(monkeypatch):
    monkeypatch.setattr('actions.volume.set_app_volume', lambda name, direction, amount: (False, 'приложение не найдено'))
    handler = _FakeHandler()

    media_cmd._app_vol(handler, 'app_vol_up', 'сделай громкость дискорда громче', 0)

    assert handler.spoken == ['приложение не найдено']
