@echo off
title Panora - premium living room 360 (retry)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
set ST_PANO_SAMPLES=256
"%BLENDER%" -b "assets\bk\q_warm\q_warm.blend" --python "scripts\interior_pano.py" -- living2 --force > "out\pano_living2b.log" 2>&1
if exist "out\web\pano\living2.jpg" goto ok
set ST_PANO_RES=3072
"%BLENDER%" -b "assets\bk\q_warm\q_warm.blend" --python "scripts\interior_pano.py" -- living2 --force > "out\pano_living2c.log" 2>&1
:ok
echo done> "out\living2_pano_done.txt"
