# VK lookup tables for actions/keysend.py — covers only key names actually used
# across the codebase today (game profiles in data/game_profiles/*.json, Photoshop/
# Figma hotkey tables in core/handler/commands/creative.py, browser/clipboard/media
# shortcuts), not the full pyautogui/pydirectinput key universe.

_F_KEYS = {f'f{i}': 0x6F + i for i in range(1, 25)}  # f1=0x70 .. f24=0x87
_NUMPAD_DIGITS = {f'numpad{i}': 0x60 + i for i in range(10)}

_NAMED_VKS = {
    'ctrl': 0x11, 'control': 0x11, 'lctrl': 0x11,
    'shift': 0x10, 'lshift': 0x10,
    'alt': 0x12, 'lalt': 0x12,
    'win': 0x5B, 'winleft': 0x5B, 'super': 0x5B,
    'enter': 0x0D, 'return': 0x0D,
    'esc': 0x1B, 'escape': 0x1B,
    'tab': 0x09,
    'space': 0x20, ' ': 0x20,
    'backspace': 0x08,
    'delete': 0x2E, 'del': 0x2E,
    'insert': 0x2D,
    'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pagedown': 0x22,
    'capslock': 0x14,
    'pause': 0x13, 'break': 0x13,
    'printscreen': 0x2C, 'prtsc': 0x2C,
    'numlock': 0x90,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'add': 0x6B,        # numpad +
    'subtract': 0x6D,   # numpad -
    'multiply': 0x6A,   # numpad *
    'divide': 0x6F,     # numpad /
    'decimal': 0x6E,    # numpad .
    '+': 0xBB, '-': 0xBD,
    '[': 0xDB, ']': 0xDD, '\\': 0xDC, ';': 0xBA, "'": 0xDE,
    ',': 0xBC, '.': 0xBE, '/': 0xBF, '`': 0xC0,
    # Hardware media/volume keys — extended keys, see _EXTENDED_VKS below.
    'volumeup': 0xAF, 'volumedown': 0xAE, 'volumemute': 0xAD,
    'playpause': 0xB3, 'nexttrack': 0xB0, 'prevtrack': 0xB1, 'stoptrack': 0xB2,
}

_STR_TO_VK: dict[str, int] = {**_F_KEYS, **_NUMPAD_DIGITS, **_NAMED_VKS}
for _d in '0123456789':
    _STR_TO_VK[_d] = ord(_d)
for _c in 'abcdefghijklmnopqrstuvwxyz':
    _STR_TO_VK[_c] = ord(_c.upper())

# VKs that require KEYEVENTF_EXTENDEDKEY (MS docs: nav cluster, right-hand
# modifiers, NUM LOCK, BREAK, PRINT SCREEN, numpad DIVIDE/ENTER — plus the
# hardware media/volume keys, which Windows also treats as extended).
_EXTENDED_VKS: frozenset[int] = frozenset({
    0x21, 0x22, 0x23, 0x24,        # pageup/pagedown/end/home
    0x25, 0x26, 0x27, 0x28,        # arrows
    0x2D, 0x2E,                    # insert/delete
    0x90, 0x13, 0x2C,              # numlock/pause/printscreen
    0x6F,                          # numpad divide
    0xAF, 0xAE, 0xAD,              # volume up/down/mute
    0xB3, 0xB0, 0xB1, 0xB2,        # media play-pause/next/prev/stop
})


def resolve_vk(key) -> int:
    """Accepts an int VK or a string key name (case-insensitive) and returns a VK int."""
    if isinstance(key, int):
        return key
    name = str(key).strip().lower()
    if name in _STR_TO_VK:
        return _STR_TO_VK[name]
    if len(name) == 1:
        return ord(name.upper())
    raise KeyError(f"Unknown key name: {key!r}")
