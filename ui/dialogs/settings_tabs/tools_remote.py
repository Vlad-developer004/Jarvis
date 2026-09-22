"""Remote-control (Telegram) card for the Tools settings tab."""
import os
import tkinter as tk
import customtkinter as ctk
from ui.hud_style import JStyle
from core import i18n
from ui.hud_constants import _BG, _PANEL, _CYAN, _GREEN, _AMBER, _WHITE
from ui.hud_utils import _blend


def build_remote_card(c_remote, hud, _add_context_menu):
    _sf = lambda n: hud._fs(n + 6)

    _remote_connected_f = tk.Frame(c_remote, bg=_PANEL)
    _remote_edit_f = tk.Frame(c_remote, bg=_PANEL)
    _remote_status = tk.Label(c_remote, text='', bg=_PANEL, fg=_blend(_WHITE, 0.4), font=(hud._F, _sf(8)), padx=14)

    _remote_entry_kw = dict(font=(hud._F, _sf(10), 'bold'), fg_color=_BG, text_color=_WHITE,
                             border_color=_blend(_CYAN, 0.35), border_width=1,
                             corner_radius=JStyle.RAD_PANEL, height=JStyle.H_NORM,
                             placeholder_text_color=_blend(_WHITE, 0.25))
    def _paste_into(entry):
        try:
            txt = c_remote.clipboard_get().strip()
        except Exception:
            return
        if txt:
            entry.delete(0, 'end')
            entry.insert(0, txt)

    _paste_btn_kw = dict(width=36, height=JStyle.H_NORM, fg_color='transparent',
                          border_color=_blend(_CYAN, 0.5), border_width=1, text_color=_CYAN,
                          hover_color=_blend(_CYAN, 0.15), font=(hud._F, _sf(11)), corner_radius=JStyle.RAD_PANEL)

    tk.Label(_remote_edit_f, text='Bot Token', bg=_PANEL, fg=_blend(_CYAN, 0.8), font=(hud._F, _sf(9), 'bold'), anchor='w').pack(fill='x', pady=(10, 0), padx=4)
    _token_row = tk.Frame(_remote_edit_f, bg=_PANEL)
    _token_row.pack(fill='x', pady=(2, 8), padx=4)
    _remote_token_entry = ctk.CTkEntry(_token_row, placeholder_text='123456:ABC-DEF...', **_remote_entry_kw)
    _remote_token_entry.pack(side='left', fill='x', expand=True, padx=(0, 6))
    ctk.CTkButton(_token_row, text='📋', command=lambda: _paste_into(_remote_token_entry), **_paste_btn_kw).pack(side='right')

    tk.Label(_remote_edit_f, text='Chat ID', bg=_PANEL, fg=_blend(_CYAN, 0.8), font=(hud._F, _sf(9), 'bold'), anchor='w').pack(fill='x', padx=4)
    _chat_row = tk.Frame(_remote_edit_f, bg=_PANEL)
    _chat_row.pack(fill='x', pady=(2, 8), padx=4)
    _remote_chat_entry = ctk.CTkEntry(_chat_row, placeholder_text='123456789', **_remote_entry_kw)
    _remote_chat_entry.pack(side='left', fill='x', expand=True, padx=(0, 6))
    ctk.CTkButton(_chat_row, text='📋', command=lambda: _paste_into(_remote_chat_entry), **_paste_btn_kw).pack(side='right')

    _add_context_menu(_remote_token_entry)
    _add_context_menu(_remote_chat_entry)

    def _show_edit_mode():
        _remote_connected_f.pack_forget()
        _remote_token_entry.delete(0, 'end')
        _remote_chat_entry.delete(0, 'end')
        _remote_token_entry.insert(0, os.environ.get('TELEGRAM_BOT_TOKEN', ''))
        _remote_chat_entry.insert(0, os.environ.get('TELEGRAM_CHAT_ID', ''))
        _remote_edit_f.pack(fill='x')

    def _show_connected_mode():
        _remote_edit_f.pack_forget()
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        _remote_connected_label.configure(text=i18n.tr('tools.remote_connected').format(chat_id=chat_id))
        _remote_connected_f.pack(fill='x')

    _remote_connected_label = tk.Label(_remote_connected_f, text='', bg=_PANEL, fg=_GREEN, font=(hud._F, _sf(10), 'bold'), anchor='w', justify='left', wraplength=320)
    _remote_connected_label.pack(fill='x', pady=(10, 4), padx=4)
    ctk.CTkButton(
        _remote_connected_f, text=i18n.tr('tools.remote_change_btn'), command=_show_edit_mode,
        height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'),
        fg_color='transparent', hover_color=_blend(_CYAN, 0.2), text_color=_WHITE,
        border_color=_blend(_CYAN, 0.6), border_width=1, corner_radius=JStyle.RAD_PANEL
    ).pack(fill='x', padx=4, pady=(0, 8))

    def _save_remote_creds():
        from ui.dialogs.extensions_common import _save_env_key, _set_feature_module_flag
        token = _remote_token_entry.get().strip()
        chat_id = _remote_chat_entry.get().strip()
        if not token or not chat_id:
            _remote_status.pack(anchor='w', pady=(0, 6))
            _remote_status.configure(text=i18n.tr('tools.mtg_required'), fg=_AMBER)
            return
        _save_env_key('TELEGRAM_BOT_TOKEN', token)
        _save_env_key('TELEGRAM_CHAT_ID', chat_id)
        os.environ['TELEGRAM_BOT_TOKEN'] = token
        os.environ['TELEGRAM_CHAT_ID'] = chat_id
        _set_feature_module_flag('remote_control', True)
        try:
            from core.engine.jarvis import get_engine
            from features.remote_control import start_remote_control
            engine = get_engine()
            if engine is not None:
                start_remote_control(engine.handler)
        except Exception:
            pass
        _remote_status.pack(anchor='w', pady=(0, 6))
        _remote_status.configure(text=i18n.tr('tools.remote_saved'), fg=_GREEN)
        _show_connected_mode()

    ctk.CTkButton(
        _remote_edit_f, text=i18n.tr('buttons.save'), command=_save_remote_creds,
        height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'),
        fg_color='transparent', hover_color=_blend(_GREEN, 0.25),
        text_color=_WHITE, border_color=_blend(_GREEN, 0.8),
        border_width=2, corner_radius=JStyle.RAD_PANEL
    ).pack(anchor='center', fill='x', padx=4, pady=(4, 4))

    from core.system import module_enabled
    if os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID') and module_enabled('remote_control'):
        _show_connected_mode()
    else:
        _show_edit_mode()
