<#
.SYNOPSIS
    Build BNC CAD from FreeCAD source using CMake + Visual Studio 2022.

.DESCRIPTION
    Configures and compiles FreeCAD with BNC branding, then applies the
    BNC overlay on top of the compiled output.

.PARAMETER FreeCADSource
    Path to the FreeCAD source repository (cloned from GitHub).
    Default: D:\freecad-source

.PARAMETER LibPackDir
    Path to the extracted FreeCAD LibPack for this version.
    Download from: https://github.com/FreeCAD/FreeCAD-LibPack/releases
    Default: C:\FreeCAD_LibPack

.PARAMETER BuildDir
    Directory for CMake build files (gets populated by compiler).
    Default: $FreeCADSource\build

.PARAMETER OutputDir
    Where the compiled BNC CAD application is installed.
    Default: C:\BNC-CAD-Output

.PARAMETER Config
    Build configuration: Release or Debug.
    Default: Release

.PARAMETER Jobs
    Parallel compile jobs. Default: number of CPU cores.

.EXAMPLE
    .\scripts\build_bnc.ps1
    .\scripts\build_bnc.ps1 -FreeCADSource "D:\freecad-1.1" -LibPackDir "C:\FreeCAD_LibPack_1.1"
#>
param(
    [string]$FreeCADSource = "D:\freecad-source",
    [string]$LibPackDir    = "C:\FreeCAD_LibPack",
    [string]$BuildDir      = "",
    [string]$OutputDir     = "C:\BNC-CAD-Output",
    [string]$Config        = "Release",
    [int]   $Jobs          = [Environment]::ProcessorCount
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($BuildDir -eq "") { $BuildDir = Join-Path $FreeCADSource "build" }

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot    = Split-Path -Parent $scriptDir
$applyScript = Join-Path $scriptDir "apply_bnc.ps1"

# ── Preflight checks ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BNC CAD — Build from Source" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

foreach ($check in @(
    @{ Path = $FreeCADSource; Label = "FreeCAD source" },
    @{ Path = $LibPackDir;    Label = "LibPack" }
)) {
    if (-not (Test-Path $check.Path)) {
        Write-Error "$($check.Label) not found at: $($check.Path)"
        Write-Host ""
        Write-Host "  Hint: Clone FreeCAD source with:" -ForegroundColor Cyan
        Write-Host "  git clone https://github.com/FreeCAD/FreeCAD.git $FreeCADSource" -ForegroundColor Cyan
        Write-Host "  Then checkout the 1.1 tag: git -C $FreeCADSource checkout tags/0.21.2 (adjust tag)" -ForegroundColor Cyan
        exit 1
    }
}

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Error "CMake not found in PATH. Install from https://cmake.org/download/"
    exit 1
}

# ── CMake Configure ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [1/4] Configuring with CMake..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

$cmakeArgs = @(
    "..",
    "-G", "Visual Studio 17 2022",
    "-A", "x64",
    "-DFREECAD_LIBPACK_DIR=$LibPackDir",
    "-DBUILD_WITH_CONDA=OFF",
    "-DCMAKE_INSTALL_PREFIX=$OutputDir",
    "-DFREECAD_PROGRAM_NAME=BNC CAD",
    "-DFREECAD_VERSION_SUFFIX=-BNC"
)

Push-Location $BuildDir
try {
    cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "CMake configure failed (exit $LASTEXITCODE)"; exit 1 }
} finally {
    Pop-Location
}

# ── Compile ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [2/4] Compiling ($Config, $Jobs parallel jobs)..." -ForegroundColor Yellow
Write-Host "  This will take 30-60 minutes on first build." -ForegroundColor DarkGray

cmake --build $BuildDir --config $Config --parallel $Jobs
if ($LASTEXITCODE -ne 0) { Write-Error "CMake build failed (exit $LASTEXITCODE)"; exit 1 }

# ── Install ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [3/4] Installing to $OutputDir..." -ForegroundColor Yellow

cmake --install $BuildDir --config $Config
if ($LASTEXITCODE -ne 0) { Write-Error "CMake install failed (exit $LASTEXITCODE)"; exit 1 }

# ── Apply BNC overlay ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [4/4] Applying BNC CAD overlay..." -ForegroundColor Yellow

& $applyScript -FreeCADTarget $OutputDir
if ($LASTEXITCODE -ne 0) { Write-Error "apply_bnc.ps1 failed (exit $LASTEXITCODE)"; exit 1 }

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  Output: $OutputDir" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host "  1. Test:    $OutputDir\bin\BNC_CAD.exe" -ForegroundColor Cyan
Write-Host "  2. Package: .\scripts\build_installer.ps1 -SourceDir '$OutputDir'" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
