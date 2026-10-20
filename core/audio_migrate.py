"""One-time migration of the saved microphone: the old setting was a PortAudio index (`audio_input_device_index`), the native capture
keeps the device by name (`audio_input_device_name`). Where PyAudio is still installed the index is turned into the name; where it is
not (or the index is stale) the setting is dropped and the Windows default input is used. Runs at most once per settings file.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def _name_for_index(index: int) -> str | None:
    try:
        import pyaudio
    except ImportError:
        return None
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_device_info_by_index(index)
        if int(info.get('maxInputChannels', 0)) > 0:
            return str(info.get('name', '')).replace('\n', ' ').strip() or None
    except Exception:
        _log.debug('index %s is not a device any more', index, exc_info=True)
    finally:
        pa.terminate()
    return None


def migrate_input_device(read, update) -> bool:
    """`read()` returns the settings dict, `update(changes, remove=...)` saves. True when something was migrated."""
    s = read()
    index = s.get('audio_input_device_index')
    if index is None:
        return False
    changes = {}
    name = None if (s.get('audio_input_device_name') or isinstance(index, bool) or not isinstance(index, int)) else _name_for_index(index)
    if name:
        changes['audio_input_device_name'] = name
    update(changes, remove=('audio_input_device_index',))
    _log.info('Microphone setting migrated: index %s -> %s', index, name or 'system default')
    return True
