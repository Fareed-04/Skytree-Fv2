@echo off
title Panora - bedroom fly-through to the balcony (1.2 s clip)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b "assets\bk\bedroom\bedroom.blend" --python "scripts\interior_pano.py" -- bedroom --spot-only > "out\fly_bedroom_spot.log" 2>&1
"%BLENDER%" -b "assets\bk\bedroom\bedroom.blend" --python "scripts\interior_fly.py" -- bedroom 88 3.2 bedroom-view > "out\fly_bedroom.log" 2>&1
echo done> "out\fly_bedroom_done.txt"
