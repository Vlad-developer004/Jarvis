@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  Jarvis Installer Build (Inno Setup)
echo ============================================================

if not exist dist\Jarvis\Jarvis.exe (
    echo [ERROR] dist\Jarvis\Jarvis.exe not found.
    echo Run build.bat first to produce the PyInstaller output.
    pause & exit /b 1
)

:: --- Locate ISCC.exe (Inno Setup 6 command-line compiler) ---
set "ISCC="
where iscc.exe >nul 2>&1 && set "ISCC=iscc.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo [ERROR] Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php
    echo         then re-run this script.
    pause & exit /b 1
)

echo Using compiler: %ISCC%
"%ISCC%" jarvis_installer.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    pause & exit /b 1
)

echo.
echo Build complete!
echo Output: installer_output\JarvisInstaller.exe
echo ============================================================
pause
