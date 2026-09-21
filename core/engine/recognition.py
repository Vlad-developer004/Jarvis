import time
import re
import queue as _queue_mod
import threading as _threading_mod
from core.system import app_state
from core.logging_setup import get_logger as _get_logger
from core.speech import stop_speaking, is_speaking
from core.nlp import _normalize_stt, extract_all_commands
from core.nlp.commands import CANON_SIMPLE, normalize_numbers
from core.nlp.semantic import classify_intent
from ui.voice_prompt_bridge import try_consume_voice_prompt
from core.engine.ets2_commands import _handle_telemetry_action

_log = _get_logger('recognition')

def _wait_until_not_speaking(timeout: float = 0.1, poll: float = 0.02) -> None:
    """Poll is_speaking() instead of a blind sleep, so we proceed as soon as
    in-flight TTS generation settles after stop_speaking() rather than always
    waiting the full timeout."""
    deadline = time.time() + timeout
    while is_speaking() and time.time() < deadline:
        time.sleep(poll)
_WAKE_BASES_SEARCH = ('джарвис', 'джарвіс')
_WAKE_BASES_SUB = ('джарвис', 'джарвіс')

class WakeRegex:
    def search(self, text: str):
        words = re.findall(r'\b\w+\b', text)
        for w in words:
            wl = w.lower()
            if wl in _WAKE_BASES_SEARCH:
                return True
        from rapidfuzz.distance import Levenshtein
        for w in words:
            wl = w.lower()
            for base in _WAKE_BASES_SEARCH:
                dist = Levenshtein.distance(wl, base)
                limit = 1 if len(wl) <= 5 else 2
                if dist <= limit:
                    return True
        return None

    def sub(self, repl, text, count=1):
        from rapidfuzz.distance import Levenshtein
        replaced = 0
        def replace_fn(match):
            nonlocal replaced
            if count is not None and replaced >= count:
                return match.group(0)
            wl = match.group(0).lower()
            if wl in _WAKE_BASES_SUB:
                replaced += 1
                return repl
            for base in _WAKE_BASES_SUB:
                dist = Levenshtein.distance(wl, base)
                limit = 1 if len(wl) <= 5 else 2
                if dist <= limit:
                    replaced += 1
                    return repl
            return match.group(0)
        return re.sub(r'\b\w+\b', replace_fn, text, count=count)

_WAKE_RE = WakeRegex()
_GAME_ON_VERBS = ('включи', 'активируй', 'запусти', 'подготовь')
_GAME_OFF_VERBS = ('выключи', 'отключи', 'отмени', 'деактивируй', 'выйди', 'закрой', 'завершить', 'закрыть', 'завершить')
_GAME_OFF_EXACT = frozenset({
    'выйди из игрового режима', 'отключи игровой режим', 'отмени игровой режим',
    'отмени режим', 'выключи игровой режим', 'выйди из игры', 'отмени режим игры',
    'конец игры', 'игра окончена', 'верни обычный режим',
    'закрой игру', 'закрыть игру', 'выйти из игры', 'завершить игру',
    'завершить игровой режим', 'выключи режим игры', 'стоп игра',
})
def _is_game_mode_off_phrase(text_norm: str) -> bool:
    if text_norm in _GAME_OFF_EXACT:
        return True
    if any(p in text_norm for p in _GAME_OFF_EXACT if len(p) >= 6):
        return True
    if 'геймод' in text_norm and any(v in text_norm for v in _GAME_OFF_VERBS):
        return True
    has_game = ('игровой' in text_norm) or ('режим игры' in text_norm)
    return has_game and any(v in text_norm for v in _GAME_OFF_VERBS)
_QUICK_GAME_FRAGS = (
    'евро трак', 'евротрак', 'euro truck', 'трак симулятор',
    ' ets', 'etс', 'етс',
    'фарминг', 'farming', ' фс ', ' фс22', ' фс25', ' fs22', ' fs25', 'ферму', 'ферма',
    'хогвартс', 'hogwarts', ' хог',
)
def _is_game_mode_on_phrase(text_norm: str) -> bool:
    if _is_game_mode_off_phrase(text_norm):
        return False
    if 'геймод' in text_norm:
        return True
    has_game = ('игровой' in text_norm) or ('режим игры' in text_norm)
    if has_game and any(v in text_norm for v in _GAME_ON_VERBS):
        return True
    padded = f' {text_norm} '
    _GO_PREFIXES = ('го в ', 'хочу в ', 'запусти ', 'включи ', 'играть в ')
    has_prefix = any(p in padded for p in _GO_PREFIXES)
    has_game_frag = any(frag in padded for frag in _QUICK_GAME_FRAGS)
    return has_prefix and has_game_frag

