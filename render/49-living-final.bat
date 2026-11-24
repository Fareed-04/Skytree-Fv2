@echo off
title Panora - premium living room 360 (final) + fly-through to the balcony
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b "assets\bk\q_warm\q_warm.blend" --python "scripts\interior_pano.py" -- living2 --force > "out\pano_living2.log" 2>&1
"%BLENDER%" -b "assets\bk\q_warm\q_warm.blend" --python "scripts\interior_fly.py" -- living2 115 3.0 living2-view > "out\fly_living2.log" 2>&1
echo done> "out\living2_done.txt"
