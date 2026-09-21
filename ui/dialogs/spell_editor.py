"""Voice-pattern ("spell") editor dialog. Split out of the old
editors.py purely for file size; no behavior change.
"""
from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _make_resizable
from ..hud_widgets import _HudScrollbar
def open_spell_editor(hud, reopen: bool = False) -> None:
    if reopen and hud._spell_win and hud._spell_win.winfo_exists():
        hud._spell_win.destroy()
    import sys, json
    from pathlib import Path
    _main = sys.modules.get('__main__')
    profile_display = getattr(_main, '_game_profile', '') if _main else ''
    
    profiles_dir = Path('data') / 'game_profiles'
    profile_file = None
    is_uk = (i18n.get_language() == 'uk')
    
    # If active profile is not Hogwarts, try to find ANY Hogwarts profile automatically
    target_kw = 'hogwarts'
    if not profile_display or target_kw not in profile_display.lower():
        # Look for first available hogwarts profile
        for p in profiles_dir.glob('*.json'):
            stem = p.stem
            if is_uk and not stem.endswith('_uk'):
                continue
            if not is_uk and stem.endswith('_uk'):
                continue
            try:
                d = json.loads(p.read_text(encoding='utf-8'))
                gname = d.get('game', p.stem)
                if target_kw in gname.lower():
                    profile_display = gname
                    if profile_display.endswith('_uk'):
                        profile_display = profile_display[:-3]
                    profile_file = p
                    break
            except Exception: pass
            
    # If still not found by search, try to match current active profile if it exists
    if not profile_file and profile_display:
        for p in profiles_dir.glob('*.json'):
            stem = p.stem
            if is_uk and not stem.endswith('_uk'):
                continue
            if not is_uk and stem.endswith('_uk'):
                continue
            try:
                d = json.loads(p.read_text(encoding='utf-8'))
                gname = d.get('game', p.stem)
                if gname.endswith('_uk'):
                    gname = gname[:-3]
                if gname == profile_display:
                    profile_file = p
                    break
            except Exception: pass

    if not profile_file:
        import tkinter.messagebox as mb
        mb.showinfo(i18n.tr('editor.patterns'), i18n.tr('editor.hogwarts_not_found'))
        return
    data = json.loads(profile_file.read_text(encoding='utf-8'))
    spells: list = data.get('spells')
    if not spells:
        import tkinter.messagebox as mb
        mb.showinfo(i18n.tr('ui.нет_паттернов'), i18n.tr('editor.no_patterns_desc'))
        return
    assign: dict[int, dict[int, str]] = {1: {}, 2: {}, 3: {}, 4: {}}
    for s in spells:
        sn = s.get('set')
        sk = s.get('key')
        if sn in (1, 2, 3, 4) and sk in ('1', '2', '3', '4'):
            assign[sn][int(sk)] = s.get('name', '')
    _slottable = [s for s in spells if s.get('name') and (not s.get('mouse')) and (not s.get('key') or s.get('key') in ('1', '2', '3', '4'))]
    all_names = ['—'] + [s['name'] for s in _slottable]
    win = tk.Toplevel(hud.root)
    hud._spell_win = win
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    win.title(f"{i18n.tr('editor.patterns')} — {profile_display}")
    try:
        if hasattr(hud, '_ico_path'):
            win.iconbitmap(hud._ico_path)
    except Exception:
        pass
    win.configure(bg=_BG)  # type: ignore[call-arg]
    win.resizable(True, False)
    win.update_idletasks()
    
    # Calculate adaptive width that fits the screen even at extreme zoom
    screen_w = win.winfo_screenwidth()
    _W = int(min(hud._px(820), screen_w * 0.95))
    _H = hud._px(500)
    
    win.minsize(hud._px(800), hud._px(500))
    win.geometry(f"{_W}x{_H}")
    _center_window(win, _W, _H)
    win.lift()
    win.focus_force()
    _F_COLORS = ['#00eaff', '#cc44ff', '#44ff88', '#ffaa00']
    _SLOT_NUMS = ['①', '②', '③', '④']
    slot_cbs: dict[tuple[int, int], 'ctk.CTkComboBox'] = {}
    def _autosave():
        profile_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    def _on_select(set_num: int, slot_num: int, chosen: str):
        old = assign[set_num].get(slot_num)
        if old and old != chosen:
            for s in spells:
                if s.get('name') == old:
                    s.pop('set', None)
                    s.pop('key', None)
        if chosen != '—':
            for s in spells:
                if s.get('name') == chosen:
                    prev_sn = s.get('set')
                    prev_sk = s.get('key')
                    if prev_sn in (1, 2, 3, 4) and prev_sk in ('1', '2', '3', '4'):
                        prev_slot = int(prev_sk)
                        if (prev_sn, prev_slot) != (set_num, slot_num):
                            assign[prev_sn].pop(prev_slot, None)
                            other = slot_cbs.get((prev_sn, prev_slot))
                            if other:
                                other.set('—')
                    s['set'] = set_num
                    s['key'] = str(slot_num)
                    assign[set_num][slot_num] = chosen
        else:
            assign[set_num].pop(slot_num, None)
        _autosave()
    tk.Frame(win, bg=_AMBER, height=3).pack(fill='x')
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', pady=(14, 0))
    tk.Label(hdr, text='★', bg=_BG, fg=_AMBER, font=(hud._F, JStyle.TEXT_H1)).pack(side='left', padx=(20, 6))
    tk.Label(hdr, text=i18n.tr('editor.patterns'), bg=_BG, fg=_AMBER, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(side='left')
    tk.Label(hdr, text=profile_display, bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL)).pack(side='right', padx=20)
    col_hdr = tk.Frame(win, bg=_BG)
    col_hdr.pack(fill='x', padx=20, pady=(10, 2))
    tk.Frame(col_hdr, bg=_BG, width=hud._px(68)).pack(side='left')
    for idx in range(4):
        cell = tk.Frame(col_hdr, bg=_BG)
        cell.pack(side='left', expand=True, fill='x')
        tk.Label(cell, text=f"{i18n.tr('editor.slot')}  {_SLOT_NUMS[idx]}", bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL), anchor='center').pack(fill='x')
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=20, pady=(0, 6))
    cards_area = tk.Frame(win, bg=_BG)
    cards_area.pack(fill='both', expand=True, padx=16, pady=(0, 12))
    for i, set_num in enumerate([1, 2, 3, 4]):
        color = _F_COLORS[i]
        card = tk.Frame(cards_area, bg=_PANEL, highlightthickness=0)
        card.pack(fill='x', pady=4)
        tk.Frame(card, bg=color, width=4).pack(side='left', fill='y')
        badge = tk.Frame(card, bg=_PANEL, width=hud._px(68))
        badge.pack(side='left', fill='y')
        badge.pack_propagate(False)
        
        
        tk.Label(badge, text=f'F{set_num}', bg=_PANEL, fg=color, font=(hud._F, JStyle.TEXT_H2, 'bold'), anchor='center').place(relx=0.5, rely=0.5, anchor='center')
        tk.Frame(card, bg=_BRD, width=1).pack(side='left', fill='y', pady=6)
        slots_row = tk.Frame(card, bg=_PANEL)
        slots_row.pack(side='left', fill='both', expand=True, padx=(8, 10), pady=8)
        for j, slot_num in enumerate([1, 2, 3, 4]):
            val = assign[set_num].get(slot_num, '—')
            filled = val != '—'
            
            # Use our premium searchable dropdown instead of basic CTkComboBox
            from ui.hud_widgets import _HUDSearchableDropdown
            v_var = tk.StringVar(value=val)
            
            # Callback to handle selection
            def _on_pick(chosen, sn=set_num, sl=slot_num):
                _on_select(sn, sl, chosen)

            cb = _HUDSearchableDropdown(hud, slots_row, all_names, v_var, 
                                       command=_on_pick, accent=color)
            cb.configure(height=JStyle.H_TOOL)
            cb.frame.pack(side='left', fill='x', expand=True, padx=(0, 4) if j < 3 else 0)
            
            # Update the global map if we need to set it from elsewhere
            slot_cbs[set_num, slot_num] = v_var
    tk.Frame(win, bg=_AMBER, height=2).pack(fill='x', side='bottom')
