# PowerShell script to apply BNC TechDraw fix WITHOUT reinstalling
# RUN AS ADMINISTRATOR

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "BNC TechDraw Fix - Direct Patch (No Reinstall Needed)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Stop FreeCAD if running
Write-Host "Stopping FreeCAD if running..."
Get-Process FreeCAD* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Source and destination
$source = "D:\BNC-FreeCAD\Mod\BNCTechDraw\InitGui.py"
$dest = "C:\Program Files (x86)\BNC_CAD\Mod\BNCTechDraw\InitGui.py"

if (-not (Test-Path $source)) {
    Write-Host "ERROR: Source file not found: $source" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path "C:\Program Files (x86)\BNC_CAD\Mod\BNCTechDraw\")) {
    Write-Host "ERROR: BNC_CAD not installed at expected location" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Backup old file
Write-Host "Backing up old InitGui.py..."
Copy-Item $dest "$dest.backup" -Force -ErrorAction SilentlyContinue

# Copy new file
Write-Host "Copying fixed InitGui.py..."
try {
    Copy-Item $source $dest -Force
    Write-Host "SUCCESS! File replaced." -ForegroundColor Green
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "Make sure you ran this script AS ADMINISTRATOR" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Clear Python cache
Write-Host "Clearing Python cache..."
Get-ChildItem "C:\Program Files (x86)\BNC_CAD\" -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "C:\Program Files (x86)\BNC_CAD\" -Filter "*.pyc" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Clear user FreeCAD cache
Write-Host "Clearing FreeCAD user cache..."
Remove-Item "$env:LOCALAPPDATA\FreeCAD\Cache" -Recurse -Force -ErrorAction SilentlyContinue

# Verify
$info = Get-Item $dest
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "FIX APPLIED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "File: $($info.FullName)"
Write-Host "Size: $($info.Length) bytes"
Write-Host "Modified: $($info.LastWriteTime)"
Write-Host ""
Write-Host "Now launch BNC CAD and test the BNC TechDraw toolbar!" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
