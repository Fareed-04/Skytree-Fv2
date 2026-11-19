@echo off
title Panora - Sky Tree: publish media to GitHub (Fareed-04/Skytree-Fv2)
cd /d "%~dp0"
set RENDER=%~dp0
set REPO=%~dp0..\skytree-Fv2
if not exist "out\site\media\p\paths.json" (
  echo  Run 40-prep-web.bat first.
  pause & exit /b 1
)
if not exist "%REPO%\.git" (
  echo  Downloading the website repo the first time - a browser window may ask you to sign in to GitHub...
  git clone https://github.com/Fareed-04/Skytree-Fv2.git "%REPO%"
  if errorlevel 1 ( echo  Download failed. Sign in with the GitHub account that has access to Fareed-04/Skytree-Fv2. & pause & exit /b 1 )
)
cd /d "%REPO%"
git pull --ff-only
git config user.name "Hassan Adil"
git config user.email "masterktwopointo@gmail.com"
echo  Copying the new media into the website...
robocopy "%RENDER%out\site\media" "public\skytree\media" /E /NFL /NDL /NJH /NP >nul
git add -A public
git commit -m "Fv2 media: 81-frame renders without the trees around the building" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01CzN9yJFvHza694gLt1EiEB"
echo  Uploading to GitHub (can take 10-30 minutes on a slow connection)...
git push origin main
if errorlevel 1 ( echo  Upload failed. Check the internet and run this file again: it continues safely. & pause & exit /b 1 )
echo.
echo  DONE. The new version is on https://github.com/Fareed-04/Skytree-Fv2
echo  If the repo is connected to Vercel, the website updates by itself in a few minutes.
pause
