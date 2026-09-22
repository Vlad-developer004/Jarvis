"""Per-session detector state for the ETS2 telemetry monitor's independent
checks (_check_*). Split out of the old monitor.py purely for file size;
no behavior change.
"""
from dataclasses import dataclass, field as _field
from typing import Optional
from features.gaming_common.real_break import RealBreakTracker
from .config import REAL_BREAK_THRESHOLDS_MIN

@dataclass
class _MonitorState:
    """Per-session detector state for _monitor_loop's independent checks."""
    fired_fuel: set = _field(default_factory=set)
    last_fuel: Optional[float] = None
    last_speed_warn: float = 0.0
    speed_was_over: bool = False
    fired_wear: set = _field(default_factory=set)
    last_engine_on: Optional[bool] = None
    fired_rest: set = _field(default_factory=set)
    last_rest_val: int = 9999
    startup_wear_spoken: bool = False
    last_wear_pct: dict = _field(default_factory=dict)
    fired_arrival: bool = False
    fired_destination: bool = False
    last_route_dist: float = 0.0
    last_fined: bool = False
    last_tollgate: bool = False
    last_ferry: bool = False
    last_train: bool = False
    last_aux_front: int = -1
    last_aux_roof: int = -1
    fired_fuel_shortage: bool = False
    idle_start_time: float = 0.0
    idle_warned: bool = False
    last_auto_limit_snapped: float = 0.0
    last_auto_lights: float = 0.0
    last_speed_limit: float = 0.0
    last_cargo_damage: float = -1.0
    pending_cargo_dmg: float = -1.0
    pending_cargo_dmg_ts: float = 0.0
    last_cargo_loaded: Optional[bool] = None
    last_delivered_rev: Optional[int] = None
    last_oil_warn: bool = False
    last_water_warn: bool = False
    last_air_warn: bool = False
    last_air_emergency: bool = False
    last_battery_warn: bool = False
    last_adblue_warn: bool = False
    fired_deadline: set = _field(default_factory=set)
    last_deadline_abs: int = 0
    blinker_on_since: float = 0.0
    blinker_was_on: bool = False
    blinker_warned_once: bool = False
    last_eta_spoken_ts: float = 0.0
    last_gear_advice_ts: float = 0.0
    last_limit_increase_ts: float = 0.0
    last_wipers_warn_ts: float = 0.0
    last_cruise_active: Optional[bool] = None
    last_trailer_attached: Optional[bool] = None
    last_live_comment_ts: float = 0.0
    last_speed_for_brake: float = 0.0
    real_break: RealBreakTracker = _field(default_factory=lambda: RealBreakTracker(REAL_BREAK_THRESHOLDS_MIN))

    def reset_on_telemetry_loss(self) -> None:
        """Reset detectors tied to a live telemetry feed. Wear tracking,
        startup_wear_spoken, last_speed_warn and last_auto_lights deliberately
        survive a telemetry blip — they don't depend on continuous polling."""
        self.last_fuel = None
        self.fired_fuel.clear()
        self.speed_was_over = False
        self.last_engine_on = None
        self.fired_rest.clear()
        self.last_rest_val = 9999
        self.fired_arrival = False
        self.fired_destination = False
        self.last_route_dist = 0.0
        self.last_fined = False
        self.last_tollgate = False
        self.last_ferry = False
        self.last_train = False
        self.last_aux_front = -1
        self.last_aux_roof = -1
        self.idle_start_time = 0.0
        self.idle_warned = False
        self.last_auto_limit_snapped = 0.0
        self.fired_fuel_shortage = False
        self.last_speed_limit = 0.0
        self.last_cargo_damage = -1.0
        self.pending_cargo_dmg = -1.0
        self.pending_cargo_dmg_ts = 0.0
        self.last_cargo_loaded = None
        self.last_delivered_rev = None
        self.last_oil_warn = False
        self.last_water_warn = False
        self.last_air_warn = False
        self.last_air_emergency = False
        self.last_battery_warn = False
        self.last_adblue_warn = False
        self.fired_deadline.clear()
        self.last_deadline_abs = 0
        self.blinker_on_since = 0.0
        self.blinker_was_on = False
        self.blinker_warned_once = False
        self.last_eta_spoken_ts = 0.0
        self.last_gear_advice_ts = 0.0
        self.last_limit_increase_ts = 0.0
        self.last_wipers_warn_ts = 0.0
        self.last_cruise_active = None
        self.last_trailer_attached = None
        self.last_speed_for_brake = 0.0


