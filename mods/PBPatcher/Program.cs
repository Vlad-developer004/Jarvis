using System;
using System.IO;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

class Program
{
    static int Main(string[] args)
    {
        var managedPath = args.Length > 0 ? args[0]
            : @"C:\Program Files (x86)\Steam\steamapps\common\Planetbase\Planetbase_Data\Managed";

        var asmPath = Path.Combine(managedPath, "Assembly-CSharp.dll");
        var modPath = Path.Combine(managedPath, "PlanetbaseTelemetry.dll");
        var bakPath = Path.Combine(managedPath, "Assembly-CSharp.bak");

        if (!File.Exists(asmPath)) { Console.WriteLine($"Not found: {asmPath}"); return 1; }
        if (!File.Exists(modPath)) { Console.WriteLine($"Not found: {modPath}"); return 1; }

        var resolver = new DefaultAssemblyResolver();
        resolver.AddSearchDirectory(managedPath);
        var readerParams = new ReaderParameters { AssemblyResolver = resolver };

        var gameAsm = AssemblyDefinition.ReadAssembly(asmPath, readerParams);
        var modAsm  = AssemblyDefinition.ReadAssembly(modPath,  readerParams);

        // Find GameManager constructor
        var gameManager = gameAsm.MainModule.Types
            .FirstOrDefault(t => t.FullName == "Planetbase.GameManager");
        if (gameManager == null) { Console.WriteLine("Planetbase.GameManager not found"); return 1; }

        var ctor = gameManager.Methods
            .FirstOrDefault(m => m.IsConstructor && !m.IsStatic);
        if (ctor == null) { Console.WriteLine("GameManager constructor not found"); return 1; }

        // Check if already patched
        var alreadyPatched = ctor.Body.Instructions
            .Any(i => i.OpCode == OpCodes.Call &&
                      i.Operand?.ToString()?.Contains("LoadMods") == true);
        if (alreadyPatched)
        {
            Console.WriteLine("Already patched — nothing to do.");
            return 0;
        }

        // Find TelemetryMod.Init() in PlanetbaseTelemetry
        var modLoader = modAsm.MainModule.Types
            .FirstOrDefault(t => t.Name == "TelemetryMod");
        if (modLoader == null) { Console.WriteLine("TelemetryMod not found in mod DLL"); return 1; }

        var loadMods = modLoader.Methods
            .FirstOrDefault(m => m.Name == "Init" && m.IsStatic);
        if (loadMods == null) { Console.WriteLine("TelemetryMod.Init() not found"); return 1; }

        // Inject call just before the final ret instruction
        var il = ctor.Body.GetILProcessor();
        var importedLoadMods = gameAsm.MainModule.Import(loadMods);
        var callInstr = il.Create(OpCodes.Call, importedLoadMods);
        var lastInstr = ctor.Body.Instructions.Last();
        il.InsertBefore(lastInstr, callInstr);

        // Backup original
        if (!File.Exists(bakPath))
            File.Copy(asmPath, bakPath);

        // Write patched assembly
        gameAsm.Write(asmPath);

        Console.WriteLine("Patch applied successfully.");
        Console.WriteLine($"Injected: {modLoader.FullName}::Init()");
        Console.WriteLine($"Into: Planetbase.GameManager::.ctor()");
        Console.WriteLine($"Backup: {bakPath}");
        return 0;
    }
}
