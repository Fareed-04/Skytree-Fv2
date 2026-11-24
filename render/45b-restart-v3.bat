@echo off
title Restart v3 capture (lighter set)
cd /d "%~dp0"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='cmd.exe'\" | Where-Object { $_.CommandLine -like '*45-splat-v3*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='blender.exe'\" | Where-Object { $_.CommandLine -like '*splat_data*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
del /q "out\splat\v3_capture_done.txt" 2>nul
timeout /t 2 >nul
start "" "%~dp045-splat-v3.bat"
