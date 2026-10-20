"""The saved microphone moves from a PortAudio index to a device name once, and never gets in the way of opening the device."""
from core import audio_migrate


class _Store:
    def __init__(self, **data):
        self.data = dict(data)

    def read(self):
        return dict(self.data)

    def update(self, changes, remove=()):
        self.data.update(changes)
        for k in remove:
            self.data.pop(k, None)
        return True


def test_an_index_becomes_a_name(monkeypatch):
    st = _Store(audio_input_device_index=1)
    monkeypatch.setattr(audio_migrate, '_name_for_index', lambda i: 'Mikrofon (fifine  Microphone)' if i == 1 else None)
    assert audio_migrate.migrate_input_device(st.read, st.update) is True
    assert st.data == {'audio_input_device_name': 'Mikrofon (fifine  Microphone)'}


def test_a_stale_index_is_dropped_and_the_default_is_used(monkeypatch):
    st = _Store(audio_input_device_index=9, other=1)
    monkeypatch.setattr(audio_migrate, '_name_for_index', lambda i: None)
    assert audio_migrate.migrate_input_device(st.read, st.update) is True
    assert st.data == {'other': 1}


def test_a_name_that_is_already_saved_wins_over_a_leftover_index(monkeypatch):
    st = _Store(audio_input_device_index=1, audio_input_device_name='Mic X')
    monkeypatch.setattr(audio_migrate, '_name_for_index', lambda i: 'Something else')
    audio_migrate.migrate_input_device(st.read, st.update)
    assert st.data == {'audio_input_device_name': 'Mic X'}


def test_nothing_happens_without_an_old_setting(monkeypatch):
    st = _Store(audio_input_device_name='Mic X')
    monkeypatch.setattr(audio_migrate, '_name_for_index', lambda i: (_ for _ in ()).throw(AssertionError('must not look up')))
    assert audio_migrate.migrate_input_device(st.read, st.update) is False
    assert st.data == {'audio_input_device_name': 'Mic X'}


def test_garbage_indices_do_not_crash(monkeypatch):
    for bad in (True, 'x', 1.5):
        st = _Store(audio_input_device_index=bad)
        monkeypatch.setattr(audio_migrate, '_name_for_index', lambda i: (_ for _ in ()).throw(AssertionError('must not look up')))
        assert audio_migrate.migrate_input_device(st.read, st.update) is True and st.data == {}
