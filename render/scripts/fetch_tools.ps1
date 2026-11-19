# Panora render kit: tools + system check. Run via render\1-setup-downloads.bat
$ErrorActionPreference = "Continue"
$Root   = Split-Path -Parent $PSScriptRoot                       # ...\sky-tree-tower\render
$Tools  = Join-Path (Split-Path -Parent (Split-Path -Parent $Root)) "tools"   # C:\Projects\tools
$Report = Join-Path $Root "system-report.txt"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null

function Say($m) { Write-Host $m; Add-Content -Path $Report -Value $m }
Set-Content -Path $Report -Value ("Panora system report  " + (Get-Date -Format "yyyy-MM-dd HH:mm"))

# ---- system
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Say ("CPU: {0} | {1} cores / {2} threads" -f $cpu.Name.Trim(), $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
Say ("RAM: {0} GB" -f $ram)
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
  Say ("Disk {0} free {1} GB of {2} GB" -f $_.DeviceID, [math]::Round($_.FreeSpace/1GB), [math]::Round($_.Size/1GB)) }
try { Say ((& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader) -join "; ") } catch { Say "nvidia-smi not found" }

# ---- installed software we care about
$apps = Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*, HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*, HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName -match "3ds Max|Corona|V-Ray|Chaos|D5|Postshot|Blender|Unreal|Twinmotion|Lumion|Enscape|Python|Node|Git" } |
  Sort-Object DisplayName -Unique
Say "Installed:"
foreach ($a in $apps) { Say ("  {0}  {1}" -f $a.DisplayName, $a.DisplayVersion) }

# ---- ffmpeg (AV1 / HEVC / H.264 encoders incl. NVENC) from BtbN builds on GitHub
$ff = Join-Path $Tools "ffmpeg"
if (-not (Test-Path (Join-Path $ff "bin\ffmpeg.exe"))) {
  Say "Downloading ffmpeg..."
  $zip = Join-Path $Tools "ffmpeg.zip"
  & curl.exe -L --retry 3 -o $zip "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
  Expand-Archive -Path $zip -DestinationPath $Tools -Force
  $dir = Get-ChildItem $Tools -Directory | Where-Object { $_.Name -like "ffmpeg-master*" } | Select-Object -First 1
  if ($dir) { if (Test-Path $ff) { Remove-Item $ff -Recurse -Force }; Rename-Item $dir.FullName "ffmpeg" }
  Remove-Item $zip -ErrorAction SilentlyContinue
}
if (Test-Path (Join-Path $ff "bin\ffmpeg.exe")) { Say ("ffmpeg: " + ((& (Join-Path $ff "bin\ffmpeg.exe") -hide_banner -encoders 2>$null | Select-String "libsvtav1|hevc_nvenc|av1_nvenc|libx264" | ForEach-Object { ($_ -split "\s+")[2] }) -join ", ")) } else { Say "ffmpeg: FAILED" }

# ---- SplatTransform (PlayCanvas) for SOG/SPZ conversion of trained splats
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
  Say "Installing @playcanvas/splat-transform..."
  & npm install -g @playcanvas/splat-transform 2>&1 | Out-Null
  $st = Get-Command splat-transform -ErrorAction SilentlyContinue
  Say ("splat-transform: " + ($(if ($st) { "installed" } else { "FAILED (run: npm install -g @playcanvas/splat-transform)" })))
} else { Say "npm not found: install Node.js LTS from nodejs.org" }

# ---- Postshot (splat trainer, already installed on this PC) - report version + CLI path
$ps = Get-ChildItem "C:\Program Files\Jawset Postshot" -Recurse -Filter "postshot-cli.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
Say ("Postshot CLI: " + ($(if ($ps) { $ps.FullName } else { "not found" })))

Say "Done."
