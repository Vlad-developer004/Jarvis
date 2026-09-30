"""Tests for the Planetbase helpers: history/forecast, advisor, journal,
autopilot and autosave (features/planetbase/{history,advisor,journal,autopilot,autosave}.py)."""

from features.planetbase import advisor, autopilot, autosave, history, journal, planet


def _valid(**over):
    base = {
        "_valid": True, "colonists": 10, "oxygen_gen": 40, "water_balance": 1.0,
        "water_capacity": 100.0, "power_capacity": 100, "power_pct": 80,
        "power_storage": 80, "water_storage": 80.0, "time_scale": 1.0, "paused": False,
        "res_vegetables": 50, "res_meat": 50, "res_meals": 50, "res_medical": 20,
        "n_intruders": 0, "n_guards": 2, "n_sick": 0, "n_medics": 1,
        "alert_state": 0, "any_disaster": False, "land_colonists": True,
        "welfare_level": 4,
    }
    base.update(over)
    return base


def _feed(field_values, scale=1.0, step=10.0):
    """Feed one sample per `step` seconds with power_storage taken from field_values."""
    history.reset()
    for i, v in enumerate(field_values):
        history.add(_valid(power_storage=v, time_scale=scale), now=1000.0 + i * step)


# ── history ──────────────────────────────────────────────────

def test_eta_for_falling_stock():
    _feed([100, 90, 80, 70, 60])  # -1 per second = -60 per minute; 60 left -> ~1 min
    eta = history.eta_minutes("power_storage")
    assert eta is not None and 0.8 < eta < 1.2


def test_eta_none_for_stable_or_growing_stock():
    _feed([50, 50, 50, 50, 50])
    assert history.eta_minutes("power_storage") is None
    _feed([10, 20, 30, 40, 50])
    assert history.eta_minutes("power_storage") is None


def test_eta_needs_enough_samples():
    _feed([100, 90])
    assert history.eta_minutes("power_storage") is None


def test_speed_change_starts_new_window():
    history.reset()
    for i, v in enumerate([100, 90, 80, 70]):
        history.add(_valid(power_storage=v, time_scale=1.0), now=1000.0 + i * 10)
    history.add(_valid(power_storage=60, time_scale=3.0), now=1040.0)
    assert history.eta_minutes("power_storage") is None


def test_paused_samples_are_dropped():
    history.reset()
    for i in range(6):
        history.add(_valid(power_storage=100 - i * 10, paused=True), now=1000.0 + i * 10)
    assert history.eta_minutes("power_storage") is None


def test_eta_beyond_two_hours_is_ignored():
    _feed([100000, 99999, 99998, 99997, 99996])
    assert history.eta_minutes("power_storage") is None


# ── advisor ──────────────────────────────────────────────────

def test_advisor_quiet_colony():
    history.reset()
    assert advisor.collect(_valid()) == []
    assert "Критичных проблем" in advisor.advise(_valid())


def test_advisor_oxygen_shortage_is_top_and_buildable():
    history.reset()
    items = advisor.collect(_valid(colonists=50, oxygen_gen=40))
    assert items[0].build == "OxygenGenerator"


def test_advisor_intruders_without_guards():
    history.reset()
    items = advisor.collect(_valid(n_intruders=2, n_guards=0))
    assert items[0].priority >= 95 and "охраны нет" in items[0].text


def test_advisor_sick_without_medics_recommends_sickbay():
    history.reset()
    items = advisor.collect(_valid(n_sick=3, n_medics=0))
    assert any(a.build == "SickBay" for a in items)


def test_advisor_disaster_with_green_code():
    history.reset()
    items = advisor.collect(_valid(any_disaster=True, alert_state=0))
    assert "жёлтый" in items[0].text


def test_advisor_invalid_telemetry():
    assert "Телеметрия недоступна" in advisor.advise({"_valid": False})


def test_advisor_pending_build_is_used_once(monkeypatch):
    history.reset()
    started = []
    from features.planetbase import commands
    monkeypatch.setattr(commands, "build", lambda key: started.append(key) or "ok")
    advisor.advise(_valid(colonists=50, oxygen_gen=40))
    assert advisor.build_pending() == "ok"
    assert started == ["OxygenGenerator"]
    assert "Нечего строить" in advisor.build_pending()


# ── journal ──────────────────────────────────────────────────

def test_journal_summary_and_window():
    journal.reset()
    journal.log("Пришёл корабль.", now=1000.0)
    journal.log("Буря закончилась.", now=1300.0)
    text = journal.summary(minutes=15, now=1360.0)
    assert "Пришёл корабль" in text and "Буря закончилась" in text
    assert "ничего заметного" in journal.summary(minutes=1, now=5000.0)


