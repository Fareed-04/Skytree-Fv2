@echo off
title Panora - LOOKDEV 3
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
if exist "out\lookdev3" del /q "out\lookdev3\*.*"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes lookdev3
echo.
echo  Finished. You can close this window.
pause
