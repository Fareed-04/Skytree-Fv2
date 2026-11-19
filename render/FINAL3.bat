@echo off
title Panora - Sky Tree FINAL 3 (final model) - safe to re-run, it continues where it stopped
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set PY=--python "scripts\produce.py" --

rem  One-time clean of everything rendered before the final model (81 frames per path now, so masks are redone too).
if not exist "out\final_v3.txt" (
  for %%k in (g1 g2 g3 m1 m2 m3 h1 h2 h3) do (
    if exist "out\web\p\%%k\day" del /q "out\web\p\%%k\day\*.*"
    if exist "out\web\p\%%k\mask" del /q "out\web\p\%%k\mask\*.*"
  )
  for %%d in (flyin explode\day stills orbit\dusk) do if exist "out\web\%%d" del /q "out\web\%%d\*.*"
  del /q "out\web\pano\terrace*.jpg" "out\web\pano\rooftop*.jpg" 2>nul
  echo cleaned> "out\final_v3.txt"
)

echo  [1/6] Terrace garden + rooftop garden 360s (day and night)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes garden_panos

echo  [2/6] Floor masks for the nine paths (81 each)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes path_masks

echo  [3/6] Main path (81 frames)...
set ST_SAMPLES=72
set ST_PATHS=m2
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

set ST_SAMPLES=
echo  [4/6] Fly-in to Residence 10-A...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes flyin

echo  [5/6] The other eight paths...
set ST_SAMPLES=72
set ST_PATHS=g2,h2,m1,m3,g1,g3,h1,h3
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

set ST_SAMPLES=
echo  [6/6] Explode, dusk orbit, stills...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes explode_day
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes orbit_dusk,stills

echo.
echo  ALL DONE. Open Claude and say "renders finished".
pause
