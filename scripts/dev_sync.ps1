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
    foreach ($mod in @("BNC_Init", "BNCCustomTools", "BNCGlobal", "BNCMCP")) {
        Sync-Dir (Join-Path $repoRoot "src\Mod\$mod") (Join-Path $Target "Mod\$mod")
    }

    # Repo-root Mod directories
    Sync-Dir (Join-Path $repoRoot "Mod\BNCTechDraw") (Join-Path $Target "Mod\BNCTechDraw")

    # BNC_MacroSetup.py
    $macroSetup = Join-Path $repoRoot "src\Mod\BNC_MacroSetup.py"
    if (Test-Path $macroSetup) {
        Sync-File $macroSetup (Join-Path $Target "Mod\BNC_MacroSetup.py")
    }

    # Modified FreeCAD module files
    foreach ($rel in @("Mod\Assembly\InitGui.py", "Mod\TechDraw\InitGui.py", "Mod\Tux\InitGui.py")) {
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

    # Macros
    $macroSrc = Join-Path $repoRoot "Macro"
    $macroDst = Join-Path $Target "Macro"
    if (Test-Path $macroSrc) {
        $macros = Get-ChildItem $macroSrc -Filter "*.FCMacro" -File -EA SilentlyContinue
        if ($macros.Count -gt 0) {
            New-Item -ItemType Directory -Path $macroDst -Force | Out-Null
            foreach ($f in $macros) { Copy-Item $f.FullName $macroDst -Force }
            Write-Ok ("Macro\*.FCMacro  (" + $macros.Count + " files)")
        }
    }

    # Branding
    $sysCfg = Join-Path $repoRoot "branding\system.cfg"
    if (Test-Path $sysCfg) {
        Sync-File $sysCfg (Join-Path $Target "system.cfg")
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
