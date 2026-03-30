<#
.SYNOPSIS
    Apply BNC CAD overlay files to a FreeCAD source or binary directory.

.DESCRIPTION
    Copies all files from the overlay/ folder into the target FreeCAD
    installation or source tree, preserving the correct Mod/ and Macro/
    directory structure.

.PARAMETER FreeCADTarget
    Path to the FreeCAD Mod parent directory (e.g. C:\BNC-CAD-Output or
    D:\freecad-source\src). Script will write to $FreeCADTarget\Mod and
    $FreeCADTarget\Macro.

.PARAMETER DryRun
    Print what would be copied without actually copying.

.EXAMPLE
    # Apply to a compiled FreeCAD output
    .\scripts\apply_bnc.ps1 -FreeCADTarget "C:\BNC-CAD-Output"

    # Apply to a conda binary distribution
    .\scripts\apply_bnc.ps1 -FreeCADTarget "C:\BNC_CAD_1.0.2"

    # Preview only
    .\scripts\apply_bnc.ps1 -FreeCADTarget "C:\BNC-CAD-Output" -DryRun
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$FreeCADTarget,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$overlayDir = Join-Path (Split-Path -Parent $scriptDir) "overlay"
$brandingDir = Join-Path (Split-Path -Parent $scriptDir) "branding"

if (-not (Test-Path $overlayDir)) {
    Write-Error "overlay/ directory not found at: $overlayDir"
    exit 1
}

function Copy-Overlay {
    param([string]$Src, [string]$Dst)
    if ($DryRun) {
        Write-Host "[DRY-RUN] Would copy: $Src  -->  $Dst" -ForegroundColor Cyan
    } else {
        $parent = Split-Path -Parent $Dst
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item $Src $Dst -Force
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BNC CAD — Apply Overlay" -ForegroundColor Green
Write-Host "  Target: $FreeCADTarget" -ForegroundColor Green
if ($DryRun) { Write-Host "  Mode: DRY RUN (no files written)" -ForegroundColor Yellow }
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# ── 1. Copy NEW BNC modules (entire directories) ──────────────────────────────
$newModules = @("BNC_Init", "BNCCustomTools", "BNCGlobal", "BNCMCP")
foreach ($mod in $newModules) {
    $srcMod = Join-Path $overlayDir "Mod\$mod"
    $dstMod = Join-Path $FreeCADTarget "Mod\$mod"
    if (Test-Path $srcMod) {
        Write-Host "  [NEW MODULE] $mod" -ForegroundColor Yellow
        if (-not $DryRun) {
            Copy-Item $srcMod $dstMod -Recurse -Force
            Get-ChildItem $dstMod -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "    [DRY-RUN] Would copy directory: $srcMod  -->  $dstMod" -ForegroundColor Cyan
        }
    } else {
        Write-Warning "  Module not found in overlay: $srcMod"
    }
}

# ── 2. Copy BNC_MacroSetup.py into Mod/ root ─────────────────────────────────
$macroSetup = Join-Path $overlayDir "Mod\BNC_MacroSetup.py"
if (Test-Path $macroSetup) {
    Write-Host "  [MOD ROOT] BNC_MacroSetup.py" -ForegroundColor Yellow
    Copy-Overlay $macroSetup (Join-Path $FreeCADTarget "Mod\BNC_MacroSetup.py")
}

# ── 3. Apply modified FreeCAD module files ────────────────────────────────────
$modifiedFiles = @(
    # Assembly modifications
    "Mod\Assembly\InitGui.py",
    # Start workbench additions/modifications
    "Mod\Start\AddSetWDButton.py",
    "Mod\Start\BNCThemeConfig.py",
    "Mod\Start\CommandStdSetWorkingDirectory.py",
    "Mod\Start\CommandStdVersionOpen.py",
    "Mod\Start\CommandStdVersionSave.py",
    "Mod\Start\CommandStdVersionSaveAs.py",
    "Mod\Start\EnforceWorkbenchSelector.py",
    "Mod\Start\ForceWorkbenchToolbar.py",
    "Mod\Start\HideHelpMenu.py",
    "Mod\Start\InitGui.py",
    # Tux toolbar fix
    "Mod\Tux\InitGui.py"
)

foreach ($rel in $modifiedFiles) {
    $src = Join-Path $overlayDir $rel
    $dst = Join-Path $FreeCADTarget $rel
    if (Test-Path $src) {
        $label = if ($rel -like "*\Start\*" -or $rel -like "*\Assembly\*" -or $rel -like "*\Tux\*") { "MODIFIED" } else { "NEW" }
        Write-Host "  [$label] $rel" -ForegroundColor $(if ($label -eq "MODIFIED") { "Magenta" } else { "Yellow" })
        Copy-Overlay $src $dst
    } else {
        Write-Warning "  File not found in overlay: $src"
    }
}

# ── 4. Copy Macros ───────────────────────────────────────────────────────────
$macroSrc = Join-Path $overlayDir "Macro"
$macroDst = Join-Path $FreeCADTarget "Macro"
if (Test-Path $macroSrc) {
    Write-Host "  [MACROS] Copying all BNC macros to $macroDst" -ForegroundColor Yellow
    if (-not $DryRun) {
        if (-not (Test-Path $macroDst)) { New-Item -ItemType Directory -Path $macroDst -Force | Out-Null }
        Copy-Item "$macroSrc\*" $macroDst -Force -Recurse
    } else {
        Get-ChildItem $macroSrc | ForEach-Object { Write-Host "    [DRY-RUN] Would copy: $($_.Name)" -ForegroundColor Cyan }
    }
}

# ── 5. Copy branding files ───────────────────────────────────────────────────
$systemCfg = Join-Path $brandingDir "system.cfg"
if (Test-Path $systemCfg) {
    Write-Host "  [BRANDING] system.cfg" -ForegroundColor Yellow
    Copy-Overlay $systemCfg (Join-Path $FreeCADTarget "system.cfg")
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
if ($DryRun) {
    Write-Host "  DRY RUN complete — no files were written." -ForegroundColor Yellow
} else {
    Write-Host "  BNC CAD overlay applied successfully!" -ForegroundColor Green
    Write-Host "  Next: Run build_bnc.ps1 or launch BNC CAD." -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Green
