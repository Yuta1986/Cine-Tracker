@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Cine-Tracker Windows build helper (PyInstaller).
rem Produces:
rem   Onedir:  dist\windows\onedir\Windows_CineTracker\Windows_CineTracker.exe
rem   Onefile: dist\windows\onefile\Windows_CineTracker.exe

pushd "%~dp0"

rem Use absolute paths for common Windows tools so Git/MSYS/etc. don't shadow them.
set "WIN_SYSTEM32=%SystemRoot%\System32"
set "CHOICE_EXE=%WIN_SYSTEM32%\choice.exe"
set "WHERE_EXE=%WIN_SYSTEM32%\where.exe"
set "EXPLORER_EXE=%WIN_SYSTEM32%\explorer.exe"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

set "VENV_DIR=.venv-win"
set "PY=%VENV_DIR%\Scripts\python.exe"

set "FETCH_COLMAP=0"
set "FETCH_FFMPEG=0"
set "BUILD_NATIVE=0"
set "FORCE=0"
set "OUT_DIR=dist\windows"
set "MODE=both"
set "MENU=0"
set "PAUSE_ON_EXIT=0"

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\\\" (
  echo NOTE: Running from a UNC path: %SCRIPT_DIR%
  echo       If you see "UNC paths are not supported", open CMD normally and run:
  echo         pushd "%SCRIPT_DIR%"
  echo         build_windows.bat ...
)

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--fetch-colmap" ( set "FETCH_COLMAP=1" & shift & goto parse_args )
if /I "%~1"=="--fetch-ffmpeg" ( set "FETCH_FFMPEG=1" & shift & goto parse_args )
if /I "%~1"=="--build-native" ( set "BUILD_NATIVE=1" & shift & goto parse_args )
if /I "%~1"=="--force" ( set "FORCE=1" & shift & goto parse_args )
if /I "%~1"=="--onedir" ( set "MODE=onedir" & shift & goto parse_args )
if /I "%~1"=="--onefile" ( set "MODE=onefile" & shift & goto parse_args )
if /I "%~1"=="--both" ( set "MODE=both" & shift & goto parse_args )
if /I "%~1"=="--menu" ( set "MENU=1" & set "PAUSE_ON_EXIT=1" & shift & goto parse_args )
if /I "%~1"=="--pause" ( set "PAUSE_ON_EXIT=1" & shift & goto parse_args )
if /I "%~1"=="--no-pause" ( set "PAUSE_ON_EXIT=0" & shift & goto parse_args )

if /I "%~1"=="--out" (
  if "%~2"=="" (
    echo Missing value for --out
    goto usage
  )
  if "%~2:~0,2%"=="--" (
    echo Missing value for --out
    goto usage
  )
  set "OUT_DIR=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--choose-out" (
  call :choose_out
  if errorlevel 1 exit /b 1
  shift
  goto parse_args
)

rem Back-compat aliases:
if /I "%~1"=="--distpath" ( shift & set "_ARG=--out" & goto parse_args_rewrite )
if /I "%~1"=="--choose-dist" ( shift & set "_ARG=--choose-out" & goto parse_args_rewrite )

if /I "%~1"=="--help" goto usage
if /I "%~1"=="/?" goto usage
echo Unknown argument: %~1
goto usage

:parse_args_rewrite
if "%_ARG%"=="--out" (
  if "%~1"=="" (
    echo Missing value for --out
    goto usage
  )
  if "%~1:~0,2%"=="--" (
    echo Missing value for --out
    goto usage
  )
  set "OUT_DIR=%~1"
  set "_ARG="
  shift
  goto parse_args
)
if "%_ARG%"=="--choose-out" (
  set "_ARG="
  call :choose_out
  if errorlevel 1 exit /b 1
  goto parse_args
)
set "_ARG="
goto parse_args

:args_done

if not exist "%WHERE_EXE%" (
  echo ERROR: Missing %WHERE_EXE%
  exit /b 1
)
"%WHERE_EXE%" python >nul 2>nul
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.10+ and try again.
  exit /b 1
)

if "%MENU%"=="1" (
  call :menu
  if errorlevel 1 exit /b 1
)

