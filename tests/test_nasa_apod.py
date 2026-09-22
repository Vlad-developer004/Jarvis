"""Tests for actions/nasa.py's get_apod() — daily caching, image/video
branching, and graceful failure. Real network calls (requests, yt_dlp
download) are mocked; the cache dict is reset before each test since it's
module-level state shared across calls.
"""
import actions.nasa as nasa


def _reset_cache(monkeypatch):
    monkeypatch.setattr(nasa, '_apod_cache', {})
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'ru')


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_get_apod_returns_image_result(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr('requests.get', lambda url, params=None, timeout=None:
                         _FakeResp(200, {'title': 'Nebula', 'explanation': 'A cloud of gas.',
                                          'media_type': 'image', 'url': 'https://nasa.gov/img.jpg'}))
    monkeypatch.setattr(nasa, '_download_file', lambda url, prefix: '/tmp/cached.jpg')

    result = nasa.get_apod()

    assert result['ok'] is True
    assert result['media_type'] == 'image'
    assert result['title'] == 'Nebula'
    assert result['image_path'] == '/tmp/cached.jpg'


def test_get_apod_returns_video_result(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr('requests.get', lambda url, params=None, timeout=None:
                         _FakeResp(200, {'title': 'Comet flyby', 'explanation': '...',
                                          'media_type': 'video', 'url': 'https://youtube.com/x'}))
    monkeypatch.setattr(nasa, '_download_video', lambda url: '/tmp/cached.mp4')

    result = nasa.get_apod()

    assert result['ok'] is True
    assert result['media_type'] == 'video'
    assert result['video_path'] == '/tmp/cached.mp4'


def test_get_apod_handles_http_error_gracefully(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr('requests.get', lambda url, params=None, timeout=None: _FakeResp(500))

    result = nasa.get_apod()

    assert result['ok'] is False
    assert 'error' in result


def test_get_apod_handles_network_exception_gracefully(monkeypatch):
    _reset_cache(monkeypatch)
    def _boom(*a, **k):
        raise ConnectionError('no network')
    monkeypatch.setattr('requests.get', _boom)

    result = nasa.get_apod()

    assert result['ok'] is False


def test_get_apod_error_message_localized_for_ukrainian(monkeypatch):
    monkeypatch.setattr(nasa, '_apod_cache', {})
    monkeypatch.setattr('core.i18n.get_speech_language', lambda: 'uk')
    monkeypatch.setattr('requests.get', lambda url, params=None, timeout=None: _FakeResp(500))

    result = nasa.get_apod()

    assert result['ok'] is False
    assert 'NASA' in result['error']


def test_get_apod_uses_same_day_cache_without_hitting_network_again(monkeypatch):
    _reset_cache(monkeypatch)
    call_count = []

    def _get(url, params=None, timeout=None):
        call_count.append(1)
        return _FakeResp(200, {'title': 'Cached day', 'explanation': '...',
                                'media_type': 'image', 'url': 'https://nasa.gov/img.jpg'})

    monkeypatch.setattr('requests.get', _get)
    monkeypatch.setattr(nasa, '_download_file', lambda url, prefix: '/tmp/x.jpg')

    first = nasa.get_apod()
    second = nasa.get_apod()

    assert len(call_count) == 1  # second call served from _apod_cache
    assert first['title'] == second['title'] == 'Cached day'


def test_get_apod_does_not_attempt_download_when_url_missing(monkeypatch):
    _reset_cache(monkeypatch)
    monkeypatch.setattr('requests.get', lambda url, params=None, timeout=None:
                         _FakeResp(200, {'title': 'No URL', 'explanation': '...', 'media_type': 'image'}))
    monkeypatch.setattr(nasa, '_download_file',
                         lambda url, prefix: (_ for _ in ()).throw(AssertionError('must not be called')))

    result = nasa.get_apod()

    assert result['ok'] is True
    assert result['image_path'] is None
