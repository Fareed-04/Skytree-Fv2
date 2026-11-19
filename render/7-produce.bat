@echo off
title Panora - production renders (orbit, floors, explode, stills)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Slicing the tower into floors, then rendering the web explorer frames into render\out\web
echo  (masks, day orbit, explode, dusk orbit, hero stills). About 2 hours. Safe to re-run: finished frames are skipped.
echo.
if exist "scene\sky-tree-v4.blend" (
  "%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py"
) else (
  "%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py"
)
echo.
echo  Finished. You can close this window.
pause
