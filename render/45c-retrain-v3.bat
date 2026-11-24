@echo off
title Restart v3 training with a better seed
cd /d "%~dp0"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='cmd.exe'\" | Where-Object { $_.CommandLine -like '*45-splat-v3*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
taskkill /f /im brush_app.exe >nul 2>&1
timeout /t 2 >nul
del /q "out\splat\train4\*.ply" 2>nul
start "" "%~dp045-splat-v3.bat"
