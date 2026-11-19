@echo off
title Panora - unit 10-A tour panoramas
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo  Downloading the two interior scenes (about 260 MB)...
"%BLENDER%" -b --factory-startup --python "scripts\fetch_blenderkit.py" -- --manifest interior_assets.json
for %%R in (living bedroom) do (
  echo  Rendering %%R panorama...
  "%BLENDER%" -b "assets\bk\%%R\%%R.blend" --python "scripts\interior_pano.py" -- %%R
)
echo  Rendering the 10th-floor balcony view...
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes view10
echo.
echo  Finished. You can close this window.
pause
