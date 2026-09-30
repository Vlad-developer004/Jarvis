using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using Planetbase;
using Module = Planetbase.Module;

namespace PlanetbaseTelemetry
{
    // Selection/camera and direct-control commands. Always called on the Unity
    // main thread from TelemetryMod.PollCommand.
    internal static class GameCommands
    {
        // Repeating the same "show" command walks through the matches.
        private static readonly Dictionary<string, int> ShowIndex = new Dictionary<string, int>();

        internal static bool Run(GameStateGame state, string cmd, string arg, out string code, out string detail)
        {
            code = "ok";
            detail = "";

            switch (cmd)
            {
                case "pause":
                case "unpause":
                case "speed_up":
                case "speed_down":
                case "speed_normal":
                case "speed":
                    Time(cmd, arg, out code, out detail);
                    return true;
                case "landing":
                    Landing(arg, out code, out detail);
                    return true;
                case "priority":
                    Priority(arg, out code, out detail);
                    return true;
                case "show":
                    Show(arg, out code, out detail);
                    return true;
                case "alert":
                    Alert(arg, out code, out detail);
                    return true;
                case "save":
                    Save(state, arg, out code, out detail);
                    return true;
                case "dump_modules":
                    DumpModules(out code, out detail);
                    return true;
            }
            return false;
        }

        // ── Time ────────────────────────────────────────────────

        private static void Time(string cmd, string arg, out string code, out string detail)
        {
            var t = TimeManager.getInstance();
            if (t == null) { code = "not_in_game"; detail = ""; return; }

            if (cmd == "pause") t.pause();
            else if (cmd == "unpause") t.unpause();
            else if (cmd == "speed_normal") { t.unpause(); t.setNormalSpeed(); }
            else if (cmd == "speed_up") { t.unpause(); t.increaseSpeed(); }
            else if (cmd == "speed_down") { t.unpause(); t.decreaseSpeed(); }
            else if (cmd == "speed")
            {
                float target;
                if (!float.TryParse(arg, NumberStyles.Float, CultureInfo.InvariantCulture, out target))
                {
                    code = "bad_argument"; detail = arg; return;
                }
                t.unpause();
                // The game only exposes single steps; walk until we reach the
                // target or stop changing (edge of the scale table).
                for (int i = 0; i < 12; i++)
                {
                    float cur = t.getTimeScale();
                    if (Math.Abs(cur - target) < 0.05f) break;
                    if (cur < target) t.increaseSpeed(); else t.decreaseSpeed();
                    if (Math.Abs(t.getTimeScale() - cur) < 0.001f) break;
                }
            }

            code = "ok";
            detail = t.isPaused() ? "paused" : t.getTimeScale().ToString("F1", CultureInfo.InvariantCulture);
        }

        // ── Landing permissions ─────────────────────────────────

        // arg: "<colonists|visitors|merchants|all>:<on|off>"
        private static void Landing(string arg, out string code, out string detail)
        {
            detail = arg;
            string[] p = arg.Split(':');
            var ships = LandingShipManager.getInstance();
            var perms = ships != null ? ships.getLandingPermissions() : null;
            if (p.Length != 2 || perms == null || (p[1] != "on" && p[1] != "off"))
            {
                code = "bad_argument";
                return;
            }

            bool allow = p[1] == "on";
            if (p[0] == "colonists" || p[0] == "all") perms.getColonistRefBool().set(allow);
            if (p[0] == "visitors" || p[0] == "all") perms.getVisitorRefBool().set(allow);
            if (p[0] == "merchants" || p[0] == "all") perms.getMerchantRefBool().set(allow);
            if (p[0] != "colonists" && p[0] != "visitors" && p[0] != "merchants" && p[0] != "all")
            {
                code = "bad_argument";
                return;
            }
            code = "ok";
        }

        // ── Construction priority ───────────────────────────────

