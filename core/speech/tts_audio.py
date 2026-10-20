"""Audio output and input-device hooks for core.speech.tts. Playback is the native audio service (core/native_audio.py, native/jarvis_audio)."""

import time

from core import native_audio


def ensure_player() -> bool:
    """Start the native player if it is not running and wait for its output stream; False when it cannot be had."""
    return native_audio.ensure_ready()


def wait_for_playback_idle(timeout: float = 90.0, poll: float = 0.08) -> None:
    native_audio.wait_idle(timeout=timeout, poll=poll)


def apply_audio_devices(output_device_name: str | None = None, input_device_name: str | None = None) -> tuple[bool, str]:
    msgs = []
    ok = True

    # --- Output (TTS) ---
    # The player follows the Windows default output device (and re-opens when it changes), so there is nothing to apply live.
    try:
        import core.audio_utils as _au
        _au._last_jarvis_hp_check = 0.0
    except Exception: pass
    if output_device_name:
        msgs.append(f'✓ Вывод сохранён ({output_device_name}) — звук идёт на устройство вывода Windows по умолчанию')
    else:
        msgs.append('✓ Вывод сброшен на системный')

    # --- Input (Microphone) ---
    try:
        from core.engine.jarvis import get_engine
        eng = get_engine()
        if eng is not None:
            from config_pack.config import RATE, CHUNK_MS
            from core.audio_utils import open_input
            chunk = int(RATE * CHUNK_MS / 1000)
            # eng.stream is read continuously by JarvisEngine.run()'s own
            # thread (self.stream.read(...) in a tight loop) — closing and
            # reassigning it from this (caller's) thread with no coordination
            # raced against an in-flight read() and corrupted the process
            # heap (Windows STATUS_HEAP_CORRUPTION, 0xc0000374 — see
            # logs/crash_dump.log). _calibrating is the same flag
            # run_calibration_ui already uses to keep that loop from touching
            # the stream while it's mid-swap; the brief sleep after setting
            # it gives a read() already in progress (bounded by one chunk's
            # duration, tens of ms) time to actually return before close().
            eng._calibrating = True
            try:
                time.sleep(0.1)
                try:
                    eng.stream.close()
                except Exception:
                    pass
                try:
                    eng.stream = open_input(RATE, chunk, device_name=input_device_name, force_default=not input_device_name)
                    msgs.append('✓ Микрофон переключён (активен немедленно)')
                except Exception as e:
                    # Try fallback to default
                    try:
                        eng.stream = open_input(RATE, chunk, force_default=True)
                        msgs.append('⚠ Не удалось переключить микрофон, восстановлен системный')
                    except Exception as e2:
                        msgs.append(f'⚠ Критическая ошибка микрофона: {e2}')
                        ok = False
            finally:
                eng._calibrating = False
        else:
            msgs.append('ℹ Движок не запущен — микрофон применится при следующем старте')
    except Exception as e:
        msgs.append(f'⚠ Ошибка входа: {e}')

    return ok, '  •  '.join(msgs)
