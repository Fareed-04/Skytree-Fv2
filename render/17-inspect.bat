@echo off
title Panora - INSPECT
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
if exist "out\inspect" del /q "out\inspect\*.*"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes inspect
echo.
echo  Finished. You can close this window.
pause
