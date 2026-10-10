@echo off
setlocal
cd /d "%~dp0"
title Motion 2.0 - Create Video
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_SYSTEM\bootstrap.ps1" -Action run %*
exit /b %errorlevel%
