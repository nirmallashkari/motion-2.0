@echo off
setlocal
cd /d "%~dp0"
title Motion 2.0 - Reset Project
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_SYSTEM\bootstrap.ps1" -Action reset %*
exit /b %errorlevel%
