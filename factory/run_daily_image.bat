@echo off
rem Maks Dvizh factory: every day - picture for today's post (images\dayN.png)
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
if not defined PY set "PY=python"
if not exist logs mkdir logs
echo ===== %date% %time% image ===== >> logs\daily_image.log
%PY% gen_image.py --today >> logs\daily_image.log 2>&1
