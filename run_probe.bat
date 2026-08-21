@echo off
rem iPhone home screen probe (read-only by default).
rem   run_probe.bat              read only, writes nothing to the device
rem   run_probe.bat --roundtrip  identity round-trip safety test (asks first)
rem
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat with the system codepage,
rem so UTF-8 Korean comments get mangled into bogus commands.
rem This window's title is intentionally left untouched.

setlocal
set "PYTHONPATH=%~dp0src"
"%~dp0.venv\Scripts\python.exe" -m ipsm.probe %*
echo.
pause
