using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using Planetbase;
using Module = Planetbase.Module;

namespace PlanetbaseTelemetry
{
    // Telemetry v2. Game objects are read on the Unity main thread (via
    // Application.onBeforeRender); a background thread only writes the file.
    public class TelemetryMod
    {
        private const int CollectIntervalMs = 2000;
        private const int Version = 2;

        private static Thread _writer;
        private static volatile bool _running;
        private static volatile string _pending;
        private static string _outputPath;
        internal static string DataDir;
        private static int _lastCollectTick;
        private static string _lastError = "";

        internal static FieldInfo CharactersField;
        internal static FieldInfo ModulesField;

        // Command channel: Jarvis writes 3 lines (id, command, argument) to _cmdPath,
        // the mod runs it on the main thread and answers with JSON in _resultPath.
        private const int CommandPollMs = 300;
        private static string _cmdPath;
        private static string _resultPath;
        private static int _lastCommandTick;
        private static long _lastCommandId;
        private static MethodInfo _startPlacingModule;

        public static void Init()
        {
            if (_running) return;

            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Planetbase");
            DataDir = dir;
            _outputPath = Path.Combine(dir, "jarvis_telemetry.json");
            _cmdPath = Path.Combine(dir, "jarvis_command.txt");
            _resultPath = Path.Combine(dir, "jarvis_command_result.json");

            const BindingFlags all = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            CharactersField = typeof(Character).GetField("mCharacters", all);
            ModulesField = typeof(Module).GetField("mModules", all);
            _startPlacingModule = typeof(GameStateGame).GetMethod(
                "startPlacingModule", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);

            _running = true;
            _lastCollectTick = Environment.TickCount;
            UnityEngine.Application.onBeforeRender += OnBeforeRender;

            _writer = new Thread(WriterLoop) { IsBackground = true, Name = "JarvisTelemetryWriter" };
            _writer.Start();
        }

        private static void OnBeforeRender()
        {
            int now = Environment.TickCount;

            if (now - _lastCommandTick >= CommandPollMs)
            {
                _lastCommandTick = now;
                PollCommand();
            }

            if (now - _lastCollectTick < CollectIntervalMs) return;
            _lastCollectTick = now;

            try
            {
                string json = CollectTelemetry();
                if (json != null) _pending = json;
            }
            catch (Exception e)
            {
                _lastError = e.GetType().Name + ": " + e.Message;
            }
        }

        // ── Commands ────────────────────────────────────────────

        private static void PollCommand()
        {
            try
            {
                if (!File.Exists(_cmdPath)) return;

                string[] lines = File.ReadAllLines(_cmdPath);
                File.Delete(_cmdPath);
                if (lines.Length < 2) return;

                long id;
                if (!long.TryParse(lines[0].Trim(), out id) || id == _lastCommandId) return;
                _lastCommandId = id;

                string cmd = lines[1].Trim();
                string arg = lines.Length > 2 ? lines[2].Trim() : "";

                string code, detail;
                try
                {
                    RunCommand(cmd, arg, out code, out detail);
                }
                catch (Exception e)
                {
                    code = "error";
                    detail = e.GetType().Name + ": " + e.Message;
                }

                var sb = new StringBuilder(128);
                sb.Append('{');
                Put(sb, "id", id);
                Put(sb, "code", code);
                Put(sb, "detail", detail);
                sb.Length--;
                sb.Append('}');
                File.WriteAllText(_resultPath, sb.ToString());
            }
            catch (Exception e)
            {
                _lastError = "command: " + e.GetType().Name + ": " + e.Message;
            }
        }