_PLAY_YT_RE = re.compile(
    r'\b(включи|поставь|запусти|найди|увімкни|знайди)\s+'
    r'(видео|ролик|клип|кліп|музыку|музику|пісню|песню)\b',
    re.IGNORECASE
)

_TIMER_SET_RE = re.compile(
    r'\b(поставь|засеки|запусти|установи)\b.{0,20}\bтаймер\b'
    r'|\bтаймер\b.{0,20}\b(поставь|засеки|запусти|установи)\b'
    r'|\bтаймер\s+на\s+\w',
    re.IGNORECASE
)
_TIMER_ADD_RE = re.compile(r'\b(добавь|продли)\b.{0,25}\bтаймер\b', re.IGNORECASE)
_TIMER_CANCEL_RE = re.compile(r'\b(отмени|сбрось|скасуй)\b.{0,10}\bтаймер\b', re.IGNORECASE)
_TIMER_STATUS_RE = re.compile(r'\bсколько\b.{0,20}\b(осталось|залишилось)\b', re.IGNORECASE)
# App volume: "громкость/звук <app> на <n>" — must bypass ML (misclassified as vol_zero/vol_set)
# Requires a non-numeric app-name word between the volume keyword and "на <digits>"
_APP_VOL_SET_RE = re.compile(
    r'\b(громкость|гучність|звук)\s+([а-яёa-z]\w*)\s+на\s+(\d+)\b',
    re.IGNORECASE
)
_APP_VOL_UP_RE = re.compile(
    r'\b(громче|гучніше|прибавь|збільши)\b.{0,20}\b(\w+(?:\s+\w+)?)\s+(громкость|гучність|звук)\b'
    r'|\b(громкость|гучність|звук)\s+([а-яёa-z]\w*)\s+(громче|гучніше|выше|вище)\b',
    re.IGNORECASE
)
_APP_VOL_DOWN_RE = re.compile(
    r'\b(тише|тихіше|убавь|зменши)\b.{0,20}\b(\w+(?:\s+\w+)?)\s+(громкость|гучність|звук)\b'
    r'|\b(громкость|гучність|звук)\s+([а-яёa-z]\w*)\s+(тише|тихіше|ниже|нижче)\b',
    re.IGNORECASE
)
# Tab commands — must bypass ML model (it confuses them with window/context actions)
# Matches only when a number/ordinal is present → close_tab_n / browser_tab (goto)
_TAB_NUM = (
    r'(?:\d+|'
    r'перв\w+|втор\w+|трет\w+|четвёрт\w+|четверт\w+|пят\w+|шест\w+|седьм\w+|'
    r'восьм\w+|девят\w+|десят\w+|одиннадцат\w+|двенадцат\w+|тринадцат\w+|'
    r'четырнадцат\w+|пятнадцат\w+|шестнадцат\w+|семнадцат\w+|восемнадцат\w+|'
    r'девятнадцат\w+|двадцат\w+|'
    r'перш\w+|друг\w+|трет\w+|четверт\w+)'
)
_TAB_OPEN_N_RE = re.compile(
    r'\b(открой|перейди|переключись|відкрий)\b.{0,20}' + _TAB_NUM + r'.{0,10}\bвкладк'
    r'|\b(открой|перейди|переключись|відкрий)\b.{0,5}\bвкладк.{0,10}' + _TAB_NUM,
    re.IGNORECASE
)
_TAB_OPEN_NEW_RE = re.compile(
    r'\b(создай|открой|відкрий|створи)\b.{0,10}\b(новую|нову|новая|нова)?\s*вкладк'
    r'|\bновая вкладка\b|\bнова вкладка\b',
    re.IGNORECASE
)
_TAB_CLOSE_N_RE = re.compile(
    r'\b(закрой|закрий)\b.{0,20}' + _TAB_NUM + r'.{0,10}\bвкладк'
    r'|\b(закрой|закрий)\b.{0,5}\bвкладк.{0,10}' + _TAB_NUM,
    re.IGNORECASE
)
_TAB_CLOSE_CUR_RE = re.compile(
    r'\b(закрой|закрий)\b.{0,15}\b(текущую|поточну|эту|цю)?\s*вкладк',
    re.IGNORECASE
)

