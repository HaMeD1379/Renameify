@echo off
REM Clean build artifacts for Renameify
REM This removes all generated build files

cd /d "%~dp0"

echo Cleaning build artifacts...

REM Remove build output directories
if exist "build\output" rmdir /s /q "build\output"
if exist "dist" rmdir /s /q "dist"
if exist "build\Renameify.spec" del /q "build\Renameify.spec"

REM Remove __pycache__ directories (but not in .venv)
for /d /r "src" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo Done!
pause
