"""Dialogs the core waits for (a name for a new folder, the files of a git commit, what to clean up, which video to play) shown in the new window instead of the old Tk dialogs.

One prompt is open at a time. `open_prompt()` publishes it on the sticky `prompt` topic ({id, kind, open, data}); the screen answers with the `prompt` command (op `answer`: {id, status, value}) and the answer is validated
here against what was offered (a cleanup can only delete paths that were listed, a commit can only stage files that were listed) before the core's callback runs. Voice phrases ("создай", "отмена", "первое") work as
before: they reach the screen as `prompt_cmd` events or finish the prompt directly. When no new window is connected `open_prompt()` returns False and the old dialog is used. The kinds are built in dialogs.py.
"""
from __future__ import annotations

import itertools
import logging
import threading
from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)
NOT_HANDLED = object()
_lock = threading.Lock()
_ids = itertools.count(1)
_cur: dict | None = None
_publish = None


def bind(publish) -> None:
    global _publish
    _publish = publish


def _emit(topic: str, payload: dict, sticky: bool = True) -> None:
    pub = _publish
    if pub is not None:
        try:
            pub(topic, payload, sticky=sticky)
        except TypeError:
            pub(topic, payload)


def available() -> bool:
    try:
        from ui_next import bridge
        return bridge.connected()
    except Exception:
        return False


class _VoiceShim:
    """Stands in for the Tk window the voice-prompt bridge expects: it runs callbacks at once and exists while the prompt is open."""

    def __init__(self, pid: int):
        self.pid = pid

    def after(self, _ms, fn):
        fn()

    def winfo_exists(self) -> bool:
        with _lock:
            return _cur is not None and _cur['id'] == self.pid


def open_prompt(kind: str, data: dict, ctx: dict, done, *, timeout: float | None = None, voice: tuple | None = None) -> bool:
    """Shows a prompt. `ctx` = {'validate': fn(value) -> cleaned value (raises ValueError)}; `done(status, value)` runs once in its own thread with status 'ok', 'cancel' or 'timeout'.
    `voice` = (confirm phrases, cancel phrases) makes spoken words press the screen's buttons. Returns False when no new window is connected."""
    global _cur
    if not available():
        return False
    prompt = {'id': next(_ids), 'kind': kind, 'data': data, 'ctx': ctx, 'done': done, 'timer': None, 'voice': None, 'timeout': timeout}
    with _lock:
        old, _cur = _cur, prompt
    if old is not None:
        _close(old, 'cancel', None)
    if timeout:
        t = threading.Timer(timeout, lambda: _finish(prompt['id'], 'timeout', None))
        t.daemon = True
        prompt['timer'] = t
        t.start()
    if voice:
        try:
            from ui_next.voice_prompt import register_voice_prompt
            shim = _VoiceShim(prompt['id'])
            prompt['voice'] = shim
            register_voice_prompt(shim, on_confirm=lambda: _emit('prompt_cmd', {'id': prompt['id'], 'action': 'confirm'}, False), on_cancel=lambda: _emit('prompt_cmd', {'id': prompt['id'], 'action': 'cancel'}, False),
                                  confirm_phrases=voice[0], cancel_phrases=voice[1])
        except Exception:
            _log.debug('voice prompt not registered', exc_info=True)
    _emit('prompt', {'id': prompt['id'], 'kind': kind, 'open': True, 'data': data, 'timeout': timeout or 0})
    if kind != 'notice':                # a notice appears in the pop-up window over any program; a question needs the main window in front
        try:
            from ui_next import host
            host.command('show')        # a question must not wait in a window hidden in the tray
        except Exception:
            pass
    return True


def update(pid: int, patch: dict) -> None:
    """Adds late data (a downloaded thumbnail) to the open prompt and sends it again."""
    with _lock:
        if _cur is None or _cur['id'] != pid:
            return
        _cur['data'] = {**_cur['data'], **patch}
        msg = {'id': pid, 'kind': _cur['kind'], 'open': True, 'data': _cur['data'], 'timeout': 0}
    _emit('prompt', msg)


def _close(prompt: dict, status: str, value) -> None:
    t = prompt.get('timer')
    if t is not None:
        t.cancel()
    if prompt.get('voice') is not None:
        try:
            from ui_next.voice_prompt import unregister_voice_prompt
            unregister_voice_prompt(prompt['voice'])
        except Exception:
            _swallow()
    _emit('prompt', {'id': prompt['id'], 'kind': prompt['kind'], 'open': False, 'data': {}, 'timeout': 0})
    done = prompt.get('done')
    if done is not None:
        threading.Thread(target=_run_done, args=(done, status, value), daemon=True, name='PromptDone').start()


def _run_done(done, status, value) -> None:
    try:
        done(status, value)
    except Exception:
        _log.exception('prompt callback failed')


def _finish(pid: int, status: str, value) -> bool:
    global _cur
    with _lock:
        if _cur is None or _cur['id'] != pid:
            return False
        prompt, _cur = _cur, None
    _close(prompt, status, value)
    return True


def answer(pid, status, value) -> dict:
    """The screen's answer. `ok` carries a value that is validated against what was offered."""
    with _lock:
        cur = _cur
    if cur is None or cur['id'] != pid:
        return {'ok': False, 'error': 'expired'}
    if status == 'ok':
        try:
            clean = cur['ctx']['validate'](value)
        except (ValueError, TypeError, KeyError):
            return {'ok': False, 'error': 'bad_value'}
        _finish(pid, 'ok', clean)
    elif status in ('cancel', 'timeout'):
        _finish(pid, 'cancel', None)
    else:
        return {'ok': False, 'error': 'bad_value'}
    return {'ok': True}


def ask(kind: str, data: dict, ctx: dict, *, timeout: float | None = None, voice: tuple | None = None):
    """Blocking version for the core's threads: (status, value), or NOT_HANDLED when no new window is connected."""
    box = {}
    ev = threading.Event()

    def done(status, value):
        box['r'] = (status, value)
        ev.set()
    if not open_prompt(kind, data, ctx, done, timeout=timeout, voice=voice):
        return NOT_HANDLED
    ev.wait()
    return box['r']


def current_id() -> int:
    with _lock:
        return _cur['id'] if _cur else 0


def is_open(kind: str) -> bool:
    with _lock:
        return _cur is not None and _cur['kind'] == kind


def finish_kind(kind: str, status: str, value=None) -> bool:
    """Ends the open prompt of a kind from the core's side (a spoken answer): True when there was one."""
    with _lock:
        cur = _cur
    if cur is None or cur['kind'] != kind:
        return False
    if status == 'ok':
        try:
            value = cur['ctx']['validate'](value)
        except (ValueError, TypeError, KeyError):
            return False
    return _finish(cur['id'], status, value)


def run(data: dict) -> dict:
    """Entry of the `prompt` bridge command: op `answer` {id, status, value}."""
    if str(data.get('op')) == 'answer':
        try:
            pid = int(data.get('id'))
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'bad_value'}
        return answer(pid, str(data.get('status', '')), data.get('value'))
    return {'ok': False, 'error': 'bad_op'}
