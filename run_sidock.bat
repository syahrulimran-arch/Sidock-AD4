@echo off
setlocal
cd /d "%~dp0"
python -m sidock.app
if errorlevel 1 (
  echo.
  echo SIDock could not start. Activate the sidock Conda environment first.
  pause
)
endlocal

