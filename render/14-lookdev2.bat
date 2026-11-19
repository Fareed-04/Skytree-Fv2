@echo off
title Panora - LOOKDEV 2
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
if exist "out\lookdev2" del /q "out\lookdev2\*.jpg"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes lookdev2
echo.
echo  Finished. You can close this window.
pause
