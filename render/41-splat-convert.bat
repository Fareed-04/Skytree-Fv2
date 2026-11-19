@echo off
setlocal enabledelayedexpansion
title Panora - Sky Tree: convert the trained splat for the website
cd /d "%~dp0"
set IN=out\splat\train\skytree_30000.ply
set OUTD=out\site\media\splat
if not exist "%IN%" (
  echo  The splat training is not finished yet: %IN% does not exist.
  echo  Wait until the training window says SPLAT TRAINING DONE, then run this again.
  pause & exit /b 1
)
if not exist "%OUTD%" mkdir "%OUTD%"
rem  Keeps only splats within 170 m of the tower (removes junk far away) and drops broken ones.
rem  GitHub refuses files over 100 MB, so it lowers the colour detail level 3, then 2, 1, 0 until the file is under 95 MB.
for %%h in (3 2 1 0) do (
  echo  Converting with colour detail level %%h ...
  call splat-transform -w "%IN%" -N -S 0,0,0,170 -H %%h "%OUTD%\skytree.spz"
  if errorlevel 1 ( echo  Conversion failed. Is Node.js installed? Run: npm install -g @playcanvas/splat-transform & pause & exit /b 1 )
  for %%s in ("%OUTD%\skytree.spz") do set SZ=%%~zs
  echo  size: !SZ! bytes
  if !SZ! LSS 99614720 goto ok
)
echo  Even the smallest version is over 95 MB. Ask for help: the splat needs to be decimated.
pause & exit /b 1
:ok
copy /y "out\splat\sky.jpg" "%OUTD%\sky.jpg" >nul
copy /y "out\splat\meta.json" "%OUTD%\meta.json" >nul
echo.
echo  DONE. Splat files are in: render\%OUTD%
echo  Next: 42-publish-github.bat
pause
