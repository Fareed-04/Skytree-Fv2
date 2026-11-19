@echo off
title Panora - exterior look-dev (materials, sky, landscape, renders)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Applying stone, slate, glass and gold materials, sky, trees, road and lights to scene\sky-tree-v2.blend
echo  Saves scene\sky-tree-v3.blend and renders 7 images (day, dusk, night). About 20-40 minutes.
echo.
"%BLENDER%" -b --factory-startup "scene\sky-tree-v2.blend" --python "scripts\lookdev.py"
echo.
echo  Finished. Tell Claude it is done. You can close this window.
pause
