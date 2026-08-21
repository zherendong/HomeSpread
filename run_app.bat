@echo off
rem iPhone home screen manager - desktop app.
rem Logs and diagnostics go to logspp_<timestamp>.log
rem NOTE: keep this file ASCII-only. cmd.exe reads .bat with the system codepage.
rem This window's title is intentionally left untouched.

setlocal
set "PYTHONPATH=%~dp0src"
"%~dp0.venv\Scripts\python.exe" -m ipsm.app %*
