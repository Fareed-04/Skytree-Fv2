@echo off
title Panora - FINAL: look-dev + production renders
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo  [1/2] Building the final scene (sky-tree-v3) + 2 check renders...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v2.blend" --python "scripts\lookdev.py" -- --only front_day,corner_day
if exist "scene\sky-tree-v4.blend" del "scene\sky-tree-v4.blend"
echo  [2/2] Production renders into render\out\web (about 2 hours)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py"
echo.
echo  Finished. You can close this window.
pause
