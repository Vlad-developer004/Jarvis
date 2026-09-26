from core.responses import spk
from core.logging_setup import get_logger as _get_logger

_log = _get_logger('song')

# Phrases that mean "listen to what THIS PC is outputting" rather than the
# default (mic, which already picks up a phone/speakers in the room).
_PC_WORDS = ('с компьютера', 'на компьютере', 'с компа', 'на пк', 'с пк',
             'з компютера', "з комп'ютера", 'з компа', 'на комп\'ютері')


def handle_song(handler, cmd, text_lower):
    source = 'pc' if any(w in text_lower for w in _PC_WORDS) else 'mic'
    handler.speak(spk('song.listening'), wait=True)
    # wait=True's "finished" signal fires slightly before the audio device
    # actually stops playing (same lag core/mic_calibration.py works around
    # with its own post-speak pause) — without this, the mic recording below
    # starts a beat early and captures the tail of "Слушаю..." itself instead
    # of the music, corrupting the very start of the fingerprint window.
    import time
    time.sleep(0.4)

    def _task():
        from actions.song_id import recognize_song
        res = recognize_song(source=source)
        if not res.get('ok'):
            err = res.get('error')
            if err == 'no_key':
                handler.speak(spk('song.no_key'))
            elif err == 'no_match':
                handler.speak(spk('song.no_match'))
            else:
                handler.speak(spk('song.error'))
            return
        title = res.get('title', '')
        artist = res.get('artist', '')
        if artist:
            handler.speak(spk('song.result', title=title, artist=artist))
        else:
            handler.speak(spk('song.result_notitle', title=title))
        _show_song_card(res)

    def _show_song_card(res: dict) -> None:
        try:
            import time as _time
            import ui.hud_ai_window as _aiw
            from ui.hud_ai_window import show_ai_window, update_ai_window_text, set_ai_window_image, hide_ai_window
            show_ai_window(res.get('title') or 'Песня', fetch_image=False)
            # show_ai_window() only *queues* the window's creation onto the
            # Tk thread (hud.root.after(0, ...)) and returns immediately —
            # calling update_ai_window_text/set_ai_window_image/hide_ai_window
            # right after, before Tk has actually processed that callback,
            # means _window_instance is still None and each of those calls
            # silently no-ops (they all guard on "if _window_instance").  That
            # produced an empty card that never got its hide_ai_window timer
            # started either, so it just sat there forever. Wait (briefly)
            # for the window to actually exist before touching it.
            for _ in range(50):  # up to ~1s
                if getattr(_aiw, '_window_instance', None) is not None:
                    break
                _time.sleep(0.02)
            lines = []
            if res.get('artist'):
                lines.append(f"Исполнитель: {res['artist']}")
            if res.get('album'):
                lines.append(f"Альбом: {res['album']}")
            if res.get('release_date'):
                lines.append(f"Дата выхода: {res['release_date']}")
            lines.append('')
            if res.get('spotify_url'):
                lines.append(f"Spotify: {res['spotify_url']}")
            if res.get('apple_music_url'):
                lines.append(f"Apple Music: {res['apple_music_url']}")
            if res.get('youtube_url'):
                lines.append(f"YouTube: {res['youtube_url']}")
            update_ai_window_text('\n'.join(lines))
            if res.get('cover_path'):
                set_ai_window_image(res['cover_path'])
            hide_ai_window(delay_ms=15000)
        except Exception as e:
            _log.error('song card display failed: %s', e, exc_info=True)

    from core.speech import run_speaking_task
    from core.i18n import get_language
    fallback = 'Не вдалося розпізнати пісню.' if get_language() == 'uk' else 'Не удалось распознать песню.'
    run_speaking_task(_task, error_message=fallback, thread_name='song-id-task', speak_fn=handler.speak)