# ── autopilot ────────────────────────────────────────────────

class _FakeCommands:
    def __init__(self):
        self.calls = []

    def execute(self, cmd, arg=""):
        self.calls.append((cmd, arg))
        return {"code": "ok"}


def _autopilot_setup(monkeypatch):
    fake = _FakeCommands()
    monkeypatch.setattr(autopilot, "commands", fake)
    monkeypatch.setattr(autopilot, "_say", lambda text: None)
    monkeypatch.setattr(autopilot, "_red_by_us", False)
    monkeypatch.setattr(autopilot, "_landing_closed_by_us", False)
    monkeypatch.setattr(autopilot, "_scale_before", None)
    return fake


def test_autopilot_disabled_does_nothing(monkeypatch):
    fake = _autopilot_setup(monkeypatch)
    autopilot.set_enabled(False)
    autopilot.tick(_valid(n_intruders=2), _valid())
    assert fake.calls == []


def test_autopilot_intruders_red_code_and_revert(monkeypatch):
    fake = _autopilot_setup(monkeypatch)
    autopilot.set_enabled(True)
    autopilot.tick(_valid(n_intruders=2), _valid())
    assert ("alert", "red") in fake.calls and ("landing", "colonists:off") in fake.calls
    autopilot.tick(_valid(n_intruders=0), _valid(n_intruders=2))
    assert ("alert", "green") in fake.calls and ("landing", "colonists:on") in fake.calls
    autopilot.set_enabled(False)


def test_autopilot_does_not_undo_manual_state(monkeypatch):
    fake = _autopilot_setup(monkeypatch)
    autopilot.set_enabled(True)
    # player already runs red code and closed landings: autopilot changes nothing
    autopilot.tick(_valid(n_intruders=1, alert_state=2, land_colonists=False), _valid())
    assert fake.calls == []
    autopilot.tick(_valid(n_intruders=0), _valid(n_intruders=1))
    assert fake.calls == []
    autopilot.set_enabled(False)


def test_autopilot_speed_reset_and_restore(monkeypatch):
    fake = _autopilot_setup(monkeypatch)
    autopilot.set_enabled(True)
    autopilot.tick(_valid(any_disaster=True, time_scale=3.0), _valid(time_scale=3.0))
    assert ("speed_normal", "") in fake.calls
    autopilot.tick(_valid(any_disaster=False, time_scale=1.0), _valid(any_disaster=True, time_scale=1.0))
    assert ("speed", "3.0") in fake.calls
    autopilot.set_enabled(False)


# ── autosave ─────────────────────────────────────────────────

def _autosave_setup(monkeypatch, now=10000.0):
    calls = []

    class Fake:
        @staticmethod
        def execute(cmd, arg=""):
            calls.append((cmd, arg))
            return {"code": "ok"}

    monkeypatch.setattr(autosave, "commands", Fake)
    monkeypatch.setattr(autosave, "_enabled", True)
    monkeypatch.setattr(autosave, "_slot", 0)
    monkeypatch.setattr(autosave.time, "time", lambda: now)
    return calls


def test_autosave_interval_and_rotation(monkeypatch):
    calls = _autosave_setup(monkeypatch)
    monkeypatch.setattr(autosave, "_last_save", 10000.0 - 700)
    autosave.tick(_valid(), _valid())
    assert calls == [("save", "jarvis_auto_1")]
    autosave.tick(_valid(), _valid())  # just saved: nothing
    assert len(calls) == 1


def test_autosave_skips_when_paused_or_invalid(monkeypatch):
    calls = _autosave_setup(monkeypatch)
    monkeypatch.setattr(autosave, "_last_save", 0.0)
    autosave.tick(_valid(paused=True), _valid())
    autosave.tick({"_valid": False}, _valid())
    assert calls == []


def test_autosave_before_danger(monkeypatch):
    calls = _autosave_setup(monkeypatch)
    monkeypatch.setattr(autosave, "_last_save", 10000.0 - 120)
    autosave.tick(_valid(n_intruders=3), _valid())
    assert calls == [("save", "jarvis_auto_1")]


def test_autosave_uses_three_slots(monkeypatch):
    calls = _autosave_setup(monkeypatch)
    for _ in range(4):
        monkeypatch.setattr(autosave, "_last_save", 0.0)
        autosave.tick(_valid(), _valid())
    assert [c[1] for c in calls] == ["jarvis_auto_1", "jarvis_auto_2", "jarvis_auto_3", "jarvis_auto_1"]


# ── planet risks ─────────────────────────────────────────────

