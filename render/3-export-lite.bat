@echo off
title Panora - light copy of the scene for analysis
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Making a light copy of scene\sky-tree.blend (about 5 minutes). The scene itself is not changed.
echo.
"%BLENDER%" -b --factory-startup "scene\sky-tree.blend" --python "scripts\export_lite.py"
echo.
echo  Finished. Tell Claude it is done. You can close this window.
pause
