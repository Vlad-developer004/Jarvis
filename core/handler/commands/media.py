import re
from core.nlp import extract_duration_seconds
from core.responses import spk

def _yt_full(handler, cmd, text_lower):
    from actions.youtube import control_youtube
    control_youtube('fullscreen'); handler.play_response()

def _yt_fwd(handler, cmd, text_lower):
    from actions.youtube import control_youtube
    control_youtube('forward', extract_duration_seconds(text_lower) or 5)

def _yt_bwd(handler, cmd, text_lower):
    from actions.youtube import control_youtube
    control_youtube('backward', extract_duration_seconds(text_lower) or 5)

def _yt_next(handler, cmd, text_lower):
    from actions.youtube import control_youtube
    if control_youtube('next_video'): handler.play_response()

def _yt_prev(handler, cmd, text_lower):
    from actions.youtube import control_youtube
    if control_youtube('prev_video'): handler.play_response()

def _yt_last_watched(handler, cmd, text_lower):
    from actions.youtube import open_last_watched_video
    from core.system import app_state as _app_state
    _BG = ('в фоне', 'фоном', 'у фоні', 'в фоновому режимі')
    _bg = _app_state.game_mode or any(w in text_lower for w in _BG)
    if open_last_watched_video(background=_bg): handler.play_response()

def _yt_channel(handler, cmd, text_lower):
    from actions.youtube import open_youtube_channel
    from core.system import app_state as _app_state
    q = text_lower
    for sw in ['открой канал', 'запусти канал', 'найди канал', 'покажи канал', 'канал']:
        q = q.replace(sw, '')
    q = q.strip()
    if q:
        open_youtube_channel(q, background=_app_state.game_mode); handler.play_response()
    else:
        handler.speak(spk('media.ask_channel'))
        handler._set_interactive('yt_channel_ask', {'background': _app_state.game_mode}, timeout=20.0)

_YT_ACTIONS = {
    'yt_full': _yt_full,
    'yt_fwd': _yt_fwd,
    'yt_bwd': _yt_bwd,
    'yt_next': _yt_next,
    'yt_prev': _yt_prev,
    'yt_last_watched': _yt_last_watched,
    'yt_channel': _yt_channel,
}

def handle_yt_control(handler, cmd, text_lower):
    action = _YT_ACTIONS.get(cmd)
    if action:
        action(handler, cmd, text_lower)

def _vol_up(handler, cmd, text_lower, amount):
    from actions.volume import change_volume
    change_volume('up', amount or 7); handler.play_response()

def _vol_down(handler, cmd, text_lower, amount):
    from actions.volume import change_volume
    change_volume('down', amount or 7); handler.play_response()

def _vol_mute(handler, cmd, text_lower, amount):
    from actions.volume import mute_volume
    mute_volume(True); handler.play_response()

def _vol_unmute(handler, cmd, text_lower, amount):
    from actions.volume import mute_volume
    mute_volume(False); handler.play_response()

def _vol_set_like(handler, cmd, text_lower, amount):
    from actions.volume import set_volume_level
    if cmd == 'vol_max' or 'максимум' in text_lower or 'максимально' in text_lower or 'максимальн' in text_lower:
        level = 100
    elif cmd == 'vol_zero' or 'минимум' in text_lower or 'минимально' in text_lower or 'ноль' in text_lower:
        level = 0
    else:
        level = amount
    set_volume_level(level / 100.0); handler.play_response()

def _audio_switch(handler, cmd, text_lower, amount):
    from actions.volume import switch_audio_output
    if switch_audio_output(text_lower): handler.play_response()
    else: handler.speak(spk('media.no_audio_device'))

def _app_vol(handler, cmd, text_lower, amount):
    from actions.volume import set_app_volume
    from core.nlp.commands import normalize_numbers
    q = normalize_numbers(text_lower)

    # Clean up text to find app name
    for sw in ['приложения', 'приложение', 'громкость', 'звук', 'сделай', 'установи', 'на', 'в', 'у', 'для']:
        q = q.replace(sw, ' ')
    for sw in ['громче', 'тише', 'увеличь', 'убавь', 'поставь', 'минимум', 'максимум', 'выставь', 'задай']:
        q = q.replace(sw, ' ')

    # Remove the numeric amount if present to avoid it being part of the app name
    if amount is not None:
        q = q.replace(str(amount), ' ')

    # Remove any remaining digits and extra spaces
    app_name_clean = re.sub(r'\d+', '', q).strip()
    app_name_clean = re.sub(r'\s+', ' ', app_name_clean)
    direction = 'up' if 'up' in cmd else ('down' if 'down' in cmd else 'set')

    # Try app volume first
    ok, res = set_app_volume(app_name_clean, direction, amount or 20)
    if ok:
        handler.play_response()
    else:
        # Fallback to system volume if app not found and name is empty or just numeric
        if not app_name_clean:
            handle_volume(handler, cmd.replace('app_', ''), text_lower, amount)
        else:
            handler.speak(res)

_VOL_ACTIONS = {
    'vol_up': _vol_up,
    'vol_down': _vol_down,
    'vol_mute': _vol_mute,
    'vol_unmute': _vol_unmute,
    'vol_set': _vol_set_like,
    'vol_max': _vol_set_like,
    'vol_zero': _vol_set_like,
    'audio_switch': _audio_switch,
    'app_vol_up': _app_vol,
    'app_vol_down': _app_vol,
    'app_vol_set': _app_vol,
}

def handle_volume(handler, cmd, text_lower, amount):
    action = _VOL_ACTIONS.get(cmd)
    if action:
        action(handler, cmd, text_lower, amount)
