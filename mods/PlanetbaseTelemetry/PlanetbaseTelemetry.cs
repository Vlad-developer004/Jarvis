using System;
using System.IO;
using System.Threading;
using Planetbase;

namespace PlanetbaseTelemetry
{
    public class TelemetryMod
    {
        private static Thread _thread;
        private static volatile bool _running;
        private static string _outputPath;

        public static void Init()
        {
            if (_running) return;

            _outputPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "Planetbase", "jarvis_telemetry.json");

            _running = true;
            _thread = new Thread(TelemetryLoop) { IsBackground = true, Name = "JarvisTelemetry" };
            _thread.Start();
        }

        private static void TelemetryLoop()
        {
            while (_running)
            {
                try
                {
                    var json = CollectTelemetry();
                    if (json != null)
                        File.WriteAllText(_outputPath, json);
                }
                catch { }
                Thread.Sleep(2000);
            }
        }

        private static string CollectTelemetry()
        {
            var colony = Colony.getInstance();
            var time = TimeManager.getInstance();

            if (colony == null || time == null)
                return null;

            int colonistCheck = colony.getColonistCount();
            bool valid = colonistCheck >= 0 && colonistCheck <= 10000;

            int colonists = colony.getColonistCount();
            bool lowFood = colony.isLowOnFood();
            long gameTime = (long)colony.getGameTime();

            int powerBalance = Module.getOverallPowerBalance();
            int powerStorage = Module.getOverallPowerStorage();
            int powerCapacity = Module.getOverallPowerStorageCapacity();
            float waterBalance = Module.getOverallWaterBalance();
            float waterStorage = Module.getOverallWaterStorage();
            float waterCapacity = Module.getOverallWaterStorageCapacity();
            int oxygenGen = Module.getOverallOxygenGeneration();
            int moduleCount = Module.getModuleCount();

            int resVegetables = Resource.getCountOfType(ResourceTypeList.VegetablesInstance);
            int resMeat       = Resource.getCountOfType(ResourceTypeList.VitromeatInstance);
            int resMeals      = Resource.getCountOfType(ResourceTypeList.MealInstance);
            int resStarch     = Resource.getCountOfType(ResourceTypeList.StarchInstance);
            int resMetal      = Resource.getCountOfType(ResourceTypeList.MetalInstance);
            int resOre        = Resource.getCountOfType(ResourceTypeList.OreInstance);
            int resBioplastic = Resource.getCountOfType(ResourceTypeList.BioplasticInstance);
            int resMedical    = Resource.getCountOfType(ResourceTypeList.MedicalSuppliesInstance);

            bool paused = time.isPaused();
            float timeScale = time.getTimeScale();

            var disasters = DisasterManager.getInstance();
            bool anyDisaster = disasters != null && disasters.anyInProgress();
            var sd = disasters?.getSandstorm();
            var sf = disasters?.getSolarFlare();
            var bz = disasters?.getBlizzard();
            bool sandstorm = sd != null && sd.isInProgress();
            bool solarFlare = sf != null && sf.isInProgress();
            bool blizzard = bz != null && bz.isInProgress();

            int humans = Character.getHumanCount();
            int powerPct = powerCapacity > 0 ? (powerStorage * 100 / powerCapacity) : 0;
            int waterPct = waterCapacity > 0 ? (int)(waterStorage * 100f / waterCapacity) : 0;

            return string.Format(
                "{{" +
                "\"valid\":{0}," +
                "\"colonists\":{1},\"humans\":{2},\"low_food\":{3},\"game_time\":{4}," +
                "\"power_balance\":{5},\"power_storage\":{6},\"power_capacity\":{7},\"power_pct\":{8}," +
                "\"water_balance\":{9},\"water_storage\":{10},\"water_capacity\":{11},\"water_pct\":{12}," +
                "\"oxygen_gen\":{13},\"module_count\":{14},\"paused\":{15},\"time_scale\":{16}," +
                "\"any_disaster\":{17},\"sandstorm\":{18},\"solar_flare\":{19},\"blizzard\":{20}," +
                "\"res_vegetables\":{21},\"res_meat\":{22},\"res_meals\":{23},\"res_starch\":{24}," +
                "\"res_metal\":{25},\"res_ore\":{26},\"res_bioplastic\":{27},\"res_medical\":{28}," +
                "\"ts\":{29}}}",
                valid ? "true" : "false",
                colonists, humans, lowFood ? "true" : "false", gameTime,
                powerBalance, powerStorage, powerCapacity, powerPct,
                waterBalance.ToString("F2", System.Globalization.CultureInfo.InvariantCulture),
                waterStorage.ToString("F1", System.Globalization.CultureInfo.InvariantCulture),
                waterCapacity.ToString("F1", System.Globalization.CultureInfo.InvariantCulture),
                waterPct,
                oxygenGen, moduleCount,
                paused ? "true" : "false",
                timeScale.ToString("F1", System.Globalization.CultureInfo.InvariantCulture),
                anyDisaster ? "true" : "false", sandstorm ? "true" : "false",
                solarFlare ? "true" : "false", blizzard ? "true" : "false",
                resVegetables, resMeat, resMeals, resStarch,
                resMetal, resOre, resBioplastic, resMedical,
                DateTimeOffset.UtcNow.ToUnixTimeSeconds()
            );
        }
    }
}
