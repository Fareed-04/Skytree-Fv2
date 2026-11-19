@echo off
title Panora - look-dev (3 review renders)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup "scene\sky-tree-v2.blend" --python "scripts\lookdev.py" -- --only front_day,aerial_day,corner_day
echo.
echo  Finished. You can close this window.
pause
