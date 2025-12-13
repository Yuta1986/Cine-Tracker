@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Cine-Tracker Windows build helper (PyInstaller).
rem Produces: dist\CineTracker\CineTracker.exe

pushd "%~dp0"

set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

set "FETCH_COLMAP=0"
set "FORCE=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--fetch-colmap" ( set "FETCH_COLMAP=1" & shift & goto parse_args )
if /I "%~1"=="--force" ( set "FORCE=1" & shift & goto parse_args )
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

echo Building with PyInstaller...
rem Put Windows builds under dist\windows\... to avoid confusion with Linux artifacts.
"%VENV_DIR%\\Scripts\\pyinstaller.exe" --clean --noconfirm --distpath "dist\\windows" packaging\\cinetracker.spec
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   dist\\windows\\Windows_CineTracker\\Windows_CineTracker.exe
echo.
popd
exit /b 0

:usage
echo.
echo Usage:
echo   build_windows.bat [--fetch-colmap] [--force]
echo.
echo Options:
echo   --fetch-colmap   Download latest COLMAP Windows CUDA build into third_party\\bin
echo   --force          Redownload/overwrite when fetching COLMAP
echo.
popd
exit /b 2
