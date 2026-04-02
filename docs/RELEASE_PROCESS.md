# BNC CAD — Release Process Guide

> **Product**: BNC CAD 1.1 (Custom FreeCAD 1.1.0 Build)
> **Repository**: `Sanjai-Jayakumar/FreeCAD` (fork of `FreeCAD/FreeCAD`)
> **Branch**: `bnc-1.1`
> **Last Updated**: April 2026

---

## Table of Contents

1. [Release Overview](#1-release-overview)
2. [Version Numbering](#2-version-numbering)
3. [Release Types](#3-release-types)
4. [Pre-Release Checklist](#4-pre-release-checklist)
5. [Step-by-Step Release Process](#5-step-by-step-release-process)
6. [Build Pipeline](#6-build-pipeline)
7. [Installer Creation](#7-installer-creation)
8. [Testing & Validation](#8-testing--validation)
9. [Publishing a Release on GitHub](#9-publishing-a-release-on-github)
10. [Post-Release Tasks](#10-post-release-tasks)
11. [Hotfix Process](#11-hotfix-process)
12. [Rollback Procedure](#12-rollback-procedure)
13. [Release Calendar](#13-release-calendar)
14. [Roles & Responsibilities](#14-roles--responsibilities)
15. [Appendix: Command Reference](#15-appendix-command-reference)

---

## 1. Release Overview

BNC CAD is a customized build of FreeCAD 1.1.0, maintained as a fork. Releases are
distributed as a **standalone Windows installer** (`BNC CAD.exe`, ~630 MB) that
includes all dependencies (Qt 6.8, OpenCASCADE 7.8, Python 3.12, VC++ Runtime).

**Release Flow:**
```
Development → Code Freeze → Build → Test → Tag → Installer → GitHub Release → Distribute
```

**Key Principle:** End users install BNC CAD from the installer and do NOT need
to install any additional software (no Python, no VC++ Redistributable, nothing).

---

## 2. Version Numbering

We follow **Semantic Versioning** (`MAJOR.MINOR.PATCH`) with an optional pre-release suffix:

| Format | Example | When to Use |
|--------|---------|-------------|
| `MAJOR.MINOR.PATCH` | `1.1.0` | Stable releases |
| `MAJOR.MINOR.PATCH-rc.N` | `1.1.1-rc.1` | Release candidates (testing) |
| `MAJOR.MINOR.PATCH-beta.N` | `1.2.0-beta.1` | Beta/preview releases |

### Version Meaning

| Part | Incremented When... | Example |
|------|---------------------|---------|
| **MAJOR** | Breaking changes or new FreeCAD base version | `1.x.x` → `2.0.0` (FreeCAD 2.0 rebase) |
| **MINOR** | New features, new BNC tools, workbench additions | `1.1.x` → `1.2.0` (new drawing generator) |
| **PATCH** | Bug fixes, icon fixes, installer fixes | `1.1.0` → `1.1.1` (assembly fix) |

### Current Version
- **BNC CAD 1.1.0** — Based on FreeCAD 1.1.0
- Next planned: **1.1.1** (patch) or **1.2.0** (feature)

### Where Version is Defined

| File | Field | Example |
|------|-------|---------|
| `installer/BNC_CAD.nsi` | `PRODUCT_VERSION` | `"1.1"` |
| `installer/BNC_CAD.nsi` | `VIProductVersion` | `"1.1.0.0"` |
| `installer/BNC_CAD.nsi` | `VIAddVersionKey "FileVersion"` | `"1.1.0.0"` |
| `branding/system.cfg` | Application version | `1.1` |
| Git tag | `bnc-v1.1.0` | Tag on the release commit |

---

## 3. Release Types

### 3.1 Stable Release
- Fully tested, production-ready
- Tagged as `bnc-v1.1.0`, `bnc-v1.1.1`, etc.
- Published on GitHub Releases with installer binary
- Distributed to all end users

### 3.2 Release Candidate (RC)
- Feature-complete, undergoing final testing
- Tagged as `bnc-v1.1.1-rc.1`, `bnc-v1.1.1-rc.2`, etc.
- Shared only with internal testers / QA team
- May have known minor issues listed in release notes

### 3.3 Hotfix Release
- Emergency fix for a critical bug in a stable release
- Created from the tagged release commit (not from latest `bnc-1.1`)
- Example: `bnc-v1.1.0` → hotfix → `bnc-v1.1.1`

---

## 4. Pre-Release Checklist

Before starting a release, verify ALL items below:

### Code Quality
- [ ] All CI/CD pipeline checks pass (green) on `bnc-1.1` branch
- [ ] No open critical/blocker bugs in the issue tracker
- [ ] All intended features for this release are merged to `bnc-1.1`
- [ ] Commit messages follow conventional format (`type(scope): description`)

### Functional Testing
- [ ] BNC CAD launches without errors
- [ ] All workbenches load (especially Assembly, PartDesign, Sketcher, TechDraw)
- [ ] BNC Custom Tools work:
  - [ ] Create New Part — dialog opens, creates part with body
  - [ ] Insert from Working Dir — file browser opens, thumbnails show
  - [ ] Origin to Assembly Constraint — executes Default.FCMacro
  - [ ] Regen Assembly — executes Regen.FCMacro, re-solves joints
  - [ ] BOM Export — generates Excel file with bill of materials
- [ ] BNC Macros work:
  - [ ] Version_Save — saves with incremented version number
  - [ ] GenerateDrawing — creates TechDraw drawing
  - [ ] FillTitleBlock — populates title block fields
  - [ ] Apply_Material — assigns material to body
  - [ ] MeasureMass — calculates mass and center of gravity
- [ ] File operations: Open, Save, Save As, Import STEP, Export STEP
- [ ] 3D viewport: rotate, pan, zoom, select, measure

### Branding
- [ ] Splash screen shows BNC CAD branding (not FreeCAD)
- [ ] App icon shows BNC CAD icon in taskbar and window
- [ ] About dialog shows correct version and BNC branding
- [ ] Window title shows "BNC CAD 1.1"

### Installer
- [ ] NSIS script has correct version numbers
- [ ] Installer creates Start Menu and Desktop shortcuts
- [ ] Installer sets registry entries for uninstall
- [ ] Uninstaller removes all files cleanly
- [ ] Fresh install on clean Windows machine works
- [ ] Upgrade install over previous version works

---

## 5. Step-by-Step Release Process

### Step 1: Freeze the Code

Stop merging new features. Only bug fixes allowed from this point.

```powershell
# Ensure you're on the latest bnc-1.1
cd D:\BNC-FreeCAD
git checkout bnc-1.1
git pull origin bnc-1.1
```

### Step 2: Update Version Numbers

Update ALL version references for the new release:

**File: `installer/BNC_CAD.nsi`**
```nsi
!define PRODUCT_VERSION "1.1.1"          ; ← Update this
VIProductVersion "1.1.1.0"              ; ← Update this (4-part)
VIAddVersionKey "FileVersion" "1.1.1.0" ; ← Update this (4-part)
```

**File: `branding/system.cfg`** (if version is referenced there)

Commit the version bump:
```powershell
git add installer/BNC_CAD.nsi branding/system.cfg
git commit -m "build(release): bump version to 1.1.1"
```

### Step 3: Build the Application

```powershell
# Configure (if not already done)
& "C:\Program Files\CMake\bin\cmake.exe" `
  -S D:\BNC-FreeCAD `
  -B D:\BNC-FreeCAD\build `
  -G "Visual Studio 17 2022" -A x64 `
  -DFREECAD_LIBPACK_DIR="C:/FreeCAD_LibPack/LibPack-1.1.0-v3.1.1.3-Release" `
  -DCMAKE_INSTALL_PREFIX="C:/BNC-CAD-Output"

# Build Release
& "C:\Program Files\CMake\bin\cmake.exe" `
  --build D:\BNC-FreeCAD\build `
  --config Release `
  --parallel 16

# Install to output directory
& "C:\Program Files\CMake\bin\cmake.exe" `
  --install D:\BNC-FreeCAD\build `
  --config Release
```

### Step 4: Copy BNC Assets

```powershell
# Copy BNC macros to install output
Copy-Item -Path "D:\BNC-FreeCAD\Macro\*" `
  -Destination "C:\BNC-CAD-Output\Macro" -Recurse -Force

# Copy default toolbar layout
Copy-Item -Path "D:\BNC-FreeCAD\installer\default_toolbar_layout.json" `
  -Destination "C:\BNC-CAD-Output\" -Force
```

### Step 5: Create the Installer

```powershell
# Create 7z archive
cd D:\BNC-FreeCAD\installer
& .\7zr.exe a -t7z -mx=9 -mfb=64 -md=32m -ms=on `
  "BNC-CAD-Output.7z" "C:\BNC-CAD-Output\*"

# Build NSIS installer
& "C:\Program Files (x86)\NSIS\makensis.exe" BNC_CAD.nsi
```

Output: `installer/BNC CAD.exe` (~630 MB)

### Step 6: Test the Installer

1. Copy `BNC CAD.exe` to a **clean test machine** (or clean folder)
2. Run as Administrator
3. Install to default location (`C:\Program Files\BNC_CAD`)
4. Launch BNC CAD from Desktop shortcut
5. Run through the [Pre-Release Checklist](#4-pre-release-checklist)
6. Test uninstall — verify clean removal

### Step 7: Tag the Release

```powershell
cd D:\BNC-FreeCAD
git tag -a bnc-v1.1.1 -m "BNC CAD v1.1.1 - <brief description>"
git push origin bnc-v1.1.1
```

### Step 8: Create GitHub Release

See [Section 9](#9-publishing-a-release-on-github) for detailed steps.

### Step 9: Distribute

- Share the GitHub Release link with end users
- Or distribute `BNC CAD.exe` directly via file share / email

---

## 6. Build Pipeline

### Build Environment Requirements

| Component | Version | Path |
|-----------|---------|------|
| Visual Studio Build Tools | 2022 (v19.44) | Default install |
| CMake | 4.3.1 | `C:\Program Files\CMake\bin\cmake.exe` |
| LibPack | v3.1.1.3 | `C:\FreeCAD_LibPack\LibPack-1.1.0-v3.1.1.3-Release` |
| NSIS | 3.x | `C:\Program Files (x86)\NSIS\makensis.exe` |
| 7zr | Latest | `D:\BNC-FreeCAD\installer\7zr.exe` |
| Python | 3.12.10 | Bundled in LibPack |
| Qt | 6.8.3 | Bundled in LibPack |

### Build Configurations

| Config | Use Case | Build Time |
|--------|----------|------------|
| **Release** | Installer / Distribution | ~15-25 min |
| **Debug** | Development / Debugging | ~20-30 min |

### Build Output

| Output | Location |
|--------|----------|
| Build artifacts | `D:\BNC-FreeCAD\build\` |
| Install tree | `C:\BNC-CAD-Output\` |
| Installer | `D:\BNC-FreeCAD\installer\BNC CAD.exe` |

---

## 7. Installer Creation

### Installer Technology
- **NSIS** (Nullsoft Scriptable Install System) with Modern UI 2.0
- Script: `installer/BNC_CAD.nsi`
- Compression: LZMA Solid (via 7z pre-compression)

### Installer Contents

| Component | Description |
|-----------|-------------|
| `bin/FreeCAD.exe` | Main application executable |
| `bin/*.dll` | All dependencies (Qt, OCCT, Python, Coin3D, VC++ Runtime) |
| `Mod/*` | All workbench modules (35+) |
| `Ext/*` | Python extension packages |
| `Macro/*` | BNC custom macros (16+) |
| `data/*` | Templates, material library, translations |
| `default_toolbar_layout.json` | BNC default toolbar configuration |

### What the Installer Does

1. Extracts 7z archive to `C:\Program Files\BNC_CAD\`
2. Removes temporary installer files (7zr.exe, .7z)
3. Resets user config (`user.cfg`) so BNC defaults apply
4. Registers in Windows Registry (Add/Remove Programs)
5. Creates Start Menu shortcut: `BNC CAD\BNC CAD 1.1`
6. Creates Desktop shortcut: `BNC CAD 1.1`
7. Copies `default_toolbar_layout.json` to install directory

### Installer Size Targets

| Component | Approximate Size |
|-----------|-----------------|
| 7z Archive | ~500-550 MB |
| Final Installer (.exe) | ~620-640 MB |
| Installed Size | ~2.5-3.0 GB |

---

## 8. Testing & Validation

### 8.1 Smoke Test (5 minutes)

Quick check that the build is not broken:

1. Launch `BNC CAD.exe`
2. Create a new document
3. Switch to Part Design workbench
4. Create a sketch → draw a rectangle → pad it
5. Save the file → close → reopen
6. Verify the model is intact

### 8.2 BNC Feature Test (15 minutes)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1 | Assembly WB loads | Switch to Assembly workbench | Toolbar appears with BNC tools |
| 2 | Create New Part | Click BNC toolbar → Create New Part | Dialog with name/description fields |
| 3 | Insert from WD | Set working dir → Insert Component | File browser with thumbnails |
| 4 | Version Save | Open file → Version Save macro | Saved as `name.001.FCStd` |
| 5 | Generate Drawing | Open part → Run GenerateDrawing | TechDraw page created |
| 6 | BOM Export | Open assembly → Run BOM | Excel file generated |
| 7 | Apply Material | Select body → Run Apply_Material | Material dialog appears |
| 8 | Measure Mass | Select body → Run MeasureMass | Mass shown in report view |

### 8.3 Regression Test (30 minutes)

| # | Area | What to Test |
|---|------|-------------|
| 1 | File Formats | Open/save FCStd, import STEP, import IGES, export STL |
| 2 | Sketcher | Create sketch, add constraints, fully constrain |
| 3 | Part Design | Pad, pocket, fillet, chamfer, mirror, pattern |
| 4 | Assembly | Insert parts, add joints (fixed, revolute, slider), solve |
| 5 | TechDraw | Create page, add views, dimension, export PDF |
| 6 | FEM | Create analysis, mesh, run solver (if Calculix available) |
| 7 | Spreadsheet | Create spreadsheet, link to model parameters |
| 8 | Material | Assign material, check in property panel |
| 9 | Preferences | Change settings, restart, verify persistence |
| 10 | Branding | Splash, icon, about dialog, window title |

### 8.4 Install/Uninstall Test

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Fresh install on clean machine | Installs successfully, launches |
| 2 | Upgrade over previous version | Installs without error, settings preserved |
| 3 | Uninstall | Removes all files, registry keys, shortcuts |
| 4 | Reinstall after uninstall | Works like fresh install |
| 5 | Non-admin user launch | App launches (installed by admin) |

---

## 9. Publishing a Release on GitHub

### Option A: Manual Release (Recommended for now)

1. Go to: `https://github.com/Sanjai-Jayakumar/FreeCAD/releases`
2. Click **"Create a new release"**
3. Fill in:
   - **Tag**: Select the tag you pushed (e.g., `bnc-v1.1.1`)
   - **Target**: `bnc-1.1`
   - **Release title**: `BNC CAD v1.1.1`
   - **Description**: Use the template below
4. **Attach the installer**: Drag `BNC CAD.exe` into the "Attach binaries" area
5. Check **"Set as the latest release"**
6. If it's a pre-release (RC/beta), check **"Set as a pre-release"**
7. Click **"Publish release"**

### Release Notes Template

```markdown
## BNC CAD v1.1.1

### What's New
- [Brief description of changes]

### Bug Fixes
- fix(assembly): [description]
- fix(icons): [description]

### Improvements
- feat(macros): [description]
- build(installer): [description]

### Installation
1. Download `BNC CAD.exe` from the Assets below
2. Run as Administrator
3. Follow the installation wizard
4. Launch from Desktop shortcut or Start Menu

### System Requirements
- Windows 10/11 (64-bit)
- 4 GB RAM minimum (8 GB recommended)
- 3 GB free disk space
- OpenGL 3.0+ compatible graphics

### Notes
- No additional software installation required (VC++ Runtime bundled)
- Previous version will be upgraded automatically
```

### Option B: Automated Release (via GitHub Actions)

The workflow file `.github/workflows/bnc_release.yml` automates the GitHub Release
creation when you push a tag. See the workflow file for details.

To trigger:
```powershell
git tag -a bnc-v1.1.1 -m "BNC CAD v1.1.1 - patch release"
git push origin bnc-v1.1.1
```

> **Note**: The installer binary (~630 MB) must still be uploaded manually to the
> GitHub Release since it requires the Windows build machine. The automated workflow
> creates the release draft with notes pre-filled for you to attach the binary.

---

## 10. Post-Release Tasks

After publishing a release:

- [ ] Verify the GitHub Release page is visible and download link works
- [ ] Test downloading the installer from GitHub and installing on a clean machine
- [ ] Notify the team / manager that the release is available
- [ ] Update any internal wiki or documentation with the new version
- [ ] If critical issues are found, proceed with [Hotfix Process](#11-hotfix-process)
- [ ] Start planning the next release — create a milestone on GitHub

---

## 11. Hotfix Process

When a critical bug is found in a released version:

```
Release v1.1.1 (has bug)
    │
    ├─── Create branch: hotfix/bnc-v1.1.2
    │       │
    │       ├── Fix the bug
    │       ├── Test the fix
    │       ├── Commit: "fix(scope): description of fix"
    │       │
    │       └── Merge back to bnc-1.1
    │
    └─── Tag: bnc-v1.1.2
         └── Build → Test → Release
```

### Hotfix Commands

```powershell
# Create hotfix branch from the release tag
git checkout -b hotfix/bnc-v1.1.2 bnc-v1.1.1

# Fix the bug, commit
git add <files>
git commit -m "fix(assembly): resolve crash on joint solve with empty assembly"

# Merge back to main development branch
git checkout bnc-1.1
git merge hotfix/bnc-v1.1.2

# Tag and push
git tag -a bnc-v1.1.2 -m "BNC CAD v1.1.2 - hotfix for assembly crash"
git push origin bnc-1.1
git push origin bnc-v1.1.2

# Build and release (same as normal release, Steps 3-9)
```

---

## 12. Rollback Procedure

If a release has a critical issue and a hotfix is not immediately possible:

### Roll Back to Previous Version

1. Go to GitHub Releases: `https://github.com/Sanjai-Jayakumar/FreeCAD/releases`
2. Find the previous stable release (e.g., `bnc-v1.1.0`)
3. Distribute that installer to affected users
4. Instruct users to uninstall current version first, then install the older one

### Roll Back Git Tag

```powershell
# Remove the broken tag (locally and remotely)
git tag -d bnc-v1.1.1
git push origin --delete bnc-v1.1.1

# On GitHub, edit the release and mark as "Draft" or delete it
```

> **Warning**: Only delete tags/releases if no users have downloaded them yet.
> Otherwise, keep the release but mark it with a warning in the description.

---

## 13. Release Calendar

### Suggested Schedule

| Release Type | Frequency | Example |
|-------------|-----------|---------|
| Patch release | As needed (bug fixes) | v1.1.1, v1.1.2, ... |
| Minor release | Monthly or per feature milestone | v1.2.0, v1.3.0, ... |
| Major release | When rebasing to new FreeCAD version | v2.0.0 |
| RC / Beta | 1 week before stable release | v1.2.0-rc.1 |

### Release Lifecycle

```
Week 1-3:  Development (features + fixes on bnc-1.1)
Week 4:    Code Freeze → RC release (bnc-vX.Y.Z-rc.1)
           Internal testing with RC build
Week 5:    Stable Release (bnc-vX.Y.Z)
           Distribute to end users
```

---

## 14. Roles & Responsibilities

| Role | Responsibilities |
|------|-----------------|
| **Developer** | Write code, follow conventional commits, pass CI checks |
| **Release Manager** | Version bump, build, test, create GitHub release |
| **QA / Tester** | Run through test checklist, report bugs |
| **Manager** | Approve release, communicate to stakeholders |

For the current team, the **Developer** and **Release Manager** may be the same person.

---

## 15. Appendix: Command Reference

### Quick Reference: Full Release Commands

```powershell
# === 1. PREPARE ===
cd D:\BNC-FreeCAD
git checkout bnc-1.1
git pull origin bnc-1.1

# === 2. VERSION BUMP ===
# (Edit installer/BNC_CAD.nsi — update version numbers)
git add installer/BNC_CAD.nsi branding/system.cfg
git commit -m "build(release): bump version to 1.1.1"

# === 3. BUILD ===
& "C:\Program Files\CMake\bin\cmake.exe" --build build --config Release --parallel 16
& "C:\Program Files\CMake\bin\cmake.exe" --install build --config Release

# === 4. COPY ASSETS ===
Copy-Item "Macro\*" "C:\BNC-CAD-Output\Macro" -Recurse -Force
Copy-Item "installer\default_toolbar_layout.json" "C:\BNC-CAD-Output\" -Force

# === 5. CREATE INSTALLER ===
cd installer
& .\7zr.exe a -t7z -mx=9 -mfb=64 -md=32m -ms=on "BNC-CAD-Output.7z" "C:\BNC-CAD-Output\*"
& "C:\Program Files (x86)\NSIS\makensis.exe" BNC_CAD.nsi

# === 6. TEST ===
# (Run smoke test + BNC feature test on the built installer)

# === 7. TAG & PUSH ===
cd D:\BNC-FreeCAD
git tag -a bnc-v1.1.1 -m "BNC CAD v1.1.1 - description"
git push origin bnc-1.1
git push origin bnc-v1.1.1

# === 8. GITHUB RELEASE ===
# Go to: https://github.com/Sanjai-Jayakumar/FreeCAD/releases/new
# Select tag, write notes, attach installer binary, publish
```

### Git Tag Commands

```powershell
git tag -l "bnc-*"                          # List all BNC tags
git tag -a bnc-v1.1.1 -m "message"         # Create annotated tag
git push origin bnc-v1.1.1                  # Push tag to GitHub
git tag -d bnc-v1.1.1                       # Delete local tag
git push origin --delete bnc-v1.1.1         # Delete remote tag
git checkout bnc-v1.1.0                     # Checkout a specific release
```

---

*This document is maintained in the BNC CAD repository at `docs/RELEASE_PROCESS.md`.*
