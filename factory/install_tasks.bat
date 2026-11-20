@echo off
rem Maks Dvizh factory: creates 3 tasks in Windows Task Scheduler for the current user (no admin rights needed)
cd /d "%~dp0"
set "PYW="
for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PYW (
  echo Python not found. Install Python 3 from python.org and run this file again.
  pause
  exit /b 1
)
schtasks /Create /F /TN "MaksDvizh-Weekly" /SC WEEKLY /D MON /ST 09:00 /TR "\"%~dp0run_weekly.bat\""
schtasks /Create /F /TN "MaksDvizh-DailyImage" /SC DAILY /ST 08:00 /TR "\"%~dp0run_daily_image.bat\""
schtasks /Create /F /TN "MaksDvizh-TELO" /SC MINUTE /MO 10 /TR "\"%PYW%\" \"%~dp0reply_telo.py\""
echo.
echo Done: MaksDvizh-Weekly (Mon 09:00), MaksDvizh-DailyImage (08:00), MaksDvizh-TELO (every 10 min).
schtasks /Query /TN "MaksDvizh-TELO"
pause