if not exist "%PY%" (
  echo Creating virtual environment: %VENV_DIR%
  python -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

echo Upgrading packaging tools...
"%PY%" -m pip install -U pip setuptools wheel
if errorlevel 1 exit /b 1

echo Installing project + dependencies...
rem Extras are optional in pyproject; this ensures core/ui deps are present.
"%PY%" -m pip install -e ".[core,ui,io]"
if errorlevel 1 exit /b 1

echo Installing PyInstaller...
"%PY%" -m pip install -U pyinstaller
if errorlevel 1 exit /b 1

if "%BUILD_NATIVE%"=="1" (
  if not defined VSINSTALLDIR (
    echo NOTE: VSINSTALLDIR is not set. If native build fails, run this from:
    echo       "Developer Command Prompt for VS 2022"
  )
  echo Building native extension (cinetracker_native)...
  if defined VCPKG_ROOT (
    "%PY%" scripts\build_extension.py --config Release --install-to src --vcpkg-root "%VCPKG_ROOT%"
  ) else (
    "%PY%" scripts\build_extension.py --config Release --install-to src
  )
  if errorlevel 1 exit /b 1
)

if "%FETCH_COLMAP%"=="1" (
  echo Fetching COLMAP Windows CUDA binary into third_party\bin ...
  if "%FORCE%"=="1" (
    "%PY%" scripts\fetch_colmap_windows_cuda.py --force
  ) else (
    "%PY%" scripts\fetch_colmap_windows_cuda.py
  )
  if errorlevel 1 exit /b 1
)

if "%FETCH_FFMPEG%"=="1" (
  echo Fetching FFmpeg Windows build into third_party\bin ...
  if "%FORCE%"=="1" (
    "%PY%" scripts\fetch_ffmpeg_windows.py --force
  ) else (
    "%PY%" scripts\fetch_ffmpeg_windows.py
  )
  if errorlevel 1 exit /b 1
)

if not exist "third_party\\bin\\colmap.exe" (
  echo WARN: third_party\bin\colmap.exe not found. It will NOT be bundled.
  echo       Use: build_windows.bat --fetch-colmap
)
if not exist "third_party\\bin\\ffmpeg.exe" (
  echo WARN: third_party\bin\ffmpeg.exe not found. It will NOT be bundled.
  echo       Use: build_windows.bat --fetch-ffmpeg
)
if not exist "third_party\\bin\\ffprobe.exe" (
  echo WARN: third_party\bin\ffprobe.exe not found. It will NOT be bundled.
)

set "APP_NAME=Windows_CineTracker"
if defined CINETRACKER_APP_NAME set "APP_NAME=%CINETRACKER_APP_NAME%"

set "PYI=%VENV_DIR%\Scripts\pyinstaller.exe"

if /I "%MODE%"=="onedir" set "MODE=onedir"
if /I "%MODE%"=="onefile" set "MODE=onefile"
if /I "%MODE%"=="both" set "MODE=both"

if "%MODE%"=="onedir" goto do_onedir
if "%MODE%"=="onefile" goto do_onefile
if "%MODE%"=="both" goto do_both
echo Invalid build mode: %MODE%
goto usage

:do_onedir
  if not exist "%PYI%" (
    echo ERROR: PyInstaller not found at: %PYI%
    echo        Try rerunning, or run: "%PY%" -m pip install -U pyinstaller
    exit /b 1
  )
  if not exist "packaging\\cinetracker.spec" (
    echo ERROR: Missing spec file: packaging\\cinetracker.spec
    exit /b 1
  )
  echo Building (onedir) with PyInstaller...
  echo   "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onedir" --workpath "build\\pyinstaller\\onedir" packaging\\cinetracker.spec
  "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onedir" --workpath "build\\pyinstaller\\onedir" packaging\\cinetracker.spec
  if errorlevel 1 exit /b 1
  goto done_build

:do_onefile
  if not exist "%PYI%" (
    echo ERROR: PyInstaller not found at: %PYI%
    echo        Try rerunning, or run: "%PY%" -m pip install -U pyinstaller
    exit /b 1
  )
  if not exist "packaging\\cinetracker_onefile.spec" (
    echo ERROR: Missing spec file: packaging\\cinetracker_onefile.spec
    exit /b 1
  )
  echo Building (onefile) with PyInstaller...
  echo   "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onefile" --workpath "build\\pyinstaller\\onefile" packaging\\cinetracker_onefile.spec
  "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onefile" --workpath "build\\pyinstaller\\onefile" packaging\\cinetracker_onefile.spec
  if errorlevel 1 exit /b 1
  goto done_build

:do_both
  if not exist "%PYI%" (
    echo ERROR: PyInstaller not found at: %PYI%
    echo        Try rerunning, or run: "%PY%" -m pip install -U pyinstaller
    exit /b 1
  )
  if not exist "packaging\\cinetracker.spec" (
    echo ERROR: Missing spec file: packaging\\cinetracker.spec
    exit /b 1
  )
  if not exist "packaging\\cinetracker_onefile.spec" (
    echo ERROR: Missing spec file: packaging\\cinetracker_onefile.spec
    exit /b 1
  )
  echo Building (onedir) with PyInstaller...
  echo   "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onedir" --workpath "build\\pyinstaller\\onedir" packaging\\cinetracker.spec
  "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onedir" --workpath "build\\pyinstaller\\onedir" packaging\\cinetracker.spec
  if errorlevel 1 exit /b 1
  echo Building (onefile) with PyInstaller...
  echo   "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onefile" --workpath "build\\pyinstaller\\onefile" packaging\\cinetracker_onefile.spec
  "%PYI%" --clean --noconfirm --distpath "%OUT_DIR%\onefile" --workpath "build\\pyinstaller\\onefile" packaging\\cinetracker_onefile.spec
  if errorlevel 1 exit /b 1
  goto done_build

:done_build
echo.
echo Build complete:
if "%MODE%"=="onedir" echo   Onedir:  %OUT_DIR%\onedir\%APP_NAME%\%APP_NAME%.exe
if "%MODE%"=="onefile" echo   Onefile: %OUT_DIR%\onefile\%APP_NAME%.exe
if "%MODE%"=="both" echo   Onedir:  %OUT_DIR%\onedir\%APP_NAME%\%APP_NAME%.exe
if "%MODE%"=="both" echo   Onefile: %OUT_DIR%\onefile\%APP_NAME%.exe
echo.
echo Opening output folder...
"%EXPLORER_EXE%" "%OUT_DIR%" >nul 2>nul
echo.
popd
if "%PAUSE_ON_EXIT%"=="1" pause
exit /b 0

:menu
echo.
echo Cine-Tracker Windows build (guided)
echo ---------------------------------
echo.
echo Choose build type:
if not exist "%CHOICE_EXE%" (
  echo ERROR: Missing %CHOICE_EXE%
  exit /b 1
)
"%CHOICE_EXE%" /C 123 /M "[1] both  [2] onedir  [3] onefile"
if errorlevel 3 set "MODE=onefile"
if errorlevel 2 set "MODE=onedir"
if errorlevel 1 set "MODE=both"

echo.
"%CHOICE_EXE%" /C YN /M "Download COLMAP Windows CUDA build into third_party\\bin? (recommended)"
if errorlevel 2 set "FETCH_COLMAP=0"
if errorlevel 1 set "FETCH_COLMAP=1"

echo.
"%CHOICE_EXE%" /C YN /M "Download FFmpeg Windows build into third_party\\bin? (recommended)"
if errorlevel 2 set "FETCH_FFMPEG=0"
if errorlevel 1 set "FETCH_FFMPEG=1"

echo.
"%CHOICE_EXE%" /C YN /M "Choose output folder in Explorer?"
if errorlevel 2 exit /b 0
call :choose_out
exit /b %errorlevel%

:choose_out
for /f "usebackq delims=" %%I in (`
  "%POWERSHELL_EXE%" -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='Select output folder'; if($d.ShowDialog() -ne 'OK'){ exit 1 }; [Console]::WriteLine($d.SelectedPath)"
`) do set "OUT_DIR=%%I"
if not defined OUT_DIR exit /b 1
exit /b 0

:usage
echo.
echo Usage:
echo   build_windows.bat [--menu] [--fetch-colmap] [--fetch-ffmpeg] [--force] [--onedir^|--onefile] [--out PATH ^| --choose-out] [--pause]
echo   (default: builds both onedir + onefile)
echo.
echo Options:
echo   --menu           Guided prompts (good for beginners)
echo   --fetch-colmap   Download latest COLMAP Windows CUDA build into third_party\\bin
echo   --fetch-ffmpeg   Download latest FFmpeg Windows build into third_party\\bin
echo   --force          Redownload/overwrite when fetching binaries
echo   --onedir         Build folder-based app only
echo   --onefile        Build single all-in-one exe only
echo   --out PATH       Set output folder root (supports spaces, default: dist\\windows)
echo   --choose-out     Pick output folder via Windows folder dialog
echo   --pause          Keep the window open at the end
echo.
popd
exit /b 2
