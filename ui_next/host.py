"""The core's side of its window.

Everything the assistant needs from the screen goes through here: the state of the voice loop (idle, listening, speaking), notices, the
answer card, reminder and timer pop-ups, the blocking questions, and commands such as "open settings". The window itself is a separate
process (ui_next/shell.py starts it); this module talks to it through the bridge (ui_next/bridge). While no window is connected every call
is a harmless no-op that reports it did nothing, so the core never waits for a screen.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)

# ---- colours of notices (the bridge turns them into info / warning / error) ----
CYAN = '#35e0ff'
AMBER = '#ffb347'
RED = '#ff5470'


# ---- the voice loop state ----
class HudState:
    IDLE = 'IDLE'
    LISTENING = 'LISTENING'
    SPEAKING = 'SPEAKING'
    LOADING = 'LOADING'

    def __init__(self):
        self._lock = threading.Lock()
        self._mode = self.IDLE

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @mode.setter
    def mode(self, v: str):
        with self._lock:
            self._mode = v

    def transition(self, expected: str, new: str) -> bool:
        """Sets `new` only if the mode is still `expected`, in one step, so a check-then-set from the audio loop cannot overwrite a change made by
        another thread in between."""
        with self._lock:
            if self._mode != expected:
                return False
            self._mode = new
            return True


STATE = HudState()


def set_mode(mode: str) -> None:
    STATE.mode = mode


def set_mode_if(expected: str, mode: str) -> bool:
    return STATE.transition(expected, mode)


# ---- notices: short messages shown in the window's header strip ----
_notices_lock = threading.Lock()
_active_notices: dict[str, tuple[str, str]] = {}      # key -> (text, colour)


def notify(key: str, text: str, color: str = CYAN, duration: Optional[int] = None) -> None:
    """Shows a message from any thread. Different keys are shown together; the same key updates its text. `duration` (ms) clears just that key later,
    without it the message stays until clear_notify(key)."""
    with _notices_lock:
        _active_notices[key] = (text, color)
    if duration is not None:
        t = threading.Timer(max(0, duration) / 1000.0, lambda: clear_notify(key))
        t.daemon = True
        t.start()


def clear_notify(key: str) -> None:
    with _notices_lock:
        _active_notices.pop(key, None)


def active_notices() -> list[tuple[str, str, str]]:
    """[(key, text, colour)] sorted by key, for the bridge's `notices` topic."""
    with _notices_lock:
        return sorted((k, t, c) for k, (t, c) in _active_notices.items())


# ---- the window ----
def connected() -> bool:
    try:
        from ui_next import bridge
        return bridge.connected()
    except Exception:
        return False


def _publish(topic: str, payload: dict, sticky: bool = False) -> bool:
    try:
        from ui_next import bridge
        if not bridge.connected():
            return False
        bridge.publish(topic, payload, sticky=sticky)
        return True
    except Exception:
        _swallow()
        return False


def command(op: str, **args) -> bool:
    """Tells the window to do something (`view`, `show`, `reactor`, `compose`, `wizard`, `guard`). False when no window is connected."""
    return _publish('uicmd', {'op': op, **args})


def show_window() -> bool:
    """Brings the window forward (out of the tray); starts it when it is not running."""
    if command('show'):
        return True
    try:
        from ui_next import shell
        return shell.ensure_running()
    except Exception:
        _swallow()
        return False


def open_view(name: str) -> bool:
    """Shows a screen: dash, commands, rems, calendar, songs, cinema, mail, games, perf, exts, voice, look (settings)."""
    show_window()
    return command('view', name=name)


def reactor(op: str, color: str = '') -> bool:
    """The reactor effects: op is `color` (with a name), `reset`, `pulse` or `glitch`."""
    return command('reactor', what=op, color=color)


def open_mail_compose() -> bool:
    show_window()
    return command('compose')


def open_wizard() -> bool:
    show_window()
    return command('wizard')


# ---- the answer card (an AI answer streaming in, a picture of the day, a recognised song) ----
def _answer(kind: str, *args) -> bool:
    try:
        from ui_next import bridge
        return bridge.answer_event(kind, *args)
    except Exception:
        _swallow()
        return False


def _mini_window_enabled() -> bool:
    try:
        from core import settings_io
        return bool(settings_io.read().get('ai_mini_window', True))
    except Exception:
        return True


def cancel_hide_ai_window() -> None:
    _answer('cancel_hide')


def show_ai_window(subject: str, fetch_image: bool = True) -> None:
    if _mini_window_enabled():
        _answer('show', subject, fetch_image)


def update_ai_window_text(text: str) -> None:
    _answer('text', text)


def set_ai_window_links(links: list) -> None:
    """Buttons on the answer card: [{'label', 'url'}] (web links only)."""
    _answer('links', links)


def set_ai_window_image(path: str) -> None:
    _answer('image', path)


def set_ai_window_video(path: str) -> None:
    _answer('video', path)


def hide_ai_window(delay_ms: int = 5000) -> None:
    _answer('hide', delay_ms)


