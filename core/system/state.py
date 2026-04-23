class AppState:
    def __init__(self):
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
app_state = AppState()
