@echo off
title Panora - search BlenderKit interiors
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup --python "scripts\bk_search.py" > "out\bk_search.log" 2>&1
echo done> "out\bk_search_done.txt"
