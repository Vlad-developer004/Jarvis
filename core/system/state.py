class AppState:
    def __init__(self):
        self.jarvis_active: bool = False
        self.last_command_time: float = 0.0
        self.dictation_mode: bool = False
        self.game_mode: bool = False
        self.game_profile: str = ''
        self.interactive_state = None
        self.interactive_data: dict = {}
        self.ignore_mode: bool = False
        self.mouse_moving: bool = False
        self.mouse_dx: int = 0
        self.mouse_dy: int = 0
        self.mouse_speed: float = 1.0
app_state = AppState()
