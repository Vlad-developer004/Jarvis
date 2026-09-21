"""
General-purpose countdown timer with milestone warnings and alarm on completion.
One active timer at a time; new timer cancels the previous one.
"""
import threading
import time
from typing import Optional

_lock = threading.Lock()
_active_timer: Optional['_Timer'] = None

# Milestones in minutes — only those < total duration are used
_MILESTONES = (30, 15, 10, 5, 1)


def _beep(freq: int, duration_ms: int):
    try:
        import winsound
        winsound.Beep(freq, duration_ms)
    except Exception:
        pass


def _alert(speak_fn, message: str, loud: bool = False):
    try:
        from core.speech import play_alert_sound
        if loud:
            play_alert_sound('alarm')
            time.sleep(0.5)
        else:
            play_alert_sound('milestone')
            time.sleep(0.25)
    except Exception:
        if loud:
            for freq in (1000, 880, 760):
                _beep(freq, 300)
                time.sleep(0.15)
        else:
            _beep(880, 250)
    speak_fn(message)


class _Timer:
    def __init__(self, total_sec: int, label: str, speak_fn, hud=None):
        self.label = label
        self._speak = speak_fn
        self._hud = hud
        self._start = time.monotonic()
        self._total_sec = total_sec
        self._cancelled = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name='jarvis-timer')
        self._thread.start()

    def cancel(self):
        self._cancelled.set()

    def remaining_sec(self) -> int:
        elapsed = time.monotonic() - self._start
        return max(0, int(self._total_sec - elapsed))

    def total_sec(self) -> int:
        return self._total_sec

    def extend(self, extra_sec: int):
        self._total_sec += extra_sec
        if self._hud is not None:
            try:
                from ui.hud_timer_widget import update_timer_total
                self._hud._hud_queue.put(lambda t=self._total_sec: update_timer_total(self._hud, t))
            except Exception:
                pass

    def _run(self):
        fired: set[int] = set()

        while True:
            if self._cancelled.is_set():
                return

            elapsed = time.monotonic() - self._start
            remaining = self._total_sec - elapsed

            if remaining <= 0:
                break

            remaining_min = remaining / 60
            for m in _MILESTONES:
                if m in fired:
                    continue
                if remaining_min <= m + 0.1 and self._total_sec / 60 > m:
                    fired.add(m)
                    if m == 1:
                        msg = 'Осталась одна минута.'
                    else:
                        from core.nlp import format_duration_russian
                        msg = f'Осталось {format_duration_russian(m)}.'
                    _alert(self._speak, msg, loud=False)
                    break

            time.sleep(0.5)

        if not self._cancelled.is_set():
            label_part = f' «{self.label}»' if self.label else ''
            msg = f'Сэр, таймер{label_part} завершён.'
            _alert(self._speak, msg, loud=True)
            _clear_active()
            _on_timer_done(self.label, self._hud)


def _on_timer_done(label: str, hud) -> None:
    if hud is None:
        return
    try:
        from ui.hud_timer_widget import hide_timer_widget, show_timer_done_popup
        hud._hud_queue.put(lambda: hide_timer_widget(hud))
        hud._hud_queue.put(lambda: show_timer_done_popup(label, hud.root))
    except Exception:
        pass


def _clear_active():
    global _active_timer
    with _lock:
        _active_timer = None


def set_timer(seconds: int, label: str, speak_fn, hud=None) -> str:
    """Start a new timer. Returns human-readable duration string."""
    global _active_timer
    from core.nlp import format_duration_russian
    with _lock:
        if _active_timer is not None:
            _active_timer.cancel()
            if hud is not None:
                try:
                    from ui.hud_timer_widget import hide_timer_widget
                    hud._hud_queue.put(lambda: hide_timer_widget(hud))
                except Exception:
                    pass
        _active_timer = _Timer(seconds, label, speak_fn, hud)

    if hud is not None:
        try:
            from ui.hud_timer_widget import show_timer_widget
            hud._hud_queue.put(lambda: show_timer_widget(hud, seconds, label))
        except Exception:
            pass

    mins = seconds // 60
    return format_duration_russian(mins) if mins >= 1 else f'{seconds} секунд'


def add_time(extra_sec: int) -> bool:
    """Add time to the running timer. Returns False if no timer active."""
    with _lock:
        if _active_timer is None:
            return False
        _active_timer.extend(extra_sec)
        return True


def cancel_timer() -> bool:
    """Cancel active timer. Returns True if one was running."""
    global _active_timer
    with _lock:
        if _active_timer is None:
            return False
        hud = _active_timer._hud
        _active_timer.cancel()
        _active_timer = None
    if hud is not None:
        try:
            from ui.hud_timer_widget import hide_timer_widget
            hud._hud_queue.put(lambda: hide_timer_widget(hud))
        except Exception:
            pass
    return True


def get_status() -> Optional[int]:
    """Returns remaining seconds, or None if no active timer."""
    with _lock:
        if _active_timer is None:
            return None
        return _active_timer.remaining_sec()
