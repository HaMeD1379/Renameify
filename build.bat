@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "BASE_PYTHON="
set "PYTHON_EXE="
set "INSTALLER_FOUND=0"
set "CLI_MODE="

if /I not "%~1"=="" (
    set "CLI_MODE=1"
    goto :dispatch_cli
)

goto :menu

:dispatch_cli
if /I "%~1"=="clean" goto :clean
if /I "%~1"=="portable" goto :portable
if /I "%~1"=="installer" goto :installer
if /I "%~1"=="both" goto :both
if /I "%~1"=="release" goto :release
if /I "%~1"=="verify" goto :verify
if /I "%~1"=="bootstrap" goto :bootstrap_only
if /I "%~1"=="help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="-h" goto :usage
if /I "%~1"=="--help" goto :usage

echo [ERROR] Unknown command: %~1
goto :usage

:menu
cls
echo.
echo ============================================================
echo   RENAMEIFY - BUILD SYSTEM
echo ============================================================
echo.
echo   [1] Bootstrap / repair Python build environment
echo   [2] Clean build artifacts
echo   [3] Build Portable version only
echo   [4] Build Installer version only
echo   [5] Build Both ^(Portable + Installer^)
echo   [6] Full Release Build ^(clean + bootstrap + both + verify^)
echo   [7] Verify existing builds
echo   [0] Exit
echo.
echo   Tip: you can also run this non-interactively:
echo        build.bat portable
echo        build.bat release
echo        build.bat verify
echo.
set /p "choice=Enter your choice (0-7): "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :bootstrap_only
if "%choice%"=="2" goto :clean
if "%choice%"=="3" goto :portable
if "%choice%"=="4" goto :installer
if "%choice%"=="5" goto :both
if "%choice%"=="6" goto :release
if "%choice%"=="7" goto :verify

echo.
echo [ERROR] Invalid choice. Please select 0-7.
call :pause_and_menu

:usage
echo.
echo Usage:
echo   build.bat ^<bootstrap^|clean^|portable^|installer^|both^|release^|verify^>
echo.
exit /b 1

:bootstrap_only
cls
echo.
echo ============================================================
echo   BOOTSTRAP / REPAIR PYTHON BUILD ENVIRONMENT
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Build environment is ready.
echo.
call :pause_and_menu
exit /b 0

:clean
cls
echo.
echo ============================================================
echo   CLEAN BUILD ARTIFACTS
echo ============================================================
echo.
call :clean_artifacts
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Clean completed.
echo.
call :pause_and_menu
exit /b 0

:portable
cls
echo.
echo ============================================================
echo   BUILD PORTABLE VERSION
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error

echo [*] Building portable version...
call :run_build --clean --portable
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Portable build completed.
echo   Output: dist\portable\Renameify.exe
echo.
call :pause_and_menu
exit /b 0

:installer
cls
echo.
echo ============================================================
echo   BUILD INSTALLER VERSION
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error

echo [*] Building installer package...
call :run_build --clean --installer
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Installer build step completed.
call :show_installer_summary
call :pause_and_menu
exit /b 0

:both
cls
echo.
echo ============================================================
echo   BUILD BOTH VERSIONS
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error

echo [*] Building portable + installer...
call :run_build --clean
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Build completed.
call :show_installer_summary
call :pause_and_menu
exit /b 0

:release
cls
echo.
echo ============================================================
echo   RENAMEIFY - FULL RELEASE BUILD
echo ============================================================
echo.
call :clean_artifacts
if errorlevel 1 goto :error
call :bootstrap_env
if errorlevel 1 goto :error

echo [*] Running full release build...
call :run_build
if errorlevel 1 goto :error

echo.
echo [*] Verifying outputs...
call :verify_core
if errorlevel 1 goto :error

echo.
echo [SUCCESS] Release build completed.
if exist "%PROJECT_ROOT%\dist" start "" "%PROJECT_ROOT%\dist"
call :pause_and_menu
exit /b 0

