"""actions/media_library.py, "продолжи сериал X", the library part of the cinema handler and the bridge ops."""
import os

import pytest

import core.settings_io as sio
from actions import media_library as ml
from actions import media_phrases as mp
from core.handler.commands import cinema as cin
from ui_next import bridge


@pytest.fixture
def lib(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    root = tmp_path / 'videos'
    files = ['Sherlock/Season 1/Sherlock.S01E01.1080p.mkv', 'Sherlock/Season 1/Sherlock.S01E02.1080p.mkv', 'Sherlock/Season 2/Sherlock.S02E01.mkv',
             'Ивановы-Ивановы 1x03.mp4', 'Movies/Dune.2021.1080p.BluRay.x264.mkv', 'Movies/Матрица (1999).avi', 'Movies/notes.txt']
    for f in files:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x')
    ml._drop_cache()
    started = []
    monkeypatch.setattr(ml.os, 'startfile', lambda p: started.append(p), raising=False)
    assert ml.add_folder(str(root))['ok']
    return started


@pytest.mark.parametrize('path,want', [
    (r'D:\S\Sherlock\Season 2\Sherlock.S02E03.1080p.mkv', ('Sherlock', 2, 3)),
    (r'D:\S\Ивановы-Ивановы 3x07.mp4', ('Ивановы-Ивановы', 3, 7)),
    (r'D:\S\Ivanovy\Сезон 4\Серия 12.mkv', ('Ivanovy', 4, 12)),
    (r'D:\S\Show s1e5.mkv', ('Show', 1, 5)),
    (r'D:\M\Dune.2021.1080p.BluRay.x264.mkv', ('Dune', None, None)),
    (r'D:\M\Матрица (1999).avi', ('Матрица', None, None)),
])
def test_parse_name(path, want):
    r = ml.parse_name(path)
    assert (r['title'], r['season'], r['episode']) == want


def test_parse_name_reads_the_year_of_a_movie():
    assert ml.parse_name(r'D:\M\Dune.2021.1080p.mkv')['year'] == 2021


def test_scan_finds_only_video_files(lib):
    items = ml.scan()
    assert len(items) == 6 and not any(i['path'].endswith('.txt') for i in items)


def test_library_groups_series_and_movies(lib):
    d = ml.library()
    assert [s['title'] for s in d['series']] == ['Sherlock', 'Ивановы-Ивановы']
    sh = next(s for s in d['series'] if s['title'] == 'Sherlock')
    assert sh['episodes'] == 3 and sh['seasons'] == 2
    assert sorted(m['title'] for m in d['movies']) == ['Dune', 'Матрица']


@pytest.mark.parametrize('q,found', [('шерлок', ''), ('Sherlock', 'sherlock'), ('sherlok', 'sherlock'), ('ивановы ивановы', 'ивановыивановы'), ('матрица', 'матрица'), ('что-то другое', '')])
def test_find(lib, q, found):
    assert ml.find(q) == found


def test_next_episode_walks_the_series_in_order_and_wraps(lib):
    k = 'sherlock'
    first = ml.next_episode(k)
    assert (first['season'], first['episode']) == (1, 1)
    ml.mark_watched(first)
    assert (ml.next_episode(k)['season'], ml.next_episode(k)['episode']) == (1, 2)
    ml.mark_watched(ml.next_episode(k))
    assert (ml.next_episode(k)['season'], ml.next_episode(k)['episode']) == (2, 1)
    ml.mark_watched(ml.next_episode(k))
    assert (ml.next_episode(k)['season'], ml.next_episode(k)['episode']) == (1, 1)      # finished: starts over
    assert ml.last_series_key() == k


def test_pick_episode(lib):
    assert ml.pick_episode('sherlock', 2, 1)['season'] == 2 and ml.pick_episode('sherlock', 3, 1) is None
    assert ml.pick_episode('ивановыивановы', None, 3)['episode'] == 3


def test_folders_are_validated(lib, tmp_path):
    assert ml.add_folder(str(tmp_path / 'nope'))['error'] == 'not_a_folder'
    assert ml.add_folder(ml.folders()[0])['error'] == 'exists'
    assert ml.remove_folder('x')['error'] == 'not_found' and ml.remove_folder(ml.folders()[0])['ok'] and ml.folders() == []


def test_play_opens_the_file_and_remembers_the_episode(lib):
    ep = ml.next_episode('sherlock')
    assert ml.play(ep) and lib == [ep['path']] and ml.library()['series'][0]['last'] == '1x01'


def test_play_refuses_a_missing_file(lib):
    assert ml.play({'path': 'C:/no/such.mkv', 'title': 'x', 'episode': None}) is False


def test_library_survives_other_cinema_settings(lib):
    from actions import cinema_services as cs
    assert cs.add('Мой', 'example.com')['ok'] and ml.folders() and cs.load()['services']


@pytest.mark.parametrize('text,title', [('продолжи сериал Шерлок', 'шерлок'), ('продолжи смотреть', ''), ('включи следующую серию Ивановы', 'ивановы'), ('продовж серіал Шерлок', 'шерлок')])
def test_parse_continue(text, title):
    assert mp.parse_continue(text) == {'title': title} and mp.route(text) == 'cinema_continue'


def test_plain_resume_is_not_a_series_command():
    assert mp.parse_continue('продолжай') is None and mp.parse_continue('продолжи') is None


class Handler:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


def test_continue_by_voice_plays_the_next_episode(lib, monkeypatch):
    h = Handler()
    cin._handle_continue(h, 'продолжи сериал sherlock')
    assert lib and lib[0].endswith('Sherlock.S01E01.1080p.mkv') and 'сезон 1' in h.spoken[0]
    cin._handle_continue(h, 'продолжи смотреть')
    assert lib[1].endswith('Sherlock.S01E02.1080p.mkv')


def test_continue_without_history_or_match(lib):
    h = Handler()
    cin._handle_continue(h, 'продолжи смотреть')
    assert 'ничего не смотрели' in h.spoken[-1]
    cin._handle_continue(h, 'продолжи сериал Дом Дракона')
    assert 'нет сериала' in h.spoken[-1] and not lib


def test_continue_without_folders(tmp_path, monkeypatch):
    path = tmp_path / 's.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    ml._drop_cache()
    h = Handler()
    cin._handle_continue(h, 'продолжи сериал X')
    assert 'папки' in h.spoken[0]


def test_watch_prefers_a_file_from_the_library_unless_a_service_is_named(lib):
    assert cin._local_match('Dune', False, None, None, 'dune')['title'] == 'Dune'
    assert cin._local_match('Sherlock', True, 2, 1, 'sherlock сезон 2')['season'] == 2
    assert cin._local_match('Dune', False, None, None, 'dune на netflix') is None
    assert cin._local_match('Неизвестный', False, None, None, '') is None


def test_bridge_library_ops(lib, monkeypatch):
    r = bridge.run_command('cinema', {'op': 'lib'})
    assert r['ok'] and len(r['series']) == 2 and r['movies_total'] == 2 and r['files'] == 6
    played = bridge.run_command('cinema', {'op': 'lib_play', 'key': 'sherlock'})
    assert played['ok'] and lib and played['played'] == lib[0]
    assert bridge.run_command('cinema', {'op': 'lib_play', 'path': 'C:/not/in/the/library.mkv'})['error'] == 'not_found'
    assert bridge.run_command('cinema', {'op': 'lib_add', 'path': 'C:/definitely/missing'})['error'] == 'not_a_folder'
    monkeypatch.setattr('ui_next.bridge.filepick.pick_folder', lambda title: '')
    assert bridge.run_command('cinema', {'op': 'lib_add'})['error'] == 'cancelled'
    removed = bridge.run_command('cinema', {'op': 'lib_remove', 'path': ml.folders()[0]})
    assert removed['ok'] and removed['folders'] == [] and os.path.isdir(os.path.dirname(lib[0]))
