# ANVIL CAD — Developer Setup & Claude AI Onboarding

> This document is for a new developer taking over the ANVIL CAD project.
> It covers the dev environment, key architecture, all active workbench features,
> and how to configure Claude Code to continue the work effectively.

---

## 1. What Is ANVIL CAD

ANVIL CAD is a **rebranded, extended build of FreeCAD 1.1** shipped by BNC Motors Pvt Ltd.
All customisations are Python files, SVGs, and macros — **no C++ compilation is ever needed**.

Key additions on top of stock FreeCAD 1.1:
- BNC branding (title bar, splash, theme, logo)
- BNC TechDraw toolbar (Generate Drawing, Fill Title Block, Insert Tolerance Table, Export PDF)
- BNC Mold Tools workbench (10 tools: Scale → Tooling Split)
- Assembly workbench patched with BNC commands
- Auto-update system
- Macro library (BOM, Family Table, Generate Drawing, etc.)

---

## 2. Repository Layout

```
d:\BNC-FreeCAD\
├── branding/               # system.cfg, themes, PreferencePacks
├── installer/              # NSIS .nsi script, 7z output
├── Macro/                  # All .FCMacro files synced to FreeCAD
├── Mod/
│   └── BNCTechDraw/        # TechDraw toolbar module + icons
├── scripts/
│   ├── dev_sync.ps1        # ← USE THIS EVERY TIME you change code
│   ├── apply_bnc.ps1       # Release-only full sync
│   └── dev_launch.ps1      # dev_sync + launch FreeCAD
└── src/
    ├── Mod/
    │   ├── BNC_Init/           # Title bar, version, macro loader
    │   ├── BNCCustomTools/     # Custom toolbar commands
    │   ├── BNCGlobal/          # Global helpers
    │   ├── BNCMCP/             # MCP integration
    │   ├── BNCMoldTools/       # Mold Tools workbench (main work area)
    │   ├── Start/              # BNC theme config, update checker, network check
    │   └── TechDraw/           # Patched TechDraw InitGui (BNC toolbar injection)
    └── Gui/
        └── PreferencePacks/    # BNC Light/Dark theme files
```

---

## 3. Dev Environment Setup

### Prerequisites
| Tool | Version | Notes |
|------|---------|-------|
| Windows 10/11 | — | All scripts are PowerShell |
| FreeCAD 1.1.x base build | 1.1.2 | Must be built or installed to `C:\BNC-CAD-Output` |
| Git | any | Repo at `d:\BNC-FreeCAD` |
| Claude Code CLI | latest | `npm install -g @anthropic-ai/claude-code` |

### First-time setup

1. **Clone the repo**
   ```powershell
   git clone <repo-url> d:\BNC-FreeCAD
   cd d:\BNC-FreeCAD
   ```

2. **Verify the FreeCAD base build exists**
   ```powershell
   Test-Path "C:\BNC-CAD-Output\bin\FreeCAD.exe"  # must return True
   ```
   If missing, ask the team for the base FreeCAD 1.1 build archive and extract to `C:\BNC-CAD-Output`.

3. **Run first sync**
   ```powershell
   .\scripts\dev_sync.ps1
   ```
   All lines should say `OK`. Then launch FreeCAD:
   ```powershell
   Start-Process "C:\BNC-CAD-Output\bin\FreeCAD.exe"
   ```

---

## 4. Daily Dev Workflow

```
Edit Python file  →  .\scripts\dev_sync.ps1  →  Restart FreeCAD  →  Test
```

- `dev_sync.ps1` copies changed files to `C:\BNC-CAD-Output` in ~2 seconds.
- Use `-Watch` flag for auto-reload on file save: `.\scripts\dev_sync.ps1 -Watch`
- **Never** edit files directly in `C:\BNC-CAD-Output` — they get overwritten on next sync.
- Only run `apply_bnc.ps1` + NSIS when making a release installer.

---

## 5. Key File Locations (Cheat Sheet)