:verify
cls
echo.
echo ============================================================
echo   BUILD VERIFICATION
echo ============================================================
echo.
call :verify_core
if errorlevel 1 goto :error
call :pause_and_menu
exit /b 0

:detect_base_python
if defined BASE_PYTHON exit /b 0
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON=py -3"
    exit /b 0
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "BASE_PYTHON=python"
    exit /b 0
)

echo [ERROR] Python 3 was not found in PATH.
echo         Install Python 3.10+ from https://www.python.org/
exit /b 1

:bootstrap_env
call :detect_base_python
if errorlevel 1 exit /b 1

echo [*] Base interpreter: %BASE_PYTHON%

echo [*] Updating system pip tooling...
call %BASE_PYTHON% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip/setuptools/wheel with the base interpreter.
    exit /b 1
)

if not exist "%VENV_PYTHON%" (
    echo [*] Creating virtual environment in .venv ...
    call %BASE_PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

set "PYTHON_EXE=%VENV_PYTHON%"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment Python was not found: %PYTHON_EXE%
    exit /b 1
)

echo [*] Using build interpreter: %PYTHON_EXE%

echo [*] Upgrading build environment tooling...
"%PYTHON_EXE%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip/setuptools/wheel in the build environment.
    exit /b 1
)

echo [*] Installing/upgrading requirements...
"%PYTHON_EXE%" -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements from requirements.txt
    exit /b 1
)

echo [*] Installing/upgrading PyInstaller...
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    exit /b 1
)

for /f "usebackq delims=" %%V in (`"%PYTHON_EXE%" --version 2^>^&1`) do echo [OK] %%V
exit /b 0

:run_build
if not defined PYTHON_EXE call :bootstrap_env
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" build\build.py %*
exit /b %errorlevel%

:clean_artifacts
echo [*] Removing old build artifacts...
if exist "build\output" rmdir /s /q "build\output"
if exist "dist" rmdir /s /q "dist"
if exist "build\Renameify.spec" del /q "build\Renameify.spec"
if exist "build\Renameify.iss" del /q "build\Renameify.iss"
if exist "__pycache__" rmdir /s /q "__pycache__"
for /d /r "src" %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
exit /b 0

:verify_core
set "PORTABLE_EXE=%PROJECT_ROOT%\dist\portable\Renameify.exe"
set "INSTALLER_GLOB=%PROJECT_ROOT%\dist\installer\Renameify-*-Setup.exe"
set "INSTALLER_FOUND=0"

if exist "%PORTABLE_EXE%" (
    echo [OK] Portable build found: %PORTABLE_EXE%
    for %%F in ("%PORTABLE_EXE%") do (
        set /a PORTABLE_SIZE=%%~zF/1024/1024
        echo      Size: !PORTABLE_SIZE! MB
    )
) else (
    echo [ERROR] Portable build not found: %PORTABLE_EXE%
    exit /b 1
)

echo.
for %%F in (%INSTALLER_GLOB%) do (
    set "INSTALLER_FOUND=1"
    echo [OK] Installer found: %%~fF
    set /a INSTALLER_SIZE=%%~zF/1024/1024
    echo      Size: !INSTALLER_SIZE! MB
)

if "!INSTALLER_FOUND!"=="0" (
    echo [INFO] Installer not found. This is expected if Inno Setup is not installed.
)

exit /b 0

:show_installer_summary
set "INSTALLER_FOUND=0"
for %%F in (dist\installer\Renameify-*-Setup.exe) do (
    set "INSTALLER_FOUND=1"
    echo   Installer: %%~nxF
)
if "!INSTALLER_FOUND!"=="0" echo   Installer: not created ^(likely missing Inno Setup^)
exit /b 0

:pause_and_menu
if defined CLI_MODE exit /b 0
pause
goto :menu

:error
echo.
echo ============================================================
echo   BUILD FAILED
echo ============================================================
echo.
echo Check the output above for the exact step that failed.
echo.
if defined CLI_MODE exit /b 1
pause
goto :menu

:exit
echo.
echo Goodbye!
exit /b 0
