@echo off
setlocal EnableExtensions

rem Deprecated: legacy "easy" wrapper used an interactive menu.
rem Use the non-interactive shortcut for best reliability.

echo NOTE: build_windows_easy.bat is deprecated.
echo       Running build_windows_quick.bat instead (no interactive prompts).
echo.

pushd "%~dp0"
call build_windows_quick.bat %*
set "EC=%ERRORLEVEL%"
popd

exit /b %EC%

