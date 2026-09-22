"""Tests for actions/dictation.py's handle_dictation_text() — the
stop/submit word detection and punctuation-word-to-symbol substitution
(e.g. "точка" -> "."). keysend.press/hotkey and pyperclip are mocked since
they'd otherwise send real key events / touch the real clipboard.
"""
import actions.dictation as dict_mod
from core.system import app_state


def _mock_io(monkeypatch):
    monkeypatch.setattr(dict_mod.keysend, 'press', lambda *a, **k: None)
    monkeypatch.setattr(dict_mod.keysend, 'hotkey', lambda *a, **k: None)
    monkeypatch.setattr('pyperclip.paste', lambda: '')
    monkeypatch.setattr('pyperclip.copy', lambda text: None)


def test_start_stop_dictation_toggles_app_state(monkeypatch):
    monkeypatch.setattr(app_state, 'dictation_mode', False)
    dict_mod.start_dictation()
    assert dict_mod.is_dictation_active() is True
    dict_mod.stop_dictation()
    assert dict_mod.is_dictation_active() is False


def test_handle_dictation_text_stop_word_stops_and_returns_no_text(monkeypatch):
    _mock_io(monkeypatch)
    monkeypatch.setattr(app_state, 'dictation_mode', True)

    result = dict_mod.handle_dictation_text('хватит')

    assert result == {'stop': True, 'submit': False, 'text': ''}
    assert app_state.dictation_mode is False


def test_handle_dictation_text_stop_word_matches_as_prefix(monkeypatch):
    _mock_io(monkeypatch)
    monkeypatch.setattr(app_state, 'dictation_mode', True)

    result = dict_mod.handle_dictation_text('стоп диктовку пожалуйста')

    assert result['stop'] is True


def test_handle_dictation_text_submit_word_presses_enter(monkeypatch):
    _mock_io(monkeypatch)
    pressed = []
    monkeypatch.setattr(dict_mod.keysend, 'press', lambda key: pressed.append(key))

    result = dict_mod.handle_dictation_text('отправь')

    assert result == {'stop': False, 'submit': True, 'text': ''}
    assert pressed == ['enter']


def test_handle_dictation_text_converts_punctuation_words(monkeypatch):
    _mock_io(monkeypatch)

    result = dict_mod.handle_dictation_text('привет мир точка как дела вопросительный знак')

    assert result['text'] == 'Привет мир. как дела?'


def test_handle_dictation_text_capitalizes_first_letter(monkeypatch):
    _mock_io(monkeypatch)

    result = dict_mod.handle_dictation_text('это тестовое предложение')

    assert result['text'].startswith('Это')


def test_handle_dictation_text_removes_space_before_punctuation(monkeypatch):
    _mock_io(monkeypatch)

    result = dict_mod.handle_dictation_text('привет запятая как дела')

    assert result['text'] == 'Привет, как дела'


def test_handle_dictation_text_new_line_word_converts_to_newline(monkeypatch):
    _mock_io(monkeypatch)

    result = dict_mod.handle_dictation_text('первая строка новая строка вторая строка')

    assert '\n' in result['text']


def test_handle_dictation_text_types_via_clipboard(monkeypatch):
    copied = []
    monkeypatch.setattr(dict_mod.keysend, 'hotkey', lambda *a, **k: None)
    monkeypatch.setattr(dict_mod.keysend, 'press', lambda *a, **k: None)
    monkeypatch.setattr('pyperclip.paste', lambda: 'old clipboard')
    monkeypatch.setattr('pyperclip.copy', lambda text: copied.append(text))

    dict_mod.handle_dictation_text('привет')

    # First copy is the dictated text (for paste), second restores old clipboard
    assert copied[0].strip() == 'Привет'
    assert copied[-1] == 'old clipboard'
