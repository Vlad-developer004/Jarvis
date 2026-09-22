"""Background-thread wrapper for anything that's expected to eventually call
speak(). An uncaught exception in a bare `threading.Thread(target=...)` dies
silently — the thread just stops, and the user is left waiting for a spoken
answer that will never come. That exact bug has shown up independently in
this codebase (actions/weather.py's forecast lookups, and a documented 2026-09
regression in features/ets2/monitor.py's _monitor_loop). Anything that speaks
from a background thread should go through this instead of a bare
threading.Thread so a bug there fails loud (into the log and, optionally,
into a spoken error) instead of just going quiet.
"""
import threading

from core.logging_setup import get_logger

_log = get_logger('speech.safe_task')


def run_speaking_task(fn, *args, error_message: str | None = None,
                       thread_name: str | None = None, daemon: bool = True,
                       speak_fn=None, **kwargs) -> threading.Thread:
    """Runs fn(*args, **kwargs) in a background thread. If fn raises, logs
    the exception and — if `error_message` is given — speaks it, instead of
    letting the thread die with no spoken response at all.

    `speak_fn` defaults to core.speech.tts.speak; pass a handler's own
    .speak (e.g. handler.speak) when the caller has one, so the fallback
    utterance goes through the same is_speaking/state bookkeeping as the
    rest of that handler's responses."""
    def _wrapped():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            _log.error('background speaking task %r failed: %s', thread_name or fn, e, exc_info=True)
            if error_message:
                try:
                    _speak = speak_fn
                    if _speak is None:
                        from core.speech.tts import speak as _speak
                    _speak(error_message)
                except Exception:
                    pass

    t = threading.Thread(target=_wrapped, daemon=daemon, name=thread_name)
    t.start()
    return t
