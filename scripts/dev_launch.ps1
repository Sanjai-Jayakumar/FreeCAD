<#
.SYNOPSIS
    Sync BNC files then launch FreeCAD dev build in one step.

.PARAMETER Target
    FreeCAD installation to sync into and launch.
    Default: C:\BNC-CAD-Output

.EXAMPLE
    .\scripts\dev_launch.ps1
#>
param(
    [string]$Target = "C:\BNC-CAD-Output"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$syncScript = Join-Path $scriptDir "dev_sync.ps1"

# Sync files
& $syncScript -Target $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Launch FreeCAD
$exe = Join-Path $Target "bin\FreeCAD.exe"
if (-not (Test-Path $exe)) {
    Write-Host "FreeCAD not found at: $exe" -ForegroundColor Red
    Write-Host "Run build_bnc.ps1 first." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  Launching $exe ..." -ForegroundColor Cyan
Start-Process $exe
