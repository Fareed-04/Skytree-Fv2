@echo off
title Panora - Sky Tree FINAL 2 (landscaping) - safe to re-run, it continues where it stopped
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set PY=--python "scripts\produce.py" --

rem  One-time clean of the renders made before the landscaping upgrade.
if not exist "out\final_v2.txt" (
  for %%k in (g1 g2 g3 m1 m2 m3 h1 h2 h3) do (
    if exist "out\web\p\%%k\day" del /q "out\web\p\%%k\day\*.*"
    if exist "out\web\p\%%k\mask" del /q "out\web\p\%%k\mask\*.*"
  )
  for %%d in (flyin explode\day stills orbit\dusk) do if exist "out\web\%%d" del /q "out\web\%%d\*.*"
  if exist "out\lookdev4" del /q "out\lookdev4\*.*"
  echo cleaned> "out\final_v2.txt"
)

echo  [1/7] Quick check renders (out\lookdev4)...
if not exist "out\lookdev4\front_ref.jpg" "%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes lookdev4

echo  [2/7] Terrace garden + rooftop garden 360s (day and night)...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes garden_panos

echo  [3/7] Floor masks for the nine paths...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes path_masks

echo  [4/7] Main path...
set ST_PATHS=m2
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

echo  [5/7] Fly-in to Residence 10-A...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes flyin

echo  [6/7] The other eight paths...
set ST_PATHS=g2,h2,m1,m3,g1,g3,h1,h3
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes paths

echo  [7/7] Explode, dusk orbit, stills...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" %PY% --passes explode_day
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" %PY% --no-slice --passes orbit_dusk,stills

echo.
echo  ALL DONE. Open Claude and say "renders finished".
pause
