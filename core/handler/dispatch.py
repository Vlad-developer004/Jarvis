import threading
import re
from core.nlp import extract_amount
from core.system import module_enabled
from .base import BaseHandler
from .interactive import handle_interactive
class CommandHandler(BaseHandler):
    def __init__(self, pa, rate, chunk, asr):
        super().__init__(pa, rate, chunk, asr)
    def handle(self, cmd: str, text: str):
        text_lower = text.lower().strip()
        amount = extract_amount(text_lower)
        if cmd == 'wake': self.play_response('wake')
        t = threading.Thread(
            target=self._execute_command,
            args=(cmd, text, text_lower, amount),
            daemon=True
        )
        t.start()
    def handle_interactive(self, text: str):
        return handle_interactive(self, text)
    def _execute_command(self, cmd: str, text: str, text_lower: str, amount: int):
        print(f'[CMD] cmd={cmd!r} text={text!r}', flush=True)
        if cmd == 'qa_search' and not module_enabled('qa'):
            self.speak('Модуль ИИ отключен в текущем профиле.')
            return
        if cmd.startswith('cinema_') and not module_enabled('cinema'):
            self.speak('Кино модуль отключен в текущем профиле.')
            return
        if cmd in ['game_mode_on', 'game_mode_off', 'exit_game', 'spell_list'] and not module_enabled('games'):
            self.speak('Игровой модуль отключен в текущем профиле.')
            return
        if cmd.startswith('ps_') and not module_enabled('photoshop_voice'):
            self.speak('Модуль Photoshop отключен в текущем профиле.')
            return
        if cmd.startswith('figma_') and not module_enabled('figma_voice'):
            self.speak('Модуль Figma отключен в текущем профиле.')
            return
        if cmd in ('net_profile_status', 'net_profile_switch', 'vpn_reminder') and not module_enabled('network_profiles'):
            self.speak('Модуль «Сеть и система» выключен. Включите расширение в центре модулей.')
            return
        if cmd == 'health_disks' and not module_enabled('system_health'):
            self.speak('Модуль «Сеть и система» выключен. Включите расширение в центре модулей.')
            return
        if cmd == 'calendar_next' and not module_enabled('calendar_ics'):
            self.speak('Модуль «Интеграции» выключен. Включите расширение в центре модулей.')
            return
        if cmd == 'inbox_unread' and not module_enabled('inbox_digest'):
            self.speak('Модуль «Интеграции» выключен. Включите расширение в центре модулей.')
            return
        if cmd == 'mail_compose' and not module_enabled('inbox_digest'):
            self.speak('Модуль «Почта» выключен. Включите расширение в центре модулей.')
            return
        if cmd.startswith('yt_') or cmd.startswith('vol_') or cmd.startswith('app_vol_') or cmd in ('media_pause', 'media_pause_youtube', 'media_pause_browser') or cmd == 'audio_switch':
            from .commands.media import handle_yt_control, handle_volume
            if cmd.startswith('yt_'): handle_yt_control(self, cmd, text_lower)
            elif cmd.startswith('vol_') or cmd.startswith('app_vol_') or cmd == 'audio_switch':
                handle_volume(self, cmd, text_lower, amount)
            elif cmd in ('media_pause', 'media_pause_youtube', 'media_pause_browser'):
                from core.system import app_state
                if app_state.mouse_moving:
                    app_state.mouse_moving = False
                elif app_state.game_mode:
                    try:
                        from core.engine.recognition import _handle_telemetry_action
                        _handle_telemetry_action('go_to_sleep', self, text='стоп')
                    except Exception:
                        import pyautogui; pyautogui.press('space')
                else:
                    ok = False
                    try:
                        from actions.system import send_play_pause_to_video
                        if cmd == 'media_pause_youtube':
                            ok = send_play_pause_to_video(prefer='youtube')
                        elif cmd == 'media_pause_browser':
                            ok = send_play_pause_to_video(prefer='browser')
                        else:
                            ok = send_play_pause_to_video()
                    except Exception:
                        ok = False
                    if not ok:
                        import pyautogui; pyautogui.press('space')
                self.play_response()
        elif cmd in ['min_all', 'min_win', 'unmin_win', 'max_win', 'close_win', 'close_all_win', 'close_other_win', 'min_other_win', 'move_monitor'] or cmd.startswith('win_snap_'):
            from .commands.windows import handle_window
            handle_window(self, cmd, text_lower, amount)
        elif cmd.startswith('mouse_'):
            from .commands.mouse import handle_mouse
            handle_mouse(self, cmd, text_lower, amount)
        elif cmd in ['shutdown', 'restart', 'dictation_on', 'system_cleanup', 'internet_speed', 'wifi_toggle', 'keyboard_lock', 'keyboard_unlock', 'shutdown_timer', 'cancel_timer', 'guard_on', 'guard_off', 'economy_on', 'economy_off', 'listen_off', 'listen_on', 'jarvis_exit', 'keyboard_lock', 'keyboard_unlock', 'bluetooth_toggle', 'reminder'] or cmd.startswith('brightness_'):
            from .commands.system import handle_system
            handle_system(self, cmd, text_lower, amount)
        elif cmd.startswith('clip_') or cmd in ['undo', 'redo', 'select_all']:
            from .commands.clip import handle_clip
            handle_clip(self, cmd, text_lower, amount)
        elif cmd in ['browser_tab', 'close_tab', 'close_tab_n', 'close_all_tabs', 'open_browser_history']:
            from .commands.browser import handle_browser
            handle_browser(self, cmd, text_lower, amount)
        elif cmd in ['qa_search']:
            from .commands.ai import handle_ai
            handle_ai(self, cmd, text_lower, amount)
        elif cmd in ['currency_rate', 'weather', 'google_search', 'translate', 'translate_speech', 'my_ip']:
            from .commands.info import handle_info
            handle_info(self, cmd, text_lower)
        elif cmd in ['empty_trash', 'create_folder', 'delete_folder', 'cd_folder', 'explorer_goto', 'find_doc', 'find_sheet', 'find_file', 'create_word_doc'] or cmd.startswith('recent_'):
            from .commands.files import handle_files
            handle_files(self, cmd, text_lower)
        elif cmd in ['screenshot', 'screenshot_terminal', 'screenshot_site', 'start_video', 'stop_video', 'save_video', 'open_saved', 'clipchamp_last', 'open_last_video', 'paste_file', 'paste_video', 'download_video'] or cmd.startswith('ocr_'):
            from .commands.video import handle_video
            handle_video(self, cmd, text_lower)
        elif cmd in ['note_save', 'cancel_reminder']:
            from .commands.notes import handle_notes
            handle_notes(self, cmd, text_lower, amount)
        elif cmd.startswith('bt') or cmd.startswith('session_') or cmd.startswith('command_') or cmd in ['change_layout', 'press_enter', 'reminder', 'cancel_reminder', 'git_commit', 'today_summary']:
            from .commands.utils import handle_utils
            handle_utils(self, cmd, text_lower)
        elif cmd.startswith('cinema_'):
            from .commands.cinema import handle_cinema
            handle_cinema(self, cmd, text_lower)
        elif cmd.startswith('ps_') or cmd.startswith('figma_'):
            from .commands.creative import handle_creative
            handle_creative(self, cmd, text_lower)
        elif cmd == 'game_mode_on':
            from .commands.game import start_game_selection_flow
            query = text_lower
            query = re.sub(r'\bджарвис(а|у|е)?\b', ' ', query)
            query = re.sub(r'^\s*(активируй|включи|запусти|подготовь)\s+(игровой|игр\w+|геймод|режим игры)\s*(для)?\s*', '', query)
            query = re.sub(r'^\s*(игровой|игр\w+|геймод|режим игры)\s*(для)?\s*', '', query)
            query = re.sub(r'^\s*(запусти игру|запусти|хочу играть в|хочу играть|играть в|играть|игру)\s*', '', query)
            query = re.sub(r'^\s*(го\s+в|хочу\s+в|включи|запусти|играть\s+в)\s*', '', query)
            query = re.sub(r'\s+', ' ', query).strip()
            start_game_selection_flow(self, query if query else None)
        elif cmd == 'game_mode_off':
            from actions.system import deactivate_game_mode, close_active_game
            if any(w in text_lower for w in ['закрой', 'выйди', 'выход']):
                close_active_game()
            deactivate_game_mode()
            try:
                self.asr.set_vad_mode(False)
                self.asr.clear_hotwords()
            except Exception:
                pass
            try:
                from actions.game_audio import game_matcher
                game_matcher.clear()
            except Exception:
                pass
            self.play_response()
        elif cmd == 'exit_game':
            from actions.system import close_active_game
            close_active_game()
            self.play_response()
        elif cmd == 'spell_list':
            from .commands.game import handle_game_extra
            handle_game_extra(self, cmd, text_lower)
        elif (cmd.startswith('open_') or cmd.startswith('close_')) and cmd not in ['open_browser_history', 'open_last_video', 'open_saved']:
            if cmd == 'open_task_manager':
                import subprocess; subprocess.Popen(['taskmgr']); self.play_response()
            elif cmd == 'open_terminal':
                from actions.system import open_terminal; open_terminal(); self.play_response()
            elif cmd == 'open_work':
                from actions.system import open_work; open_work(); self.play_response()
            elif cmd == 'close_work':
                from actions.app_launcher import close_app; close_app('antigravity'); self.play_response()
            else:
                from actions.app_launcher import open_app, close_app
                if cmd.startswith('open_'):
                    app_key = cmd[5:]
                    ok, res = open_app(app_key)
                else:
                    app_key = cmd[6:]
                    ok, res = close_app(app_key)
                if ok: self.play_response()
                elif cmd.startswith('open_'): self.speak(f'Не удалось открыть: {res}')
        elif cmd == 'play_yt':
            from actions.youtube import _open_youtube_url
            import urllib.parse as _up
            is_music = any(w in text_lower for w in ['песню', 'песня', 'музыку', 'музыка', 'трек'])
            query = text_lower
            for sw in ['включи песню', 'поставь песню', 'найди песню',
                       'включи музыку', 'поставь музыку', 'найди музыку',
                       'включи видео', 'поставь видео', 'найди видео',
                       'включи', 'поставь', 'найди']:
                query = query.replace(sw, '')
            query = query.strip()
            if not query:
                _open_youtube_url('https://www.youtube.com')
                self.play_response()
            else:
                yt_query = f'{query} песня' if is_music else query
                def _play(q=yt_query, orig=query, music=is_music):
                    url = None
                    try:
                        import urllib.request as _ur, urllib.parse as _up2, re as _re2
                        _q = _up2.quote(q)
                        print(f'[play_yt] searching: {q!r}', flush=True)
                        req = _ur.Request(
                            f'https://www.youtube.com/results?search_query={_q}',
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                     'Accept-Language': 'en-US,en;q=0.9'})
                        with _ur.urlopen(req, timeout=8) as r:
                            html = r.read().decode('utf-8', errors='ignore')
                        ids = list(dict.fromkeys(_re2.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)))
                        print(f'[play_yt] found ids: {ids[:3]}', flush=True)
                        if ids:
                            url = f'https://www.youtube.com/watch?v={ids[0]}'
                    except Exception as e:
                        print(f'[play_yt] error: {e}', flush=True)
                    if not url:
                        sp = '&sp=EgIQAQ%3D%3D' if music else ''
                        url = f'https://www.youtube.com/results?search_query={_up.quote(orig)}{sp}'
                    print(f'[play_yt] opening: {url}', flush=True)
                    _open_youtube_url(url)
                    self.play_response()
                threading.Thread(target=_play, daemon=True).start()
        elif cmd in ['net_profile_status', 'net_profile_switch', 'vpn_reminder', 'health_disks', 'calendar_next', 'inbox_unread', 'mail_compose']:
            from .commands.integrations import handle_integrations
            handle_integrations(self, cmd, text_lower)
        elif cmd in ['time_now', 'system_status', 'how_are_you', 'system_insult', 'praise']:
            from .commands.social import handle_social
            handle_social(self, cmd, text_lower)
    def _launch_game_engine(self, game_info):
        from .commands.game import launch_game_engine
        launch_game_engine(self, game_info)
    def _apply_game_profile(self, profile, name):
        from .commands.game import apply_game_profile
        apply_game_profile(self, profile, name)
def parse_folder_name(text_lower: str, mode: str) -> str:
    tokens = text_lower.replace('—', ' ').split()
    keyword = 'создай' if mode == 'create' else 'удали'
    if 'папку' in tokens:
        idx = tokens.index('папку')
        name = ' '.join([t for t in tokens[idx+1:] if t != 'здесь']).strip()
        for word in ['новую', 'новую', 'новый']:
            if name.lower().startswith(word):
                name = name[len(word):].strip()
        return name
    elif keyword in tokens:
        idx = tokens.index(keyword)
        return ' '.join([t for t in tokens[idx+1:] if t not in ('здесь', 'папку')]).strip()
    return ''
def parse_cd_name(text_lower: str) -> str:
    tokens = text_lower.replace('—', ' ').split()
    if 'папку' in tokens:
        idx = tokens.index('папку')
        return ' '.join([t for t in tokens[idx+1:] if t != 'здесь']).strip()
    elif 'зайди' in tokens:
        idx = tokens.index('зайди')
        return ' '.join([t for t in tokens[idx+1:] if t not in ('в', 'папку', 'сюда', 'здесь')]).strip()
    return ''
