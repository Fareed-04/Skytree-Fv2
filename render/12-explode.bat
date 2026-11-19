@echo off
title Panora - EXPLODE
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
if exist "out\web\explode\day" del /q "out\web\explode\day\*.jpg"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes explode_day
echo.
echo  Finished. You can close this window.
pause