        private static void RunCommand(string cmd, string arg, out string code, out string detail)
        {
            code = "unknown_command";
            detail = cmd;

            var gm = GameManager.getInstance();
            var state = gm != null ? gm.getGameState() as GameStateGame : null;
            if (state == null)
            {
                code = "not_in_game";
                detail = "";
                return;
            }

            if (cmd == "build")
                StartBuild(state, arg, out code, out detail);
            else if (cmd == "list_modules")
            {
                code = "ok";
                detail = ListModuleTypes();
            }
            else if (!GameCommands.Run(state, cmd, arg, out code, out detail))
            {
                code = "unknown_command";
                detail = cmd;
            }
        }

        private static object GetPrivate(object target, string name)
        {
            var f = target.GetType().GetField(
                name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            return f != null ? f.GetValue(target) : null;
        }

        private static void CallPrivate(object target, string name)
        {
            var m = target.GetType().GetMethod(
                name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public, null, Type.EmptyTypes, null);
            if (m != null) m.Invoke(target, null);
        }

        internal static string ModuleKey(ModuleType type)
        {
            string n = type.GetType().Name;
            return n.StartsWith("ModuleType") ? n.Substring("ModuleType".Length) : n;
        }

        private static string ListModuleTypes()
        {
            var sb = new StringBuilder();
            foreach (ModuleType t in TypeList<ModuleType, ModuleTypeList>.get())
            {
                if (sb.Length > 0) sb.Append(", ");
                sb.Append(ModuleKey(t)).Append('=').Append(t.getName());
            }
            return sb.ToString();
        }

        // Same entry point the build-menu buttons use: the game then shows the
        // placement ghost and the player positions, resizes and confirms it.
        private static void StartBuild(GameStateGame state, string key, out string code, out string detail)
        {
            detail = "";
            ModuleType found = null;
            foreach (ModuleType t in TypeList<ModuleType, ModuleTypeList>.get())
            {
                if (string.Equals(ModuleKey(t), key, StringComparison.OrdinalIgnoreCase))
                {
                    found = t;
                    break;
                }
            }

            if (found == null)
            {
                code = "unknown_type";
                detail = key;
                return;
            }

            var challenge = ChallengeManager.getInstance();
            if (challenge != null && challenge.isModuleDisabled(found))
            {
                code = "disabled";
                detail = ModuleKey(found);
                return;
            }

            var required = found.getRequiredModuleType();
            if (required != null && !Module.isModuleTypeBuilt(required))
            {
                code = "requires";
                detail = ModuleKey(required);
                return;
            }

            if (_startPlacingModule == null)
            {
                code = "error";
                detail = "startPlacingModule not found";
                return;
            }

            // The game's own state machine: 0 = normal, 1 = placing a module, 2 = editing
            // a module, others = component placement etc. Only start from 0 or 1. Never
            // call cancelComponentPlacement here: with no component it still runs
            // onComponentPlacementEnd, which switches to edit mode and throws on a null
            // active module, leaving the game in a broken state.
            int mode = Convert.ToInt32(GetPrivate(state, "mMode") ?? 0);
            if (mode != 0 && mode != 1)
            {
                code = "busy";
                detail = mode.ToString(CultureInfo.InvariantCulture);
                return;
            }
            if (mode == 1 && GetPrivate(state, "mActiveModule") != null)
                CallPrivate(state, "cancelModulePlacement");

            try
            {
                _startPlacingModule.Invoke(state, new object[] { found });
            }
            catch (TargetInvocationException e)
            {
                Exception inner = e.InnerException ?? e;
                code = "error";
                detail = inner.GetType().Name + ": " + inner.Message;
                return;
            }
            code = "started";
            detail = ModuleKey(found);
        }

        // Runs on its own thread so the file keeps a fresh "ts" heartbeat even when
        // Unity stops rendering (game minimised/unfocused). The snapshot itself is
        // then the last one collected on the main thread, which is still accurate
        // because the game does not advance while it is in the background.
        private static void WriterLoop()
        {
            while (_running)
            {
                try
                {
                    string json = _pending;
                    if (json != null && json.Length > 1)
                    {
                        string body = json.Substring(0, json.Length - 1) +
                            ",\"ts\":" + DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(CultureInfo.InvariantCulture) + "}";
                        File.WriteAllText(_outputPath, body);
                    }
                }
                catch { }
                Thread.Sleep(1000);
            }
        }

