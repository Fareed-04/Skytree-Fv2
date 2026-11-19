@echo off
title Panora - 9 PATHS (2560x1440, resumable)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes path_masks
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes paths
echo.
echo  Finished. You can close this window.
pause
