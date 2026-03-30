<#
.SYNOPSIS
    Upgrade BNC CAD to a new FreeCAD version by rebasing the BNC overlay
    branch onto the new release tag.

.DESCRIPTION
    Automates the Git workflow for upgrading BNC CAD to a new FreeCAD version:
    1. Fetches the new FreeCAD tag from upstream
    2. Creates a new bnc-X.X branch from that tag
    3. Cherry-picks (or rebases) all BNC commits from the current branch

    After this script completes, conflicts (if any) must be resolved manually.

.PARAMETER NewVersion
    The new FreeCAD version, e.g. "1.1" or "1.1.0"

.PARAMETER NewTag
    The exact Git tag name on the upstream FreeCAD repo (e.g. "1.1.0").
    If not provided, attempts to find a tag matching NewVersion.

.PARAMETER CurrentBranch
    The existing BNC branch to cherry-pick commits FROM.
    Default: bnc-1.0.2

.EXAMPLE
    # Upgrade to FreeCAD 1.1
    .\scripts\upgrade_to_new_fc.ps1 -NewVersion "1.1"

    # With explicit tag name
    .\scripts\upgrade_to_new_fc.ps1 -NewVersion "1.1" -NewTag "1.1.0"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$NewVersion,

    [string]$NewTag = "",

    [string]$CurrentBranch = "bnc-1.0.2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$newBranch = "bnc-$NewVersion"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BNC CAD — Upgrade to FreeCAD $NewVersion" -ForegroundColor Green
Write-Host "  From: $CurrentBranch" -ForegroundColor DarkGray
Write-Host "  To:   $newBranch" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Confirm not in the middle of a merge/rebase
$mergeHead = Join-Path (git rev-parse --git-dir) "MERGE_HEAD"
$rebaseDir = Join-Path (git rev-parse --git-dir) "rebase-merge"
if ((Test-Path $mergeHead) -or (Test-Path $rebaseDir)) {
    Write-Error "Repository is in the middle of a merge or rebase. Resolve that first."
    exit 1
}

# ── Step 1: Fetch upstream tags ───────────────────────────────────────────────
Write-Host "  [1/5] Fetching upstream FreeCAD tags..." -ForegroundColor Yellow
git fetch upstream --tags
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to fetch from upstream. Check your network connection."
    Write-Host "  upstream remote: $(git remote get-url upstream)" -ForegroundColor Cyan
    exit 1
}

# ── Step 2: Find the tag ──────────────────────────────────────────────────────
Write-Host "  [2/5] Locating FreeCAD $NewVersion tag..." -ForegroundColor Yellow
if ($NewTag -eq "") {
    $allTags = git tag -l | Where-Object { $_ -like "*$NewVersion*" }
    if ($null -eq $allTags -or $allTags.Count -eq 0) {
        Write-Host ""
        Write-Host "  Available tags matching partial search:" -ForegroundColor Cyan
        git tag -l | Where-Object { $_ -match "\d+\.\d+" } | Select-Object -Last 20
        Write-Error "No tag found matching '$NewVersion'. Use -NewTag to specify the exact tag name."
        exit 1
    }
    # Prefer exact match or the first result
    $NewTag = ($allTags | Where-Object { $_ -eq $NewVersion }) 
    if ($null -eq $NewTag) { $NewTag = $allTags | Select-Object -First 1 }
    Write-Host "  Found tag: $NewTag" -ForegroundColor Green
} else {
    $tagExists = git tag -l $NewTag
    if (-not $tagExists) {
        Write-Error "Tag '$NewTag' not found. Run: git fetch upstream --tags"
        exit 1
    }
}

# ── Step 3: Collect BNC commits from current branch ──────────────────────────
Write-Host "  [3/5] Collecting BNC commits from '$CurrentBranch'..." -ForegroundColor Yellow

# Get the merge-base between bnc-1.0.2 and the FreeCAD tag it was based on
# BNC commits = all commits on current branch NOT reachable from any FreeCAD tag
$bncCommits = git log --oneline $CurrentBranch --not --tags="[0-9]*" 2>$null
if (-not $bncCommits) {
    # Fallback: all commits on the branch
    $bncCommits = git log --oneline $CurrentBranch
}

Write-Host ""
Write-Host "  BNC commits to carry forward:" -ForegroundColor Cyan
$bncCommits | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
Write-Host ""

# ── Step 4: Create new branch from the FreeCAD tag ───────────────────────────
Write-Host "  [4/5] Creating '$newBranch' from tag '$NewTag'..." -ForegroundColor Yellow

$branchExists = git branch --list $newBranch
if ($branchExists) {
    Write-Warning "  Branch '$newBranch' already exists!"
    $confirm = Read-Host "  Delete and recreate it? [y/N]"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "  Aborted. Checkout the branch manually: git checkout $newBranch" -ForegroundColor Cyan
        exit 0
    }
    git branch -D $newBranch
}

git checkout -b $newBranch $NewTag
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create branch '$newBranch' from tag '$NewTag'"; exit 1 }

# ── Step 5: Rebase BNC changes onto the new branch ───────────────────────────
Write-Host "  [5/5] Rebasing BNC commits onto FreeCAD $NewVersion..." -ForegroundColor Yellow
Write-Host "  Command: git rebase --onto $newBranch <base> $CurrentBranch" -ForegroundColor DarkGray
Write-Host ""

# Two-arg rebase: replay all unique commits from CurrentBranch onto newBranch
git rebase $NewTag $CurrentBranch --onto $newBranch
$rebaseResult = $LASTEXITCODE

# ── Result ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green

if ($rebaseResult -eq 0) {
    Write-Host "  Rebase complete — no conflicts!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  You are now on branch: $(git branch --show-current)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test the BNC changes:  .\scripts\apply_bnc.ps1 -FreeCADTarget <path> -DryRun" -ForegroundColor Cyan
    Write-Host "  2. Build:                 .\scripts\build_bnc.ps1 -FreeCADSource <src>" -ForegroundColor Cyan
    Write-Host "  3. Push to GitLab:        git push origin $newBranch" -ForegroundColor Cyan
} else {
    Write-Host "  Rebase paused — conflicts need manual resolution." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  For each conflicting file:" -ForegroundColor Cyan
    Write-Host "    1. Open file and resolve <<<<<< ====== >>>>>> markers" -ForegroundColor Cyan
    Write-Host "    2. git add <resolved-file>" -ForegroundColor Cyan
    Write-Host "    3. git rebase --continue" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  To abort and go back:  git rebase --abort" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Current conflict status:" -ForegroundColor DarkGray
    git status --short
}

Write-Host "========================================" -ForegroundColor Green
