@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  Jarvis Build Script
echo ============================================================

:: --- Kill running instance ---
taskkill /F /IM Jarvis.exe 2>nul
timeout /t 1 /nobreak >nul

:: --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause & exit /b 1
)

:: --- Check PyInstaller ---
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] PyInstaller not found. Installing...
    pip install pyinstaller
)

:: --- Clean previous build ---
echo Cleaning previous build...
if exist build rmdir /S /Q build
if exist dist\Jarvis rmdir /S /Q dist\Jarvis

:: --- Build ---
:: Suppress pygame/pkg_resources deprecation noise on stderr (optional).
set PYTHONWARNINGS=ignore::UserWarning:pkg_resources
echo Starting PyInstaller build...
echo (Silero TTS pulls PyTorch; hook-torch and dependency analysis can take several minutes.)
python -m PyInstaller jarvis.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause & exit /b 1
)

:: --- Verify exe was created ---
if not exist dist\Jarvis\Jarvis.exe (
    echo [ERROR] dist\Jarvis\Jarvis.exe not found after build.
    pause & exit /b 1
)

:: --- Create required dirs ---
if not exist dist\Jarvis\logs   mkdir dist\Jarvis\logs
if not exist dist\Jarvis\data   mkdir dist\Jarvis\data
if not exist dist\Jarvis\models mkdir dist\Jarvis\models

:: --- Copy assets ---
echo Copying assets...
if exist audio    robocopy audio    dist\Jarvis\audio    /E /NFL /NDL /NJH /NJS /XD __pycache__
if exist data     robocopy data     dist\Jarvis\data     /E /NFL /NDL /NJH /NJS /XD __pycache__
if exist assets   robocopy assets   dist\Jarvis\assets   /E /NFL /NDL /NJH /NJS /XD __pycache__
if exist models   robocopy models   dist\Jarvis\models   /E /NFL /NDL /NJH /NJS /XD __pycache__
if exist config_pack robocopy config_pack dist\Jarvis\config_pack /E /NFL /NDL /NJH /NJS /XD __pycache__

:: --- Copy optional files ---
if exist .env (
    copy /Y .env dist\Jarvis\.env >nul
    echo .env copied.
) else (
    echo [WARN] .env not found - Telegram alerts will not work.
)

if exist jarvis_task.xml (
    copy /Y jarvis_task.xml dist\Jarvis\jarvis_task.xml >nul
    echo jarvis_task.xml copied.
)

:: --- Copy game profiles if present ---
if exist data\game_profiles (
    if not exist dist\Jarvis\data\game_profiles mkdir dist\Jarvis\data\game_profiles
    robocopy data\game_profiles dist\Jarvis\data\game_profiles /E /NFL /NDL /NJH /NJS
)

:: --- Show dist size ---
echo.
echo Build complete!
for /f "tokens=3" %%a in ('dir dist\Jarvis /s /-c 2^>nul ^| findstr "File(s)"') do (
    set SIZE=%%a
)
echo Output: dist\Jarvis\Jarvis.exe
if defined SIZE echo Total size: !SIZE! bytes

echo ============================================================
pause
