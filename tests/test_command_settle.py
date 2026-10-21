"""A chained phrase runs with silent_mode set; it must be cleared only after the command worker has run the commands, not after a fixed sleep."""
import queue
import threading
import time
import types

from core.engine import recognition as rec
from core.handler.dispatch import CommandHandler


def _stub():
    return types.SimpleNamespace(_cmd_queue=queue.Queue())


def test_idle_queue_returns_at_once():
    assert CommandHandler.wait_commands_idle(_stub(), timeout=0.5) is True


def test_waits_for_the_worker_to_finish_the_queued_command():
    h = _stub()
    h._cmd_queue.put('x')
    done = []

    def worker():
        h._cmd_queue.get()
        time.sleep(0.15)
        done.append(1)
        h._cmd_queue.task_done()
    threading.Thread(target=worker, daemon=True).start()
    assert CommandHandler.wait_commands_idle(h, timeout=2.0) is True
    assert done == [1]


def test_gives_up_after_the_timeout():
    h = _stub()
    h._cmd_queue.put('x')                                  # nobody works on it
    t = time.monotonic()
    assert CommandHandler.wait_commands_idle(h, timeout=0.2) is False
    assert time.monotonic() - t < 1.0


def test_settle_tolerates_a_handler_without_the_method():
    rec._settle(object())                                  # fakes in other tests have no worker


def test_settle_calls_the_handler_when_it_has_one():
    calls = []
    rec._settle(types.SimpleNamespace(wait_commands_idle=lambda: calls.append(1)))
    assert calls == [1]


def test_the_fetching_phrase_does_not_hold_back_the_request(monkeypatch):
    """"Узнаю погоду" used to be spoken with wait=True, so the network request began only after the phrase had finished playing."""
    from core.handler.commands import info
    spoken, started = [], []
    handler = types.SimpleNamespace(speak=lambda text, **kw: spoken.append((text, kw)))
    monkeypatch.setattr('actions.weather.is_weather_voice_cached', lambda *a: False)
    monkeypatch.setattr('core.speech.run_speaking_task', lambda fn, **kw: started.append(fn))
    info._weather(handler, 'weather', 'какая погода')
    assert spoken and not spoken[0][1].get('wait')
    assert started
