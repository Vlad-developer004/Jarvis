"""Polls state the core already maintains and publishes changes to the UI."""
from __future__ import annotations

import logging
import sys
import threading
import time

_log = logging.getLogger(__name__)
_POLL_SEC = 0.05
_LEVEL_FULL_SCALE = 4000.0   # RMS (int16) treated as "full" for the visual level
_WEATHER_EVERY_SEC = 600.0


def notice_severity(color: str) -> str:
    """Maps the HUD notice colour (hex) to info / warn / err."""
    try:
        c = color.lstrip('#')
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except Exception:
        return 'info'
    if r > 190 and g < 130:
        return 'err'
    if r > 190 and g > 130 and b < 120:
        return 'warn'
    return 'info'


class Observer:
    def __init__(self, publish) -> None:
        self._publish = publish
        self._last: dict[str, object] = {}
        self._level_ts = 0.0
        self._timers_ts = 0.0
        self._slow_ts = 0.0

    def start(self) -> None:
        threading.Thread(target=self._loop, name='ui-bridge-observer', daemon=True).start()
        threading.Thread(target=self._weather_loop, name='ui-bridge-weather', daemon=True).start()
        threading.Thread(target=self._nowplaying_loop, name='ui-bridge-nowplaying', daemon=True).start()

    def _changed(self, key: str, value) -> bool:
        if self._last.get(key) == value:
            return False
        self._last[key] = value
        return True

    def _loop(self) -> None:
        while True:
            try:
                self._tick()
            except Exception:
                _log.debug('observer tick failed', exc_info=True)
            time.sleep(_POLL_SEC)

    def _tick(self) -> None:
        from core.system import app_state
        from ui_next import host
        mode = host.STATE.mode
        if self._changed('state', mode):
            self._publish('state', {'mode': mode})
        muted = bool(app_state.ignore_mode)
        if self._changed('muted', muted):
            self._publish('muted', {'on': muted})
        game = (bool(app_state.game_mode), str(app_state.game_profile or ''))
        if self._changed('game', game):
            self._publish('game', {'on': game[0], 'profile': game[1]})
        now = time.monotonic()
        if now - self._level_ts >= 0.07:
            self._level_ts = now
            level = round(min(1.0, (float(app_state.mic_level) / _LEVEL_FULL_SCALE) ** 0.5), 2)
            if self._changed('level', level):
                self._publish('level', {'v': level}, sticky=False)
        speech = int(float(app_state.last_speech_ts) * 1000)
        if self._changed('speech', speech):
            self._publish('speech', {'ts': speech})
        if now - self._slow_ts >= 2.0:
            self._slow_ts = now
            self._slow_topics()
        if now - self._timers_ts >= 0.5:
            self._timers_ts = now
            timers = self._timers_payload()
            if self._changed('timers', timers):
                self._publish('timers', timers)
        guard = sys.modules.get('features.guard')
        on = bool(guard is not None and guard.is_active())
        if self._changed('guard', on):
            self._publish('guard', {'on': on})
        notices = [{'id': k, 'text': t, 'sev': notice_severity(c)} for k, t, c in host.active_notices()]
        if self._changed('notices', notices):
            self._publish('notices', notices)

    def _nowplaying_loop(self) -> None:
        """What plays on this PC (Windows media sessions), once a second. The position is published when something other than its normal progress changed."""
        from actions import now_playing
        if not now_playing.available():
            return
        last: dict = {}
        while True:
            try:
                rows = now_playing.snapshot()
                now = time.monotonic()
                key = [(r['id'], r['title'], r['artist'], r['status'], r['dur'], r['current'], tuple(r['can'].values())) for r in rows]
                moved = False
                for r in rows:
                    prev = last.get(r['id'])
                    if prev is not None:
                        expect = prev[0] + ((now - prev[1]) if prev[2] == 'playing' else 0.0)
                        moved = moved or abs(r['pos'] - expect) > 3.0
                last = {r['id']: (r['pos'], now, r['status']) for r in rows}
                if self._changed('nowplaying', key) or moved:
                    self._last['nowplaying'] = key
                    self._publish('nowplaying', {'sessions': rows, 'at': int(time.time() * 1000)})
            except Exception:
                _log.debug('nowplaying tick failed', exc_info=True)
            time.sleep(1.0)

    def _slow_topics(self) -> None:
        """Settings-like values that change rarely: mic profile (gain/threshold) and Windows autostart."""
        try:
            from core.mic_calibration import load_profile
            p = load_profile()
            mic = {'gain': float(p.get('gain', 0) or 0), 'threshold': p.get('threshold')}
            if self._changed('mic', mic):
                self._publish('mic', mic)
        except Exception:
            _log.debug('mic profile read failed', exc_info=True)
        try:
            from .extensions import publish_extensions
            publish_extensions(self._publish, only_if_changed=True)
        except Exception:
            _log.debug('extensions read failed', exc_info=True)
        try:
            from .songs import publish_songs
            publish_songs(self._publish, only_if_changed=True)
        except Exception:
            _log.debug('songs read failed', exc_info=True)
        try:
            from core import i18n
            lang = i18n.get_language()
            if self._changed('lang', lang):
                self._publish('lang', {'language': lang})
        except Exception:
            _log.debug('language read failed', exc_info=True)
        try:
            from core.system import autostart_enabled
            on = bool(autostart_enabled())
            if self._changed('autostart', on):
                self._publish('autostart', {'on': on})
        except Exception:
            _log.debug('autostart read failed', exc_info=True)

    @staticmethod
    def _timers_payload() -> dict:
        """The running timer (actions.game_timer) and reminders not fired yet (features.reminder); modules not loaded yet count as empty."""
        timer = None
        gt = sys.modules.get('actions.game_timer')
        if gt is not None:
            with gt._lock:
                t = gt._active_timer
            if t is not None:
                timer = {'label': t.label or '', 'remaining': t.remaining_sec(), 'total': t.total_sec()}
        reminders = []
        rm = sys.modules.get('features.reminder')
        if rm is not None:
            reminders = [{'id': rid, 'text': msg, 'at': int(deadline * 1000)} for rid, deadline, msg in rm.pending_items()]
        return {'timer': timer, 'reminders': reminders}

    def _weather_loop(self) -> None:
        time.sleep(5.0)
        while True:
            try:
                from actions.weather import get_weather_hud
                d = get_weather_hud()
                payload = {k: d.get(k) for k in ('ok', 'city', 'temp', 'feels', 'desc', 'code', 'sunrise', 'sunset', 'wind', 'humidity', 'pressure', 'wind_dir', 'gust', 'clouds', 'vis_km', 'uv', 'pop', 'tmax', 'tmin', 'aqi', 'vs_yesterday')}
                if self._changed('weather', payload):
                    self._publish('weather', payload)
            except Exception:
                _log.debug('weather fetch failed', exc_info=True)
            time.sleep(_WEATHER_EVERY_SEC)
