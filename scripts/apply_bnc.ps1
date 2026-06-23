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

# ── 5b. Install BNC theme stylesheets ────────────────────────────────────────
$styleDir    = Join-Path $FreeCADTarget "data\Gui\Stylesheets"
$paramDstDir = Join-Path $styleDir "parameters"
$paramSrcDir = Join-Path $brandingDir "Stylesheets\parameters"
$fcQss       = Join-Path $styleDir "FreeCAD.qss"
$fcOverlay   = Join-Path $styleDir "overlay\Freecad Overlay.qss"

if (Test-Path $styleDir) {
    Write-Host "  [THEME] Installing BNC theme stylesheets..." -ForegroundColor Yellow

    # Copy YAML parameter files
    if (Test-Path $paramSrcDir) {
        if (-not $DryRun) {
            if (-not (Test-Path $paramDstDir)) { New-Item -ItemType Directory -Path $paramDstDir -Force | Out-Null }
            Copy-Item "$paramSrcDir\BNC Theme Light.yaml" $paramDstDir -Force
            Copy-Item "$paramSrcDir\BNC Theme Dark.yaml"  $paramDstDir -Force
        } else {
            Write-Host "    [DRY-RUN] Would copy BNC Theme *.yaml to $paramDstDir" -ForegroundColor Cyan
        }
    } else {
        Write-Warning "  Branding Stylesheets/parameters not found: $paramSrcDir"
    }

    # Create BNC QSS aliases (same base QSS, BNC-specific YAML supplies the colours)
    foreach ($theme in @("BNC Theme Light", "BNC Theme Dark")) {
        if (Test-Path $fcQss) {
            Write-Host "  [THEME] $theme.qss" -ForegroundColor Yellow
            Copy-Overlay $fcQss (Join-Path $styleDir "$theme.qss")
        }
        if (Test-Path $fcOverlay) {
            Write-Host "  [THEME] $theme Overlay.qss" -ForegroundColor Yellow
            Copy-Overlay $fcOverlay (Join-Path $styleDir "$theme Overlay.qss")
        }
    }
} else {
    Write-Warning "  Stylesheets directory not found at: $styleDir"
}

# ── 5c. Install BNC PreferencePacks (theme picker entries) ───────────────────
$packsDir    = Join-Path $FreeCADTarget "data\Gui\PreferencePacks"
$packsSrcDir = Join-Path $brandingDir "PreferencePacks"
if ((Test-Path $packsDir) -and (Test-Path $packsSrcDir)) {
    Write-Host "  [THEME] Installing BNC PreferencePacks..." -ForegroundColor Yellow
    foreach ($theme in @("BNC Theme Light", "BNC Theme Dark")) {
        $dst = Join-Path $packsDir $theme
        $src = Join-Path $packsSrcDir $theme
        if (Test-Path $src) {
            if (-not $DryRun) {
                New-Item -ItemType Directory -Path $dst -Force | Out-Null
                Copy-Item "$src\*" $dst -Force
            } else {
                Write-Host "    [DRY-RUN] Would copy: $src --> $dst" -ForegroundColor Cyan
            }
        }
    }
    # Replace package.xml to show only BNC themes
    $pkgSrc = Join-Path $packsSrcDir "package.xml"
    if (Test-Path $pkgSrc) {
        Write-Host "  [THEME] PreferencePacks\package.xml" -ForegroundColor Yellow
        Copy-Overlay $pkgSrc (Join-Path $packsDir "package.xml")
    }
}

# ── 6. Install community workbench Python dependencies ───────────────────────
$pythonExe = Join-Path $FreeCADTarget "bin\python.exe"
if (Test-Path $pythonExe) {
    Write-Host "  [DEPS] Installing networkx (SheetMetal Unfolder)..." -ForegroundColor Yellow
    if (-not $DryRun) {
        & $pythonExe -m pip install networkx --quiet 2>&1 | Out-Null
        Write-Host "  [DEPS] networkx installed" -ForegroundColor Cyan
    }
}

# ── 7. Clone community workbenches ───────────────────────────────────────────
$communityMods = @(
    [pscustomobject]@{ Name="Fasteners";    Url="https://github.com/shaise/FreeCAD_FastenersWB.git" },
    [pscustomobject]@{ Name="SheetMetal";   Url="https://github.com/shaise/FreeCAD_SheetMetal.git" },
    [pscustomobject]@{ Name="CurvedShapes"; Url="https://github.com/chbergmann/CurvedShapesWorkbench.git" },
    [pscustomobject]@{ Name="Curves";       Url="https://github.com/tomate44/CurvesWB.git" }
)

foreach ($wb in $communityMods) {
    $dstMod = Join-Path $FreeCADTarget "Mod\$($wb.Name)"
    if (Test-Path $dstMod) {
        Write-Host "  [COMMUNITY] $($wb.Name) — already present, skipping clone" -ForegroundColor Cyan
    } else {
        Write-Host "  [COMMUNITY] Cloning $($wb.Name)..." -ForegroundColor Yellow
        if (-not $DryRun) {
            git clone --depth=1 $wb.Url $dstMod 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "  Failed to clone $($wb.Name) — skipping"
            }
        } else {
            Write-Host "    [DRY-RUN] Would clone: $($wb.Url)  -->  $dstMod" -ForegroundColor Cyan
        }
    }
}

# Curves namespace-package shim: copy after cloning so it survives
$curvesShimSrc = Join-Path $scriptDir "..\Mod\Curves\InitGui.py"
$curvesShimDst = Join-Path $FreeCADTarget "Mod\Curves\InitGui.py"
$curvesDir     = Join-Path $FreeCADTarget "Mod\Curves"
if ((Test-Path $curvesDir) -and (Test-Path $curvesShimSrc)) {
    Write-Host "  [COMMUNITY] Curves — installing namespace-package shim" -ForegroundColor Yellow
    Copy-Overlay (Resolve-Path $curvesShimSrc) $curvesShimDst
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
if ($DryRun) {
    Write-Host "  DRY RUN complete - no files were written." -ForegroundColor Yellow
} else {
    Write-Host "  BNC CAD overlay applied successfully!" -ForegroundColor Green
    Write-Host "  Next: Run build_bnc.ps1 or launch BNC CAD." -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Green
