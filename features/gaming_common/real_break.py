"""Real-world (not in-game) continuous-play reminder — shared by ETS2's
_check_real_break (keyed off engineEnabled) and Planetbase's (keyed off the
'paused' flag). Deliberately independent of either game's own in-game
fatigue/rest mechanic: it tracks real wall-clock time so a player who never
takes an in-game rest stop still gets nudged toward an actual break."""
from __future__ import annotations
import time


class RealBreakTracker:
    def __init__(self, thresholds_min: list[int]):
        self.thresholds_min = sorted(thresholds_min)
        self.start_ts: float | None = None
        self.fired: set[int] = set()

    def check(self, active: bool) -> int | None:
        """Call once per tick with whether the player is actively engaged
        right now (engine on / game not paused). Returns the threshold (in
        minutes) that just crossed, or None if nothing fired this tick.
        `active=False` resets the timer — a real pause counts as a break."""
        if not active:
            self.start_ts = None
            self.fired = set()
            return None
        now = time.time()
        if self.start_ts is None:
            self.start_ts = now
            return None
        elapsed_min = (now - self.start_ts) / 60.0
        for threshold in self.thresholds_min:
            if threshold in self.fired:
                continue
            if elapsed_min >= threshold:
                self.fired.add(threshold)
                return threshold
        return None
