from __future__ import annotations
import math, time
import tkinter as tk
from . import hud_constants as _c
from .hud_constants import _CYAN, _MAG, _GREEN, _WHITE, _DYN, _STA, _GRID, _DIM, _TEXT, _AMBER
from .hud_state import HudState, STATE
from .hud_utils import _blend
def draw_static(hud) -> None:
    c = hud._canvas
    cx, cy = (hud._cx, hud._cy)
    c.delete(_STA)
    step = 44
    for gx in range(0, cx * 2, step):
        c.create_line(gx, 0, gx, cy * 2, fill=_GRID, width=1, tags=_STA)
    for gy in range(0, cy * 2, step):
        c.create_line(0, gy, cx * 2, gy, fill=_GRID, width=1, tags=_STA)
    cs, mg = (24, 16)
    for (bx, by), (fx, fy) in (((mg, mg), (+1, +1)), ((cx * 2 - mg - cs, mg), (-1, +1)), ((mg, cy * 2 - mg - cs), (+1, -1)), ((cx * 2 - mg - cs, cy * 2 - mg - cs), (-1, -1))):
        for col, pts in ((_blend(_CYAN, 0.4), [(bx, by, bx + cs * fx, by), (bx, by, bx, by + cs * fy)]), (_CYAN, [(bx, by, bx + (cs - 4) * fx, by), (bx, by, bx, by + (cs - 4) * fy)])):
            for x1, y1, x2, y2 in pts:
                c.create_line(x1, y1, x2, y2, fill=col, width=2, tags='static')
    c.tag_lower('static')
def animate(hud) -> None:
    mode = STATE.mode
    fps = hud._FPS_IDLE if mode == HudState.IDLE else hud._FPS_ACTIVE
    try:
        draw_frame(hud)
    except Exception:
        pass
    hud.root.after(1000 // fps, lambda: animate(hud))
def draw_poly(hud, c, cx, cy, r, sides, rotation=0, tags=_DYN, **kwargs):
    pts = []
    for i in range(sides):
        ang = math.radians(rotation + i * (360 / sides))
        pts.extend([cx + r * math.cos(ang), cy - r * math.sin(ang)])
    return c.create_polygon(pts, tags=tags, **kwargs)
def init_anim_objects(hud) -> None:
    c = hud._canvas
    cx, cy = hud._cx, hud._cy
    scale = min(cx * 0.9, cy * 0.78)
    hud._anim_scale = scale
    c.delete(_DYN)
    r_out = scale * 0.74
    r_in  = scale * 0.54
    r_riv = r_in * 0.88
    _lp   = _c._LOW_PERF_MODE
    n_blades = 6 if _lp else 10
    n_riv    = 12 if _lp else 24
    dot_r = max(2, int(scale * 0.018))
    sw    = max(2, int(scale * 0.016))
    dummy = [cx, cy] * 20
    hud._blade_ids = [
        c.create_polygon(dummy, fill=_blend(_CYAN, 0.22),
                         outline=_blend(_CYAN, 0.9), width=2, tags=_DYN)
        for _ in range(n_blades)
    ]
    hud._n_blades = n_blades
    hud._outer_ring_ids = [
        c.create_oval(cx - r_out * 1.04, cy - r_out * 1.04,
                      cx + r_out * 1.04, cy + r_out * 1.04,
                      outline=_blend(_CYAN, 0.35), width=2, tags=_DYN),
        c.create_oval(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                      outline=_blend(_CYAN, 0.25), width=1, tags=_DYN),
    ]
    hud._rivet_ids = []
    for i in range(n_riv):
        a  = math.radians(i * 360 / n_riv)
        rx = cx + r_riv * math.cos(a)
        ry = cy - r_riv * math.sin(a)
        hud._rivet_ids.append(
            c.create_oval(rx - dot_r, ry - dot_r, rx + dot_r, ry + dot_r,
                          fill=_blend(_CYAN, 0.7), outline='', tags=_DYN)
        )
    hud._inner_ring_ids = []
    for ri, alpha, w in ((0.4, 0.4, 2), (0.32, 0.35, 1), (0.24, 0.3, 1)):
        r = scale * ri
        hud._inner_ring_ids.append(
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=_blend(_CYAN, alpha), width=w, tags=_DYN)
        )
    r_ia = scale * 0.4
    hud._arc_id = c.create_arc(
        cx - r_ia, cy - r_ia, cx + r_ia, cy + r_ia,
        start=0, extent=90, outline=_CYAN, width=2, style='arc', tags=_DYN,
    )
    hud._spoke_ids = [
        c.create_line(cx, cy, cx, cy,
                      fill=_blend(_CYAN, 0.75), width=sw, tags=_DYN)
        for _ in range(3)
    ]
    nr0 = scale * 0.1
    hud._core_ids = [
        c.create_oval(cx - nr0 * 2.2, cy - nr0 * 2.2, cx + nr0 * 2.2, cy + nr0 * 2.2,
                      fill=_blend(_CYAN, 0.12), outline='', tags=_DYN),
        c.create_oval(cx - nr0 * 1.4, cy - nr0 * 1.4, cx + nr0 * 1.4, cy + nr0 * 1.4,
                      fill=_blend(_CYAN, 0.45), outline='', tags=_DYN),
        c.create_oval(cx - nr0, cy - nr0, cx + nr0, cy + nr0,
                      fill=_WHITE, outline='', tags=_DYN),
    ]
    _title_fs = max(10, int(scale * 0.092))
    _state_fs = max(8,  int(scale * 0.062))
    hud._title_shadow_id = c.create_text(
        cx + 2, cy - scale * 0.9 + 2,
        text='J.A.R.V.I.S.', fill=_blend(_CYAN, 0.2),
        font=(hud._F, _title_fs, 'bold'), tags=_DYN,
    )
    hud._title_id = c.create_text(
        cx, cy - scale * 0.9,
        text='J.A.R.V.I.S.', fill=_WHITE,
        font=(hud._F, _title_fs, 'bold'), tags=_DYN,
    )
    hud._status_id = c.create_text(
        cx, cy + scale * 0.9,
        text=STATE.label, fill=_CYAN,
        font=(hud._F, _state_fs, 'bold'), tags=_DYN,
    )
