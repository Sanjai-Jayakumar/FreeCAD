<#
.SYNOPSIS
    Sync BNC customization files from the repo to a FreeCAD installation.
    No rebuild, no reinstall -- just copy the changed files and restart FreeCAD.

.PARAMETER Target
    FreeCAD installation to sync into.
    Default: C:\BNC-CAD-Output  (the dev build directory)
    Release: "C:\Program Files (x86)\BNC_CAD"  (requires running as Admin)

.PARAMETER Watch
    Keep running and re-sync automatically whenever any .py, .svg or
    .FCMacro file in the repo changes.  Press Ctrl+C to stop.

.EXAMPLE
    # One-time sync after every code change
    .\scripts\dev_sync.ps1

    # Sync into the installed release copy (run as Admin)
    .\scripts\dev_sync.ps1 -Target "C:\Program Files (x86)\BNC_CAD"

    # Auto-watch: re-syncs whenever you save a file
    .\scripts\dev_sync.ps1 -Watch
#>
param(
    [string]$Target = "C:\BNC-CAD-Output",
    [switch]$Watch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step([string]$msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  !!  $msg" -ForegroundColor Yellow }

function Clear-Pycache([string]$dir) {
    if (-not (Test-Path $dir)) { return }
    Get-ChildItem $dir -Filter "__pycache__" -Recurse -Directory -EA SilentlyContinue |
        Remove-Item -Recurse -Force -EA SilentlyContinue
    Get-ChildItem $dir -Filter "*.pyc" -Recurse -File -EA SilentlyContinue |
        Remove-Item -Force -EA SilentlyContinue
}

function Sync-Dir([string]$src, [string]$dst) {
    if (-not (Test-Path $src)) { Write-Warn "Source not found, skipping: $src"; return }
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Copy-Item "$src\*" $dst -Recurse -Force
    Clear-Pycache $dst
    Write-Ok (Split-Path $src -Leaf)
}

function Sync-File([string]$src, [string]$dst) {
    if (-not (Test-Path $src)) { Write-Warn "Source not found, skipping: $src"; return }
    $dstDir = Split-Path $dst -Parent
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    Copy-Item $src $dst -Force
    $pycache = Join-Path $dstDir "__pycache__"
    if (Test-Path $pycache) { Remove-Item $pycache -Recurse -Force -EA SilentlyContinue }
    Write-Ok (Split-Path $src -Leaf)
}

# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

function Invoke-Sync {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host ""
    Write-Host "[$ts] Syncing BNC files to: $Target" -ForegroundColor White
    Write-Host "--------------------------------------------" -ForegroundColor DarkGray

    if (-not (Test-Path $Target)) {
        Write-Host "  ERROR: Target not found: $Target" -ForegroundColor Red
        Write-Host "  Run build_bnc.ps1 first to create the output directory." -ForegroundColor Yellow
        return
    }

    # New BNC modules (full directories)
    foreach ($mod in @("BNC_Init", "BNCCustomTools", "BNCGlobal", "BNCMCP", "BNCMoldTools", "BNCGSD", "BNCClassA")) {
        Sync-Dir (Join-Path $repoRoot "src\Mod\$mod") (Join-Path $Target "Mod\$mod")
    }

    # Repo-root Mod directories
    Sync-Dir (Join-Path $repoRoot "Mod\BNCTechDraw")   (Join-Path $Target "Mod\BNCTechDraw")
    Sync-Dir (Join-Path $repoRoot "Mod\BNCPartDesign") (Join-Path $Target "Mod\BNCPartDesign")

    # Anvil Mold workbench (thin UI) + headless core library it shells out to
    Sync-Dir (Join-Path $repoRoot "Mod\anvil-mold\anvil-mold-wb") (Join-Path $Target "Mod\AnvilMold")
    Sync-Dir (Join-Path $repoRoot "Mod\anvil-mold\anvil-mold-core\anvil_mold_core") (Join-Path $Target "Mod\AnvilMold\anvil_mold_core")

    # BNC_MacroSetup.py
    $macroSetup = Join-Path $repoRoot "src\Mod\BNC_MacroSetup.py"
    if (Test-Path $macroSetup) {
        Sync-File $macroSetup (Join-Path $Target "Mod\BNC_MacroSetup.py")
    }

    # Modified FreeCAD module files
    foreach ($rel in @(
        "Mod\Assembly\InitGui.py",
        "Mod\Assembly\CommandInsertNewPart.py",
        "Mod\Assembly\CommandCreateAssembly.py",
        "Mod\Assembly\Assembly\__init__.py",
        "Mod\TechDraw\InitGui.py",
        "Mod\PartDesign\InitGui.py",
        "Mod\Tux\InitGui.py"
    )) {
        Sync-File (Join-Path $repoRoot "src\$rel") (Join-Path $Target $rel)
    }

    # Start workbench Python files
    $startSrc = Join-Path $repoRoot "src\Mod\Start"
    $startDst = Join-Path $Target "Mod\Start"
    if (Test-Path $startSrc) {
        $pyFiles = Get-ChildItem $startSrc -Filter "*.py" -File -EA SilentlyContinue
        if ($pyFiles.Count -gt 0) {
            New-Item -ItemType Directory -Path $startDst -Force | Out-Null
            foreach ($f in $pyFiles) { Copy-Item $f.FullName $startDst -Force }
            Clear-Pycache $startDst
            Write-Ok ("Start\*.py  (" + $pyFiles.Count + " files)")
        }
    }

    # Macros — copy to BNC-CAD-Output AND FreeCAD user macro dir
    $macroSrc = Join-Path $repoRoot "Macro"
    $macroDst = Join-Path $Target "Macro"
    $userMacroDir = Join-Path $env:APPDATA "FreeCAD\v1-1\Macro"
    if (Test-Path $macroSrc) {
        $macros = Get-ChildItem $macroSrc -Filter "*.FCMacro" -File -EA SilentlyContinue
        if ($macros.Count -gt 0) {
            New-Item -ItemType Directory -Path $macroDst -Force | Out-Null
            foreach ($f in $macros) { Copy-Item $f.FullName $macroDst -Force }
            # BNC macros live ONLY in the app macro dir. Toolbar buttons and the
            # keyboard shortcuts run them from here, so they no longer need to be
            # in the user macro dir — keeping them out leaves the user's
            # Execute-Macro list clean (only macros the USER creates appear).
            # Remove any BNC macros a previous sync copied into the user dir.
            if (Test-Path $userMacroDir) {
                foreach ($f in $macros) {
                    $u = Join-Path $userMacroDir $f.Name
                    if (Test-Path $u) { Remove-Item $u -Force -EA SilentlyContinue }
                }
            }
            Write-Ok ("Macro\*.FCMacro  (" + $macros.Count + " files, app-dir only)")
        }
    }

    # App icons — copied to {homePath}/icons/ so BitmapFactory overrides compiled resources
    $iconsDir = Join-Path $Target "icons"
    New-Item -ItemType Directory -Force $iconsDir | Out-Null
    foreach ($sz in @(16, 32, 48, 64)) {
        $iconSrc = Join-Path $repoRoot "src\Gui\Icons\freecad-icon-$sz.png"
        if (Test-Path $iconSrc) { Copy-Item $iconSrc (Join-Path $iconsDir "freecad-icon-$sz.png") -Force }
    }
    Write-Ok "freecad-icon-16/32/48/64.png (app icon override)"

    # branding.xml — controls splash text color/position (hides FreeCAD-drawn title+version)
    $brandingXml = Join-Path $repoRoot "branding\branding.xml"
    if (Test-Path $brandingXml) {
        Sync-File $brandingXml (Join-Path $Target "bin\branding.xml")
    }

    # Splash image override — placed in user AppData so it wins over compiled resources
    $splashSrc = Join-Path $repoRoot "src\Gui\Icons\freecadsplash2.png"
    $splashDst = Join-Path $env:APPDATA "FreeCAD\v1-1\Gui\images\splash_image.png"
    if (Test-Path $splashSrc) {
        New-Item -ItemType Directory -Force (Split-Path $splashDst) | Out-Null
        Copy-Item $splashSrc $splashDst -Force
        Write-Ok "splash_image.png (user override)"
    }

    # Branding
    $sysCfg = Join-Path $repoRoot "branding\system.cfg"
    if (Test-Path $sysCfg) {
        Sync-File $sysCfg (Join-Path $Target "system.cfg")
    }

    # BNC TechDraw templates
    $tmplSrc = Join-Path $repoRoot "src\data\Mod\TechDraw\Templates"
    $tmplDst = Join-Path $Target "data\Mod\TechDraw\Templates"
    if (Test-Path $tmplSrc) {
        New-Item -ItemType Directory -Path $tmplDst -Force | Out-Null
        Copy-Item "$tmplSrc\*.svg" $tmplDst -Force
        Write-Ok "TechDraw Templates (BNC)"
    }

    # BNC theme stylesheets (YAML params + QSS aliases)
    $styleDir    = Join-Path $Target "data\Gui\Stylesheets"
    $paramSrcDir = Join-Path $repoRoot "branding\Stylesheets\parameters"
    $paramDstDir = Join-Path $styleDir "parameters"
    $fcQss       = Join-Path $styleDir "FreeCAD.qss"
    $fcOverlay   = Join-Path $styleDir "overlay\Freecad Overlay.qss"
    if ((Test-Path $styleDir) -and (Test-Path $paramSrcDir)) {
        New-Item -ItemType Directory -Path $paramDstDir -Force | Out-Null
        Copy-Item "$paramSrcDir\BNC Theme Light.yaml" $paramDstDir -Force
        Copy-Item "$paramSrcDir\BNC Theme Dark.yaml"  $paramDstDir -Force
        foreach ($theme in @("BNC Theme Light", "BNC Theme Dark")) {
            if (Test-Path $fcQss)    { Copy-Item $fcQss    (Join-Path $styleDir "$theme.qss")         -Force }
            if (Test-Path $fcOverlay){ Copy-Item $fcOverlay (Join-Path $styleDir "$theme Overlay.qss") -Force }
        }
        Write-Ok "BNC theme stylesheets"
    }

    # BNC PreferencePacks (theme picker entries)
    $packsDir    = Join-Path $Target "data\Gui\PreferencePacks"
    $packsSrcDir = Join-Path $repoRoot "branding\PreferencePacks"
    if ((Test-Path $packsDir) -and (Test-Path $packsSrcDir)) {
        foreach ($theme in @("BNC Theme Light", "BNC Theme Dark")) {
            $dst = Join-Path $packsDir $theme
            $src = Join-Path $packsSrcDir $theme
            if (Test-Path $src) {
                New-Item -ItemType Directory -Path $dst -Force | Out-Null
                Copy-Item "$src\*" $dst -Force
            }
        }
        $pkgSrc = Join-Path $packsSrcDir "package.xml"
        if (Test-Path $pkgSrc) { Copy-Item $pkgSrc $packsDir -Force }
        Write-Ok "BNC PreferencePacks"
    }

    # Community workbench shims (clone once if missing, then sync shim file)
    $communityMods = @(
        [pscustomobject]@{ Name="Fasteners";    Url="https://github.com/shaise/FreeCAD_FastenersWB.git" },
        [pscustomobject]@{ Name="SheetMetal";   Url="https://github.com/shaise/FreeCAD_SheetMetal.git" },
        [pscustomobject]@{ Name="CurvedShapes"; Url="https://github.com/chbergmann/CurvedShapesWorkbench.git" },
        [pscustomobject]@{ Name="Curves";       Url="https://github.com/tomate44/CurvesWB.git" }
    )
    foreach ($wb in $communityMods) {
        $dstMod = Join-Path $Target "Mod\$($wb.Name)"
        if (-not (Test-Path $dstMod)) {
            Write-Step "Cloning $($wb.Name) community workbench..."
            git clone --depth=1 $wb.Url $dstMod 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "$($wb.Name) cloned" }
            else { Write-Warn "Failed to clone $($wb.Name)" }
        }
    }
    # Curves namespace-package shim
    $curvesShim = Join-Path $repoRoot "Mod\Curves\InitGui.py"
    $curvesDir  = Join-Path $Target "Mod\Curves"
    if ((Test-Path $curvesDir) -and (Test-Path $curvesShim)) {
        Sync-File $curvesShim (Join-Path $curvesDir "InitGui.py")
    }

    Write-Host "--------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  Done. Restart FreeCAD to pick up changes." -ForegroundColor Green
    Write-Host "  Exe: $Target\bin\FreeCAD.exe" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Watch mode
# ---------------------------------------------------------------------------

if ($Watch) {
    Write-Host ""
    Write-Host "Watch mode -- monitoring repo for .py / .svg / .FCMacro changes." -ForegroundColor Magenta
    Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

    Invoke-Sync

    $watcher = New-Object System.IO.FileSystemWatcher
    $watcher.Path = $repoRoot
    $watcher.IncludeSubdirectories = $true
    $watcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::FileName
    $watcher.Filter = "*.*"
    $watcher.EnableRaisingEvents = $true

    $lastSyncTime = [DateTime]::MinValue
    $debounceMs = 800

    Write-Host ""
    Write-Host "  Watching $repoRoot ..." -ForegroundColor DarkGray

    $changeTypes = [System.IO.WatcherChangeTypes]::Changed -bor `
                   [System.IO.WatcherChangeTypes]::Created -bor `
                   [System.IO.WatcherChangeTypes]::Renamed

    try {
        while ($true) {
            $ev = $watcher.WaitForChanged($changeTypes, 1000)
            if ($ev.TimedOut) { continue }

            $name = $ev.Name
            $ext = [System.IO.Path]::GetExtension($name).ToLower()
            if ($ext -notin @(".py", ".svg", ".fcmacro")) { continue }

            $now = [DateTime]::Now
            if (($now - $lastSyncTime).TotalMilliseconds -lt $debounceMs) { continue }
            $lastSyncTime = $now

            Write-Host ""
            Write-Host "  Changed: $name" -ForegroundColor Yellow
            Invoke-Sync
        }
    }
    finally {
        $watcher.Dispose()
    }
}
else {
    Invoke-Sync
}
