@echo off
title Panora - Sky Tree splat v3: facade close-ups + sharpest training (safe to re-run after a power cut)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set BRUSH=tools\brush\brush_app.exe
taskkill /f /im brush_app.exe >nul 2>&1
if exist "out\splat\train4\skytree4_40000.ply" goto convert
if exist "out\splat\v3_capture_done.txt" goto train
echo  [1/3] Rendering about 190 facade close-ups (existing views are kept; about 60 minutes)...
set ST_SPLAT_V2=1
set ST_SPLAT_V3=1
set ST_SAMPLES=96
set ST_SPARSE_SECS=500
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes splat_data > "out\splat_capture_v3.log" 2>&1
echo done> "out\splat\v3_capture_done.txt"
:train
echo  [2/3] Training the v3 splat (60k steps, up to 4.5M splats; about 65 min)...
if not exist "out\splat\train4" mkdir "out\splat\train4"
"%BRUSH%" "out\splat" --total-steps 40000 --max-splats 4000000 --refine-every 200 --growth-grad-threshold 0.000012 --growth-select-fraction 0.25 --growth-stop-iter 28000 --sh-degree 3 --max-resolution 1920 --eval-split-every 100 --eval-every 30000 --export-every 10000 --export-path "out\splat\train4" --export-name "skytree4_{iter}.ply" > "out\brush_train_v3.log" 2>&1
:convert
set IN=
for %%N in (40000 30000 20000) do if not defined IN if exist "out\splat\train4\skytree4_%%N.ply" set IN=out\splat\train4\skytree4_%%N.ply
if not defined IN ( echo  No usable checkpoint yet - run this file again. & pause & exit /b 1 )
echo  [3/3] Converting %IN% for the website...
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 1 "out\splat\train4\skytree_v3.spz"
if not exist "out\sp" mkdir "out\sp"
del /q "out\sp\v3.part*" 2>nul
powershell -NoProfile -Command "$s=[IO.File]::OpenRead('out\splat\train4\skytree_v3.spz'); $buf=New-Object byte[] 15728640; $i=0; while(($r=$s.Read($buf,0,$buf.Length)) -gt 0){ $o=[IO.File]::Create(('out\sp\v3.part{0}' -f $i)); $o.Write($buf,0,$r); $o.Close(); $i++ }; $s.Close()"
echo %IN%> "out\splat\v3_all_done.txt"
echo  DONE. Claude will pick it up from here.
