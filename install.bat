@echo off
rem Wrapper so install.ps1 can be launched from cmd.exe.
rem Typing ".\install.ps1" in cmd does NOT run PowerShell - it opens the file
rem with whatever is associated with .ps1 (usually Notepad), so nothing installs.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
