@echo off
title Panora - Sky Tree splat v2b: ~800 extra close-up views + sharp training (all automatic, about 8 hours)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set BRUSH=tools\brush\brush_app.exe
set ST_SPLAT_V2=1
if exist "out\splat\train3\skytree3_80000.ply" goto convert
if exist "out\splat\v2b_capture_done.txt" goto train
echo  [1/3] Rendering the extra close-up views (existing views are kept; about 4 hours)...
set ST_SAMPLES=96
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes splat_data > "out\splat_capture_v2b.log" 2>&1
echo done> "out\splat\v2b_capture_done.txt"
:train
echo  [2/3] Training the sharp splat (80k steps; about 3-4 hours)...
if not exist "out\splat\train3" mkdir "out\splat\train3"
"%BRUSH%" "out\splat" --total-steps 80000 --max-splats 3500000 --refine-every 250 --growth-grad-threshold 0.000015 --growth-select-fraction 0.25 --growth-stop-iter 45000 --sh-degree 3 --max-resolution 1920 --eval-split-every 80 --eval-every 20000 --export-every 10000 --export-path "out\splat\train3" --export-name "skytree3_{iter}.ply" > "out\brush_train_v2b.log" 2>&1
if exist "out\splat\train3\skytree3_80000.ply" goto convert
echo  Training at full size failed, retrying at 1440 px...
"%BRUSH%" "out\splat" --total-steps 80000 --max-splats 3500000 --refine-every 250 --growth-grad-threshold 0.000015 --growth-select-fraction 0.25 --growth-stop-iter 45000 --sh-degree 3 --max-resolution 1440 --eval-split-every 80 --eval-every 20000 --export-every 10000 --export-path "out\splat\train3" --export-name "skytree3_{iter}.ply" > "out\brush_train_v2b_1440.log" 2>&1
:convert
echo  [3/3] Converting for the website: quick preview, phone and desktop versions...
set IN=out\splat\train3\skytree3_80000.ply
if not exist "%IN%" ( echo  Training did not finish - run this file again. & pause & exit /b 1 )
set OUTD=out\site\media\splat
if not exist "%OUTD%" mkdir "%OUTD%"
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 1 "%OUTD%\skytree.spz"
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 0 --decimate-adaptive 1500000 "out\splat\train3\mobile.ply"
call splat-transform -w "out\splat\train3\mobile.ply" "%OUTD%\skytree_m.spz"
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 0 --decimate-adaptive 300000 "out\splat\train3\preview.ply"
call splat-transform -w "out\splat\train3\preview.ply" "%OUTD%\skytree_p.spz"
copy /y "out\splat\sky.jpg" "%OUTD%\sky.jpg" >nul
echo {"file": "skytree.spz", "file_mobile": "skytree_m.spz", "file_preview": "skytree_p.spz", "offset": [-158.0, -5.5, 0.0], "sky_yaw_deg": 0.0, "map_bearing_deg": 0.0}> "%OUTD%\meta.json"
if not exist "out\sp" mkdir "out\sp"
del /q "out\sp\*.part*" 2>nul
for %%F in (skytree skytree_m skytree_p) do powershell -NoProfile -Command "$s=[IO.File]::OpenRead('%OUTD%\%%F.spz'); $buf=New-Object byte[] 15728640; $i=0; while(($r=$s.Read($buf,0,$buf.Length)) -gt 0){ $o=[IO.File]::Create(('out\sp\%%F.part{0}' -f $i)); $o.Write($buf,0,$r); $o.Close(); $i++ }; $s.Close()"
echo done> "out\splat\v2b_all_done.txt"
echo  SPLAT V2B DONE. Files in %OUTD%
pause
