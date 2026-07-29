# BNCClassA — GUI Smoke Test

Deploy with `.\scripts\dev_sync.ps1`, launch `C:\BNC-CAD-Output\bin\FreeCAD.exe`,
switch to the **Class-A Surface** workbench. Build the test scene by running
`docs/make_test_scene.py` in the Python console (it creates `PatchA_reference`,
`PatchB_broken` — a jittered neighbor — and a `Profile` CV curve).

Headless math tests (run before any GUI session):

```powershell
& "C:\BNC-CAD-Output\bin\FreeCADCmd.exe" "<repo>\src\Mod\BNCClassA\BNCClassA\tests\run_all.py"
```

Expected: `43 tests, 0 failures`.

## The key end-to-end sequence

1. Select a face of `PatchA_reference` + Ctrl-select the adjacent face of
   `PatchB_broken` → **Continuity Check** → all three rows FAIL (the jitter).
2. Pick PatchB's edge nearest PatchA, Ctrl-pick PatchA's matching edge →
   **Match Surface**, continuity G2 → Apply → the "Achieved" row must show
   ~0 mm / ~0° / ~0 rel, and re-running **Continuity Check** shows green PASS.
3. Select both faces → **Zebra** → stripes must flow across the joint without
   kinks or jumps while orbiting the camera.

## Per-command checklist

| Command | Steps | Expected |
|---|---|---|
| CV Curve | toolbar → click 4 points in the 3D view | curve + grey CV hull appears after 4th click |
| Edit Curve | select a CVCurve → command → drag a CV | curve follows live; Shift/X/Y/Z modifiers work; one undo step per drag |
| Rebuild Curve | select any sketch/edge → command | deviation shown before OK; result is a CV curve |
| Blend Curve | pick two curve ends → command | G2 blend appears; StartContinuity/Tension editable in properties |
| Project Curve | select curve + face → command | projected CV curve lies on the face |
| Extract Isoparm | select a face → command → move slider | orange preview line sweeps the face; OK creates the curve |
| Extrude | select Profile → command, +Z, 50 mm | CV surface; ShowHull displays a 4×4 net |
| Revolve | select Profile → command, 90° | surface of revolution; approximation error printed in console |
| Loft | select 2-3 curves in order → command | surface through the sections |
| Birail | select profile + 2 rails → command | swept surface, fit deviation in status |
| Square Patch | pick 4 connected boundary edges | patch appears; per-edge continuity in properties |
| Freeform Blend | pick one edge on each of two faces | blend strip; zebra flows across both joints |
| Class-A Fillet | select 2 intersecting faces, radius | fillet strip between contact curves |
| Edit Surface | select CVSurface → command → drag CVs | Shift drags a whole row; detach-at-isoparm splits into 2 patches |
| Match Surface | (see key sequence above) | achieved G0/G1/G2 reported after Apply |
| Extend | pick a boundary edge of a CVSurface | surface grows past that edge, no visible seam under zebra |
| Trim / Untrim | CVSurface + closed curve on it | trimmed face; CV editing still works; Untrim restores |
| Rebuild Surface | select any imported/native face | single-span CV surface + deviation |
| Mirror | select CVSurface (near a plane), XZ | mirrored copy; seam G2-clean when "force seam" checked (verify with Continuity Check) |
| Bake | select a BlendSurface/SquarePatch | replaced by an editable CVSurface |
| Curvature Comb | select an edge | teeth + envelope; scale/density sliders live |
| Zebra | select faces | stripes; count/width/angle sliders update instantly |
| Highlight Lines | select object → compute | white HLR lines; line count changes with spinner |
| Curvature Map | select faces | blue-grey-red map; mode switch instant |
| Env Map | select faces | studio reflection; scene combo switches |
| Continuity Check | 2 faces (+optional shared edge) | table min/max/mean + green/red ticks in 3D + CSV export |
| Deviation | 2 objects | rainbow distance map + measured range |
| Draft Analysis | (reused from Mold Tools) | opens the BNCMold draft analysis panel |

## Notes / known v1 limits

- Match Surface and Square Patch expect untrimmed single-span CV surfaces on
  the surface being modified (use Rebuild Surface first for imported faces).
- Rebuild Surface samples the untrimmed host surface (trims ignored).
- Deviation distances are point-cloud sampled (resolution follows quality).
- Revolve above 120° should be built as two segments (warning shown).