| What to change | File |
|---|---|
| App version number | `src/Mod/Start/UpdateChecker.py` — `CURRENT_VERSION` |
| Title bar text | `src/Mod/BNC_Init/BNC_Init/InitGui.py` |
| TechDraw toolbar buttons | `Mod/BNCTechDraw/InitGui.py` + `src/Mod/TechDraw/InitGui.py` (lines 606-610) |
| TechDraw toolbar icons | `Mod/BNCTechDraw/icons/` |
| Macros | `Macro/*.FCMacro` |
| Mold Tools workbench | `src/Mod/BNCMoldTools/BNCMoldTools/` |
| BNC themes (QSS colours) | `branding/Stylesheets/parameters/*.yaml` |
| TechDraw page templates | `C:\BNC-CAD-Output\data\Mod\TechDraw\Templates\*_BNC_Template.svg` |

---

## 6. BNC Mold Tools Workbench

Located at `src/Mod/BNCMoldTools/BNCMoldTools/`. Each tool is one `Command*.py` file.

### Tool Status (as of June 2026)

| Tool | File | Status |
|------|------|--------|
| Scale | `CommandScale.py` | ✅ Working |
| Draft Analysis | `CommandDraftAnalysis.py` | ✅ Working (QThread, Coin3D overlay) |
| Draft | `CommandDraft.py` | ✅ Working |
| Split Line | `CommandSplitLine.py` | ✅ Working |
| Parting Line | `CommandPartingLine.py` | ✅ Working — `OuterWire.Edges` for face-click, face_boundary runs BEFORE sign-change |
| Shut-Off Surface | `CommandShutOffSurface.py` | ✅ Working — Face + Edge selections, one compound per selection set |
| Parting Surface | `CommandPartingSurface.py` | ✅ Working |
| Tooling Split | `CommandToolingSplit.py` | ✅ Working — QThread worker, cavity 30% transparent blue, core 30% transparent orange |
| Core | `CommandCore.py` | ✅ Working — auto-detects Cavity/Core/MoldScale/any solid |
| Undercut Analysis | `CommandUndercutAnalysis.py` | ✅ Working |

### Critical Tooling Split notes

- **Cavity** = lower block with basket exterior pocket, 30% blue transparency
- **Core** = flat plate + basket inner protrusion, 30% orange, `DisplayMode="Shaded"` (hides hole edges)
- `split_coord = min(detected, bb.ZMax)` — caps parting plane at part's actual top (prevents thin lid artefact)
- `removeInternalWires(maxArea)` used on core insert to close small through-holes
- `_compute_tooling_shapes()` runs in `QThread` (thread-safe geometry only)
- `_create_tooling_features()` runs on main thread (document writes only)
- After creation: `viewIsometric()` + `fitAll()` for correct default view

### Critical Parting Line note

Face boundary detection runs **before** sign-change candidates. If this order is reversed, "no parting edges found" error appears for top faces.

### Critical Shut-Off Surface note

`_SelObserver.addSelection()` handles both `Face*` and `Edge*` sub-element names. All collected shapes go into one `Part.Compound` → single model-tree entry.

### FreeCAD API gotchas (do not ignore)

| Gotcha | Rule |
|--------|------|
| `DiffuseColor` on `Part::Feature` | **Never use** — makes geometry render as wireframe in FreeCAD 1.1. Use Coin3D overlay instead. |
| Coin3D discretize | Use `discretize()` not `tessellate()` for edge point sampling |
| Coin3D SoSwitch off | Use `-1` not `SO_SWITCH_NONE` |
| `QHBoxLayout(parent)` inside a `QGroupBox` | Set layout on `QVBoxLayout(grp)` first, then add row with `addLayout(row)` — double-parent warning otherwise |

---

## 7. TechDraw Export PDF

The `ExportPDF.FCMacro` (in `Macro/`) is a clean PDF exporter that works around FreeCAD's broken hatch-pattern PDF code.

**Strategy (tried in order):**
1. Export page as SVG via FreeCAD's ViewObject API
2. Convert SVG → PDF using Microsoft Edge headless (best quality, no Acrobat errors)
3. Convert SVG → PDF using Qt `QSvgRenderer` + `QPdfWriter`
4. Native FreeCAD PDF export (fallback — known Acrobat warning)

