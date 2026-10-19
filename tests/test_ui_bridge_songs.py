import pytest

from ui_next import bridge
from ui_next.bridge import songs

ENTRY = {
    'title': 'Птичка', 'artist': 'HammAli & Navai', 'recognized_at': 1000.0, 'source': 'shazam', 'cover_path': '',
    'spotify_url': 'spotify:search:x', 'apple_music_url': 'intent://music.apple.com/x#Intent;end', 'youtube_url': 'https://www.youtube.com/watch?v=abc',
}


def test_links_are_web_urls_only():
    assert songs.link(ENTRY, 'youtube') == 'https://www.youtube.com/watch?v=abc'
    assert songs.link(ENTRY, 'spotify').startswith('https://open.spotify.com/search/')
    assert songs.link(ENTRY, 'apple').startswith('https://music.apple.com/search?term=')
    assert songs.link({**ENTRY, 'youtube_url': 'javascript:alert(1)'}, 'youtube') == ''
    assert songs.link({'title': 'a'}, 'spotify') == ''
    assert songs.link(ENTRY, 'nope') == ''


def test_payload_and_commands(monkeypatch):
    from actions import song_cache
    monkeypatch.setattr(song_cache, 'list_recent', lambda limit=100: [ENTRY])
    monkeypatch.setattr(song_cache, 'song_count', lambda: 1)
    data = songs.payload()
    row = data['songs'][0]
    assert data['total'] == 1 and row['title'] == 'Птичка' and row['links'] == ['spotify', 'apple', 'youtube'] and row['cover'] == ''

    opened = []
    import webbrowser
    monkeypatch.setattr(webbrowser, 'open', lambda u: opened.append(u) or True)
    assert bridge.run_command('song_open', {'id': row['id'], 'service': 'youtube'}) == {'ok': True}
    assert opened == ['https://www.youtube.com/watch?v=abc']
    assert bridge.run_command('song_open', {'id': 'unknown', 'service': 'youtube'})['ok'] is False
    assert bridge.run_command('song_open', {'id': row['id'], 'service': 'bogus'})['ok'] is False


def test_clear_command(monkeypatch):
    from actions import song_cache
    called = []
    monkeypatch.setattr(song_cache, 'clear', lambda: called.append(1))
    monkeypatch.setattr(song_cache, 'list_recent', lambda limit=100: [])
    monkeypatch.setattr(song_cache, 'song_count', lambda: 0)
    assert bridge.run_command('song_clear', {}) == {'ok': True}
    assert called == [1]
