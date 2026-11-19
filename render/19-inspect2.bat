@echo off
title Panora - INSPECT 2
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup "scene\sky-tree-v3.blend" --python "scripts\produce.py" -- --no-slice --passes inspect2
echo  Finished.
