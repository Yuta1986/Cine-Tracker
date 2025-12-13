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

echo Building with PyInstaller...
rem Put Windows builds under dist\windows\... to avoid confusion with Linux artifacts.
"%VENV_DIR%\\Scripts\\pyinstaller.exe" --clean --noconfirm --distpath "%DISTPATH%" packaging\\cinetracker.spec
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   %DISTPATH%\\%APP_NAME%\\%APP_NAME%.exe
echo.
echo Opening output folder...
explorer "%DISTPATH%\\%APP_NAME%" >nul 2>nul
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
echo   build_windows.bat [--fetch-colmap] [--force] [--distpath PATH ^| --choose-dist]
echo.
echo Options:
echo   --fetch-colmap   Download latest COLMAP Windows CUDA build into third_party\\bin
echo   --force          Redownload/overwrite when fetching COLMAP
echo   --distpath PATH  Set PyInstaller output folder (supports spaces)
echo   --choose-dist    Pick output folder via Windows folder dialog
echo.
popd
exit /b 2
