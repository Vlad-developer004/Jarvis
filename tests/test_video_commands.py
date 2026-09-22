"""Tests for core/handler/commands/video.py — screenshots, video recording,
saved-video ordinal parsing, file paste type detection, OCR. Previously
untested; _open_saved's digit-vs-word ordinal parsing and _paste_file's
file-type detection are the trickiest text-parsing logic in this file.
"""
import core.handler.commands.video as video_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []
        self.interactive_calls = []

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))

    def _set_interactive(self, *a, **k):
        self.interactive_calls.append((a, k))


# ── handle_video routing ──────────────────────────────────────────────────

def test_handle_video_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(video_cmd._VIDEO_ACTIONS, 'screenshot', lambda h, t: called.append(t))
    handler = _FakeHandler()

    video_cmd.handle_video(handler, 'screenshot', 'сделай скриншот')

    assert called == ['сделай скриншот']


def test_video_actions_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(video_cmd._VIDEO_ACTIONS.keys()) - set(INTENTS.keys())
    assert not unknown, f'_VIDEO_ACTIONS has non-existent intent keys: {unknown}'


def test_paste_file_and_paste_video_share_the_same_handler():
    assert video_cmd._VIDEO_ACTIONS['paste_file'] is video_cmd._VIDEO_ACTIONS['paste_video']


# ── _start_video monitor branching ───────────────────────────────────────

def test_start_video_single_monitor_records_directly(monkeypatch):
    monkeypatch.setattr('actions.windows.get_monitors', lambda: [{'primary': True}])
    recorded = []
    monkeypatch.setattr(video_cmd, 'start_video_recording',
                         lambda with_mic, idx: recorded.append((with_mic, idx)) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._start_video(handler, 'запиши экран')

    assert recorded == [(False, 0)]
    assert handler.play_response_calls
    assert handler.interactive_calls == []


def test_start_video_multiple_monitors_asks_which_one(monkeypatch):
    monitors = [{'primary': True}, {'primary': False}]
    monkeypatch.setattr('actions.windows.get_monitors', lambda: monitors)
    handler = _FakeHandler()

    video_cmd._start_video(handler, 'запиши экран с микрофоном')

    assert handler.spoken
    assert handler.interactive_calls
    state = handler.interactive_calls[0][0][0]
    assert state['with_mic'] is True
    assert state['monitors'] == monitors


# ── _open_saved ordinal/number parsing ───────────────────────────────────

def test_open_saved_parses_digit_index(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_saved_video', lambda idx, background: captured.append(idx) or True)
    handler = _FakeHandler()

    video_cmd._open_saved(handler, 'открой сохранённое видео 3')

    assert captured == [3]


def test_open_saved_parses_ordinal_word_when_no_digit(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_saved_video', lambda idx, background: captured.append(idx) or True)
    handler = _FakeHandler()

    video_cmd._open_saved(handler, 'открой седьмое сохранённое видео')

    assert captured == [7]


def test_open_saved_last_keyword_uses_negative_index(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_saved_video', lambda idx, background: captured.append(idx) or True)
    handler = _FakeHandler()

    video_cmd._open_saved(handler, 'открой последнее сохранённое видео')

    assert captured == [-1]


def test_open_saved_no_match_speaks_error(monkeypatch):
    monkeypatch.setattr(video_cmd, 'open_saved_video', lambda idx, background: False)
    handler = _FakeHandler()

    video_cmd._open_saved(handler, 'открой видео', )

    assert handler.spoken
    assert handler.play_response_calls == []


# ── _open_last_video app detection ───────────────────────────────────────

def test_open_last_video_detects_clipchamp_cyrillic_spelling(monkeypatch):
    # Regression: RU/UK ASR transcribes the app name in Cyrillic, so a
    # Latin-only 'clip' substring check never matched real speech.
    captured = []
    monkeypatch.setattr(video_cmd, 'open_last_video_file', lambda app: captured.append(app) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._open_last_video(handler, 'открой последнее видео в клипчампе')

    assert captured == ['clipchamp']


def test_open_last_video_detects_clipchamp_latin_spelling(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_last_video_file', lambda app: captured.append(app) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._open_last_video(handler, 'открой в clipchamp')

    assert captured == ['clipchamp']


def test_open_last_video_detects_vlc(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_last_video_file', lambda app: captured.append(app) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._open_last_video(handler, 'открой видео в vlc')

    assert captured == ['vlc']


def test_open_last_video_defaults_to_default_app(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'open_last_video_file', lambda app: captured.append(app) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._open_last_video(handler, 'открой последнее видео')

    assert captured == ['default']


# ── _paste_file type detection and query stripping ───────────────────────

def test_paste_file_detects_video_type(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'find_and_paste_file',
                         lambda ftype, target_filename=None: captured.append((ftype, target_filename)) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._paste_file(handler, 'вставь видео отпуск')

    # No dedicated 'вставь видео' prefix in the strip list — only bare
    # 'вставь' matches, so 'видео' stays part of the remaining query. Type
    # detection ('видео' in text_lower) still correctly picks 'video'.
    assert captured == [('video', 'видео отпуск')]


def test_paste_file_detects_photo_type(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'find_and_paste_file',
                         lambda ftype, target_filename=None: captured.append((ftype, target_filename)) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._paste_file(handler, 'отправь фото кот')

    assert captured[0][0] == 'photo'


def test_paste_file_treats_last_keyword_as_no_specific_target(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'find_and_paste_file',
                         lambda ftype, target_filename=None: captured.append(target_filename) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._paste_file(handler, 'вставь последний')

    assert captured == [None]


def test_paste_file_defaults_to_document_type(monkeypatch):
    captured = []
    monkeypatch.setattr(video_cmd, 'find_and_paste_file',
                         lambda ftype, target_filename=None: captured.append(ftype) or (True, 'ok'))
    handler = _FakeHandler()

    video_cmd._paste_file(handler, 'вставь файл отчёт')

    assert captured == ['document']


# ── OCR ─────────────────────────────────────────────────────────────────

def test_ocr_screen_speaks_result_on_success(monkeypatch):
    monkeypatch.setattr('actions.ocr.ocr_from_screenshot', lambda: (True, 'распознанный текст'))
    handler = _FakeHandler()

    video_cmd._ocr_screen(handler, 'распознай текст на экране')

    assert 'распознанный текст' in handler.spoken
    assert handler.play_response_calls


def test_ocr_screen_speaks_error_on_failure(monkeypatch):
    monkeypatch.setattr('actions.ocr.ocr_from_screenshot', lambda: (False, 'ошибка OCR'))
    handler = _FakeHandler()

    video_cmd._ocr_screen(handler, 'распознай текст на экране')

    assert handler.play_response_calls == []
    assert handler.spoken
