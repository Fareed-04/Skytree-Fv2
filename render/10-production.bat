@echo off
title Panora - PRODUCTION (orbits, stills, explode, tour)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo  [1/4] Day orbit, hero stills, dusk orbit (unsliced scene)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes orbit_day,stills,orbit_dusk
echo  [2/4] Explode animation (sliced scene)...
if exist "scene\sky-tree-v4.blend" del "scene\sky-tree-v4.blend"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --passes explode_day
echo  [3/4] Interior scenes for the 10-A tour...
"%BLENDER%" -b --factory-startup --python "scripts\fetch_blenderkit.py" -- --manifest interior_assets.json
for %%R in (living bedroom) do "%BLENDER%" -b "assets\bk\%%R\%%R.blend" --python "scripts\interior_pano.py" -- %%R
echo  [4/4] 10th-floor balcony view...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes view10
echo.
echo  Finished. You can close this window.
pause
