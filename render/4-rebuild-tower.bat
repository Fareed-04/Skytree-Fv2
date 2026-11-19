@echo off
title Panora - rebuild the missing tower floors
cd /d "%~dp0"
set BLENDER=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64\blender.exe
echo.
echo  Adding the 5 missing tower floors and moving the pavilions onto the podium roof.
echo  Saves scene\sky-tree-v2.blend (the original is kept) and renders 4 previews. About 10-20 minutes.
echo.
"%BLENDER%" -b --factory-startup "scene\sky-tree.blend" --python "scripts\rebuild_tower.py"
echo.
echo  Finished. Tell Claude it is done. You can close this window.
pause
