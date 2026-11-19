@echo off
title Panora - tour panoramas with lighting variants
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
for %%R in (living bedroom) do (
  "%BLENDER%" -b "assets\bk\%%R\%%R.blend" --python "scripts\interior_pano.py" -- %%R --lights
)
if exist "out\web\pano\view.jpg" del /q "out\web\pano\view*.jpg"
"%BLENDER%" -b --factory-startup "scene\sky-tree-v4.blend" --python "scripts\produce.py" -- --passes view10
echo.
echo  Finished. You can close this window.
pause
