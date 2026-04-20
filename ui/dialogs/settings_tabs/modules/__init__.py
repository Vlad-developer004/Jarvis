import tkinter as tk
import customtkinter as ctk
from .premium_view import build_modules_tab as _build

def build_modules_tab(inner, win, hud, _save_hud_settings):
    _build(inner, win, hud, _save_hud_settings)