# ---- reminders and timers ----
def show_alert(title: str, text: str, *, tone: str = 'info', image: str = '', actions: list | None = None, voice: tuple | None = None, done=None, timeout: float | None = None) -> bool:
    """A pop-up the user dismisses (a reminder that is due, a timer that ended). `actions` = [{'id', 'label', 'primary'?}] adds buttons beside the
    default one; `done(status, value)` runs once when it closes, value being the id of the pressed extra button (or None). `voice` = (words that
    confirm, words that cancel) lets a spoken word close it. False when no window is connected."""
    ids = {str(a.get('id')) for a in (actions or [])}
    try:
        from ui_next.bridge import prompts
        data = {'tone': tone, 'title': str(title)[:120], 'text': str(text)[:600], 'image': image, 'actions': [{'id': str(a['id']), 'label': str(a['label'])[:40], 'primary': bool(a.get('primary'))} for a in (actions or [])]}
        return prompts.open_prompt('notice', data, {'validate': lambda v: v if v in ids else None}, done or (lambda s, v: None), timeout=timeout, voice=voice)
    except Exception:
        _swallow()
        return False


def toast(key: str, title: str, text: str, *, color: str = CYAN, tone: str = 'info', actions: list | None = None, done=None, timeout: float | None = 30,
          notice_ms: int = 20000) -> bool:
    """A message the user can see without hearing it: a notice in the header strip, and a pop-up unless game mode is on (a pop-up over a game
    would still pull the player's eyes out of it). Returns whether the pop-up was shown."""
    notify(key, f'{title}. {text}', color, duration=notice_ms)
    try:
        from core.system import app_state
        if app_state.game_snapshot()[0]:
            return False
    except Exception:
        _swallow()
    return show_alert(title, text, tone=tone, actions=actions, done=done, timeout=timeout)


def show_timer_done(label: str) -> bool:
    return show_alert('Таймер', f'Время вышло: {label}' if label else 'Время вышло', tone='info')


# ---- settings the old HUD kept in memory ----
def settings() -> dict:
    try:
        from core import settings_io
        return settings_io.read()
    except Exception:
        return {}


def launch_rules() -> dict:
    rules = settings().get('app_launch_rules', {})
    return rules if isinstance(rules, dict) else {}


# ---- blocking questions (the window shows them; without a window they count as cancelled) ----
VOICE_CONFIRM = ('создай', 'создать', 'створи', 'create', 'сделай', 'подтверди', 'готово', 'отправь', 'да', 'окей', 'okay', 'ok')
VOICE_CANCEL = ('отмена', 'отменить', 'нет', 'закрой', 'закрыть', 'cancel', 'хватит', 'стоп')
VOICE_COMMIT_CONFIRM = ('коммит', 'commit', 'закоммить', 'отправь', 'залей', 'пуш', 'push', 'подтверди', 'готово', 'создай', 'сделай', 'да', 'окей', 'okay', 'ok')


def _dialogs():
    from ui_next.bridge import dialogs
    return dialogs


def ask_text(*, title, header, ok_text=None, cancel_text=None, placeholder='', hint_voice=None, voice_confirm_phrases=None, voice_cancel_phrases=None,
             require_message_to_confirm=False, initial_path=None, show_extension_field=False, default_extension=None, initial_value=None, **_old_window_sizes):
    """A line of text, optionally with a folder and a file type: the text, (folder, text), (folder, name, extension), or None when cancelled."""
    from core import i18n
    d = _dialogs()
    res = d.ask_text(title=title, header=header, ok_text=ok_text or i18n.tr('buttons.ok') or 'ОК', cancel_text=cancel_text or i18n.tr('buttons.cancel'), placeholder=placeholder,
                     hint_voice=hint_voice if hint_voice is not None else i18n.tr('name_dlg.default_hint'),
                     voice_confirm=tuple(voice_confirm_phrases) if voice_confirm_phrases is not None else VOICE_CONFIRM,
                     voice_cancel=tuple(voice_cancel_phrases) if voice_cancel_phrases is not None else VOICE_CANCEL,
                     require_message_to_confirm=require_message_to_confirm, initial_path=initial_path, show_extension_field=show_extension_field,
                     default_extension=default_extension, initial_value=initial_value)
    return None if res is d.NOT_HANDLED else res


def ask_git_stage(repo_path, files):
    """The files and options of a git commit as a dict, or None when cancelled."""
    d = _dialogs()
    res = d.ask_git_stage(repo_path, files)
    return None if res is d.NOT_HANDLED else res


def open_cleanup(candidates, on_confirm) -> bool:
    return _dialogs().open_cleanup(candidates, on_confirm)


def open_yt_picker(candidates, on_select, on_timeout=None, on_cancel=None, timeout_sec: float = 20.0) -> bool:
    return _dialogs().open_yt_picker(candidates, on_select, on_timeout, on_cancel, timeout_sec)


def select_index(i: int) -> bool:
    return _dialogs().yt_select(i)


def cancel_picker() -> bool:
    return _dialogs().yt_cancel()


def is_picker_open() -> bool:
    return _dialogs().yt_open()


def show_guard_alert(image_path) -> bool:
    return _dialogs().show_guard_alert(image_path)


def exit_now(code: int = 0) -> None:
    """Ends the core: closes the window process and the bridge first (os._exit skips the exit hooks that would do it)."""
    import os
    try:
        from ui_next import shell
        shell.stop()
    except Exception:
        _swallow()
    try:
        from ui_next import bridge
        bridge.stop()
    except Exception:
        _swallow()
    os._exit(code)
