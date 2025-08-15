@echo off
echo Starting Probable Spork System...
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start the system
python start_system.py

pause
