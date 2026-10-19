"""Bridge between the Jarvis core and the new UI (started by main.py at startup).

Core code calls only the cheap hooks below (``heard``/``reply``); everything else is
read by the observer thread from state the core already keeps (HUD state, app_state,
HUD notices), so the audio and dispatch paths are not touched.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time

from typing import TYPE_CHECKING

from .hub import Hub
from core.safe import swallow as _swallow

if TYPE_CHECKING:     # never runs: it lets PyInstaller see the screens that run_command imports by name
    from . import ai, backup, cinema, dev, modules, perf, prompts, tools, wizard  # noqa: F401

_log = logging.getLogger(__name__)
_hub: Hub | None = None
_lock = threading.Lock()
_pending_heard = ''
_pending_ts = 0.0
_history: list[dict] = []
_handler = None            # CommandHandler of the running core: lets the UI run catalog commands
_catalog: dict | None = None
_HISTORY_MAX = 12
_PAIR_WINDOW_SEC = 20.0
_MERGE_WINDOW_MS = 8000
_DID_MAX = 160


_STRESS_RE = re.compile(r'\+(?=[A-Za-zЀ-ӿ])')   # TTS stress marks like "д+а"


def display_text(text: str) -> str:
    """Speech text as shown on screen: no <break/> tags, *emphasis* asterisks or "+" stress marks."""
    try:
        from core.speech.tts import strip_speech_markup
        text = strip_speech_markup(text)
    except Exception:
        _swallow()
    return _STRESS_RE.sub('', text).strip()


def _cmd_autostart(data: dict) -> dict:
    from core.system import autostart_enabled, autostart_set
    autostart_set(bool(data.get('on')))
    return {'ok': True, 'on': autostart_enabled()}


def _catalog_item(cid: str) -> dict | None:
    cat = _catalog
    return next((i for i in cat['items'] if i['id'] == cid), None) if cat else None


def _run_phrase(handler, phrase: str, cid: str) -> None:
    try:
        heard(phrase)               # shows the phrase in the core and pairs it with the reply in the history
        handler.handle(cid, phrase)
    except Exception:
        _log.exception('ui command %s failed', cid)


def _cmd_run(data: dict) -> dict:
    """Runs a catalog command through the same handler voice uses. Only catalog ids are accepted (never free text)."""
    cid = str(data.get('id', ''))
    item = _catalog_item(cid)
    if item is None or item['mode'] == 'voice':
        return {'ok': False, 'error': 'not_runnable'}
    if item['mode'] == 'confirm' and data.get('confirm') is not True:
        return {'ok': False, 'error': 'confirm_required'}
    handler = _handler
    if handler is None:
        return {'ok': False, 'error': 'no_handler'}
    phrase = item.get('try')
    if not phrase:
        return {'ok': False, 'error': 'not_runnable'}
    threading.Thread(target=_run_phrase, args=(handler, phrase, cid), daemon=True, name='ui-bridge-run').start()
    return {'ok': True, 'phrase': phrase}


def _cmd_mic(data: dict) -> dict:
    """Microphone on/off = the old HUD reactor click: ignore_mode (Jarvis ignores everything until switched back on)."""
    from core.system import app_state
    with app_state._lock:       # same lock toggle_ignore_mode() takes
        app_state.ignore_mode = not bool(data.get('on'))
        muted = app_state.ignore_mode
    return {'ok': True, 'muted': muted}


def _publish_catalog() -> None:
    global _catalog
    try:
        from .catalog import build_catalog
        _catalog = build_catalog()
        publish('catalog', _catalog)
    except Exception:
        _log.exception('command catalog failed')


_TIMER_MAX_SEC = 24 * 3600


def _seconds(data: dict) -> int | None:
    try:
        n = int(data.get('seconds'))
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= _TIMER_MAX_SEC else None


def _speaker():
    h = _handler
    return h.speak if h is not None else (lambda _t: None)


def _cmd_timer(data: dict) -> dict:
    """start (replaces a running one, like the voice command), add, cancel."""
    from actions import game_timer
    op = str(data.get('op', 'start'))
    if op == 'cancel':
        return {'ok': game_timer.cancel_timer()}
    secs = _seconds(data)
    if secs is None:
        return {'ok': False, 'error': 'bad_seconds'}
    if op == 'add':
        return {'ok': game_timer.add_time(secs)}
    if op == 'sub':
        return {'ok': game_timer.sub_time(secs)}
    if op == 'start':
        game_timer.set_timer(secs, str(data.get('label') or '').strip()[:60], _speaker())
        return {'ok': True}
    return {'ok': False, 'error': 'bad_op'}


def _cmd_reminder(data: dict) -> dict:
    from features import reminder
    if str(data.get('op', 'add')) == 'cancel':
        try:
            return {'ok': reminder.cancel_reminder(int(data.get('id')))}
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'bad_id'}
    secs = _seconds(data)
    text = str(data.get('text') or '').strip()[:120]
    if secs is None or not text:
        return {'ok': False, 'error': 'bad_args'}
    reminder.schedule_reminder(secs, text, _speaker())
    return {'ok': True}


def _cmd_game_launch(data: dict) -> dict:
    """Launches an installed game from the published library (by id): same path as the voice command."""
    from . import library
    handler = _handler
    if handler is None:
        return {'ok': False, 'error': 'no_handler'}
    game = library.find(str(data.get('id', '')))
    if game is None:
        return {'ok': False, 'error': 'unknown_game'}
    handler._launch_game_engine(game)
    return {'ok': True, 'name': game.name}


def _cmd_library(data: dict) -> dict:
    from . import library
    return {'ok': library.scan_async(publish, force=True)}


def _cmd_guard(data: dict) -> dict:
    """{on: bool}: switches the camera guard (it takes a few seconds to learn the owner's face, so the answer does not wait; the `guard` topic follows)."""
    from features import guard
    if 'on' not in data:
        return {'ok': True, 'on': guard.is_active()}
    want = bool(data.get('on'))

    def work():
        from ui_next import host
        ok, res = guard.start_guard() if want else guard.stop_guard()
        if not ok and want:
            host.notify('guard', 'Охрана не включилась: ' + str(res), host.RED, duration=8000)
    threading.Thread(target=work, name='ui-guard', daemon=True).start()
    return {'ok': True, 'pending': True}


def _publish_catalog_async() -> None:
    threading.Thread(target=_publish_catalog, name='ui-bridge-catalog', daemon=True).start()


# Commands the UI may send. Keep this a short whitelist: each entry is something the old HUD already let the user do.
# Handlers that read this package's state (the running handler, the catalog) live here; the router of an operation lives in routes.py;
# a screen that has a `run(data)` of its own is named in _SCREENS and imported on first use.
_SCREENS = {'tools': 'tools', 'modules': 'modules', 'dev': 'dev', 'ai': 'ai', 'backup': 'backup', 'wizard': 'wizard', 'cinema': 'cinema', 'prompt': 'prompts', 'perf': 'perf'}
_ROUTES = ('extension', 'ext_setup', 'profile', 'currency', 'voice', 'mail', 'media', 'calendar', 'song_open', 'song_clear', 'answer', 'open_url')
COMMANDS = {'autostart': _cmd_autostart, 'run': _cmd_run, 'mic': _cmd_mic, 'timer': _cmd_timer, 'reminder': _cmd_reminder, 'game_launch': _cmd_game_launch, 'library': _cmd_library, 'guard': _cmd_guard}


def run_command(cmd: str, data: dict):
    fn = COMMANDS.get(cmd)
    if fn is not None:
        return fn(data)
    if cmd in _ROUTES:
        from . import routes
        return getattr(routes, cmd)(data)
    if cmd in _SCREENS:
        import importlib
        return importlib.import_module(f'{__name__}.{_SCREENS[cmd]}').run(data)
    return None


def set_handler(handler) -> None:
    """The command handler exists once the engine is ready; from then on the window can run commands."""
    global _handler
    _handler = handler


def connected() -> bool:
    """True while a new-UI window is listening: the core then shows answer cards and dialogs there instead of in the old Tk windows."""
    hub = _hub
    return hub is not None and hub.has_clients()


def answer_event(kind: str, *args) -> bool:
    """Core hook for the answer card (ui/hud_ai_window.py): True when the new window is connected and took the event, so the old Tk window stays closed."""
    if not connected():
        return False
    from . import answer
    return answer.event(kind, *args)


def publish(topic: str, payload, *, sticky: bool = True) -> None:
    hub = _hub
    if hub is not None:
        hub.publish(topic, payload, sticky=sticky)


def heard(text: str) -> None:
    """Core hook: a final recognised phrase."""
    global _pending_heard, _pending_ts
    if _hub is None or not text:
        return
    with _lock:
        _pending_heard, _pending_ts = text, time.time()
    publish('heard', {'text': text, 'ts': int(time.time() * 1000)}, sticky=False)


def reply(text: str) -> None:
    """Core hook: text handed to TTS. Paired with the last heard phrase into the history list."""
    global _pending_heard
    if _hub is None or not text or not text.strip():
        return
    text = display_text(text)
    if not text:
        return
    now = time.time()
    with _lock:
        said = _pending_heard if now - _pending_ts <= _PAIR_WINDOW_SEC else ''
        _pending_heard = ''
        last = _history[-1] if _history else None
        if not said and last is not None and now * 1000 - last['ts'] < _MERGE_WINDOW_MS:
            last['did'] = (last['did'] + ' ' + text.strip())[:_DID_MAX]   # streamed answer: one history row
            last['ts'] = int(now * 1000)
        else:
            _history.append({'said': said, 'did': text.strip()[:_DID_MAX], 'ts': int(now * 1000)})
            del _history[:-_HISTORY_MAX]
        snapshot = list(_history)
    publish('reply', {'text': text.strip(), 'ts': int(now * 1000)}, sticky=False)
    publish('history', snapshot)


def start(handler=None) -> int | None:
    """Starts the hub, the discovery file and the observer. Safe to call twice. ``handler`` enables running commands from the UI."""
    global _hub, _handler
    with _lock:
        if _hub is not None:
            return _hub.port
        _handler = handler
        hub = Hub()
        hub.command_handler = run_command
        port = hub.start()
        hub.write_info()
        _hub = hub
    import atexit
    atexit.register(hub.remove_info)
    from .observer import Observer
    Observer(publish).start()
    threading.Thread(target=_publish_catalog, name='ui-bridge-catalog', daemon=True).start()
    from . import library
    library.scan_async(publish)
    from .extensions import publish_extensions
    publish_extensions(publish)
    from .songs import publish_songs
    publish_songs(publish)
    from . import voice
    voice.bind(publish)
    from . import answer, prompts
    answer.bind(publish)
    prompts.bind(publish)
    from . import perf
    perf.bind(publish)
    from . import mail as _mail
    threading.Thread(target=_mail.warm, daemon=True, name='ui-bridge-mail-warm').start()
    _log.info('UI bridge listening on 127.0.0.1:%s', port)
    return port


def stop() -> None:
    global _hub
    with _lock:
        hub, _hub = _hub, None
    if hub is not None:
        hub.remove_info()
        hub.stop()
