"""core.system.state: paired fields change together, and concurrent toggles never lose an update."""
import threading

from core.system.state import AppState


def _hammer(fn, threads=8, rounds=3000):
    barrier = threading.Barrier(threads)
    errors = []

    def run(i):
        barrier.wait()
        try:
            for r in range(rounds):
                fn(i, r)
        except BaseException as e:   # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=run, args=(i,)) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors, errors


def test_game_flag_and_profile_are_never_seen_torn():
    st = AppState()
    seen_bad = []

    def work(i, r):
        if i % 2 == 0:
            st.set_game(True, f'game{i}') if r % 2 else st.set_game(False, '')
        else:
            on, profile = st.game_snapshot()
            if on != bool(profile):
                seen_bad.append((on, profile))
    _hammer(work)
    assert not seen_bad


def test_detected_game_and_exe_stay_a_pair():
    st = AppState()
    bad = []

    def work(i, r):
        if i % 2 == 0:
            st.set_detected(f'g{i}', f'g{i}.exe') if r % 2 else st.set_detected()
        else:
            game, exe = st.detected_snapshot()
            if bool(game) != bool(exe) or (game and exe != game + '.exe'):
                bad.append((game, exe))
    _hammer(work)
    assert not bad


def test_toggling_from_many_threads_loses_no_flip():
    st = AppState()
    _hammer(lambda i, r: st.toggle_ignore_mode(), threads=8, rounds=2500)
    assert st.ignore_mode is False          # 20000 flips: an even number, every one counted


def test_defaults_and_set_game_off():
    st = AppState()
    assert st.game_snapshot() == (False, '') and st.detected_snapshot() == ('', '')
    st.set_game(True, 'ets2')
    assert st.game_mode is True and st.game_profile == 'ets2'
    st.set_game(False)
    assert st.game_snapshot() == (False, '')
