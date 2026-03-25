@echo off
REM Quick build script for Renameify
REM Usage: build.bat [--clean]

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Run the build script
python build\build.py %*

pause
