"""Reactor mic-mute toggle and voice-driven cosmetic effects (color
override, pulse/glitch bursts). Split out of ui/hud.py, same pattern as
hud_layout.py/hud_renderer.py/hud_camera.py: free functions taking `hud`
as the first argument, thinly delegated to from JarvisHUD methods.
"""
from __future__ import annotations
import math
import time
import tkinter as tk
from core import i18n
from .hud_constants import _RED, _CYAN, _GREEN, _AMBER, _MAG, _WHITE


def toggle_mic_mute(hud) -> None:
    from core.system import app_state
    muted = app_state.toggle_ignore_mode()
    try: hud.show_msg(i18n.tr('hud.mic_muted' if muted else 'hud.mic_active'), _RED if muted else _GREEN)
    except: pass

def reactor_hit(hud, evt: tk.Event) -> bool:
    scale = getattr(hud, '_anim_scale', 0)
    if scale <= 0:
        return False
    dx, dy = evt.x - hud._cx, evt.y - hud._cy
    return math.hypot(dx, dy) <= scale * 0.8

def on_reactor_click(hud, evt: tk.Event) -> None:
    if reactor_hit(hud, evt):
        toggle_mic_mute(hud)

def on_reactor_motion(hud, evt: tk.Event) -> None:
    hover = reactor_hit(hud, evt)
    if hover != getattr(hud, '_reactor_hover', None):
        hud._reactor_hover = hover
        try: hud._canvas.configure(cursor='hand2' if hover else '')
        except Exception: pass

def set_reactor_color(hud, name: str) -> None:
    colors = {
        'red': _RED, 'cyan': _CYAN, 'green': _GREEN,
        'amber': _AMBER, 'magenta': _MAG, 'white': _WHITE,
    }
    hud._reactor_color_override = colors.get(name)

def reset_reactor_color(hud) -> None:
    hud._reactor_color_override = None

def trigger_reactor_pulse(hud) -> None:
    hud._reactor_pulse_until = time.time() + 2.0

def trigger_reactor_glitch(hud) -> None:
    hud._reactor_glitch_until = time.time() + 1.2
