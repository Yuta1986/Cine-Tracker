@echo off
setlocal EnableExtensions

rem Beginner-friendly guided build (opens prompts and pauses at the end).
rem This wrapper *also* pauses on failure so errors don't flash and disappear.

pushd "%~dp0"
call build_windows.bat --menu %*
set "EC=%ERRORLEVEL%"
popd

if not "%EC%"=="0" (
  echo.
  echo Build failed with exit code %EC%.
  echo If the window closed immediately before, run from a terminal so you can read errors:
  echo   - CMD:        build_windows_easy.bat
  echo   - PowerShell: .\\build_windows_easy.bat
  echo.
  echo If the guided menu is the problem in your environment, try the non-interactive shortcut:
  echo   build_windows_quick.bat
)

pause
exit /b %EC%