        // ── JSON helpers ────────────────────────────────────────

        private static void Put(StringBuilder sb, string key, int v)
        {
            sb.Append('"').Append(key).Append("\":").Append(v.ToString(CultureInfo.InvariantCulture)).Append(',');
        }

        private static void Put(StringBuilder sb, string key, long v)
        {
            sb.Append('"').Append(key).Append("\":").Append(v.ToString(CultureInfo.InvariantCulture)).Append(',');
        }

        private static void Put(StringBuilder sb, string key, float v, string fmt)
        {
            sb.Append('"').Append(key).Append("\":").Append(v.ToString(fmt, CultureInfo.InvariantCulture)).Append(',');
        }

        private static void Put(StringBuilder sb, string key, bool v)
        {
            sb.Append('"').Append(key).Append("\":").Append(v ? "true" : "false").Append(',');
        }

        private static void Put(StringBuilder sb, string key, string v)
        {
            sb.Append('"').Append(key).Append("\":\"");
            if (v != null)
            {
                foreach (char ch in v)
                {
                    if (ch == '"' || ch == '\\') sb.Append('\\').Append(ch);
                    else if (ch < 0x20) sb.Append(' ');
                    else sb.Append(ch);
                }
            }
            sb.Append("\",");
        }

        // ── Collection ──────────────────────────────────────────

        private static string CollectTelemetry()
        {
            var colony = Colony.getInstance();
            var time = TimeManager.getInstance();

            if (colony == null || time == null)
                return null;

            int colonists = colony.getColonistCount();
            bool valid = colonists >= 0 && colonists <= 10000;

            var sb = new StringBuilder(2048);
            sb.Append('{');

            Put(sb, "v", Version);
            Put(sb, "valid", valid);
            Put(sb, "colonists", colonists);
            Put(sb, "humans", Character.getHumanCount());
            Put(sb, "low_food", colony.isLowOnFood());
            Put(sb, "game_time", (long)colony.getGameTime());

            int powerCapacity = Module.getOverallPowerStorageCapacity();
            int powerStorage = Module.getOverallPowerStorage();
            float waterCapacity = Module.getOverallWaterStorageCapacity();
            float waterStorage = Module.getOverallWaterStorage();
            Put(sb, "power_balance", Module.getOverallPowerBalance());
            Put(sb, "power_storage", powerStorage);
            Put(sb, "power_capacity", powerCapacity);
            Put(sb, "power_pct", powerCapacity > 0 ? (powerStorage * 100 / powerCapacity) : 0);
            Put(sb, "water_balance", Module.getOverallWaterBalance(), "F2");
            Put(sb, "water_storage", waterStorage, "F1");
            Put(sb, "water_capacity", waterCapacity, "F1");
            Put(sb, "water_pct", waterCapacity > 0 ? (int)(waterStorage * 100f / waterCapacity) : 0);
            Put(sb, "oxygen_gen", Module.getOverallOxygenGeneration());
            Put(sb, "module_count", Module.getModuleCount());

            Put(sb, "paused", time.isPaused());
            Put(sb, "time_scale", time.getTimeScale(), "F1");

            var disasters = DisasterManager.getInstance();
            bool anyDisaster = disasters != null && disasters.anyInProgress();
            var sd = disasters != null ? disasters.getSandstorm() : null;
            var sf = disasters != null ? disasters.getSolarFlare() : null;
            var bz = disasters != null ? disasters.getBlizzard() : null;
            var storm = disasters != null ? disasters.getStormInProgress() : null;
            Put(sb, "any_disaster", anyDisaster);
            Put(sb, "sandstorm", sd != null && sd.isInProgress());
            Put(sb, "solar_flare", sf != null && sf.isInProgress());
            Put(sb, "blizzard", bz != null && bz.isInProgress());
            Put(sb, "disaster_intensity", storm != null ? storm.getIntensity() : 0f, "F2");

            Put(sb, "res_vegetables", Resource.getCountOfType(ResourceTypeList.VegetablesInstance));
            Put(sb, "res_meat", Resource.getCountOfType(ResourceTypeList.VitromeatInstance));
            Put(sb, "res_meals", Resource.getCountOfType(ResourceTypeList.MealInstance));
            Put(sb, "res_starch", Resource.getCountOfType(ResourceTypeList.StarchInstance));
            Put(sb, "res_metal", Resource.getCountOfType(ResourceTypeList.MetalInstance));
            Put(sb, "res_ore", Resource.getCountOfType(ResourceTypeList.OreInstance));
            Put(sb, "res_bioplastic", Resource.getCountOfType(ResourceTypeList.BioplasticInstance));
            Put(sb, "res_medical", Resource.getCountOfType(ResourceTypeList.MedicalSuppliesInstance));
            Put(sb, "res_spares", Resource.getCountOfType(ResourceTypeList.SparesInstance));
            Put(sb, "res_coins", Resource.getCountOfType(ResourceTypeList.CoinsInstance));

            // Each section is isolated: a failure there only zeroes its own fields.
            Section(sb, "colony", () => CollectColony(sb, colony));
            Section(sb, "security", () => CollectSecurity(sb));
            Section(sb, "planet", () => CollectPlanet(sb));
            Section(sb, "characters", () => CollectCharacters(sb));
            Section(sb, "modules", () => CollectModules(sb));

            Put(sb, "err", _lastError);
            Put(sb, "collected_ts", DateTimeOffset.UtcNow.ToUnixTimeSeconds());

            sb.Length--; // trailing comma
            sb.Append('}');
            return sb.ToString();
        }

