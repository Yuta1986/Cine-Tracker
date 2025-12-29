@echo off
setlocal EnableExtensions

rem Non-interactive Windows build (no menu).
rem Recommended default: fetch COLMAP+FFmpeg and build both outputs.
rem If you want to override behavior, pass flags through (e.g. --onedir, --onefile, --out).

pushd "%~dp0"
call build_windows.bat --fetch-colmap --fetch-ffmpeg --pause %*
set "EC=%ERRORLEVEL%"
popd

exit /b %EC%

