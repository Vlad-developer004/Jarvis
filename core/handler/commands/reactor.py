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
    from ui import hud as _hud
    h = getattr(_hud, '_hud', None)
    if not h:
        handler.speak(spk('hud.not_running'))
        return
    if cmd in _COLOR_BY_CMD:
        color = _COLOR_BY_CMD[cmd]
        h._hud_queue.put(lambda c=color: h._set_reactor_color(c))
    elif cmd == 'reactor_reset':
        h._hud_queue.put(lambda: h._reset_reactor_color())
    elif cmd == 'reactor_pulse':
        h._hud_queue.put(lambda: h._trigger_reactor_pulse())
    elif cmd == 'reactor_glitch':
        h._hud_queue.put(lambda: h._trigger_reactor_glitch())
    else:
        return
    handler.play_response()
