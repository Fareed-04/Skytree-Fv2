@echo off
title Panora - build the Blender render scene
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Building the Blender scene from the 3ds Max export (render\from-max\parts)
echo  This imports ~5 GB of geometry and renders 5 previews. Expect 15-40 minutes.
echo  Progress is also written to render\scene\build-log.txt
echo.
"%BLENDER%" -b --factory-startup --python "scripts\build_scene.py"
echo.
echo  Finished. Tell Claude it's done. You can close this window.
pause
