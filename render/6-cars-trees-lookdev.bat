@echo off
title Panora - download cars, palms and trees (BlenderKit, free)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Downloading 23 free BlenderKit models (cars, bus, palms, trees, shrubs, flowers) - about 700 MB.
echo.
"%BLENDER%" -b --factory-startup --python "scripts\fetch_blenderkit.py"
echo.
echo  Now running the look-dev with the new models (20-40 minutes)...
echo.
"%BLENDER%" -b --factory-startup "scene\sky-tree-v2.blend" --python "scripts\lookdev.py"
echo.
echo  Finished. Tell Claude it is done. You can close this window.
pause