def test_planet_levels_and_unknown_values():
    assert planet.level({"risk_sandstorm": "High"}, "sandstorm") == 3
    assert planet.level({"risk_sandstorm": "Variable"}, "sandstorm") == 2
    assert planet.level({"risk_sandstorm": "Low"}, "sandstorm") == 1
    assert planet.level({"risk_sandstorm": "None"}, "sandstorm") == 0
    assert planet.level({}, "sandstorm") == 0
    assert planet.level({"risk_meteor": "weird"}, "meteor") == 0


def test_reserve_bonus_grows_with_storm_risk_and_is_capped():
    assert planet.reserve_bonus({}) == 0
    assert planet.reserve_bonus({"risk_sandstorm": "High"}) == 15
    assert planet.reserve_bonus({"risk_sandstorm": "Variable"}) == 8
    both = {"risk_sandstorm": "High", "risk_blizzard": "High"}
    assert planet.reserve_bonus(both) == 20
    # meteors/thunderstorms don't drain reserves
    assert planet.reserve_bonus({"risk_meteor": "High", "risk_thunderstorm": "High"}) == 0


def test_planet_report_lists_all_risks():
    text = planet.report(_valid(planet="Oasis", difficulty="Hard", risk_meteor="High"))
    assert "Oasis" in text and "Hard" not in text
    for label in ("песчаные бури", "солнечные вспышки", "метели", "метеориты", "грозы"):
        assert label in text
    assert "метеориты — высокий" in text
    assert "Телеметрия недоступна" in planet.report({"_valid": False})


def test_advisor_storm_prone_planet_wants_more_storage_earlier():
    history.reset()
    calm = advisor.collect(_valid(power_pct=55))
    stormy = advisor.collect(_valid(power_pct=55, risk_sandstorm="High"))
    assert not any(a.build == "PowerCollector" for a in calm)
    assert any(a.build == "PowerCollector" for a in stormy)


def test_advisor_meteor_and_thunderstorm_defenses():
    history.reset()
    data = _valid(module_count=20, risk_meteor="High", risk_thunderstorm="Variable",
                  n_anti_meteor=0, n_lightning_rod=0)
    builds = {a.build for a in advisor.collect(data)}
    assert {"AntiMeteorLaser", "LightningRod"} <= builds
    done = _valid(module_count=20, risk_meteor="High", risk_thunderstorm="Variable",
                  n_anti_meteor=1, n_lightning_rod=2)
    builds = {a.build for a in advisor.collect(done)}
    assert "AntiMeteorLaser" not in builds and "LightningRod" not in builds
    # a tiny early colony isn't nagged about defenses yet
    early = _valid(module_count=3, risk_meteor="High", n_anti_meteor=0)
    assert "AntiMeteorLaser" not in {a.build for a in advisor.collect(early)}


def test_monitor_low_power_alert_fires_earlier_on_storm_planet(monkeypatch):
    from features.planetbase import monitor
    spoken = []
    monkeypatch.setattr(monitor, "_speak", spoken.append)
    monkeypatch.setattr(monitor, "_alert", lambda phrases, tone="warn": spoken.append(("alert", tone)))
    monkeypatch.setattr(monitor, "_cooldown_ok", lambda key: True)
    monkeypatch.setattr(monitor, "_prev", {})
    monkeypatch.setattr(monitor, "_first_tick", True)

    base = _valid(power_pct=30, water_balance=5.0, res_metal=99, res_bioplastic=99, res_medical=99,
                  res_vegetables=99, res_meat=99, res_meals=99)
    monitor._check(dict(base))
    assert ("alert", "warn") not in spoken  # 30% is above the flat 20% floor

    spoken.clear()
    monkeypatch.setattr(monitor, "_first_tick", True)
    monitor._check(dict(base, risk_sandstorm="High"))  # floor is now 35%
    assert ("alert", "warn") in spoken


# ── telemetry freshness (heartbeat vs snapshot) ──────────────

def test_heartbeat_fresh_snapshot_stale_is_valid_but_stale(monkeypatch):
    from features.planetbase import telemetry
    monkeypatch.setattr(telemetry.time, "time", lambda: 1000.0)
    data = {"valid": True, "ts": 999, "collected_ts": 900}  # game minimised: frozen snapshot
    telemetry._apply_freshness(data)
    assert data["_valid"] is True and data["_stale"] is True


def test_dead_heartbeat_is_invalid(monkeypatch):
    from features.planetbase import telemetry
    monkeypatch.setattr(telemetry.time, "time", lambda: 1000.0)
    data = {"valid": True, "ts": 900, "collected_ts": 900}  # game closed
    telemetry._apply_freshness(data)
    assert data["_valid"] is False


