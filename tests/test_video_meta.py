"""ui_next/bridge/video_meta.py: the Videos screen must not wait for the network. Details arrive piece by piece, are kept on disk and are loaded at start."""
import json
import threading
import time

import pytest

from ui_next.bridge import video_meta as vm

URL = 'https://www.youtube.com/watch?v=JRMve8qLlIs'
VID = 'JRMve8qLlIs'


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(vm, '_cache', {})
    monkeypatch.setattr(vm, '_pending', set())
    monkeypatch.setattr(vm, '_pool', None)
    monkeypatch.setattr(vm, '_loaded', False)
    monkeypatch.setattr(vm, '_disk_path', lambda: str(tmp_path / 'video_meta.json'))
    return tmp_path


def wait(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_the_title_is_shown_while_the_thumbnail_and_length_are_still_loading(env, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(vm, '_oembed', lambda vid: {'title': 'Песня', 'author': 'Автор'})
    monkeypatch.setattr(vm, '_thumb', lambda vid: gate.wait(3) and 'data:image/jpeg;base64,AAAA')
    monkeypatch.setattr(vm, '_duration', lambda vid: gate.wait(3) and '3:45')
    vm.lookup([URL])                                                      # starts the fetch
    assert wait(lambda: vm.lookup([URL])['items'].get(URL, {}).get('title') == 'Песня')
    early = vm.lookup([URL])
    assert early['items'][URL]['thumb'] == '' and early['pending'] == 1  # the rest is still on its way: the screen keeps asking
    gate.set()
    assert wait(lambda: vm.lookup([URL])['pending'] == 0)
    done = vm.lookup([URL])['items'][URL]
    assert done == {'title': 'Песня', 'author': 'Автор', 'thumb': 'data:image/jpeg;base64,AAAA', 'duration': '3:45'}


def test_one_failing_part_does_not_lose_the_others(env, monkeypatch):
    def boom(vid):
        raise OSError('offline')
    monkeypatch.setattr(vm, '_oembed', lambda vid: {'title': 'T', 'author': 'A'})
    monkeypatch.setattr(vm, '_thumb', boom)
    monkeypatch.setattr(vm, '_duration', lambda vid: '1:00')
    vm.lookup([URL])
    assert wait(lambda: vm.lookup([URL])['pending'] == 0)
    assert vm.lookup([URL])['items'][URL] == {'title': 'T', 'author': 'A', 'thumb': '', 'duration': '1:00'}


def test_details_are_kept_on_disk_and_shown_at_once_after_a_restart(env, monkeypatch):
    monkeypatch.setattr(vm, '_oembed', lambda vid: {'title': 'Песня', 'author': 'Автор'})
    monkeypatch.setattr(vm, '_thumb', lambda vid: 'data:image/jpeg;base64,AAAA')
    monkeypatch.setattr(vm, '_duration', lambda vid: '3:45')
    vm.lookup([URL])
    assert wait(lambda: vm.lookup([URL])['pending'] == 0)
    assert wait(lambda: (env / 'video_meta.json').exists())
    assert json.loads((env / 'video_meta.json').read_text(encoding='utf-8'))[VID]['title'] == 'Песня'
    # a new run: memory is empty, the network is down; the screen still gets everything and nothing is requested
    monkeypatch.setattr(vm, '_cache', {})
    monkeypatch.setattr(vm, '_loaded', False)
    for name in ('_oembed', '_thumb', '_duration'):
        monkeypatch.setattr(vm, name, lambda vid: pytest.fail('the network must not be asked for a known video'))
    res = vm.lookup([URL])
    assert res['pending'] == 0 and res['items'][URL]['title'] == 'Песня' and res['items'][URL]['duration'] == '3:45'


def test_a_broken_or_foreign_cache_file_is_ignored(env):
    (env / 'video_meta.json').write_text(json.dumps({'not-an-id': {'title': 'x'}, VID: 'junk'}), encoding='utf-8')
    vm._load_disk()
    assert vm._cache == {}
    (env / 'video_meta.json').write_text('{ not json', encoding='utf-8')
    vm._loaded = False
    vm._load_disk()
    assert vm._cache == {}


def test_warm_fetches_the_saved_videos_before_the_screen_is_opened(env, monkeypatch):
    from ui_next.bridge import tools
    monkeypatch.setattr(tools, 'get_state', lambda: {'videos': [{'ts': 't', 'url': URL}]})
    seen = []
    monkeypatch.setattr(vm, '_oembed', lambda vid: seen.append(vid) or {'title': 'T', 'author': 'A'})
    monkeypatch.setattr(vm, '_thumb', lambda vid: '')
    monkeypatch.setattr(vm, '_duration', lambda vid: '')
    vm.warm()
    assert wait(lambda: seen == [VID])


def test_only_youtube_links_are_ever_requested(env, monkeypatch):
    monkeypatch.setattr(vm, '_oembed', lambda vid: pytest.fail('a foreign address must not be fetched'))
    assert vm.lookup(['https://evil.example/watch?v=JRMve8qLlIs', 'file:///etc/passwd'])['items'] == {}
