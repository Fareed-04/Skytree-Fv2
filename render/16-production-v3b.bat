@echo off
title Panora - PRODUCTION v3b (no cars)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
for %%d in (orbit\day orbit\dusk explode\day flyin stills ground\day) do if exist "out\web\%%d" del /q "out\web\%%d\*.*"
echo  [1/3] Golden-hour orbit, eye-level orbit, fly-in...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes orbit_day,orbit_ground,flyin
echo  [2/3] Explode...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes explode_day
echo  [3/3] Dusk orbit and stills...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes orbit_dusk,stills
echo.
echo  Finished. You can close this window.
pause
