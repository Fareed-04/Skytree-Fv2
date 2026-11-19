@echo off
title Panora - downloads for renders and splats
cd /d "%~dp0"
echo.
echo  Step 1/2: system check + tools (ffmpeg, splat-transform)
echo  ---------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\fetch_tools.ps1"
echo.
echo  Step 2/2: free CC0 assets from Poly Haven (skies, textures, trees) ~3 GB
echo  ------------------------------------------------------------------------
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup --python "scripts\fetch_assets.py"
echo.
echo  All done. You can close this window. Results: render\system-report.txt and render\assets\download-log.txt
pause
