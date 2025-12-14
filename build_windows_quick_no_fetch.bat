@echo off
setlocal EnableExtensions

rem Non-interactive Windows build (no menu, no downloads).
rem Use this if downloads are blocked or you already populated third_party\bin yourself.

pushd "%~dp0"
call build_windows.bat --pause %*
set "EC=%ERRORLEVEL%"
popd

exit /b %EC%