        // arg: "selected:<on|off>" or "type:<ModuleKey>:<on|off>"
        private static void Priority(string arg, out string code, out string detail)
        {
            detail = "0";
            string[] p = arg.Split(':');
            bool on = p.Length > 0 && p[p.Length - 1] == "on";
            if (p.Length < 2 || (p[p.Length - 1] != "on" && p[p.Length - 1] != "off"))
            {
                code = "bad_argument";
                return;
            }

            if (p[0] == "selected")
            {
                var c = Selection.getSelectedConstruction();
                if (c == null) { code = "nothing_selected"; return; }
                c.setHighPriority(on);
                code = "ok";
                detail = "1";
                return;
            }

            if (p[0] == "type" && p.Length == 3)
            {
                int n = 0;
                foreach (Module m in Modules())
                {
                    if (!string.Equals(TelemetryMod.ModuleKey(m.getModuleType()), p[1], StringComparison.OrdinalIgnoreCase))
                        continue;
                    m.setHighPriority(on);
                    n++;
                }
                code = n > 0 ? "ok" : "none";
                detail = n.ToString(CultureInfo.InvariantCulture);
                return;
            }

            code = "bad_argument";
        }

        // ── Select + move camera ────────────────────────────────

        // arg: sick | ko | intruders | guards | damaged | unpowered | unoperated | module:<Key>
        private static void Show(string arg, out string code, out string detail)
        {
            detail = arg;
            var targets = new List<Selectable>();

            string[] p = arg.Split(':');
            switch (p[0])
            {
                case "sick":
                case "ko":
                case "intruders":
                case "guards":
                    foreach (Character c in Characters())
                    {
                        if (c.isDestroyed() || c.isDead()) continue;
                        var spec = c.getSpecialization();
                        bool match =
                            (p[0] == "intruders" && spec is Intruder) ||
                            (p[0] == "guards" && spec is Guard && c is Human) ||
                            (p[0] == "ko" && c is Human && c.isKo()) ||
                            (p[0] == "sick" && c is Human && ((Human)c).getCondition() != null);
                        if (match) targets.Add(c);
                    }
                    break;
                case "damaged":
                case "unpowered":
                case "unoperated":
                case "module":
                    foreach (Module m in Modules())
                    {
                        if (m.isDestroyed()) continue;
                        bool match =
                            (p[0] == "damaged" && m.isExtremelyDamaged()) ||
                            (p[0] == "unpowered" && !m.isPowered()) ||
                            (p[0] == "unoperated" && m.isUnoperated()) ||
                            (p[0] == "module" && p.Length == 2 &&
                                string.Equals(TelemetryMod.ModuleKey(m.getModuleType()), p[1], StringComparison.OrdinalIgnoreCase));
                        if (match) targets.Add(m);
                    }
                    break;
                default:
                    code = "bad_argument";
                    return;
            }

            if (targets.Count == 0)
            {
                code = "none";
                detail = "0";
                return;
            }

            int last;
            if (!ShowIndex.TryGetValue(arg, out last)) last = -1;
            int idx = (last + 1) % targets.Count;
            ShowIndex[arg] = idx;

            Selectable target = targets[idx];
            Selection.clear();
            target.setSelected(true);
            var cam = CameraManager.getInstance();
            if (cam != null) cam.scrollToPosition(target.getPosition());

            code = "shown";
            detail = (idx + 1).ToString(CultureInfo.InvariantCulture) + "/" +
                     targets.Count.ToString(CultureInfo.InvariantCulture);
        }

        // ── Alert / save / data dump ────────────────────────────

        // arg: green | yellow | red
        private static void Alert(string arg, out string code, out string detail)
        {
            detail = arg;
            var security = SecurityManager.getInstance();
            if (security == null) { code = "not_in_game"; return; }

            if (arg == "green") security.setAlertState(AlertState.NoAlert);
            else if (arg == "yellow") security.setAlertState(AlertState.YellowAlert);
            else if (arg == "red") security.setAlertState(AlertState.RedAlert);
            else { code = "bad_argument"; return; }
            code = "ok";
        }

