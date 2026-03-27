@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:menu
cls
echo.
echo ============================================================
echo   RENAMEIFY - BUILD SYSTEM
echo ============================================================
echo.
echo   Select build option:
echo.
echo   [1] Clean build artifacts
echo   [2] Build Portable version only (quick)
echo   [3] Build Installer version only
echo   [4] Build Both (Portable + Installer)
echo   [5] Full Release Build (clean + verify + both)
echo   [6] Verify existing builds
echo   [0] Exit
echo.
echo ============================================================
echo.

set /p "choice=Enter your choice (0-6): "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :clean
if "%choice%"=="2" goto :portable
if "%choice%"=="3" goto :installer
if "%choice%"=="4" goto :both
if "%choice%"=="5" goto :release
if "%choice%"=="6" goto :verify

echo.
echo [ERROR] Invalid choice. Please select 0-6.
timeout /t 2 >nul
goto :menu

REM ============================================================
REM Clean build artifacts
REM ============================================================
:clean
cls
echo.
echo ============================================================
echo   CLEAN BUILD ARTIFACTS
echo ============================================================
echo.
echo Cleaning build artifacts...
echo.

REM Remove build output directories
if exist "build\output" (
    echo [*] Removing build\output...
    rmdir /s /q "build\output"
)
if exist "dist" (
    echo [*] Removing dist...
    rmdir /s /q "dist"
)
if exist "build\Renameify.spec" (
    echo [*] Removing build\Renameify.spec...
    del /q "build\Renameify.spec"
)

REM Remove __pycache__ directories (but not in .venv)
echo [*] Removing Python cache files...
for /d /r "src" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo.
echo [SUCCESS] Clean completed!
echo.
pause
goto :menu

REM ============================================================
REM Build Portable version only (quick)
REM ============================================================
:portable
cls
echo.
echo ============================================================
echo   BUILD PORTABLE VERSION
echo ============================================================
echo.

call :setup_env
if errorlevel 1 goto :error

echo [*] Building portable version...
echo.
python build\build.py --clean --portable

if errorlevel 1 goto :error

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo ============================================================
echo.
echo   Portable exe: dist\portable\Renameify.exe
echo.
echo   You can now run or distribute this file.
echo   Config will be stored in Documents\Renameify\
echo.

pause
goto :menu

REM ============================================================
REM Build Installer version only
REM ============================================================
:installer
cls
echo.
echo ============================================================
echo   BUILD INSTALLER VERSION
echo ============================================================
echo.

call :setup_env
if errorlevel 1 goto :error

echo [*] Building portable first (required for installer)...
echo.
python build\build.py --clean --portable
if errorlevel 1 goto :error

echo.
echo [*] Building installer...
echo.
python build\build.py --installer

if errorlevel 1 (
    echo.
    echo [ERROR] Installer build failed!
    echo Make sure Inno Setup is installed:
    echo https://jrsoftware.org/isdl.php
    pause
    goto :menu
)

echo.
echo ============================================================
echo   BUILD COMPLETE!
echo ============================================================
echo.
dir /b dist\installer\*.exe
echo.
echo   Installer created successfully!
echo.

pause
goto :menu

REM ============================================================
REM Build Both (Portable + Installer)
REM ============================================================
:both
cls
echo.
echo ============================================================
echo   BUILD BOTH VERSIONS
echo ============================================================
echo.

call :setup_env
if errorlevel 1 goto :error

echo [*] Starting build process...
echo.
python build\build.py

if errorlevel 1 goto :error

echo.
echo [SUCCESS] Build completed!
echo.
pause
goto :menu

REM ============================================================
REM Full Release Build
REM ============================================================
:release
cls
echo.
echo ============================================================
echo   RENAMEIFY - RELEASE BUILD
echo ============================================================
echo.
echo   This will create production-ready builds:
echo   - Portable version (compressed with UPX)
echo   - Installer version (Windows installer)
echo.
echo   Press Ctrl+C to cancel, or
pause

REM Step 1: Clean
echo.
echo ============================================================
echo   Step 1: Cleaning Previous Builds
echo ============================================================
echo.
echo [*] Removing old build artifacts...

if exist "build\output" rmdir /s /q "build\output"
if exist "dist" rmdir /s /q "dist"
if exist "build\Renameify.spec" del /q "build\Renameify.spec"
for /d /r "src" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo [OK] Clean completed
echo.

REM Step 2: Setup environment
echo.
echo ============================================================
echo   Step 2: Environment Setup
echo ============================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARNING] No virtual environment found
    echo           Using system Python
)
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    goto :error
)

echo [*] Python version:
python --version
echo.

REM Step 3: Verify dependencies
echo.
echo ============================================================
echo   Step 3: Verifying Dependencies
echo ============================================================
echo.
echo [*] Checking requirements.txt...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    goto :error
)
echo [OK] Dependencies verified
echo.

