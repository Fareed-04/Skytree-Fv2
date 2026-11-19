@echo off
title Panora - Sky Tree: convert the finished renders into website media
cd /d "%~dp0"
if not exist "out\web\stills\corner_night.jpg" (
  echo  The final render is not finished yet. Wait until FINAL4 says ALL DONE, then run this again.
  pause & exit /b 1
)
set BDIR=%~dp0..\..\panora-render\blender\blender-5.2.3-windows-x64
set PYEXE=
for /d %%v in ("%BDIR%\5.*") do if exist "%%v\python\bin\python.exe" set "PYEXE=%%v\python\bin\python.exe"
if not defined PYEXE (
  echo  Could not find Blender's Python inside %BDIR%
  pause & exit /b 1
)
echo  [1/2] Installing the image tools (first time only, needs internet)...
"%PYEXE%" -m ensurepip >nul 2>&1
"%PYEXE%" -m pip install --quiet --disable-pip-version-check pillow opencv-python-headless imageio-ffmpeg
if errorlevel 1 (
  echo  Installing the image tools failed. Check the internet connection and run this file again.
  pause & exit /b 1
)
echo  [2/2] Converting frames to WebP, encoding the fly-in video, copying 360s (about 20-40 minutes)...
"%PYEXE%" "scripts\prep_media.py" "out\web" "out\site\media"
if errorlevel 1 (
  echo  Something went wrong. Take a photo of this window and send it to whoever helps you.
  pause & exit /b 1
)
echo.
echo  DONE. Website media is in: render\out\site\media
echo  Next: 42-publish-github.bat  (or 41-splat-convert.bat first, if the splat training is finished)
pause
