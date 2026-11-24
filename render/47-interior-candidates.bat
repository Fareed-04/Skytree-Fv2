@echo off
title Panora - premium interior candidates: download + quick 360 previews
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup --python "scripts\fetch_blenderkit.py" -- --manifest interior_v2.json > "out\interior_v2_fetch.log" 2>&1
for %%R in (q_lux q_warm q_open q_haven) do (
  "%BLENDER%" -b "assets\bk\%%R\%%R.blend" --python "scripts\interior_pano.py" -- %%R --quick > "out\interior_%%R.log" 2>&1
)
echo done> "out\interior_v2_done.txt"