REM Step 4: Build portable
echo.
echo ============================================================
echo   Step 4: Building Portable Version
echo ============================================================
echo.
python build\build.py --portable
if errorlevel 1 goto :error

REM Step 5: Build installer
echo.
echo ============================================================
echo   Step 5: Building Installer Version
echo ============================================================
echo.
python build\build.py --installer
if errorlevel 1 (
    echo [WARNING] Installer build failed or skipped
    echo           This is OK if Inno Setup is not installed
    set INSTALLER_FAILED=1
)

REM Step 6: Verify builds
echo.
echo ============================================================
echo   Step 6: Verifying Build Outputs
echo ============================================================
echo.

set HAS_PORTABLE=0
set HAS_INSTALLER=0

if exist "dist\portable\Renameify.exe" (
    set HAS_PORTABLE=1
    for %%F in ("dist\portable\Renameify.exe") do (
        set /a PORTABLE_SIZE=%%~zF/1024/1024
        echo [OK] Portable: Renameify.exe
        echo     Size: !PORTABLE_SIZE! MB
        echo     Path: %%~fF
    )
    echo.
) else (
    echo [ERROR] Portable exe not found!
    goto :error
)

for %%F in (dist\installer\Renameify-*-Setup.exe) do (
    set HAS_INSTALLER=1
    set /a INSTALLER_SIZE=%%~zF/1024/1024
    echo [OK] Installer: %%~nxF
    echo     Size: !INSTALLER_SIZE! MB
    echo     Path: %%~fF
    echo.
)

if !HAS_INSTALLER! EQU 0 (
    echo [WARNING] Installer not found
    echo           Install Inno Setup from: https://jrsoftware.org/isdl.php
    echo.
)

REM Success summary
echo.
echo ============================================================
echo   RELEASE BUILD COMPLETE!
echo ============================================================
echo.
echo   * Portable version built successfully
if !HAS_INSTALLER! EQU 1 (
    echo   * Installer version built successfully
) else (
    echo   - Installer skipped ^(Inno Setup not installed^)
)
echo.
echo   Distribution files ready in: dist\
echo.
echo   Next steps:
echo   1. Test the portable exe: dist\portable\Renameify.exe
if !HAS_INSTALLER! EQU 1 (
    echo   2. Test the installer: dist\installer\Renameify-*-Setup.exe
)
echo   3. Create GitHub Release
echo   4. Upload distribution files
echo.
echo ============================================================
echo.

REM Open dist folder
start "" "%~dp0dist"

pause
goto :menu

REM ============================================================
REM Verify existing builds
REM ============================================================
:verify
cls
echo.
echo ============================================================
echo   BUILD VERIFICATION
echo ============================================================
echo.

set PORTABLE_EXE=dist\portable\Renameify.exe
set INSTALLER_PATTERN=dist\installer\Renameify-*-Setup.exe

echo Checking build outputs...
echo.

REM Check portable
if exist "%PORTABLE_EXE%" (
    echo [OK] Portable version found
    for %%F in ("%PORTABLE_EXE%") do (
        set /a SIZE=%%~zF/1024/1024
        echo     File: %%~nxF
        echo     Size: !SIZE! MB
        echo     Path: %%~fF
    )
    echo.
) else (
    echo [MISSING] Portable version not found
    echo           Expected: %PORTABLE_EXE%
    echo.
)

REM Check installer
set FOUND_INSTALLER=0
for %%F in (%INSTALLER_PATTERN%) do (
    set FOUND_INSTALLER=1
    echo [OK] Installer version found
    set /a SIZE=%%~zF/1024/1024
    echo     File: %%~nxF
    echo     Size: !SIZE! MB
    echo     Path: %%~fF
    echo.
)

if !FOUND_INSTALLER! EQU 0 (
    echo [MISSING] Installer version not found
    echo           Expected pattern: %INSTALLER_PATTERN%
    echo.
)

echo ============================================================
echo   Distribution Files
echo ============================================================
echo.

if exist dist\ (
    echo dist\
    if exist dist\portable\ (
        echo   portable\
        for %%F in (dist\portable\*) do echo     - %%~nxF
    )
    if exist dist\installer\ (
        echo   installer\
        for %%F in (dist\installer\*) do echo     - %%~nxF
    )
    echo.
) else (
    echo [WARNING] No dist\ folder found
    echo           Run a build first
    echo.
)

echo ============================================================
echo.
pause
goto :menu

REM ============================================================
REM Helper: Setup environment
REM ============================================================
:setup_env
if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found - using system Python
    echo.
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)
exit /b 0

REM ============================================================
REM Error handler
REM ============================================================
:error
echo.
echo ============================================================
echo   BUILD FAILED!
echo ============================================================
echo.
echo   Check the errors above for details.
echo.
pause
goto :menu

REM ============================================================
REM Exit
REM ============================================================
:exit
echo.
echo Goodbye!
exit /b 0
