@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build_windows.ps1"
if errorlevel 1 (
  echo.
  echo The installer build failed. Review the error above.
  pause
  exit /b 1
)
echo.
echo SIDock installer build completed successfully.
pause
endlocal