If the auto SVG export fails, the macro prompts the user to:
- Use TechDraw → Export Page as SVG manually
- Then select that SVG file in the dialog
- The macro converts it via Edge

**Button location:** TechDraw workbench → BNC TechDraw toolbar → red PDF icon with blue arrow.

---

## 8. Setting Up Claude Code

### Install

```powershell
npm install -g @anthropic-ai/claude-code
```

Then in the repo directory:
```powershell
cd d:\BNC-FreeCAD
claude
```

### Memory system

Claude's memory for this project lives at:
```
C:\Users\{username}\.claude\projects\d--BNC-FreeCAD\memory\
```

The memory files give Claude context about the project so it doesn't need re-explaining each session. Key memory files:

| File | Contents |
|------|----------|
| `MEMORY.md` | Index of all memory files |
| `project_bnc_cad.md` | Version workflow, build vs dev, targets |
| `project_architecture.md` | Key file locations, FreeCAD internals |
| `feedback_workflow.md` | dev_sync iteration rule |
| `feedback_freecad_diffusecolor.md` | Never use DiffuseColor on Part::Feature |
| `feedback_freecad_coin3d.md` | Coin3D edge overlay rules |
| `project_draft_analysis.md` | Draft Analysis tool working state |
| `project_parting_line.md` | Parting Line tool working state |

When you start a new session, Claude automatically loads `MEMORY.md` and can read individual memory files on demand.

### Recommended first message to Claude in a new session

```
I'm continuing the ANVIL CAD project (d:\BNC-FreeCAD).
Please read the memory files to get context, then I'll describe what I need.
```

### What Claude can do in this project

- Edit Python files in `src/Mod/BNCMoldTools/`, `Macro/`, `Mod/BNCTechDraw/`
- Run `.\scripts\dev_sync.ps1` to sync and `Start-Process FreeCAD.exe` to restart
- Debug FreeCAD Python errors from screenshots or log output
- Add new toolbar commands, macros, or Mold Tools workbench features
- Work with FreeCAD's Part (BRep), TechDraw, and PartDesign APIs

### Things Claude should NOT do without asking

- Edit files in `C:\BNC-CAD-Output\` directly (always edit repo, then sync)
- Run `apply_bnc.ps1` or the NSIS build (release-only)
- Push to git remote without confirmation
- Delete or rename existing working tool commands

---

## 9. Active Issues / Known Limitations (June 2026)

| Issue | Status | Notes |
|-------|--------|-------|
| TechDraw PDF Acrobat error | Partially fixed | SVG→Edge path works; auto SVG export method name TBD |
| Core protrusion holes | Cosmetic | `DisplayMode="Shaded"` hides edge lines; through-holes geometrically present (need side cores) |
| Side cores | Not implemented | User said "side core later" — future feature |
| Tooling Split performance | Fixed | Now runs in QThread |

---

## 10. Useful Commands Reference

```powershell
# Sync changes and restart FreeCAD
.\scripts\dev_sync.ps1; Start-Process "C:\BNC-CAD-Output\bin\FreeCAD.exe"

# Watch mode (auto-sync on file save)
.\scripts\dev_sync.ps1 -Watch

# Check which Python packages are in FreeCAD's environment
C:\BNC-CAD-Output\bin\python.exe -c "import pkg_resources; print([p.project_name for p in pkg_resources.working_set])"

# Open ANVIL CAD directly
Start-Process "C:\BNC-CAD-Output\bin\FreeCAD.exe"

# Build release installer (admin required)
.\scripts\apply_bnc.ps1
makensis installer\BNC_CAD.nsi
```

---

## 11. Contact / Handover Notes

- **Previous developer**: Sanjai Jayakumar (git user)
- **Email on file**: Mathavan.N@bncmotors.in
- **Branch**: `bnc-1.1` (main development branch)
- **Base**: FreeCAD 1.1.1 merged in as `fe4a9b48e6`

All BNC work is in commits on `bnc-1.1`. The `main` branch tracks upstream FreeCAD.
