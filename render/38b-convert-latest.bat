@echo off
title Panora - Sky Tree splat v2b: publish the newest finished checkpoint (no training)
cd /d "%~dp0"
taskkill /f /im brush_app.exe >nul 2>&1
:convert
set IN=
for %%N in (50000 45000 40000 35000 30000 25000 20000) do if not defined IN if exist "out\splat\train3\skytree3_%%N.ply" set IN=out\splat\train3\skytree3_%%N.ply
if not defined IN ( echo  No usable checkpoint yet - run this file again. & pause & exit /b 1 )
echo  [2/2] Converting %IN% for the website...
set OUTD=out\site\media\splat
if not exist "%OUTD%" mkdir "%OUTD%"
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 1 "%OUTD%\skytree.spz"
call splat-transform -w "%IN%" -N -S 0,0,0,170 -H 0 "out\splat\train3\full_h0.ply"
if not exist "out\sp" mkdir "out\sp"
del /q "out\sp\*.part*" 2>nul
for %%F in (skytree) do powershell -NoProfile -Command "$s=[IO.File]::OpenRead('%OUTD%\%%F.spz'); $buf=New-Object byte[] 15728640; $i=0; while(($r=$s.Read($buf,0,$buf.Length)) -gt 0){ $o=[IO.File]::Create(('out\sp\%%F.part{0}' -f $i)); $o.Write($buf,0,$r); $o.Close(); $i++ }; $s.Close()"
echo %IN%> "out\splat\v2b_all_done.txt"
echo  DONE. Claude will pick it up from here.