        private static void Section(StringBuilder sb, string name, Action body)
        {
            int mark = sb.Length;
            try
            {
                body();
            }
            catch (Exception e)
            {
                sb.Length = mark;
                _lastError = name + ": " + e.GetType().Name + ": " + e.Message;
            }
        }

        private static void CollectColony(StringBuilder sb, Colony colony)
        {
            var prestige = colony.getPrestigeIndicator();
            var welfare = colony.getWelfareIndicator();
            Put(sb, "prestige", prestige != null ? prestige.getValue() : 0f, "F1");
            Put(sb, "prestige_level", prestige != null ? (int)prestige.getLevel() : -1);
            Put(sb, "welfare", welfare != null ? welfare.getValue() : 0f, "F1");
            Put(sb, "welfare_level", welfare != null ? (int)welfare.getLevel() : -1);

            var tech = TechManager.getInstance();
            Put(sb, "techs_acquired", tech != null ? tech.getAcquiredCount() : 0);
        }

        private static void CollectSecurity(StringBuilder sb)
        {
            var security = SecurityManager.getInstance();
            // 0 = no alert (green), 1 = yellow, 2 = red
            Put(sb, "alert_state", security != null ? (int)security.getAlertState() : -1);
            Put(sb, "outside_allowed", security != null && security.isGoingOutsideAllowed());

            var ships = LandingShipManager.getInstance();
            var perms = ships != null ? ships.getLandingPermissions() : null;
            Put(sb, "land_colonists", perms != null && perms.areColonistsAllowed());
            Put(sb, "land_visitors", perms != null && perms.areVisitorsAllowed());
            Put(sb, "land_merchants", perms != null && perms.areMerchantsAllowed());
        }

