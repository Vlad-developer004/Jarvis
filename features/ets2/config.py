FUEL_THRESHOLDS = [300, 200, 100, 50, 30, 15]
SPEED_OVER_LIMIT = 5.0
SPEED_COOLDOWN = 20.0
WEAR_THRESHOLDS = [25, 50, 75, 90]
REST_THRESHOLDS = [180, 60, 30]
WEAR_COMPONENTS = [
    ("wearEngine",       "двигатель"),
    ("wearTransmission", "коробка передач"),
    ("wearChassis",      "шасси"),
    ("wearCabin",        "кабина"),
    ("wearWheels",       "колёса"),
]
POLL_INTERVAL = 0.5
IDLE_WARN_SECONDS = 5 * 60
ROUTE_DIVERGE_DELTA = 500
ROUTE_DIVERGE_WINDOW = 30
DEADLINE_THRESHOLDS = [120, 60, 30]
BLINKER_WARN_SECONDS = 12.0
BLINKER_REPEAT_SECONDS = 22.0
ETA_INTERVAL_SECONDS = 1500.0
GEAR_ADVICE_COOLDOWN = 90.0
RPM_HIGH_FACTOR = 0.82
RPM_LOW_FACTOR = 0.28
RPM_LOW_THROTTLE_MIN = 0.55
LIVE_COMMENT_INTERVAL_SECONDS = 900.0
LIVE_COMMENT_MIN_SPEED_KMH = 60.0
LIVE_COMMENT_MIN_ROUTE_DIST_M = 5000.0
# A drop of this many km/h between two consecutive polls (POLL_INTERVAL
# apart) counts as one harsh-braking event for the end-of-job driving score,
# but only when starting from a real driving speed — otherwise routine
# stop-and-go queueing at low speed would count as "harsh braking".
HARSH_BRAKE_DROP_KMH = 18.0
HARSH_BRAKE_MIN_SPEED_KMH = 30.0
