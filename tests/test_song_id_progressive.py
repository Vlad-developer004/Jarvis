"""actions/song_id.py recognize_song(): a short recording first, a longer one only after "no match" (it always listened for ten seconds before)."""
import pytest

from actions import song_cache, song_id


@pytest.fixture
def rec(monkeypatch):
    log = {'record': [], 'query': []}
    answers = []

    def record_mic(seconds, wait=None):
        log['record'].append((seconds, wait))
        return b'\x01\x00' * 1600, 16000

    def query(path):
        log['query'].append(path)
        return answers.pop(0)
    monkeypatch.setattr(song_id, '_record_mic', record_mic)
    monkeypatch.setattr(song_id, '_query_shazam', query)
    monkeypatch.setattr(song_id, '_query_audd', lambda path: {'ok': False, 'error': 'no_key'})
    monkeypatch.setattr(song_cache, 'remember', lambda res: None)
    log['answers'] = answers
    return log


OK = {'ok': True, 'title': 'T', 'artist': 'A'}
NO = {'ok': False, 'error': 'no_match'}


def test_a_known_song_is_recognised_from_the_short_recording(rec):
    rec['answers'] += [OK]
    res = song_id.recognize_song('mic')
    assert res['ok'] and res['source'] == 'shazam'
    assert rec['record'] == [(5, None)]                  # five seconds, not ten


def test_the_second_try_is_longer_and_only_waits_for_the_rest(rec):
    rec['answers'] += [NO, OK]
    assert song_id.recognize_song('mic')['ok']
    assert rec['record'] == [(5, None), (10, 5)]         # the ring buffer already holds the first five seconds


def test_no_match_twice_is_reported_as_no_match(rec):
    rec['answers'] += [NO, NO]
    assert song_id.recognize_song('mic') == {'ok': False, 'error': 'no_match'}
    assert len(rec['record']) == 2


def test_a_network_error_is_not_retried_with_a_longer_recording(rec):
    rec['answers'] += [{'ok': False, 'error': 'network'}]
    assert song_id.recognize_song('mic')['error'] != 'no_match'
    assert len(rec['record']) == 1


def test_a_request_shorter_than_the_first_try_listens_once(rec):
    rec['answers'] += [NO]
    song_id.recognize_song('mic', seconds=3)
    assert rec['record'] == [(3, None)]


# ---- 'auto': the PC's own audio on headphones ----
@pytest.fixture
def output(monkeypatch):
    from core import native_audio
    info = {}
    monkeypatch.setattr(native_audio, 'query_output', lambda: info.get('v'))
    return info


def test_headphones_record_the_pc_audio_not_the_mic(rec, output, monkeypatch):
    output['v'] = {'name': 'Headphones', 'kind': 'headphones', 'is_headphones': True}
    loop = []
    monkeypatch.setattr(song_id, '_record_loopback', lambda seconds: loop.append(seconds) or (b'\x01\x00' * 3200, 16000, 2))
    rec['answers'] += [OK]
    assert song_id.recognize_song()['ok']
    assert loop == [5] and rec['record'] == []             # the mic was not even opened


def test_speakers_still_use_the_microphone(rec, output, monkeypatch):
    output['v'] = {'name': 'Speakers', 'kind': 'speakers', 'is_headphones': False}
    monkeypatch.setattr(song_id, '_record_loopback', lambda seconds: pytest.fail('loopback must not be used on speakers'))
    rec['answers'] += [OK]
    assert song_id.recognize_song()['ok'] and rec['record'] == [(5, None)]


def test_an_unknown_output_device_uses_the_microphone(rec, output):
    output['v'] = None
    rec['answers'] += [OK]
    assert song_id.recognize_song()['ok'] and rec['record'] == [(5, None)]


def test_when_nothing_plays_on_the_pc_the_mic_is_the_fallback(rec, output, monkeypatch):
    output['v'] = {'kind': 'headset', 'is_headphones': True}
    monkeypatch.setattr(song_id, '_record_loopback', lambda seconds: None)    # loopback heard nothing
    rec['answers'] += [OK]
    assert song_id.recognize_song()['ok'] and rec['record'] == [(5, None)]


def test_an_explicit_source_is_respected(rec, output, monkeypatch):
    output['v'] = {'kind': 'headphones', 'is_headphones': True}
    rec['answers'] += [OK]
    assert song_id.recognize_song('mic')['ok'] and rec['record'] == [(5, None)]
