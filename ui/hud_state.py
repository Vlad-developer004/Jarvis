from __future__ import annotations
import threading
from core import i18n

class HudState:
    IDLE = 'IDLE'
    LISTENING = 'LISTENING'
    SPEAKING = 'SPEAKING'
    LOADING = 'LOADING'
    _LABELS = {'IDLE': 'hud.state.waiting', 'LISTENING': 'hud.state.listening', 'SPEAKING': 'hud.state.speaking', 'LOADING': 'hud.state.loading'}
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
            key = self._LABELS.get(self._mode, self._mode)
            return i18n.tr(key) if key in self._LABELS.values() else key
STATE = HudState()
def set_mode(mode: str) -> None:
    STATE.mode = mode