def _sem_parse(text: str, is_waiting_answer: bool = False) -> list[tuple[str, str]]:
    """Semantic replacement for extract_all_commands. Returns [(intent, text)] or [].

    Pass is_waiting_answer=True when the system is waiting for a yes/no
    confirmation — enables Layer 0 confirmation intercept in the classifier.
    """
    # CANON exact-match takes priority even over wake-word detection — phrases like
    # "закрой джарвиса" contain the wake word but must resolve to jarvis_exit, not 'wake'.
    try:
        _t_pre = normalize_numbers(_normalize_stt(text).lower().strip())
        _canon_hit_pre = CANON_SIMPLE.get(_t_pre) or CANON_SIMPLE.get(text.lower().strip())
        if _canon_hit_pre:
            return [(_canon_hit_pre, text)]
    except Exception:
        pass
    # Wake words must never reach the semantic classifier — they get misclassified
    if _WAKE_RE.search(text.lower()):
        return [('wake', text)]
    # "открой браузер и ютуб" → open both independently; YouTube as app, not tab
    _tl = text.lower()
    if re.search(r'\bбраузер\b', _tl) and re.search(r'\bютуб\b', _tl):
        return [('open_browser', text), ('open_youtube', text)]
    # Structural rule: "включи/поставь видео/ролик/клип/музыку [anything]" → play_yt
    # Use the LAST match so "включи песню включи видео" → plays video, not song
    _yt_matches = list(_PLAY_YT_RE.finditer(text))
    if _yt_matches:
        return [('play_yt', text[_yt_matches[-1].start():])]
    # Timer rules — bypass semantic model until rebuild
    if _TIMER_ADD_RE.search(text):
        return [('timer_add', text)]
    if _TIMER_CANCEL_RE.search(text):
        return [('timer_cancel', text)]
    if _TIMER_STATUS_RE.search(text):
        return [('timer_status', text)]
    if _TIMER_SET_RE.search(text):
        return [('timer_set', text)]
    # Tab commands — bypass ML model entirely (order: numbered first, then simple)
    if _TAB_CLOSE_N_RE.search(text):
        return [('close_tab_n', text)]
    if _TAB_CLOSE_CUR_RE.search(text):
        return [('close_tab', text)]
    # App-specific volume — must come before CANON/ML to avoid vol_zero misclassification
    # normalize_numbers converts "сто" → "100" so the digit-based regex works
    try:
        _text_norm_vol = normalize_numbers(text.lower())
    except Exception:
        _text_norm_vol = text
    if _APP_VOL_SET_RE.search(_text_norm_vol):
        return [('app_vol_set', text)]
    if _APP_VOL_UP_RE.search(text):
        return [('app_vol_up', text)]
    if _APP_VOL_DOWN_RE.search(text):
        return [('app_vol_down', text)]
    if _TAB_OPEN_N_RE.search(text):
        return [('browser_tab', text)]
    if _TAB_OPEN_NEW_RE.search(text):
        return [('browser_tab', text)]
    # CANON exact-match takes priority over the ML model — avoids misclassification
    # of well-known phrases like "открой корзину" → open_word
    try:
        _t = normalize_numbers(_normalize_stt(text).lower().strip())
        _canon_hit = CANON_SIMPLE.get(_t) or CANON_SIMPLE.get(text.lower().strip())
        if _canon_hit:
            return [(_canon_hit, text)]
    except Exception:
        pass
    # Guard: if any qa keyword appears in the first 4 words → qa_search regardless of classifier
    _QA_WORDS = {'скажи', 'расскажи', 'поясни', 'объясни', 'розкажи', 'відповідай', 'ответь', 'відповіди'}
    _tl_strip = text.lower().strip()
    _first_words = set(_tl_strip.split()[:4])
    if _first_words & _QA_WORDS:
        return [('qa_search', text)]
    try:
        intent = classify_intent(text, is_waiting_answer=is_waiting_answer)
        if intent:
            if intent == 'reported_speech':
                return []
            return [(intent, text)]
    except Exception:
        pass
    # Fallback to rule-based matcher when semantic returns None or fails
    try:
        cmds = extract_all_commands(text)
        # Never surface reported_speech as an executable command
        return [(c, s) for c, s in cmds if c != 'reported_speech']
    except Exception:
        return []