        private static void CollectPlanet(StringBuilder sb)
        {
            var planet = PlanetManager.getCurrentPlanet();
            if (planet == null) return;
            Put(sb, "planet", planet.getName());
            Put(sb, "difficulty", planet.getDifficultyString());
            Put(sb, "risk_sandstorm", planet.getSandstormRisk().ToString());
            Put(sb, "risk_solar_flare", planet.getSolarFlareRisk().ToString());
            Put(sb, "risk_blizzard", planet.getBlizzardRisk().ToString());
            Put(sb, "risk_meteor", planet.getMeteorRisk().ToString());
            Put(sb, "risk_thunderstorm", planet.getThunderstormRisk().ToString());
        }

        private static void CollectCharacters(StringBuilder sb)
        {
            var list = CharactersField != null ? CharactersField.GetValue(null) as IEnumerable : null;
            if (list == null) return;

            int workers = 0, biologists = 0, engineers = 0, medics = 0, guards = 0;
            int bots = 0, intruders = 0, visitors = 0;
            int sick = 0, ko = 0, lowStatus = 0, fighting = 0;

            foreach (object o in list)
            {
                var c = o as Character;
                if (c == null || c.isDestroyed() || c.isDead()) continue;

                var spec = c.getSpecialization();
                if (spec is Intruder) { intruders++; continue; }
                if (spec is Visitor) { visitors++; continue; }
                if (c is Bot) { bots++; continue; }
                if (!(c is Human)) continue;

                if (spec is Worker) workers++;
                else if (spec is Biologist) biologists++;
                else if (spec is Engineer) engineers++;
                else if (spec is Medic) medics++;
                else if (spec is Guard) guards++;

                if (((Human)c).getCondition() != null) sick++;
                if (c.isKo()) ko++;
                if (c.isLowStatus()) lowStatus++;
                if (c.isFighting()) fighting++;
            }

            Put(sb, "n_workers", workers);
            Put(sb, "n_biologists", biologists);
            Put(sb, "n_engineers", engineers);
            Put(sb, "n_medics", medics);
            Put(sb, "n_guards", guards);
            Put(sb, "n_bots", bots);
            Put(sb, "n_intruders", intruders);
            Put(sb, "n_visitors", visitors);
            Put(sb, "n_sick", sick);
            Put(sb, "n_ko", ko);
            Put(sb, "n_low_status", lowStatus);
            Put(sb, "n_fighting", fighting);
        }

        private static void CollectModules(StringBuilder sb)
        {
            var list = ModulesField != null ? ModulesField.GetValue(null) as IEnumerable : null;
            if (list == null) return;

            int damaged = 0, unpowered = 0, unoperated = 0, vitalDown = 0;
            int antiMeteor = 0, lightningRods = 0;
            float spaceSum = 0f;
            int spaceCount = 0;

            foreach (object o in list)
            {
                var m = o as Module;
                if (m == null || m.isDestroyed()) continue;

                bool bad = false;
                if (m.isExtremelyDamaged()) { damaged++; bad = true; }
                if (!m.isPowered()) { unpowered++; bad = true; }
                if (m.isUnoperated()) { unoperated++; bad = true; }
                if (bad && m.isVital()) vitalDown++;

                var type = m.getModuleType();
                if (type != null && m.isBuilt())
                {
                    string key = ModuleKey(type);
                    if (key == "AntiMeteorLaser") antiMeteor++;
                    else if (key == "LightningRod") lightningRods++;
                }
                if (type != null && type.hasFlag(ModuleType.FlagStorage))
                {
                    spaceSum += m.getResourceSpaceRatio();
                    spaceCount++;
                }
            }

            Put(sb, "mod_damaged", damaged);
            Put(sb, "mod_unpowered", unpowered);
            Put(sb, "mod_unoperated", unoperated);
            Put(sb, "mod_vital_down", vitalDown);
            Put(sb, "n_anti_meteor", antiMeteor);
            Put(sb, "n_lightning_rod", lightningRods);
            Put(sb, "storage_modules", spaceCount);
            Put(sb, "storage_space_avg", spaceCount > 0 ? spaceSum / spaceCount : 0f, "F2");
        }
    }
}
