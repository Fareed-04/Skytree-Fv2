@echo off
title Panora - Sky Tree: restart everything after a power cut / reboot
cd /d "%~dp0"
echo.
echo  Sky Tree - restart after a power cut
echo  ====================================
echo  This checks what is already finished and restarts only what is not.
echo  Nothing finished is lost: every step continues where it stopped.
echo.

rem  1) Remove broken (0 KB) images left behind if the power went off while a file was being saved.
for /r "out\web" %%f in (*.jpg *.png) do if %%~zf==0 (echo  removing broken file %%f & del "%%f")
if exist "out\splat\images" for %%f in ("out\splat\images\*.png") do if %%~zf==0 (echo  removing broken file %%f & del "%%f")

rem  2) Final render (FINAL4). Its last picture is stills\corner_night.jpg.
if exist "out\web\stills\corner_night.jpg" (
  echo  [done]     Final render
) else (
  echo  [restart]  Final render  - FINAL4.bat
  start "" "%~dp0FINAL4.bat"
)

rem  3) Splat capture. It writes out\splat\meta.json when it is complete. It waits for the final render by itself.
if exist "out\splat\meta.json" (
  echo  [done]     Splat capture
) else (
  echo  [restart]  Splat capture - 32-splat-capture.bat
  start "" "%~dp032-splat-capture.bat"
)

rem  4) Splat training. It waits for the capture by itself. Training cannot resume: an interrupted run starts again from 0.
if exist "out\splat\train\skytree_30000.ply" (
  echo  [done]     Splat training
) else (
  echo  [restart]  Splat training - 35-splat-train.bat
  start "" "%~dp035-splat-train.bat"
)

echo.
echo  When all three say [done], run 40-prep-web.bat, then 41-splat-convert.bat, then 42-publish-github.bat.
echo  You can close this small window now. Leave the other windows open.
pause
