@echo off
rem Activa el arranque automatico con Windows (y arranca el programa ya).
cd /d "%~dp0"
".venv\Scripts\python.exe" autostart.py install
pause
