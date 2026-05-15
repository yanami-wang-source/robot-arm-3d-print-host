@echo off
setlocal
cd /d "%~dp0"

echo Starting Print Host...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_print_host.ps1"
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Print Host exited with code %EXITCODE%.
    echo Check the messages above, then press any key to close.
    pause >nul
)

endlocal & exit /b %EXITCODE%
