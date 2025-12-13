@echo off
rem Beginner-friendly guided build (opens prompts and pauses at the end).
pushd "%~dp0"
call build_windows.bat --menu %*
popd
