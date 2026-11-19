@echo off
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
"%BLENDER%" -b --factory-startup --python "scripts\pack_web.py"
