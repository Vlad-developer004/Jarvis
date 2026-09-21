; Inno Setup script for J.A.R.V.I.S.
; Packages the PyInstaller output in dist\Jarvis into a single installer exe.
;
; Requires: dist\Jarvis\Jarvis.exe already built (run build.bat first).
; Compile with Inno Setup 6: ISCC.exe jarvis_installer.iss
; (or open this file in the Inno Setup Compiler GUI and press Build)

#define MyAppName "J.A.R.V.I.S."
#define MyAppVersion "1.5"
#define MyAppExeName "Jarvis.exe"

[Setup]
; Fixed AppId so upgrades over an existing install work correctly.
AppId={{4E6F9E6B-8B7A-4C1E-9E5D-2B0B7E6C9C11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Jarvis
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; User must scroll through and accept EULA.txt (liability disclaimer + a
; plain description of what the app does) before Next is enabled.
LicenseFile=EULA.txt
; No admin rights needed: the app self-updates and writes logs inside its own
; folder (core/logging_setup.py, core/system/updater.py), so it must live
; somewhere the current user can always write to without elevation.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer_output
OutputBaseFilename=JarvisInstaller
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Requires an existing PyInstaller build — run build.bat first.
Source: "dist\Jarvis\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Removes runtime-generated files (logs/, cache under data/) that aren't part
; of the original file list. User settings/secrets live in %APPDATA%\Jarvis,
; a separate location (see config_pack/config.py) — untouched by this.
Type: filesandordirs; Name: "{app}"
