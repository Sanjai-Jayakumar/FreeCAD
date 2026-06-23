# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parting Surface — task panel with auto-detected Parting Line, distance and
pull-direction controls.  Matches SolidWorks Parting Surface workflow."""

import os
import math
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore, QtGui
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_AXIS_DIRS = {
    "+Z (Up)":    FreeCAD.Vector(0,  0,  1),
    "-Z (Down)":  FreeCAD.Vector(0,  0, -1),
    "+Y":         FreeCAD.Vector(0,  1,  0),
    "-Y":         FreeCAD.Vector(0, -1,  0),
    "+X":         FreeCAD.Vector( 1, 0,  0),
    "-X":         FreeCAD.Vector(-1, 0,  0),
}


# ── Surface builder ───────────────────────────────────────────────────────────

def _perp_offset(pt, ref_center, pull, dist):
    """Offset a point outward from ref_center in the parting plane (⊥ to pull)."""
    tx = pt.x - ref_center.x
    ty = pt.y - ref_center.y
    tz = pt.z - ref_center.z
    d  = tx*pull.x + ty*pull.y + tz*pull.z
    ox = tx - d*pull.x
    oy = ty - d*pull.y
    oz = tz - d*pull.z
    olen = (ox*ox + oy*oy + oz*oz) ** 0.5
    if olen < 1e-6:
        return FreeCAD.Vector(pt.x, pt.y, pt.z)   # no perpendicular component
    return FreeCAD.Vector(
        pt.x + (ox / olen) * dist,
        pt.y + (oy / olen) * dist,
        pt.z + (oz / olen) * dist,
    )


def _build_parting_surface(parting_shape, pull_dir, distance_mm, ref_center=None):
    """Build parting surface as a set of ruled-surface strips.

    For each parting-line edge:
      1. Discretise the edge into N points (inner curve).
      2. Offset every point outward from the part centre, perpendicular to pull
         (outer curve).  Each point gets its OWN radial direction so the strip
         fans out uniformly in the parting plane — not as a pinwheel.
      3. Build a ruled surface between inner and outer BSpline curves.

    The result lies flat in the parting plane (perpendicular to pull direction).
    """
    import Part

    pull  = pull_dir.normalize()
    edges = parting_shape.Edges

    if not edges:
        raise ValueError("Parting line has no edges.")

    # Parting-line centre (used as reference for outward direction)
    if ref_center is None:
        all_pts = []
        for e in edges:
            for v in e.Vertexes:
                all_pts.append(v.Point)
        if all_pts:
            cx = sum(p.x for p in all_pts) / len(all_pts)
            cy = sum(p.y for p in all_pts) / len(all_pts)
            cz = sum(p.z for p in all_pts) / len(all_pts)
            ref_center = FreeCAD.Vector(cx, cy, cz)
        else:
            ref_center = FreeCAD.Vector(0, 0, 0)

    surfaces = []

    for edge in edges:
        try:
            # More points → smoother surface (1 pt per 2 mm, min 8, max 60)
            n = max(8, min(60, int(edge.Length / 2.0)))
            raw  = edge.discretize(Number=n)

            inner_pts = [FreeCAD.Vector(p.x, p.y, p.z) for p in raw]
            outer_pts = [_perp_offset(p, ref_center, pull, distance_mm)
                         for p in inner_pts]

            # Build BSpline curves so makeRuledSurface can use them
            inner_bsp = Part.BSplineCurve()
            inner_bsp.interpolate(inner_pts)
            outer_bsp = Part.BSplineCurve()
            outer_bsp.interpolate(outer_pts)

            inner_edge = inner_bsp.toShape()
            outer_edge = outer_bsp.toShape()

            surf = Part.makeRuledSurface(inner_edge, outer_edge)
            if surf and not surf.isNull():
                surfaces.append(surf)

        except Exception:
            # Fallback to simple edge.extrude at the midpoint direction
            try:
                mp   = edge.discretize(Number=3)[1]
                mfv  = FreeCAD.Vector(mp.x, mp.y, mp.z)
                ofpt = _perp_offset(mfv, ref_center, pull, distance_mm)
                vec  = FreeCAD.Vector(ofpt.x - mfv.x,
                                      ofpt.y - mfv.y,
                                      ofpt.z - mfv.z)
                surfaces.append(edge.extrude(vec))
            except Exception:
                pass

    if not surfaces:
        raise ValueError("Could not create any parting surface strips.")

    return Part.Compound(surfaces)


# ── Helper: find parting line and reference solid ────────────────────────────

def _find_parting_and_solid():
    """Return (parting_obj, solid_obj) from the active document."""
    doc = FreeCAD.ActiveDocument
    if not doc:
        return None, None

    parting_obj = None
    solid_obj   = None

    # Priority: selected objects
    for s in Gui.Selection.getSelectionEx():
        obj = s.Object
        if parting_obj is None and ("PartingLine" in obj.Name or
                                    "Parting Line" in obj.Label):
            parting_obj = obj
        elif solid_obj is None and hasattr(obj, "Shape") \
                and not obj.Shape.isNull() and obj.Shape.Volume > 0 \
                and "Parting" not in obj.Name:
            solid_obj = obj

    # Fallback: scan document
    if parting_obj is None:
        for obj in doc.Objects:
            if "PartingLine" in obj.Name or obj.Label == "Parting Line":
                parting_obj = obj
                break

    if solid_obj is None:
        for obj in doc.Objects:
            if hasattr(obj, "Shape") and not obj.Shape.isNull() \
                    and obj.Shape.Volume > 0 and "Parting" not in obj.Name \
                    and "ShutOff" not in obj.Name:
                solid_obj = obj
                break

    return parting_obj, solid_obj


# ── Task Panel ────────────────────────────────────────────────────────────────

class _PartingSurfacePanel:
    def __init__(self, parting_obj, solid_obj):
        self._parting_obj = parting_obj
        self._solid_obj   = solid_obj

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Parting Surface")
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.setSpacing(6)

        # ── Parting Line input ────────────────────────────────────────────
        grp_pl = QtWidgets.QGroupBox("Parting Line")
        gl_pl  = QtWidgets.QFormLayout(grp_pl)

        self._pl_edit = QtWidgets.QLineEdit()
        self._pl_edit.setReadOnly(True)
        if parting_obj:
            self._pl_edit.setText(parting_obj.Label)
            self._pl_edit.setStyleSheet(
                "background:#c8ffc8;border:1px solid #007700;"
                "border-radius:3px;padding:2px;")
        else:
            self._pl_edit.setText("No Parting Line found")
            self._pl_edit.setStyleSheet(
                "background:#ffd0d0;border:1px solid #cc0000;"
                "border-radius:3px;padding:2px;")
        gl_pl.addRow("Source:", self._pl_edit)
        layout.addWidget(grp_pl)

        # ── Parting Surface parameters ─────────────────────────────────────
        grp_ps = QtWidgets.QGroupBox("Parting Surface")
        gl_ps  = QtWidgets.QFormLayout(grp_ps)

        self._dist_spin = QtWidgets.QDoubleSpinBox()
        self._dist_spin.setRange(1.0, 10000.0)
        self._dist_spin.setDecimals(2)
        self._dist_spin.setValue(60.0)
        self._dist_spin.setSuffix(" mm")
        self._dist_spin.setToolTip("How far the surface extends outward from the parting line")
        gl_ps.addRow("Extension:", self._dist_spin)

        self._dir_combo = QtWidgets.QComboBox()
        self._dir_combo.addItems(list(_AXIS_DIRS.keys()))
        self._dir_combo.setCurrentIndex(0)   # +Z (Up) default
        self._dir_combo.setToolTip("Mold opening (pull) direction")
        gl_ps.addRow("Pull direction:", self._dir_combo)

        layout.addWidget(grp_ps)

        # ── Status ─────────────────────────────────────────────────────────
        self._status = QtWidgets.QLabel(
            "Adjust the extension distance and pull direction, then click OK.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "font-size:10px;color:#333;background:#ffffcc;"
            "border:1px solid #ccbb00;border-radius:3px;padding:4px;")
        layout.addWidget(self._status)
        layout.addStretch()

    def isAllowedAlterSelection(self): return True
    def isAllowedAlterView(self):      return True
    def isAllowedAlterDocument(self):  return False

    def accept(self):
        if not self._parting_obj or not hasattr(self._parting_obj, "Shape") \
                or self._parting_obj.Shape.isNull():
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Parting Surface",
                "No valid Parting Line found.\n"
                "Run the Parting Line command first.")
            Gui.Control.closeDialog()
            return

        pull_dir  = _AXIS_DIRS[self._dir_combo.currentText()]
        distance  = self._dist_spin.value()

        # Reference centre from the solid body
        ref_center = None
        if self._solid_obj and hasattr(self._solid_obj, "Shape") \
                and not self._solid_obj.Shape.isNull():
            try:
                ref_center = self._solid_obj.Shape.BoundBox.Center
            except Exception:
                pass

        try:
            compound = _build_parting_surface(
                self._parting_obj.Shape, pull_dir, distance, ref_center)

            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Parting Surface")
            feat = doc.addObject("Part::Feature", "PartingSurface")
            feat.Label = "Parting Surface"
            feat.Shape = compound
            try:
                feat.ViewObject.ShapeColor  = (0.6, 0.78, 1.0)
                feat.ViewObject.Transparency = 45
                feat.ViewObject.LineColor    = (0.0, 0.25, 0.8)
            except Exception:
                pass
            doc.commitTransaction()
            doc.recompute()
        except Exception as e:
            try:
                FreeCAD.ActiveDocument.abortTransaction()
            except Exception:
                pass
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Parting Surface",
                f"Failed to create surface:\n{e}")

        Gui.Control.closeDialog()

    def reject(self):
        Gui.Control.closeDialog()


# ── Command ───────────────────────────────────────────────────────────────────

class CommandPartingSurface:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldPartingSurface.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_PartingSurface", "Parting Surface"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_PartingSurface",
                        "Create the surface separating core and cavity around the part exterior."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        parting_obj, solid_obj = _find_parting_and_solid()

        try:
            Gui.Control.closeDialog()
        except Exception:
            pass

        panel = _PartingSurfacePanel(parting_obj, solid_obj)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_PartingSurface", CommandPartingSurface())