_MODE_COLORS: dict = {}
def _get_mode_colors(core_col: str) -> dict:
    if core_col not in _MODE_COLORS:
        _MODE_COLORS[core_col] = {
            'blade_fill':    _blend(core_col, 0.22),
            'blade_outline': _blend(core_col, 0.9),
            'outer0':        _blend(core_col, 0.35),
            'outer1':        _blend(core_col, 0.25),
            'rivet':         _blend(core_col, 0.7),
            'inner0':        _blend(core_col, 0.4),
            'inner1':        _blend(core_col, 0.35),
            'inner2':        _blend(core_col, 0.3),
            'spoke':         _blend(core_col, 0.75),
            'core0':         _blend(core_col, 0.12),
            'core1':         _blend(core_col, 0.45),
            'title_shadow':  _blend(core_col, 0.2),
        }
    return _MODE_COLORS[core_col]
def draw_frame(hud) -> None:
    if not hud._blade_ids:
        return
    c  = hud._canvas
    cx = hud._cx
    cy = hud._cy
    t  = time.time()
    mode = STATE.mode
    if mode == HudState.IDLE:
        core_col = _CYAN
        spd   = 1.0
        pulse = math.sin(t * 1.5) * 3
    elif mode == HudState.LISTENING:
        core_col = _GREEN
        spd   = 2.4
        pulse = math.sin(t * 7.5) * 6
    else:
        core_col = _MAG
        spd   = 3.8
        pulse = math.sin(t * 14.0) * 4
    cols = _get_mode_colors(core_col)
    scale  = hud._anim_scale
    r_out  = scale * 0.74
    r_in   = scale * 0.54
    n_blades   = hud._n_blades
    rot_b      = t * 5 * spd % 360
    step_ang   = 360.0 / n_blades
    blade_span = step_ang * 0.7
    blade_fill    = cols['blade_fill']
    blade_outline = cols['blade_outline']
    steps = 4 if _c._LOW_PERF_MODE else 8
    for i, bid in enumerate(hud._blade_ids):
        ca = rot_b + i * step_ang
        a1 = ca - blade_span * 0.5
        a2 = ca + blade_span * 0.5
        pts: list[float] = []
        for s in range(steps + 1):
            a = math.radians(a1 + (a2 - a1) * s / steps)
            pts.append(cx + r_out * math.cos(a))
            pts.append(cy - r_out * math.sin(a))
        for s in range(steps, -1, -1):
            a = math.radians(a1 + (a2 - a1) * s / steps)
            pts.append(cx + r_in * math.cos(a))
            pts.append(cy - r_in * math.sin(a))
        c.coords(bid, *pts)
        c.itemconfig(bid, fill=blade_fill, outline=blade_outline)
    if getattr(hud, '_last_mode_col', None) != core_col:
        hud._last_mode_col = core_col
        c.itemconfig(hud._outer_ring_ids[0], outline=cols['outer0'])
        c.itemconfig(hud._outer_ring_ids[1], outline=cols['outer1'])
        riv_col = cols['rivet']
        for rid in hud._rivet_ids:
            c.itemconfig(rid, fill=riv_col)
        for rid, col_key in zip(hud._inner_ring_ids, ('inner0', 'inner1', 'inner2')):
            c.itemconfig(rid, outline=cols[col_key])
        c.itemconfig(hud._title_shadow_id, fill=cols['title_shadow'])
    rot_ir = -t * 12 * spd % 360
    c.itemconfig(hud._arc_id, start=rot_ir, outline=core_col)
    r_sp_out  = scale * 0.38
    r_sp_in   = scale * 0.12
    rot_sp    = t * 10 * spd % 360
    spoke_col = cols['spoke']
    for i, sid in enumerate(hud._spoke_ids):
        a  = math.radians(rot_sp + i * 120)
        c.coords(sid,
                 cx + r_sp_in  * math.cos(a), cy - r_sp_in  * math.sin(a),
                 cx + r_sp_out * math.cos(a), cy - r_sp_out * math.sin(a))
        c.itemconfig(sid, fill=spoke_col)
    nr = scale * 0.1 + pulse * 0.25
    c.coords(hud._core_ids[0],
             cx - nr * 2.2, cy - nr * 2.2, cx + nr * 2.2, cy + nr * 2.2)
    c.itemconfig(hud._core_ids[0], fill=cols['core0'])
    c.coords(hud._core_ids[1],
             cx - nr * 1.4, cy - nr * 1.4, cx + nr * 1.4, cy + nr * 1.4)
    c.itemconfig(hud._core_ids[1], fill=cols['core1'])
    c.coords(hud._core_ids[2], cx - nr, cy - nr, cx + nr, cy + nr)
    status_col = _CYAN if mode == HudState.IDLE else core_col
    c.itemconfig(hud._status_id, fill=status_col, text=STATE.label)
    hud._tick += 1
    _sys_every = 50 if _c._LOW_PERF_MODE else 25
    if hud._tick % _sys_every == 0:
        hud._update_sys_widgets()
