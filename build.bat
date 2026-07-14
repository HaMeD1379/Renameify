@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "BASE_PYTHON="
set "PYTHON_EXE="
set "CLI_MODE="
set "VERIFY_REQUIRE_INSTALLER=1"

if /I not "%~1"=="" (
    set "CLI_MODE=1"
    goto :dispatch_cli
)

goto :menu

:dispatch_cli
if /I "%~1"=="bootstrap" goto :bootstrap_only
if /I "%~1"=="clean" goto :clean
if /I "%~1"=="installer" goto :installer
if /I "%~1"=="stage" goto :stage
if /I "%~1"=="release" goto :release
if /I "%~1"=="verify" goto :verify
if /I "%~1"=="help" goto :usage_success
if /I "%~1"=="/?" goto :usage_success
if /I "%~1"=="-h" goto :usage_success
if /I "%~1"=="--help" goto :usage_success

echo [ERROR] Unknown command: %~1
goto :usage_error

:menu
cls
echo.
echo ============================================================
echo   RENAMEIFY - INSTALLER BUILD SYSTEM
echo ============================================================
echo.
echo   [1] Bootstrap / repair build environment
echo   [2] Clean build artifacts
echo   [3] Stage app files only ^(dist\app^)
echo   [4] Build installer
echo   [5] Full release ^(clean + bootstrap + installer + verify^)
echo   [6] Verify existing build
echo   [0] Exit
echo.
echo   Non-interactive:
echo        build.bat installer
echo        build.bat release
echo        build.bat stage
echo.
echo   Requirements: Python 3.10+, Flutter 3.x, PyInstaller, Inno Setup 6
echo.
set /p "choice=Enter your choice (0-6): "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :bootstrap_only
if "%choice%"=="2" goto :clean
if "%choice%"=="3" goto :stage
if "%choice%"=="4" goto :installer
if "%choice%"=="5" goto :release
if "%choice%"=="6" goto :verify

echo.
echo [ERROR] Invalid choice. Please select 0-6.
call :pause_and_menu

:usage_success
echo.
echo Usage:
echo   build.bat ^<bootstrap^|clean^|stage^|installer^|release^|verify^>
echo.
exit /b 0

:usage_error
echo.
echo Usage:
echo   build.bat ^<bootstrap^|clean^|stage^|installer^|release^|verify^>
echo.
exit /b 1

:bootstrap_only
cls
echo.
echo ============================================================
echo   BOOTSTRAP / REPAIR BUILD ENVIRONMENT
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error
echo.
echo [SUCCESS] Build environment is ready.
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
call :pause_and_menu
exit /b 0

:stage
cls
echo.
echo ============================================================
echo   STAGE APPLICATION FILES
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error
call :run_build --clean --stage-only
if errorlevel 1 goto :error
echo.
echo [SUCCESS] App staged in dist\app
call :pause_and_menu
exit /b 0

:installer
cls
echo.
echo ============================================================
echo   BUILD INSTALLER
echo ============================================================
echo.
call :bootstrap_env
if errorlevel 1 goto :error
call :run_build --clean
if errorlevel 1 goto :error
echo.
echo [SUCCESS] Installer build completed.
call :show_summary
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
call :run_build
if errorlevel 1 goto :error
set "VERIFY_REQUIRE_INSTALLER=1"
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
set "VERIFY_REQUIRE_INSTALLER=0"
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
exit /b 1

:bootstrap_env
call :detect_base_python
if errorlevel 1 exit /b 1

echo [*] Checking Flutter installation...
call flutter --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Flutter not found in PATH.
    exit /b 1
)

if not exist "%VENV_PYTHON%" (
    echo [*] Creating virtual environment in .venv ...
    call %BASE_PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)

set "PYTHON_EXE=%VENV_PYTHON%"
echo [*] Updating Python build environment...
"%PYTHON_EXE%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m pip install --upgrade -r requirements.txt
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1
exit /b 0

:run_build
if not defined PYTHON_EXE call :bootstrap_env
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" build\build.py %*
exit /b %errorlevel%

:clean_artifacts
echo [*] Removing build artifacts...
if exist "build\output" rmdir /s /q "build\output"
if exist "build\renameify_bridge.spec" del /q "build\renameify_bridge.spec"
if exist "build\Renameify.iss" del /q "build\Renameify.iss"
if exist "dist" rmdir /s /q "dist"
if exist "flutter_app\build" rmdir /s /q "flutter_app\build"
if exist "__pycache__" rmdir /s /q "__pycache__"
for /d /r "src" %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
for /d /r "tests" %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
exit /b 0

:verify_core
set "APP_EXE=%PROJECT_ROOT%\dist\app\Renameify.exe"
set "BRIDGE_EXE=%PROJECT_ROOT%\dist\app\renameify_bridge.exe"
set "INSTALLER_FOUND=0"

if not exist "%APP_EXE%" (
    echo [ERROR] App executable not found: %APP_EXE%
    exit /b 1
)
echo [OK] App executable: %APP_EXE%

if not exist "%BRIDGE_EXE%" (
    echo [ERROR] Bridge executable not found: %BRIDGE_EXE%
    exit /b 1
)
echo [OK] Bridge executable: %BRIDGE_EXE%

for %%F in ("%PROJECT_ROOT%\dist\Renameify-*-Setup.exe") do (
    if exist "%%~fF" (
        set "INSTALLER_FOUND=1"
        echo [OK] Installer: %%~fF
    )
)
if "!INSTALLER_FOUND!"=="0" if "%VERIFY_REQUIRE_INSTALLER%"=="1" (
    echo [ERROR] Installer not found in dist\
    exit /b 1
)
if "!INSTALLER_FOUND!"=="0" echo [WARN] Installer not found in dist\ ^(stage-only build is OK^)
exit /b 0

:show_summary
for %%F in (dist\Renameify-*-Setup.exe) do (
    if exist "%%~fF" echo   Installer: %%~fF
)
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
if defined CLI_MODE exit /b 1
pause
goto :menu

:exit
echo.
exit /b 0
