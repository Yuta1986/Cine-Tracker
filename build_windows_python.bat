@echo off
setlocal EnableExtensions

rem Alternative Windows build entrypoint that avoids complex batch logic.
rem Uses Python to drive venv/pip/fetch/PyInstaller steps.

pushd "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.10+ and try again.
  popd
  exit /b 1
)

python scripts\build_windows.py %*
set "EC=%ERRORLEVEL%"
popd

pause
exit /b %EC%