def test_old_mod_without_collected_ts_is_never_stale(monkeypatch):
    from features.planetbase import telemetry
    monkeypatch.setattr(telemetry.time, "time", lambda: 1000.0)
    data = {"valid": True, "ts": 999}
    telemetry._apply_freshness(data)
    assert data["_valid"] is True and data["_stale"] is False


def test_extras_tick_ignores_stale_snapshots():
    from features.planetbase import extras
    history.reset()
    extras.tick(_valid(_stale=True))
    assert history._samples.__len__() == 0
    extras.tick(_valid())
    assert history._samples.__len__() == 1


def test_command_timeout_removes_unconsumed_command(monkeypatch, tmp_path):
    from features.planetbase import commands
    monkeypatch.setattr(commands, "_CMD_FILE", tmp_path / "jarvis_command.txt")
    monkeypatch.setattr(commands, "_RESULT_FILE", tmp_path / "jarvis_command_result.json")
    monkeypatch.setattr(commands, "_TIMEOUT", 0.3)
    assert commands.execute("pause") is None
    assert not (tmp_path / "jarvis_command.txt").exists()


# ── installer: locked DLL must not abort monitor startup ─────

def test_install_mod_keeps_existing_dll_when_copy_is_locked(monkeypatch, tmp_path):
    from features.planetbase import installer
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / installer._MOD_DLL).write_bytes(b"new")
    managed = tmp_path / "Managed"
    managed.mkdir()
    (managed / installer._MOD_DLL).write_bytes(b"old-loaded-by-game")
    monkeypatch.setattr(installer, "_ASSETS", assets)

    def locked(*a, **k):
        raise PermissionError("in use")
    monkeypatch.setattr(installer.shutil, "copy2", locked)

    assert installer._install_mod(managed) is True  # old DLL still usable
    (managed / installer._MOD_DLL).unlink()
    assert installer._install_mod(managed) is False  # nothing installed at all


# ── profile / game data consistency ──────────────────────────

# Module keys reported by the game's own data (mod command dump_modules).
_GAME_MODULE_KEYS = {
    "Airlock", "OxygenGenerator", "Canteen", "Dorm", "Cabin", "BioDome", "ProcessingPlant",
    "Factory", "MultiDome", "Bar", "Storage", "SickBay", "Lab", "RoboticsFacility",
    "ControlCenter", "BasePad", "SolarPanel", "WindTurbine", "PowerCollector",
    "WaterExtractor", "WaterTank", "Mine", "LandingPad", "Starport", "RadioAntenna",
    "Telescope", "AntiMeteorLaser", "LightningRod", "Signpost", "Pyramid", "Monolith",
}


def _profile_actions():
    import json
    import pathlib
    path = pathlib.Path(__file__).resolve().parent.parent / "data" / "game_profiles" / "planetbase.json"
    return [sp.get("telemetry_action", "") for sp in json.loads(path.read_text(encoding="utf-8"))["spells"]]


def test_profile_module_keys_exist_in_the_game():
    for action in _profile_actions():
        if action.startswith("build:"):
            assert action.split(":", 1)[1] in _GAME_MODULE_KEYS, action
        if action.startswith("cmd:show:module:"):
            assert action.rsplit(":", 1)[1] in _GAME_MODULE_KEYS, action


def test_every_module_has_a_spoken_name_and_a_build_phrase():
    from features.planetbase import commands
    built = {a.split(":", 1)[1] for a in _profile_actions() if a.startswith("build:")}
    assert set(commands._NAMES) == _GAME_MODULE_KEYS
    assert built == _GAME_MODULE_KEYS


def test_advisor_build_keys_are_real_game_modules():
    history.reset()
    data = _valid(colonists=50, oxygen_gen=40, n_sick=3, n_medics=0, low_food=True,
                  risk_meteor="High", risk_thunderstorm="High", risk_sandstorm="High",
                  module_count=30, n_anti_meteor=0, n_lightning_rod=0, power_pct=30,
                  welfare_level=0, water_balance=-1.0)
    for item in advisor.collect(data):
        assert item.build is None or item.build in _GAME_MODULE_KEYS


# ── build command safety replies / census ────────────────────

def test_build_busy_reply(monkeypatch):
    from features.planetbase import commands
    monkeypatch.setattr(commands, "_send", lambda cmd, arg="": {"code": "busy", "detail": "2"})
    assert "завершите текущее действие" in commands.build("SolarPanel")


def test_census_lists_specialties():
    from features.planetbase import extras
    text = extras.census(_valid(colonists=372, n_workers=100, n_bots=73, n_low_status=83, n_sick=1))
    assert "роботов 73" in text and "рабочих 100" in text and "22 процентов" in text and "больных 1" in text
    assert "Телеметрия недоступна" in extras.census({"_valid": False})
