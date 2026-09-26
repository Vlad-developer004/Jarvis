import threading as _threading

class AppState:
    def __init__(self):
        # Guards compound (read-modify-write) mutations only — e.g. toggling a
        # flag. Plain single-attribute get/set elsewhere is already atomic
        # under the GIL and doesn't need this; see toggle_ignore_mode() for
        # the one confirmed race this fixes (reactor click thread vs. voice
        # command thread both touching ignore_mode).
        self._lock: _threading.Lock = _threading.Lock()
        self.pytorch_loaded: _threading.Event = _threading.Event()
        self.nlp_loading: bool = False  # True while semantic model weights are loading
        self.jarvis_active: bool = False
        self.last_command_time: float = 0.0
        self.dictation_mode: bool = False
        self.game_mode: bool = False
        self.game_profile: str = ''
        self.detected_game: str = '' # Game profile stem detected in focus
        self.detected_exe: str = ''  # EXE name in focus
        self.interactive_state = None
        self.interactive_data: dict = {}
        self.ignore_mode: bool = False
        self.mouse_moving: bool = False
        self.mouse_dx: int = 0
        self.mouse_dy: int = 0
        self.mouse_speed: float = 1.0
        self.hud = None
        self.last_media_hwnd: int = 0
        self.remote_control_enabled: bool = True
        # Live mic-activity readout for the HUD (single-attribute writes,
        # no lock needed — see class docstring above). Updated every audio
        # frame from the engine's hot loop (core/engine/jarvis.py), read
        # periodically by the HUD's own polling loop — never call into the
        # HUD directly from the audio thread (binding rule: UI updates only
        # through the existing message-passing mechanism).
        self.mic_level: int = 0        # last frame's RMS (core.audio_utils.rms_int16 scale)
        self.last_speech_ts: float = 0.0  # time.time() of the last detected voice onset, 0 = never

    def toggle_ignore_mode(self) -> bool:
        """Atomically flip ignore_mode and return the new value. Use this
        instead of `app_state.ignore_mode = not app_state.ignore_mode` —
        that read-modify-write can race with the direct assignments in
        core/handler/commands/system.py's listen_on/listen_off (different
        thread: voice command vs. reactor click)."""
        with self._lock:
            self.ignore_mode = not self.ignore_mode
            return self.ignore_mode
app_state = AppState()

