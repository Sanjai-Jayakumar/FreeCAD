<#
.SYNOPSIS
    One-shot: install prerequisites, download LibPack, then build ANVIL CAD.

.DESCRIPTION
    Runs the complete build pipeline:
      1. Installs 7-Zip  (winget)
      2. Installs CMake  (winget)
      3. Installs VS 2022 Build Tools + Desktop C++ workload  (winget)
      4. Downloads FreeCAD LibPack 1.1 v3.1.1.3  (~948 MB)
      5. Extracts LibPack to C:\FreeCAD_LibPack
      6. Calls build_bnc.ps1 to configure + compile + install ANVIL CAD

    Run this script from an Administrator PowerShell window.
    The compilation step (step 6) takes ~30-60 minutes.

.PARAMETER SkipInstall
    Skip winget installs (use if tools are already installed).

.PARAMETER SkipDownload
    Skip LibPack download (use if already downloaded to D:\).

.PARAMETER LibPackDir
    Where to extract the LibPack.  Default: C:\FreeCAD_LibPack

.PARAMETER OutputDir
    Where to install the finished ANVIL CAD application.  Default: C:\BNC-CAD-Output

.EXAMPLE
    # Full setup + build (first time):
    .\scripts\setup_and_build.ps1

    # Re-run build only (tools + LibPack already present):
    .\scripts\setup_and_build.ps1 -SkipInstall -SkipDownload
#>
param(
    [switch]$SkipInstall,
    [switch]$SkipDownload,
    [string]$LibPackDir  = "C:\FreeCAD_LibPack",
    [string]$OutputDir   = "C:\BNC-CAD-Output"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot    = Split-Path -Parent $scriptDir
$buildScript = Join-Path $scriptDir "build_bnc.ps1"

# ── LibPack constants ────────────────────────────────────────────────────────
$LibPackVersion   = "3.1.1.3"
$LibPackFileName  = "LibPack-1.1.0-v3.1.1.3-Release.7z"
$LibPackUrl       = "https://github.com/FreeCAD/FreeCAD-LibPack/releases/download/$LibPackVersion/$LibPackFileName"
$LibPackArchive   = "D:\$LibPackFileName"

# ── Helper: print banner ─────────────────────────────────────────────────────
function Banner([string]$msg, [string]$color = "Green") {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor $color
    Write-Host "  $msg"  -ForegroundColor $color
    Write-Host ("=" * 60) -ForegroundColor $color
}

function Step([string]$msg) {
    Write-Host ""
    Write-Host ">>> $msg" -ForegroundColor Cyan
}

# ── Check admin ──────────────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Banner "Relaunching as Administrator..." "Yellow"
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
    foreach ($p in $PSBoundParameters.GetEnumerator()) {
        if ($p.Value -is [switch]) {
            if ($p.Value) { $argList += " -$($p.Key)" }
        } else {
            $argList += " -$($p.Key) `"$($p.Value)`""
        }
    }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit 0
}

Banner "ANVIL CAD — Full Setup & Build"

# ============================================================
# PHASE 1 — Install tools
# ============================================================
if (-not $SkipInstall) {
    Step "Phase 1/4 — Installing build tools"

    # --- 7-Zip ---
    $sevenZip = "C:\Program Files\7-Zip\7z.exe"
    if (-not (Test-Path $sevenZip)) {
        Write-Host "  Installing 7-Zip..." -ForegroundColor Yellow
        winget install --id 7zip.7zip --silent --accept-package-agreements --accept-source-agreements
        if (-not (Test-Path $sevenZip)) {
            # Fallback: check 32-bit path
            $sevenZip = "C:\Program Files (x86)\7-Zip\7z.exe"
        }
    } else {
        Write-Host "  7-Zip already present." -ForegroundColor DarkGray
    }

    # --- CMake ---
    $cmakePath = (Get-Command cmake -ErrorAction SilentlyContinue)?.Source
    if (-not $cmakePath) {
        Write-Host "  Installing CMake..." -ForegroundColor Yellow
        winget install --id Kitware.CMake --silent --accept-package-agreements --accept-source-agreements
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User")
        $cmakePath = (Get-Command cmake -ErrorAction SilentlyContinue)?.Source
        if (-not $cmakePath) {
            # Known install location
            $cmakePath = (Get-ChildItem "C:\Program Files\CMake\bin\cmake.exe" -ErrorAction SilentlyContinue)?.FullName
            if ($cmakePath) { $env:PATH = "C:\Program Files\CMake\bin;$env:PATH" }
        }
    } else {
        Write-Host "  CMake already present: $cmakePath" -ForegroundColor DarkGray
    }
    if (-not $cmakePath) { Write-Error "CMake not found after install — please reboot and rerun."; exit 1 }

    # --- VS 2022 Build Tools + C++ workload ---
    # vswhere ships with VS installer; also check known path
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $vsFound = $false
    if (Test-Path $vswhere) {
        $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath 2>$null
        $vsFound = ($vsPath -ne $null -and $vsPath -ne "")
    }

    if (-not $vsFound) {
        Write-Host "  Installing VS 2022 Build Tools + C++ workload..." -ForegroundColor Yellow
        Write-Host "  (This downloads ~3 GB and may take 20-40 minutes)" -ForegroundColor DarkGray
        winget install --id Microsoft.VisualStudio.2022.BuildTools `
            --silent --accept-package-agreements --accept-source-agreements `
            --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --includeRecommended"
        Write-Host "  VS 2022 Build Tools installation complete." -ForegroundColor Green
    } else {
        Write-Host "  VS 2022 Build Tools already present: $vsPath" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  (Skipping tool install — -SkipInstall)" -ForegroundColor DarkGray
}

# ============================================================
# PHASE 2 — Download LibPack
# ============================================================
if (-not $SkipDownload) {
    Step "Phase 2/4 — Downloading FreeCAD LibPack $LibPackVersion (~948 MB)"
    if (Test-Path $LibPackArchive) {
        $existingSize = (Get-Item $LibPackArchive).Length
        Write-Host "  Already downloaded ($([math]::Round($existingSize/1MB)) MB): $LibPackArchive" -ForegroundColor DarkGray
    } else {
        Write-Host "  Downloading to: $LibPackArchive"
        Write-Host "  URL: $LibPackUrl"
        Write-Host ""
        # Use BITS for resumable download with progress
        $bitsJob = Start-BitsTransfer -Source $LibPackUrl -Destination $LibPackArchive -Asynchronous -DisplayName "LibPack Download"
        try {
            while ($bitsJob.JobState -notin @("Transferred","Error")) {
                $pct = if ($bitsJob.BytesTotal -gt 0) { [math]::Round(($bitsJob.BytesTransferred/$bitsJob.BytesTotal)*100, 1) } else { 0 }
                $mb  = [math]::Round($bitsJob.BytesTransferred/1MB, 0)
                Write-Host "  $pct% — ${mb} MB downloaded..." -ForegroundColor Yellow -NoNewline
                Write-Host "`r" -NoNewline
                Start-Sleep -Seconds 5
            }
            if ($bitsJob.JobState -eq "Error") {
                Write-Host "  BITS failed, falling back to Invoke-WebRequest..." -ForegroundColor Yellow
                Remove-BitsTransfer $bitsJob -ErrorAction SilentlyContinue
                Invoke-WebRequest -Uri $LibPackUrl -OutFile $LibPackArchive -UseBasicParsing
            } else {
                Complete-BitsTransfer $bitsJob
            }
        } catch {
            Remove-BitsTransfer $bitsJob -ErrorAction SilentlyContinue
            throw
        }
        Write-Host ""
        Write-Host "  Download complete: $LibPackArchive" -ForegroundColor Green
    }
} else {
    Write-Host "  (Skipping download — -SkipDownload)" -ForegroundColor DarkGray
}

