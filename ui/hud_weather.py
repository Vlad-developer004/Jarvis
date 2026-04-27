from __future__ import annotations
import threading
from .hud_constants import _WHITE, _TEXT, _DIM
from . import hud_renderer as renderer
def weather_tick(hud) -> None:
    if not hud._widget_vis.get('weather', True):
        return
    threading.Thread(target=lambda: _fetch_weather(hud), daemon=True).start()
    
    # Adaptive retry: if last data failed, retry much sooner (30s) instead of 10m
    delay = 600000
    if hasattr(hud, '_last_weather_data') and hud._last_weather_data and not hud._last_weather_data.get('ok'):
        delay = 30000
        
    hud.root.after(delay, lambda: weather_tick(hud))
def _fetch_weather(hud) -> None:
    try:
        from actions.weather import get_weather_hud
        data = get_weather_hud()
        hud._hud_queue.put(lambda: apply_weather(hud, data))
    except Exception:
        pass
def apply_weather(hud, d: dict) -> None:
    if not hud._widget_vis.get('weather', True):
        return
    hud._last_weather_data = d
    try:
        col = d.get('color', '#ffffff')
        hud._wx_icon_lbl.configure(text=d.get('icon', '?'), fg=col)
        hud._wx_temp_lbl.configure(text=f"{d.get('temp', 0):+d}°" if d.get('ok') else '—°', fg=_WHITE)
        hud._wx_feels_lbl.configure(text=f"ощущается {d.get('feels', 0):+d}°")
        hud._wx_desc_lbl.configure(text=d.get('desc', '—').upper(), fg=_TEXT if d.get('ok') else _DIM)
        hud._wx_city_lbl.configure(text=d.get('city', '—'))
        hud._wx_wind_lbl.configure(text=str(d.get('wind', '—')))
        hud._wx_hum_lbl.configure(text=f"{d.get('humidity', '—')}%")
        hud._wx_pres_lbl.configure(text=str(d.get('pressure', '—')) if d.get('ok') else '—')
        if d.get('ok'):
            hud._top_rise = d.get('sunrise', '—:—')
            hud._top_set = d.get('sunset', '—:—')
            renderer.draw_top_strip(hud)
    except Exception:
        pass
