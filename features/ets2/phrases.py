"""Re-export shim: the original phrases.py content now lives in
phrases_common.py / phrases_job.py / phrases_driving.py /
phrases_warnings.py (split by theme purely for file size). Kept so
existing `from .phrases import (...)` / `from features.ets2.phrases import X`
call sites don't need to change.
"""
from .phrases_common import (
    _decline_ru, _decline_uk, _fmt_km, _fmt_min, _fmt_euro, _fmt_xp,
    _transliterate_city, _resolve_addr, _addr, _r, _pct_str, _fuel_phrase,
    _WEAR_NAMES_UK, _WEAR_NAMES_RU_STRESSED, _WEAR_NAMES_UK_STRESSED,
)
from .phrases_job import announce_job_start, announce_job_delivered, _wear_phrase
from .phrases_driving import (
    event_engine_off, event_speed_over, event_speed_limit_drop, event_speed_limit_rise,
    event_cruise_auto, event_cruise_on, event_cruise_off, event_almost_there,
    event_destination, event_idle, event_eta, event_gear_high_rpm, event_gear_low_rpm,
    event_rain_no_lights, event_blinker_on,
)
from .phrases_warnings import (
    event_cargo_damaged, event_fine_speeding, event_fine_other, event_tollgate,
    event_ferry, event_train, event_startup_wear, event_component_damaged,
    event_rest_warning, event_post_rest, event_deadline_warning, event_fuel_shortage,
    event_lights_aux_front, event_lights_aux_roof, event_oil_pressure, event_water_temp,
    event_air_pressure_emergency, event_air_pressure_warning, event_battery_warning,
    event_adblue_warning, event_trailer_attached, event_trailer_detached,
)
