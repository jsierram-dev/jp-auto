@echo off
rem Desactiva el arranque automatico con Windows.
cd /d "%~dp0"
".venv\Scripts\python.exe" autostart.py uninstall
pause