# ============================================================
# PHASE 3 — Extract LibPack
# ============================================================
Step "Phase 3/4 — Extracting LibPack to $LibPackDir"

if (Test-Path (Join-Path $LibPackDir "bin")) {
    Write-Host "  LibPack already extracted." -ForegroundColor DarkGray
} else {
    if (-not (Test-Path $LibPackArchive)) {
        Write-Error "LibPack archive not found: $LibPackArchive — run without -SkipDownload"
        exit 1
    }

    $sevenZipExe = "C:\Program Files\7-Zip\7z.exe"
    if (-not (Test-Path $sevenZipExe)) {
        $sevenZipExe = "C:\Program Files (x86)\7-Zip\7z.exe"
    }
    if (-not (Test-Path $sevenZipExe)) {
        Write-Error "7-Zip not found.  Install 7-Zip and rerun, or extract $LibPackArchive manually to $LibPackDir"
        exit 1
    }

    New-Item -ItemType Directory -Path $LibPackDir -Force | Out-Null
    Write-Host "  Extracting $LibPackArchive ..." -ForegroundColor Yellow
    Write-Host "  (This may take several minutes)" -ForegroundColor DarkGray

    # 7z extracts a single top-level folder inside the archive; move contents up
    $tempDir = "$LibPackDir\_extract_tmp"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    & $sevenZipExe x $LibPackArchive -o"$tempDir" -y | Out-Null

    # Move extracted contents into $LibPackDir
    $inner = Get-ChildItem $tempDir -Directory | Select-Object -First 1
    if ($inner) {
        Get-ChildItem $inner.FullName | Move-Item -Destination $LibPackDir -Force
    } else {
        Get-ChildItem $tempDir | Move-Item -Destination $LibPackDir -Force
    }
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "  LibPack extracted to: $LibPackDir" -ForegroundColor Green
}

# ============================================================
# PHASE 4 — Build ANVIL CAD
# ============================================================
Step "Phase 4/4 — Building ANVIL CAD 1.1 from source"
Write-Host "  Source:  $repoRoot" -ForegroundColor DarkGray
Write-Host "  LibPack: $LibPackDir" -ForegroundColor DarkGray
Write-Host "  Output:  $OutputDir" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Compilation typically takes 30-60 minutes." -ForegroundColor Yellow

# Re-add CMake to PATH if needed
$env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    $env:PATH = "C:\Program Files\CMake\bin;$env:PATH"
}

& $buildScript `
    -FreeCADSource $repoRoot `
    -LibPackDir    $LibPackDir `
    -OutputDir     $OutputDir

if ($LASTEXITCODE -ne 0) {
    Banner "Build FAILED (exit $LASTEXITCODE)" "Red"
    exit $LASTEXITCODE
}

Banner "ANVIL CAD build complete!  Exe: $OutputDir\bin\BNC_CAD.exe"
