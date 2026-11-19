@echo off
title Panora - PRODUCTION v2
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo  [1/4] Day orbit (unsliced scene)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes orbit_day
echo  [2/4] Explode animation (sliced scene)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes explode_day
echo  [3/4] Hero stills + balcony view...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes stills,view10
echo  [4/4] Dusk orbit...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes orbit_dusk
echo.
echo  Finished. You can close this window.
pause
