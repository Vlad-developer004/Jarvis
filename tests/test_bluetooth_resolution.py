"""Tests for the pure device-resolution and result-formatting logic in
actions/bluetooth.py — fuzzy name matching, category-based fallback
("подключи наушники" -> find any headphone-like paired device), and the
tri-state (ok=True/False/None) result handler that decides between a
confirmation, an error, or a disambiguation prompt. No real Bluetooth radio
or PnP calls are exercised — those need actual hardware/ctypes and are out
of scope, same as other OS-integration code this session has left out.
"""
import actions.bluetooth as bt

_DEVICES = [
    {'name': 'JBL Tune 510BT', 'address': 1, 'connected': False},
    {'name': 'Logitech MX Master 3', 'address': 2, 'connected': True},
    {'name': 'Sony WH-1000XM4', 'address': 3, 'connected': False},
    {'name': 'Xbox Wireless Controller', 'address': 4, 'connected': False},
]


# ── _fuzzy_find_device ────────────────────────────────────────────────────

def test_fuzzy_find_matches_close_name():
    dev, score = bt._fuzzy_find_device(_DEVICES, 'jbl')
    assert dev['name'] == 'JBL Tune 510BT'
    assert score >= 45


def test_fuzzy_find_matches_partial_model_name():
    dev, score = bt._fuzzy_find_device(_DEVICES, 'mx master')
    assert dev['name'] == 'Logitech MX Master 3'


def test_fuzzy_find_returns_none_for_unrelated_query():
    dev, score = bt._fuzzy_find_device(_DEVICES, 'совершенно другое устройство xyz123')
    assert dev is None
    assert score == 0


# ── _category_find_all ────────────────────────────────────────────────────

def test_category_find_all_matches_headphones_by_category_word():
    result = bt._category_find_all(_DEVICES, 'подключи наушники')
    names = {d['name'] for d in result}
    assert 'JBL Tune 510BT' in names
    assert 'Sony WH-1000XM4' in names
    assert 'Logitech MX Master 3' not in names


def test_category_find_all_matches_gamepad_category():
    result = bt._category_find_all(_DEVICES, 'подключи геймпад')
    names = {d['name'] for d in result}
    assert names == {'Xbox Wireless Controller'}


def test_category_find_all_returns_empty_for_non_category_query():
    result = bt._category_find_all(_DEVICES, 'подключи что-то непонятное')
    assert result == []


# ── _resolve_device (fuzzy first, category fallback) ─────────────────────

def test_resolve_device_prefers_fuzzy_match_over_category():
    resolved = bt._resolve_device(_DEVICES, 'jbl')
    assert resolved['name'] == 'JBL Tune 510BT'


def test_resolve_device_falls_back_to_category_when_fuzzy_fails_and_one_candidate():
    resolved = bt._resolve_device(_DEVICES, 'геймпад')
    assert resolved['name'] == 'Xbox Wireless Controller'


def test_resolve_device_returns_list_when_category_has_multiple_candidates():
    resolved = bt._resolve_device(_DEVICES, 'наушники')
    assert isinstance(resolved, list)
    assert len(resolved) == 2


def test_resolve_device_returns_none_when_nothing_matches():
    resolved = bt._resolve_device(_DEVICES, 'абракадабра штука xyz')
    assert resolved is None


# ── _bt_handle_result tri-state logic ─────────────────────────────────────

class _Speaks(list):
    def __call__(self, text):
        self.append(text)


def test_bt_handle_result_success_speaks_confirmation(monkeypatch):
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'ru')
    spoken = _Speaks()

    bt._bt_handle_result(True, 'JBL Tune 510BT', 'connect', spoken)

    assert spoken == ['JBL Tune 510BT подключён.']


def test_bt_handle_result_failure_speaks_the_error_message_verbatim(monkeypatch):
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'ru')
    spoken = _Speaks()

    bt._bt_handle_result(False, 'Устройство не найдено.', 'connect', spoken)

    assert spoken == ['Устройство не найдено.']


def test_bt_handle_result_ambiguous_prompts_for_disambiguation(monkeypatch):
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'ru')
    spoken = _Speaks()
    candidates = [{'name': 'JBL Tune 510BT'}, {'name': 'Sony WH-1000XM4'}]

    class _FakeHandler:
        pass
    handler = _FakeHandler()

    bt._bt_handle_result(None, candidates, 'connect', spoken, handler=handler)

    assert spoken and 'JBL Tune 510BT' in spoken[0] and 'Sony WH-1000XM4' in spoken[0]
    assert handler._bt_pending == {'action': 'connect', 'candidates': candidates}


def test_bt_handle_result_ukrainian_uses_correct_verb(monkeypatch):
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'uk')
    spoken = _Speaks()

    bt._bt_handle_result(True, 'JBL Tune 510BT', 'disconnect', spoken)

    assert spoken == ['JBL Tune 510BT відключено.']