        // Saves under a Jarvis-owned name so the player's own slots are never overwritten.
        private static void Save(GameStateGame state, string name, out string code, out string detail)
        {
            detail = name;
            foreach (char ch in name)
            {
                if (!char.IsLetterOrDigit(ch) && ch != '_' && ch != '-') { code = "bad_argument"; return; }
            }
            if (name.Length == 0) { code = "bad_argument"; return; }
            if (!state.isSaveAllowed()) { code = "not_allowed"; return; }
            state.saveGame(name);
            code = "ok";
        }

        private static string Esc(string v)
        {
            if (v == null) return "";
            var sb = new StringBuilder(v.Length);
            foreach (char ch in v)
            {
                if (ch == '"' || ch == '\\') sb.Append('\\').Append(ch);
                else if (ch < 0x20) sb.Append(' ');
                else sb.Append(ch);
            }
            return sb.ToString();
        }

        // Writes every buildable module type (names, requirements, sizes, costs) so
        // Jarvis can answer questions from real game data instead of guesses.
        private static void DumpModules(out string code, out string detail)
        {
            var sb = new StringBuilder(4096);
            sb.Append('[');
            int n = 0;
            foreach (ModuleType t in TypeList<ModuleType, ModuleTypeList>.get())
            {
                if (n++ > 0) sb.Append(',');
                var req = t.getRequiredModuleType();
                sb.Append("{\"key\":\"").Append(Esc(TelemetryMod.ModuleKey(t))).Append('"');
                sb.Append(",\"name\":\"").Append(Esc(t.getName())).Append('"');
                sb.Append(",\"requires\":\"").Append(req != null ? Esc(TelemetryMod.ModuleKey(req)) : "").Append('"');
                sb.Append(",\"exterior\":").Append(t.isExterior() ? "true" : "false");
                sb.Append(",\"min_size\":").Append(t.getMinSize());
                sb.Append(",\"max_size\":").Append(t.getMaxSize());
                sb.Append(",\"default_size\":").Append(t.getDefaultSize());
                sb.Append(",\"max_users\":").Append(t.getMaxUsers());
                sb.Append(",\"prestige\":").Append(t.getPrestige());
                sb.Append(",\"cost\":{");
                ResourceAmounts cost = null;
                try { cost = t.calculateCost(t.getDefaultSize()); } catch { }
                if (cost != null)
                {
                    for (int i = 0; i < cost.getCount(); i++)
                    {
                        var a = cost.get(i);
                        if (i > 0) sb.Append(',');
                        string rn = a.getResourceType().GetType().Name;
                        if (rn.StartsWith("ResourceType")) rn = rn.Substring("ResourceType".Length);
                        sb.Append('"').Append(Esc(rn)).Append("\":").Append(a.getAmount());
                    }
                }
                sb.Append("}}");
            }
            sb.Append(']');
            File.WriteAllText(Path.Combine(TelemetryMod.DataDir, "jarvis_modules.json"), sb.ToString(), new UTF8Encoding(false));
            code = "ok";
            detail = n.ToString(CultureInfo.InvariantCulture);
        }

        // ── Object lists ────────────────────────────────────────

        private static IEnumerable Characters()
        {
            var list = TelemetryMod.CharactersField != null
                ? TelemetryMod.CharactersField.GetValue(null) as IEnumerable : null;
            if (list == null) yield break;
            foreach (object o in new ArrayList(ToList(list)))
            {
                var c = o as Character;
                if (c != null) yield return c;
            }
        }

        private static IEnumerable Modules()
        {
            var list = TelemetryMod.ModulesField != null
                ? TelemetryMod.ModulesField.GetValue(null) as IEnumerable : null;
            if (list == null) yield break;
            foreach (object o in new ArrayList(ToList(list)))
            {
                var m = o as Module;
                if (m != null) yield return m;
            }
        }

        // Snapshot so game-side list changes during our loop can't invalidate the enumerator.
        private static ArrayList ToList(IEnumerable source)
        {
            var copy = new ArrayList();
            foreach (object o in source) copy.Add(o);
            return copy;
        }
    }
}
