@echo off
title Panora - Sky Tree FINAL renders (safe to re-run: it continues where it stopped)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set PY=--python "scripts\produce.py" --

rem  One-time clean of renders made before the site upgrade (wall, parking, signage, lighting).
if not exist "out\final_v1.txt" (
  for %%d in (flyin explode\day stills orbit\dusk) do if exist "out\web\%%d" del /q "out\web\%%d\*.*"
  del /q "out\web\pano\view*.jpg" 2>nul
  echo cleaned> "out\final_v1.txt"
)

echo  [1/6] Tour 360s: living + bedroom in morning / sunset / night, balcony view and Pine Avenue...
for %%R in (living bedroom) do "%BLENDER%" -b "assets\bk\%%R\%%R.blend" --python "scripts\interior_pano.py" -- %%R --lights
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes view10

echo  [2/6] Floor masks for all nine camera paths...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes path_masks

echo  [3/6] Main path (mid height, mid distance) at 2560 x 1440...
set ST_PATHS=m2
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

echo  [4/6] Fly-in to Residence 10-A (starts from the main path)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes flyin

echo  [5/6] The other eight paths...
set ST_PATHS=g2,h2,m1,m3,g1,g3,h1,h3
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

echo  [6/6] Explode, dusk orbit and stills...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes explode_day
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes orbit_dusk,stills

echo.
echo  ALL DONE. Open Claude and say "renders finished".
pause
