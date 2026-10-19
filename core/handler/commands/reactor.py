"""Voice-driven cosmetic effects for the HUD reactor visual (color override,
one-shot pulse / glitch bursts). Purely decorative — never touches
app_state or the audio pipeline.
"""
from core.responses import spk

_COLOR_BY_CMD = {
    'reactor_color_red': 'red',
    'reactor_color_cyan': 'cyan',
    'reactor_color_green': 'green',
    'reactor_color_amber': 'amber',
    'reactor_color_magenta': 'magenta',
    'reactor_color_white': 'white',
}


def handle_reactor(handler, cmd: str, text_lower: str, amount) -> None:
    from ui_next import host
    if cmd in _COLOR_BY_CMD:
        ok = host.reactor('color', _COLOR_BY_CMD[cmd])
    elif cmd == 'reactor_reset':
        ok = host.reactor('reset')
    elif cmd == 'reactor_pulse':
        ok = host.reactor('pulse')
    elif cmd == 'reactor_glitch':
        ok = host.reactor('glitch')
    else:
        return
    if ok:
        handler.play_response()
    else:
        handler.speak(spk('hud.not_running'))
