@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Cine-Tracker Windows build helper (PyInstaller).
rem Produces: dist\CineTracker\CineTracker.exe

pushd "%~dp0"

set "VENV_DIR=.venv-win"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

set "FETCH_COLMAP=0"
set "FORCE=0"
set "DISTPATH=dist\\windows"
set "BUILD_ONEDIR=1"
set "BUILD_ONEFILE=1"

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
if /I "%~1"=="--force" ( set "FORCE=1" & shift & goto parse_args )
if /I "%~1"=="--onedir" ( set "BUILD_ONEDIR=1" & set "BUILD_ONEFILE=0" & shift & goto parse_args )
if /I "%~1"=="--onefile" ( set "BUILD_ONEDIR=0" & set "BUILD_ONEFILE=1" & shift & goto parse_args )
if /I "%~1"=="--both" ( set "BUILD_ONEDIR=1" & set "BUILD_ONEFILE=1" & shift & goto parse_args )
if /I "%~1"=="--distpath" (
  if "%~2"=="" (
    echo Missing value for --distpath
    goto usage
  )
  set "DISTPATH=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--choose-dist" (
  call :choose_dist
  if errorlevel 1 exit /b 1
  shift
  goto parse_args
)
if /I "%~1"=="--help" goto usage
if /I "%~1"=="/?" goto usage
echo Unknown argument: %~1
goto usage

:args_done

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.10+ and try again.
  exit /b 1
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

if "%FETCH_COLMAP%"=="1" (
  echo Fetching COLMAP Windows CUDA binary into third_party\bin ...
  if "%FORCE%"=="1" (
    "%PY%" scripts\fetch_colmap_windows_cuda.py --force
  ) else (
    "%PY%" scripts\fetch_colmap_windows_cuda.py
  )
  if errorlevel 1 exit /b 1
)

if not exist "third_party\\bin\\colmap.exe" (
  echo WARN: third_party\bin\colmap.exe not found. It will NOT be bundled.
  echo       Use: build_windows.bat --fetch-colmap
)
if not exist "third_party\\bin\\ffmpeg.exe" (
  echo WARN: third_party\bin\ffmpeg.exe not found. It will NOT be bundled.
)
if not exist "third_party\\bin\\ffprobe.exe" (
  echo WARN: third_party\bin\ffprobe.exe not found. It will NOT be bundled.
)

set "APP_NAME=Windows_CineTracker"
if defined CINETRACKER_APP_NAME set "APP_NAME=%CINETRACKER_APP_NAME%"

set "PYI=%VENV_DIR%\\Scripts\\pyinstaller.exe"

if "%BUILD_ONEDIR%"=="1" (
  echo Building (onedir) with PyInstaller...
  "%PYI%" --clean --noconfirm --distpath "%DISTPATH%\\onedir" --workpath "build\\pyinstaller\\onedir" packaging\\cinetracker.spec
  if errorlevel 1 exit /b 1
)

if "%BUILD_ONEFILE%"=="1" (
  echo Building (onefile) with PyInstaller...
  "%PYI%" --clean --noconfirm --distpath "%DISTPATH%\\onefile" --workpath "build\\pyinstaller\\onefile" packaging\\cinetracker_onefile.spec
  if errorlevel 1 exit /b 1
)

echo.
echo Build complete:
if "%BUILD_ONEDIR%"=="1" echo   Onedir:  %DISTPATH%\\onedir\\%APP_NAME%\\%APP_NAME%.exe
if "%BUILD_ONEFILE%"=="1" echo   Onefile: %DISTPATH%\\onefile\\%APP_NAME%.exe
echo.
echo Opening output folder...
explorer "%DISTPATH%" >nul 2>nul
echo.
popd
exit /b 0

:choose_dist
for /f "usebackq delims=" %%I in (`
  powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='Select output folder for dist'; if($d.ShowDialog() -ne 'OK'){ exit 1 }; [Console]::WriteLine($d.SelectedPath)"
`) do set "DISTPATH=%%I"
if not defined DISTPATH exit /b 1
exit /b 0

:usage
echo.
echo Usage:
echo   build_windows.bat [--fetch-colmap] [--force] [--onedir^|--onefile^|--both] [--distpath PATH ^| --choose-dist]
echo.
echo Options:
echo   --fetch-colmap   Download latest COLMAP Windows CUDA build into third_party\\bin
echo   --force          Redownload/overwrite when fetching COLMAP
echo   --onedir         Build folder-based app (default: builds both)
echo   --onefile        Build single all-in-one exe (default: builds both)
echo   --both           Build both outputs (default)
echo   --distpath PATH  Set PyInstaller output folder (supports spaces)
echo   --choose-dist    Pick output folder via Windows folder dialog
echo.
popd
exit /b 2