def draw_top_strip(hud, evt=None) -> None:
    c = hud._top_canvas
    W = c.winfo_width()
    if W < 10:
        try:
            W = hud._mid.winfo_width()
        except:
            pass
    if W < 10:
        return
    s = hud._ui_scale * hud.zoom_factor
    ico_sz = max(30, int(38 * s))
    fs_time = max(18, int(22 * s))
    fs_lbl = max(9, int(10 * s))
    fs_bar = max(9, int(10 * s))
    gap = max(8, int(10 * s))
    pad_v = max(12, int(16 * s))
    row_gap = max(18, int(22 * s))
    bar_h = max(6, int(8 * s))
    bar_pad = max(30, int(48 * s))
    lbl_gap = max(3, int(4 * s))
    bar_mb = max(10, int(12 * s))
    is_small = W < 500 or (W < 900 and hud.zoom_factor > 1.5)
    row_gap = max(10, int(14 * s)) if is_small else max(18, int(22 * s))
    bar_mb = max(6, int(8 * s)) if is_small else max(10, int(12 * s))
    text_h = fs_lbl + lbl_gap + fs_time
    row_h = max(ico_sz, text_h)
    H_single = row_gap + fs_bar + bar_mb + bar_h
    H_text = row_gap + fs_bar + row_gap
    H_need = pad_v + row_h + H_single + H_text + pad_v
    c.configure(height=H_need)
    c.delete('all')
    cx = W // 2
    txt_w = max(int(fs_time * 3.6), int(fs_lbl * 6))
    blk_w = ico_sz + gap + txt_w
    div_gap = max(18, int(22 * s))
    if W < 500: div_gap = max(6, int(8 * s))
    left_x = cx - div_gap - blk_w
    right_x = cx + div_gap
    row_cy = pad_v + row_h // 2
    def _draw_block(bx, ico_img, label, time_str, time_col):
        if ico_img:
            c.create_image(bx, row_cy - ico_sz // 2, anchor='nw', image=ico_img)
        tx = bx + ico_sz + gap
        ty_lbl = row_cy - text_h // 2
        ty_time = ty_lbl + fs_lbl + lbl_gap
        c.create_text(tx, ty_lbl, text=label, anchor='nw', fill=_DIM, font=(hud._F, fs_lbl, 'bold'), tags='top_txt')
        c.create_text(tx, ty_time, text=time_str, anchor='nw', fill=time_col, font=(hud._F, fs_time, 'bold'), tags='top_txt')
    _draw_block(left_x, hud._rise_icon_img, 'ВОСХОД', hud._top_rise, _AMBER)
    c.create_line(cx, pad_v, cx, pad_v + row_h, fill=_CYAN, width=2)
    _draw_block(right_x, hud._set_icon_img, 'ЗАКАТ', hud._top_set, _MAG)
    label_y = pad_v + row_h + row_gap
    bar_y = label_y + fs_bar + bar_mb
    bx0, bx1 = (bar_pad, W - bar_pad)
    _tcol = _AMBER if 'ДЕНЬ' in hud._top_week else _MAG
    l_week = hud._top_week
    l_day = hud._top_day
    if is_small:
        if 'СВЕТОВОЙ' in l_week:
            l_week = 'ДЕНЬ'
            l_day = 'ЗАКАТ'
        if 'НОЧНОЙ' in l_week:
            l_week = 'НОЧЬ'
            l_day = 'РАССВЕТ'
    c.create_text(bx0, label_y, text=l_week, anchor='nw', fill=_tcol, font=(hud._F, fs_bar, 'bold'))
    c.create_text(cx, label_y, text=hud._top_pct_str, anchor='n', fill=_TEXT, font=(hud._F, fs_bar, 'bold'))
    c.create_text(bx1, label_y, text=l_day, anchor='ne', fill=_tcol, font=(hud._F, fs_bar, 'bold'))
    c.create_rectangle(bx0, bar_y, bx1, bar_y + bar_h, fill=_GRID, outline='', width=0)
    fill1 = int((bx1 - bx0) * max(0.0, min(1.0, hud._top_pct)))
    if fill1 > 0:
        c.create_rectangle(bx0, bar_y, bx0 + fill1, bar_y + bar_h, fill=_tcol, outline='', width=0)
    label_y2 = bar_y + bar_h + row_gap
    yday_str = getattr(hud, '_top_yday_str', '')
    wday_str = getattr(hud, '_top_wday_str', '')
    week_str = getattr(hud, '_top_week_str', '')
    if is_small:
        yday_str = yday_str.replace('ДЕНЬ', 'Д.')
        week_str = week_str.replace('НЕДЕЛЯ', 'Н.')
        if W < 500 or hud.zoom_factor > 1.8:
            yday_str = yday_str.replace('Д.', '')
            week_str = week_str.replace('Н.', '')
            if ' ' in yday_str: yday_str = yday_str.split()[-1]
            if ' ' in week_str: week_str = week_str.split()[-1]
            wday_str = wday_str[:3] + '.' if len(wday_str) > 3 else wday_str
    c.create_text(bx0, label_y2, text=yday_str, anchor='nw', fill=_CYAN, font=(hud._F, fs_bar, 'bold'))
    c.create_text(cx, label_y2, text=wday_str, anchor='n', fill=_TEXT, font=(hud._F, fs_bar, 'bold'))
    c.create_text(bx1, label_y2, text=week_str, anchor='ne', fill=_CYAN, font=(hud._F, fs_bar, 'bold'))
def draw_bot_strip(hud, evt=None) -> None:
    c = hud._bot_canvas
    c.delete('all')
    hud._bot_items.clear()
    W = c.winfo_width()
    H = c.winfo_height()
    if W < 10 or H < 10:
        return
    is_narrow = W < 500
    s = hud._ui_scale * hud.zoom_factor
    fs = max(9, int(11 * s))
    dot_r = max(2, int(3 * s)) if is_narrow else max(3, int(4 * s))
    box_pad_x = max(8, int(12 * s)) if is_narrow else max(16, int(20 * s))
    box_pad_y = max(6, int(10 * s)) if is_narrow else max(8, int(12 * s))
    states = [(HudState.IDLE, 'ОЖИД.' if is_narrow else 'ОЖИДАНИЕ'), (HudState.LISTENING, 'СЛУШ.' if is_narrow else 'СЛУШАЮ'), (HudState.SPEAKING, 'ГОВ.' if is_narrow else 'ГОВОРЮ')]
    boxes = []
    tw_total = 0
    for _, text in states:
        tid = c.create_text(0, -100, text=text, font=(hud._F, fs, 'bold'))
        bbox = c.bbox(tid)
        c.delete(tid)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        bx_w = dot_r * 2 + tw + box_pad_x * 2 + 10
        boxes.append((bx_w, th))
        tw_total += bx_w
    tw_total = sum((b[0] for b in boxes))
    cy = H // 2
    mode = STATE.mode
    active_col = {HudState.IDLE: _CYAN, HudState.LISTENING: _GREEN, HudState.SPEAKING: _MAG}
    for i, (state, text) in enumerate(states):
        is_active = state == mode
        col = active_col.get(state, _CYAN)
        bc = col if is_active else _blend(col, 0.3)
        tc = _WHITE if is_active else _DIM
        dot_c = col if is_active else _DIM
        bx_w, th = boxes[i]
        bx_h = th + box_pad_y * 2
        target_cx = (i + 1) * (W // 4)
        x0 = target_cx - bx_w // 2
        x1 = target_cx + bx_w // 2
        y0 = cy - bx_h // 2
        y1 = cy + bx_h // 2
        cl = max(4, int(6 * s))
        thick = 2 if is_active else 1
        ids = []
        bg_col = _blend(col, 0.1)
        bg_id = c.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, fill=bg_col if is_active else '', outline='')
        ids.append(bg_id)
        brd_col = bc if is_active else ''
        ids.append(c.create_line(x0, y0 + cl, x0, y0, x0 + cl, y0, fill=brd_col, width=thick))
        ids.append(c.create_line(x0, y1 - cl, x0, y1, x0 + cl, y1, fill=brd_col, width=thick))
        ids.append(c.create_line(x1, y0 + cl, x1, y0, x1 - cl, y0, fill=brd_col, width=thick))
        ids.append(c.create_line(x1, y1 - cl, x1, y1, x1 - cl, y1, fill=brd_col, width=thick))
        dx = x0 + box_pad_x + dot_r
        dot_id = c.create_oval(dx - dot_r, cy - dot_r, dx + dot_r, cy + dot_r, fill=dot_c, outline='')
        txt_id = c.create_text(dx + dot_r + 10, cy, text=text, anchor='w', fill=tc, font=(hud._F, fs, 'bold'))
        ids.extend([dot_id, txt_id])
        hud._bot_items.append({'state': state, 'col': col, 'ids': ids})
