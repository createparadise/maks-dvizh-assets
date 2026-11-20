@echo off
rem Maks Dvizh factory: once a week - 7 new posts (write_week.py) -> VK postponed posts (vk_autopost.py)
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
if not defined PY set "PY=python"
if not exist logs mkdir logs
echo ===== %date% %time% weekly ===== >> logs\run_weekly.log
%PY% write_week.py >> logs\run_weekly.log 2>&1
if errorlevel 1 goto fail
%PY% vk_autopost.py >> logs\run_weekly.log 2>&1
if errorlevel 1 goto fail
echo OK >> logs\run_weekly.log
exit /b 0
:fail
echo FAILED - see logs\run_weekly.log >> logs\run_weekly.log
exit /b 1
