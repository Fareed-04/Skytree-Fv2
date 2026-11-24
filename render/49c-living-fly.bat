@echo off
title Panora - living room fly-through (into the curtains)
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
:wait
if not exist "out\living2_pano_done.txt" ( timeout /t 15 >nul & goto wait )
"%BLENDER%" -b "assets\bk\q_warm\q_warm.blend" --python "scripts\interior_fly.py" -- living2 84 3.4 living2-curtain > "out\fly_living2c.log" 2>&1
echo done> "out\living2_fly2_done.txt"