def handle_recognized_text(text: str, handler):
    text_low = text.lower().strip()
    print(f"[RECOGNITION] Jarvis heard: {text!r}", flush=True)
    
    # Only interrupt if we are NOT in interactive state AND we heard a wake word or a command
    is_wake = bool(_WAKE_RE.search(text_low))
    parsed_cmds = None
    
    if is_speaking():
        if is_wake or (handler.interactive_state and len(text_low) > 3):
            stop_speaking()
            _wait_until_not_speaking()
    text = text.strip()
    if not text: return
    try:
        if try_consume_voice_prompt(text):
            return
    except Exception:
        pass
    if app_state.game_mode:
        app_state.last_command_time = time.time()
    if handler.interactive_state:
        if handler.is_speaking: stop_speaking(); _wait_until_not_speaking()
        app_state.last_command_time = time.time()
        handler.handle_interactive(text); return
    # --- GAME MODE HANDLING ---
    text_norm = _normalize_stt(text)
    if app_state.game_mode:
        if _is_game_mode_off_phrase(text_norm):
            handler.handle('game_mode_off', text); return
        
        # Strip wake word if present to improve matching accuracy in game mode
        is_wake_present = bool(_WAKE_RE.search(text_norm))
        text_for_game = _WAKE_RE.sub('', text_norm, count=1).strip() if is_wake_present else text_norm
        
        print(f"[RECOGNITION] Game Mode Input: raw={text!r}, norm={text_norm!r}, clean={text_for_game!r}, is_wake={is_wake_present}", flush=True)

        from actions.game_input import cast_command
        _fuzzy = 0.75
        ok, matched_name, _act = cast_command(text_for_game, fuzzy_threshold=_fuzzy)

        if ok:
            print(f"[RECOGNITION] Game Command Matched: {matched_name!r}", flush=True)
            # ETS2's telemetry_action handler lives here in recognition.py (fuel/cruise/etc).
            # Other profiles (Planetbase, FS22, Hogwarts) already handle their own
            # telemetry_action internally inside cast_command. cast_command now returns
            # the matched telemetry_action directly, so no second fuzzy-match pass is needed.
            if _act and 'euro truck' in (app_state.game_profile or '').lower():
                print(f"[RECOGNITION] Dispatching Telemetry Action: {_act!r}", flush=True)
                # Pass text_for_game to avoid wake-word interference in telemetry handlers
                _handle_telemetry_action(_act, handler, text=text_for_game)
            return
        else:
            print(f"[RECOGNITION] No Game Command Match for: {text_for_game!r}", flush=True)
        
        if _is_game_mode_on_phrase(text_norm):
            handler.handle('game_mode_on', text); return

        # GAME MODE PASSTHROUGH: allow a curated set of system commands even while in-game.
        # Only commands that make sense mid-game: media, volume, AI queries, timers, screenshots.
        _GAME_PASSTHROUGH = frozenset({
            # Volume / audio
            'vol_up', 'vol_down', 'vol_set', 'vol_mute', 'vol_unmute', 'vol_max', 'vol_zero',
            'audio_switch',
            # Brightness
            'brightness_up', 'brightness_down', 'brightness_set',
            # Media playback
            'media_pause', 'media_play',
            'media_pause_youtube', 'media_play_youtube',
            'media_pause_browser', 'media_play_browser',
            # YouTube / video
            'play_yt', 'open_youtube', 'yt_fwd', 'yt_bwd', 'yt_next', 'yt_prev',
            'yt_full', 'yt_last_watched', 'yt_channel', 'open_last_video',
            'open_saved', 'download_video', 'save_video',
            # Info / AI
            'qa_search', 'google_search', 'time_now', 'weather',
            'currency_rate', 'today_summary',
            # Timers / reminders
            'reminder', 'cancel_reminder', 'shutdown_timer', 'cancel_timer',
            # Screenshot
            'screenshot',
            # Jarvis control
            'game_mode_off', 'jarvis_exit', 'restart_jarvis', 'listen_off', 'listen_on',
            # Timer
            'timer_set', 'timer_status', 'timer_cancel', 'timer_add',
            # Misc useful in-game
            'how_are_you', 'praise',
        })
        sem_cmds = _sem_parse(text_for_game if text_for_game else text_norm)
        passthrough = [(c, seg) for c, seg in sem_cmds if c in _GAME_PASSTHROUGH]
        if passthrough:
            print(f"[RECOGNITION] Game Passthrough: {[c for c,_ in passthrough]}", flush=True)
            app_state.last_command_time = time.time()
            for c, seg in passthrough:
                handler.handle(c, seg)
                time.sleep(0.05)
            return

        # STRICT GAME MODE: If in game mode and no game command matched, do not process global commands.
        return
    else:
        # BACKGROUND MACRO SUPPORT
        # If not in game mode, but a game is detected in focus
        if app_state.detected_game:
            from actions.game_input import cast_command, load_profile as _gi_load
            from actions.game_input_parts.profile import _profile_name as _gi_pname

            # If the profile for the detected game is not yet loaded into the input engine, load it silently
            # But don't speak or anything.
            if not _gi_pname or _gi_pname.lower() != app_state.detected_game.replace('_', ' ').lower():
                 _gi_load(app_state.detected_game)

            # Try to cast. If it's a very strong match, execute it.
            # We use a higher threshold for background macros to avoid false positives.
            ok, _, _act = cast_command(text, fuzzy_threshold=0.85)
            if ok:
                if _act and 'euro_truck' in app_state.detected_game.lower():
                    _handle_telemetry_action(_act, handler, text=text)
                return

    if app_state.dictation_mode:
        from actions.dictation import handle_dictation_text
        res = handle_dictation_text(text)
        if res['stop']:
            app_state.dictation_mode = False; handler.play_response()
        return
    text_lower = text.lower().strip()
    is_wake = bool(_WAKE_RE.search(text_lower))
    parsed_cmds = None
    if not is_wake:
        parsed_cmds = _sem_parse(text)
        is_wake = any(c == 'wake' for c, _ in parsed_cmds)
    # Context filter: if no wake word detected and Jarvis is not active,
    # check semantically whether this phrase is even addressed to Jarvis.
    # Skip filter when in interactive state (e.g. qa_clarify follow-up) — those are always for Jarvis.
    if not is_wake and not app_state.jarvis_active and not getattr(app_state, 'ignore_mode', False) and not handler.interactive_state:
        if not parsed_cmds:
            try:
                from core.nlp.semantic import is_command as _sem_is_cmd
                if not _sem_is_cmd(text_lower):
                    print(f"[SEMANTIC] Context filter: ignoring '{text_lower[:60]}'", flush=True)
                    return
            except Exception:
                pass
    if not app_state.jarvis_active:
        cmds_early = parsed_cmds if parsed_cmds is not None else _sem_parse(text)
        early_allowed = {'show_hud', 'show_help', 'mail_compose', 'qa_search'}
        early = [(c, s) for c, s in cmds_early if c in early_allowed]
        if early:
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            for c, seg in early:
                handler.handle(c, seg)
                time.sleep(0.05)
            return
        if handler.interactive_state:
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            handler.handle_interactive(text)
            return
        if getattr(app_state, 'ignore_mode', False):
            cmds_ign = parsed_cmds if parsed_cmds is not None else _sem_parse(text)
            cmds_listen = [(c, s) for c, s in cmds_ign if c == 'listen_on']
            if cmds_listen:
                app_state.jarvis_active = True
                app_state.last_command_time = time.time()
                for c, seg in cmds_listen:
                    handler.handle(c, seg)
                    time.sleep(0.05)
            return
        elif is_wake:
            app_state.jarvis_active = True; app_state.last_command_time = time.time()
            rest = _WAKE_RE.sub('', text_lower, count=1).strip().strip(',').strip()
            cmds = _sem_parse(rest) if rest else []
            real = [m for m in cmds if m[0] != 'wake']
            if not real:
                if getattr(app_state, 'ignore_mode', False):
                    return
                
                # FALLBACK: If there was text after the wake word but no local command matched,
                # we no longer send it to AI automatically to avoid false triggers.
                # AI activation is now strictly tied to the 'qa_search' command (e.g. "скажи").
                print(f"[RECOGNITION] Wake word heard, no immediate command. Speaking 'Yes sir'.", flush=True)
                handler.handle('wake', 'джарвис')
            else:
                handler.silent_mode = len(real) > 1
                print(f"[RECOGNITION] Global commands matched: {[c for c, _ in real]}", flush=True)
                for c, seg in real:
                    handler.handle(c, seg); time.sleep(0.1)
                if handler.silent_mode:
                    handler.silent_mode = False; handler.play_response('confirm', override_silent=True)
    else:
        # While in AI conversation mode: if no recognizable command matched, route to qa_clarify
        if handler.interactive_state == 'qa_clarify':
            _qa_cmds = parsed_cmds if parsed_cmds is not None else _sem_parse(text)
            _real = [(c, s) for c, s in _qa_cmds if c not in ('wake', 'reported_speech')]
            if not _real:
                # No command matched — treat as follow-up AI question
                app_state.last_command_time = time.time()
                handler.handle_interactive(text)
                return
            # A real command was spoken — clear qa_clarify and execute normally
        try:
            from actions.meetings import match_meeting, open_meeting
            matched = match_meeting(text_lower)
            if matched:
                app_state.last_command_time = time.time()
                if open_meeting(matched):
                    handler.speak(f'Открываю — {matched.get("name", "")}.')
                return
        except Exception:
            pass
        cmds = parsed_cmds if parsed_cmds is not None else _sem_parse(text)
        # If wake word ate the whole command, strip it and re-parse the remainder
        if cmds and all(c == 'wake' for c, _ in cmds):
            _rest = _WAKE_RE.sub('', text_lower, count=1).strip().strip(',').strip()
            if _rest:
                _rest_cmds = [m for m in _sem_parse(_rest) if m[0] != 'wake']
                if _rest_cmds:
                    cmds = _rest_cmds
        if getattr(app_state, 'ignore_mode', False) and cmds:
            cmds = [(c, s) for c, s in cmds if c == 'listen_on']
            if not cmds:
                return
        if cmds:
            app_state.last_command_time = time.time()
            try:
                from config_pack.config import WAKE_WORD_MODE
                mode = WAKE_WORD_MODE
            except Exception:
                mode = 'single'
                
            has_real = any((c != 'wake' for c, _ in cmds))
            if mode == 'single':
                # 'single' response mode: ignore repeated wake words while already active to prevent spam
                filtered = [(c, seg) for c, seg in cmds if c != 'wake']
            else:
                # 'continuous' response mode: always answer 'Yes sir' on wake word even if already active
                filtered = [(c, seg) for c, seg in cmds if not (has_real and c == 'wake')]
                
            handler.silent_mode = len(filtered) > 1
            for c, seg in filtered:
                if c == 'dictation_on':
                    from actions.dictation import start_dictation
                    start_dictation(); app_state.dictation_mode = True
                    if not handler.silent_mode: handler.play_response()
                else:
                    print(f"[RECOGNITION] Executing global command: action={c!r}, segment={seg!r}", flush=True)
                    handler.handle(c, seg)
                time.sleep(0.1)
            if handler.silent_mode:
                handler.silent_mode = False; handler.play_response('confirm', override_silent=True)
        elif not getattr(app_state, 'ignore_mode', False):
            # Jarvis is active (mid-conversation, within the wake-mode follow-up
            # window) and heard something, but nothing matched at all — previously
            # this fell through to complete silence, so the user had no way to
            # tell "not understood" apart from "didn't hear you" apart from
            # "ignored on purpose". A short cooldown keeps a run of fragmentary
            # ASR misses from turning into a chatty loop of "not understood".
            now_nu = time.time()
            if now_nu - handler._last_not_understood_ts >= 4.0:
                handler._last_not_understood_ts = now_nu
                print(f"[RECOGNITION] Active but nothing matched for: {text_lower!r} — giving feedback.", flush=True)
                handler.play_response('not_understood', override_silent=True)
def flush_final(asr, handler, transcribe_queue: _queue_mod.Queue):
    from config_pack.config import RATE as _RATE
    audio = bytes(asr._audio_buffer)
    asr.reset()
    if not audio or not transcribe_queue:
        return
    item = (audio, handler)
    evicted = 0
    while evicted < 200:
        try:
            transcribe_queue.put_nowait(item)
            if evicted:
                try:
                    from core.voice_debug_log import voice_event
                    voice_event(f'QUEUE_EVICT oldest x{evicted} sec={len(audio) / 2 / _RATE:.2f}')
                except Exception:
                    pass
            return
        except _queue_mod.Full:
            try:
                transcribe_queue.get_nowait()
                evicted += 1
            except _queue_mod.Empty:
                break
    try:
        transcribe_queue.put_nowait(item)
    except _queue_mod.Full:
        try:
            from core.voice_debug_log import voice_event
            voice_event(f'QUEUE_FULL dropped sec={len(audio) / 2 / _RATE:.2f} evicted={evicted}')
        except Exception:
            pass
