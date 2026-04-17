from __future__ import annotations
import threading
class HudState:
    IDLE = 'IDLE'
    LISTENING = 'LISTENING'
    SPEAKING = 'SPEAKING'
    _LABELS = {'IDLE': 'ОЖИДАНИЕ', 'LISTENING': 'СЛУШАЮ', 'SPEAKING': 'ГОВОРЮ'}
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
    @property
    def label(self) -> str:
        with self._lock:
            return self._LABELS.get(self._mode, self._mode)
STATE = HudState()
def set_mode(mode: str) -> None:
    STATE.mode = mode
