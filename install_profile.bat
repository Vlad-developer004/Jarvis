@echo off
setlocal

echo =============================================
echo Jarvis dependency installer
echo =============================================
echo 1^) Lightweight (base)
echo 2^) Full (all features)
echo 3^) Vision/Game only (base + vision)
echo 4^) Web/QA only (base + web)
echo.
set /p MODE=Choose profile [1-4]: 

if "%MODE%"=="1" (
    pip install -r requirements.txt
    goto :done
)
if "%MODE%"=="2" (
    pip install -r requirements-full.txt
    goto :done
)
if "%MODE%"=="3" (
    pip install -r requirements-base.txt -r requirements-vision-game.txt
    goto :done
)
if "%MODE%"=="4" (
    pip install -r requirements-base.txt -r requirements-web-qa.txt
    goto :done
)

echo Invalid choice.
exit /b 1

:done
echo.
echo Installation complete.
exit /b 0
