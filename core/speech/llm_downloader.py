"""Fetches the default local-chat model on demand instead of shipping it in
every installer.

The default model is the stock Q5_K_M GGUF quant of Vikhr-Llama-3.2-1B-Instruct
from its official Hugging Face repo (persona/style comes entirely from
_SYSTEM_PROMPT in llm_chat.py, not from any fine-tune baked into the weights):
https://huggingface.co/Vikhrmodels/Vikhr-Llama-3.2-1B-instruct-GGUF

Users can still point Jarvis at their own GGUF file via Settings > Voice
(llm_chat_model_path) — this module only covers the no-custom-model case.
"""

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core.logging_setup import get_logger

_log = get_logger('llm_downloader')

_MODEL_URL = (
    'https://huggingface.co/Vikhrmodels/Vikhr-Llama-3.2-1B-instruct-GGUF'
    '/resolve/main/Vikhr-Llama-3.2-1B-Q5_K_M.gguf'
)

_lock = threading.Lock()
_downloading = False
_cancel_event = threading.Event()


class _Cancelled(Exception):
    pass


def default_model_path() -> str:
    from core.speech.llm_chat import get_default_model_path
    return get_default_model_path()


def is_default_model_present() -> bool:
    return os.path.isfile(default_model_path())


def is_downloading() -> bool:
    return _downloading


def cancel_download() -> None:
    """No-op if nothing is running — the worker just checks this flag
    between chunks, so cancelling a finished/absent download is safe."""
    _cancel_event.set()


def download_default_model(
    on_progress: Optional[Callable[[int, int], None]] = None,
    on_done: Optional[Callable[[bool, str], None]] = None,
) -> bool:
    """Downloads the default model in a background daemon thread.

    on_progress(bytes_done, bytes_total) — total is 0 if the server didn't
    send Content-Length; throttled to ~4/s so it's safe to marshal straight
    into a UI update.
    on_done(ok, message) — called exactly once, from the worker thread; the
    caller is responsible for dispatching to the UI thread if needed (same
    convention as model_fetcher.refresh_async). ok is False both on a real
    failure and on cancel_download() — callers that need to tell them apart
    should check is_default_model_present() / their own cancel flag.

    Not resumable: a dropped connection or cancel_download() always restarts
    from 0 next time, there's no HTTP Range retry. Fine for a one-shot ~870MB
    fetch on the happy path; revisit if flaky-connection retries turn out to
    be common in practice.

    Returns False immediately (no thread started, on_done not called) if a
    download is already in progress.
    """
    global _downloading
    if not _lock.acquire(blocking=False):
        return False
    _downloading = True
    _cancel_event.clear()

    def _work():
        global _downloading
        dest = Path(default_model_path())
        tmp = dest.with_suffix('.part')
        ok, msg = False, ''
        try:
            import requests
            dest.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(_MODEL_URL, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get('Content-Length', 0))
                done = 0
                last_report = 0.0
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if _cancel_event.is_set():
                            raise _Cancelled()
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if on_progress and now - last_report >= 0.25:
                            last_report = now
                            on_progress(done, total)
                if on_progress:
                    on_progress(done, total)
                if total and done != total:
                    raise RuntimeError(f'Файл оборвался: получено {done} из {total} байт.')
            # llama.cpp can hard-crash the process on a corrupt/truncated
            # GGUF (see validate_gguf_model's docstring) — verify in a
            # throwaway subprocess before the real download ever replaces
            # a working model file.
            from core.speech.llm_chat import validate_gguf_model
            valid, vmsg = validate_gguf_model(str(tmp))
            if not valid:
                raise RuntimeError(f'Скачанный файл не прошёл проверку: {vmsg}')
            os.replace(tmp, dest)
            ok, msg = True, 'Модель загружена и проверена.'
            _log.info('Default chat model downloaded to %s', dest)
        except _Cancelled:
            ok, msg = False, 'Загрузка отменена.'
            _log.info('Default chat model download cancelled by user.')
        except Exception as e:
            _log.error('Default model download failed: %s', e)
            ok, msg = False, str(e)
        finally:
            if not ok:
                try:
                    if tmp.exists():
                        tmp.unlink()
                except Exception:
                    pass
            _downloading = False
            _lock.release()
            if on_done:
                try:
                    on_done(ok, msg)
                except Exception:
                    pass

    threading.Thread(target=_work, daemon=True, name='llm_model_download').start()
    return True
