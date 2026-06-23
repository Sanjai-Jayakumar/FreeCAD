# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tooling Split — SolidWorks-style task panel.

Auto-detects Core (ShutOff), Cavity (ShutOff) and Parting Surface from the
document, shows them in labelled sections, and creates the Cavity and Core
mold blocks with the part pocket cut into each.
"""

import os
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore, QtGui
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")


# ── Document scanner ──────────────────────────────────────────────────────────

def _scan_document():
    """Return (part_obj, shutoff_objs, parting_surface_obj, parting_line_obj)."""
    doc = FreeCAD.ActiveDocument
    if not doc:
        return None, [], None, None

    part_obj           = None
    shutoff_objs       = []
    parting_surface_obj = None
    parting_line_obj   = None

    sel = Gui.Selection.getSelectionEx()
    for s in sel:
        obj = s.Object
        if hasattr(obj, "Shape") and not obj.Shape.isNull() \
                and obj.Shape.Volume > 0 and "Parting" not in obj.Name \
                and "ShutOff" not in obj.Name and "Core" not in obj.Name \
                and "Cavity" not in obj.Name:
            if part_obj is None:
                part_obj = obj

    for obj in doc.Objects:
        lbl = obj.Label.lower()
        nm  = obj.Name.lower()
        if "shutoff" in lbl or "shutoff" in nm or "shut-off" in lbl:
            shutoff_objs.append(obj)
        elif "partingsurface" in nm or "parting surface" in lbl \
                or lbl == "parting surface":
            parting_surface_obj = obj
        elif "partingline" in nm or lbl == "parting line" \
                or "parting line" in lbl:
            parting_line_obj = obj
        elif part_obj is None and hasattr(obj, "Shape") \
                and not obj.Shape.isNull() and obj.Shape.Volume > 0 \
                and "parting" not in lbl and "shutoff" not in lbl \
                and "core" not in lbl and "cavity" not in lbl:
            part_obj = obj

    return part_obj, shutoff_objs, parting_surface_obj, parting_line_obj


# ── Helper: coloured feature list widget ─────────────────────────────────────

def _make_feature_list(objs, color="#ccddff", empty_text="(none detected)"):
    lw = QtWidgets.QListWidget()
    lw.setMaximumHeight(72)
    lw.setStyleSheet(
        f"QListWidget {{ background: {color}; border: 1px solid #aaa; "
        f"border-radius: 3px; font-size: 11px; }}"
    )
    if objs:
        for o in objs:
            lw.addItem(o.Label)
    else:
        item = QtWidgets.QListWidgetItem(empty_text)
        item.setForeground(QtGui.QColor("#888888"))
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
        lw.addItem(item)
    return lw


# ── Task Panel ────────────────────────────────────────────────────────────────

class _ToolingSplitPanel:

    def __init__(self, part_obj, shutoff_objs, parting_surface_obj,
                 parting_line_obj):
        self._part_obj           = part_obj
        self._shutoff_objs       = shutoff_objs
        self._parting_surface_obj = parting_surface_obj
        self._parting_line_obj   = parting_line_obj

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Tooling Split")
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.setSpacing(4)

        # ── Block Size ────────────────────────────────────────────────────
        grp_bs = QtWidgets.QGroupBox("Block Size")
        gl_bs  = QtWidgets.QFormLayout(grp_bs)
        gl_bs.setSpacing(5)

        # Cavity depth (above parting)
        row_c = QtWidgets.QHBoxLayout()
        cav_icon = QtWidgets.QLabel("▲")
        cav_icon.setStyleSheet("color:#3377cc;font-weight:bold;font-size:14px;")
        cav_icon.setFixedWidth(20)
        row_c.addWidget(cav_icon)
        self._cav_spin = QtWidgets.QDoubleSpinBox()
        self._cav_spin.setRange(1.0, 5000.0)
        self._cav_spin.setDecimals(2)
        self._cav_spin.setValue(35.0)
        self._cav_spin.setSuffix(" mm")
        self._cav_spin.setToolTip("Block height above parting surface (Cavity half)")
        row_c.addWidget(self._cav_spin)
        gl_bs.addRow("Cavity depth:", row_c)

        # Core depth (below parting)
        row_r = QtWidgets.QHBoxLayout()
        core_icon = QtWidgets.QLabel("▼")
        core_icon.setStyleSheet("color:#cc6622;font-weight:bold;font-size:14px;")
        core_icon.setFixedWidth(20)
        row_r.addWidget(core_icon)
        self._core_spin = QtWidgets.QDoubleSpinBox()
        self._core_spin.setRange(1.0, 5000.0)
        self._core_spin.setDecimals(2)
        self._core_spin.setValue(90.0)
        self._core_spin.setSuffix(" mm")
        self._core_spin.setToolTip("Block height below parting surface (Core half)")
        row_r.addWidget(self._core_spin)
        gl_bs.addRow("Core depth:", row_r)

        self._interlock_chk = QtWidgets.QCheckBox("Interlock surface")
        self._interlock_chk.setToolTip(
            "Add interlocking geometry to guide mold halves together")
        gl_bs.addRow(self._interlock_chk)

        # Split axis
        self._axis_combo = QtWidgets.QComboBox()
        self._axis_combo.addItems(["Z (vertical)", "Y", "X"])
        gl_bs.addRow("Split Axis:", self._axis_combo)

        layout.addWidget(grp_bs)

        # ── Core section ─────────────────────────────────────────────────
        grp_core = QtWidgets.QGroupBox("Core")
        gl_core  = QtWidgets.QVBoxLayout(grp_core)
        gl_core.setSpacing(2)
        gl_core.addWidget(_make_feature_list(
            [o for o in shutoff_objs],
            color="#fff4e0"))
        layout.addWidget(grp_core)

        # ── Cavity section ────────────────────────────────────────────────
        grp_cav = QtWidgets.QGroupBox("Cavity")
        gl_cav  = QtWidgets.QVBoxLayout(grp_cav)
        gl_cav.setSpacing(2)
        gl_cav.addWidget(_make_feature_list(
            [o for o in shutoff_objs],
            color="#e8f0ff"))
        layout.addWidget(grp_cav)

        # ── Parting Surface section ───────────────────────────────────────
        grp_ps = QtWidgets.QGroupBox("Parting Surface")
        gl_ps  = QtWidgets.QVBoxLayout(grp_ps)
        gl_ps.setSpacing(2)
        ps_list = _make_feature_list(
            [parting_surface_obj] if parting_surface_obj else [],
            color="#f0e8ff")
        gl_ps.addWidget(ps_list)
        layout.addWidget(grp_ps)

        # ── Status ────────────────────────────────────────────────────────
        status_text = "Ready." if part_obj else \
            "⚠ No solid body found. Select the scaled body first."
        self._status = QtWidgets.QLabel(status_text)
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
        if not self._part_obj or not hasattr(self._part_obj, "Shape") \
                or self._part_obj.Shape.isNull():
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Tooling Split",
                "No solid body found.\n"
                "Select the scaled/solid body and re-run Tooling Split.")
            Gui.Control.closeDialog()
            return

        cav_depth = self._cav_spin.value()
        core_depth = self._core_spin.value()
        axis       = self._axis_combo.currentText()

        Gui.Control.closeDialog()

        # Show progress dialog — heavy geometry runs in a background thread
        prog = _ProgressDlg(Gui.getMainWindow())
        worker = _ToolingSplitWorker(
            self._part_obj, self._shutoff_objs,
            self._parting_surface_obj, self._parting_line_obj,
            cav_depth, core_depth, axis)

        def _on_done(cavity_shape, core_shape):
            prog.accept()
            _create_tooling_features(
                cavity_shape, core_shape,
                self._part_obj, self._shutoff_objs,
                self._parting_surface_obj, self._parting_line_obj)

        def _on_error(msg):
            prog.accept()
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Tooling Split",
                f"Tooling split failed:\n{msg}")

        worker.finished.connect(_on_done)
        worker.error_occurred.connect(_on_error)
        worker.start()
        prog.exec_()

    def reject(self):
        Gui.Control.closeDialog()


# ── Background worker + progress dialog ──────────────────────────────────────

class _ProgressDlg(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tooling Split…")
        self.setWindowFlags(
            QtCore.Qt.Dialog |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint)
        self.setFixedSize(340, 90)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "Computing cavity and core — please wait…"))
        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 0)   # indeterminate / marquee
        layout.addWidget(bar)

    def closeEvent(self, ev):
        ev.ignore()


class _ToolingSplitWorker(QtCore.QThread):
    finished      = QtCore.Signal(object, object)   # cavity_shape, core_shape
    error_occurred = QtCore.Signal(str)

    def __init__(self, part_obj, shutoff_objs, parting_surface_obj,
                 parting_line_obj, cav_depth, core_depth, axis):
        super().__init__()
        self._part_obj            = part_obj
        self._shutoff_objs        = list(shutoff_objs)
        self._parting_surface_obj = parting_surface_obj
        self._parting_line_obj    = parting_line_obj
        self._cav_depth           = cav_depth
        self._core_depth          = core_depth
        self._axis                = axis

    def run(self):
        try:
            cavity_shape, core_shape = _compute_tooling_shapes(
                self._part_obj, self._shutoff_objs,
                self._parting_surface_obj, self._parting_line_obj,
                self._cav_depth, self._core_depth, self._axis)
            self.finished.emit(cavity_shape, core_shape)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ── Core tooling split logic ──────────────────────────────────────────────────

def _compute_tooling_shapes(part_obj, shutoff_objs, parting_surface_obj,
                             parting_line_obj, cav_depth, core_depth, axis):
    """Compute cavity and core shapes (geometry only — safe to run in a thread).
    Returns (cavity_shape, core_shape).

    Split coordinate priority:
      1. Parting Line bbox (most accurate — at the actual parting edge)
      2. Parting Surface bbox centre
      3. Part bbox MAX along the pull axis (parting at the open top of the part)

    Block footprint = parting surface extent (or part bbox) + 5 % margin on each side.
    This matches the SolidWorks Tooling Split behaviour shown in the reference images.
    """
    import Part
    shape = part_obj.Shape
    bb    = shape.BoundBox

    def _bbox_coord(bbox_obj, ax, use_max=False):
        """Return mid (or max) coordinate along the requested axis."""
        b = bbox_obj.Shape.BoundBox
        if ax == "Z (vertical)":
            return b.ZMax if use_max else (b.ZMin + b.ZMax) / 2.0
        if ax == "Y":
            return b.YMax if use_max else (b.YMin + b.YMax) / 2.0
        return b.XMax if use_max else (b.XMin + b.XMax) / 2.0

    # ── Determine parting split coordinate ───────────────────────────────
    # The split plane must be AT the part's outermost face along the pull axis
    # (bb.ZMax for +Z pull).  Using a value ABOVE that leaves a thin solid "lid"
    # over the basket void in the cavity — the cavity then appears closed.
    #
    # We read parting line / parting surface to guide the split, but always
    # cap the result at the part's own bbox maximum so the cavity stays open.

    if axis == "Z (vertical)":
        part_max = bb.ZMax
    elif axis == "Y":
        part_max = bb.YMax
    else:
        part_max = bb.XMax

    split_coord = None

    # 1. Parting Line bbox maximum (closest to the real parting edge)
    if parting_line_obj and hasattr(parting_line_obj, "Shape") \
            and not parting_line_obj.Shape.isNull():
        try:
            split_coord = _bbox_coord(parting_line_obj, axis, use_max=True)
        except Exception:
            pass

    # 2. Parting Surface bbox maximum
    if split_coord is None and parting_surface_obj \
            and hasattr(parting_surface_obj, "Shape") \
            and not parting_surface_obj.Shape.isNull():
        try:
            split_coord = _bbox_coord(parting_surface_obj, axis, use_max=True)
        except Exception:
            pass

    # 3. Fallback: part's outermost face
    if split_coord is None:
        split_coord = part_max

    # ── Cap at part_max so the cavity void is always open at the parting face ─
    # Any overshoot (parting surface fillet / rounding) leaves a solid lid;
    # clamping here eliminates it.
    split_coord = min(split_coord, part_max)

    # ── Block footprint: use parting surface extent + margin ─────────────
    margin = max(bb.DiagonalLength * 0.05, 10.0)

    # Start from part bbox
    fx0, fx1 = bb.XMin - margin, bb.XMax + margin
    fy0, fy1 = bb.YMin - margin, bb.YMax + margin
    fz0, fz1 = bb.ZMin - margin, bb.ZMax + margin

    # Expand to include the parting surface footprint
    for surf_obj in [parting_surface_obj, parting_line_obj]:
        if surf_obj and hasattr(surf_obj, "Shape") \
                and not surf_obj.Shape.isNull():
            try:
                sb = surf_obj.Shape.BoundBox
                fx0 = min(fx0, sb.XMin - margin)
                fx1 = max(fx1, sb.XMax + margin)
                fy0 = min(fy0, sb.YMin - margin)
                fy1 = max(fy1, sb.YMax + margin)
            except Exception:
                pass

    # ── Build mold blocks ─────────────────────────────────────────────────
    if axis == "Z (vertical)":
        cavity_box = Part.makeBox(
            fx1 - fx0, fy1 - fy0, cav_depth,
            FreeCAD.Vector(fx0, fy0, split_coord))
        core_box = Part.makeBox(
            fx1 - fx0, fy1 - fy0, core_depth,
            FreeCAD.Vector(fx0, fy0, split_coord - core_depth))
    elif axis == "Y":
        cavity_box = Part.makeBox(
            fx1 - fx0, cav_depth, fz1 - fz0,
            FreeCAD.Vector(fx0, split_coord, fz0))
        core_box = Part.makeBox(
            fx1 - fx0, core_depth, fz1 - fz0,
            FreeCAD.Vector(fx0, split_coord - core_depth, fz0))
    else:  # X
        cavity_box = Part.makeBox(
            cav_depth, fy1 - fy0, fz1 - fz0,
            FreeCAD.Vector(split_coord, fy0, fz0))
        core_box = Part.makeBox(
            core_depth, fy1 - fy0, fz1 - fz0,
            FreeCAD.Vector(split_coord - core_depth, fy0, fz0))

    # ── Boolean cut ───────────────────────────────────────────────────────
    #
    # CAVITY (lower block):
    #   Cut by basket first, then each ShutOff individually — avoids
    #   non-manifold failures from fusing all tools into one.
    #   All basket exterior features + hole features live here.
    #
    # CORE (upper block):
    #   Flat plate + basket protrusion with through-holes FILLED.
    #   The basket solid has physical holes; we fill them by creating
    #   solid cylinders at each ShutOff surface location (ShutOff surfaces
    #   mark every hole with its centre, radius and normal direction).
    #   Result: basket profile on core with no visible holes.

    import math as _math

    # ── Cavity ────────────────────────────────────────────────────────────
    try:
        cavity_shape = core_box.cut(shape)
    except Exception:
        cavity_shape = core_box

    for so in shutoff_objs:
        if hasattr(so, "Shape") and not so.Shape.isNull():
            try:
                cavity_shape = cavity_shape.cut(so.Shape)
            except Exception:
                pass

    # ── Core: flat plate + basket protrusion with holes filled ───────────
    # 1. Actual basket shape below parting (shape.common) = correct profile.
    # 2. Fill every through-hole with an exact-fit cylinder (radius + 0.1 mm,
    #    height = hole wall thickness + 0.3 mm margin each end).
    # 3. Clip the filled insert to the EXACT basket bbox — this:
    #    a) removes any pipe artefacts that extend outside the basket walls,
    #    b) forces fill-cylinder end faces to be coplanar with the basket
    #       outer faces so OCCT merges them → no visible hole circles.
    # 4. Fuse into core plate (compound fallback if fuse fails).

    try:
        part_insert = shape.common(core_box)
    except Exception:
        part_insert = None

    if part_insert is not None and not part_insert.isNull():
        # ── Close through-holes using removeInternalWires ─────────────
        # This removes small closed wires (hole outlines) from every face
        # in the shell, closing the openings without expensive booleans.
        try:
            total_area = sum(f.Area for f in part_insert.Faces)
            max_hole   = total_area * 0.003   # threshold: holes < 0.3% of total area
            cleaned    = part_insert.removeInternalWires(max_hole)
            if not cleaned.isNull():
                if cleaned.Volume > 1e-6:
                    part_insert = cleaned
                else:
                    solid = Part.makeSolid(cleaned)
                    if not solid.isNull() and solid.Volume > 1e-6:
                        part_insert = solid
        except Exception:
            pass   # not available in this FreeCAD build — holes remain

    # ── Fuse protrusion into core plate ──────────────────────────────────
    if part_insert is not None and not part_insert.isNull() \
            and part_insert.Volume > 1e-6:
        try:
            core_shape = cavity_box.fuse(part_insert)
            if core_shape.isNull():
                raise ValueError("null")
        except Exception:
            core_shape = Part.makeCompound([cavity_box, part_insert])
    else:
        core_shape = cavity_box

    return cavity_shape, core_shape


def _create_tooling_features(cavity_shape, core_shape,
                              part_obj, shutoff_objs,
                              parting_surface_obj, parting_line_obj):
    """Create FreeCAD document features from pre-computed shapes (main thread)."""
    doc = FreeCAD.ActiveDocument
    doc.openTransaction("Tooling Split")

    cav_feat = doc.addObject("Part::Feature", "MoldCavity")
    cav_feat.Label = "Cavity"
    cav_feat.Shape = cavity_shape
    try:
        cav_feat.ViewObject.ShapeColor   = (0.55, 0.75, 1.0)   # blue
        cav_feat.ViewObject.Transparency = 30   # see-through so basket pocket depth is visible
    except Exception:
        pass

    core_feat = doc.addObject("Part::Feature", "MoldCore")
    core_feat.Label = "Core"
    core_feat.Shape = core_shape
    try:
        core_feat.ViewObject.ShapeColor   = (1.0, 0.65, 0.35)
        core_feat.ViewObject.Transparency = 30
        core_feat.ViewObject.DisplayMode  = "Shaded"  # hide all edge lines incl. hole circles
    except Exception:
        pass

    hide_list = ([part_obj, parting_surface_obj, parting_line_obj]
                 + list(shutoff_objs))
    for obj in hide_list:
        if obj is not None:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass

    doc.commitTransaction()
    doc.recompute()

    # Set view to look from above-isometric so the basket pocket in the
    # cavity is immediately visible (like the SolidWorks reference view)
    try:
        import FreeCADGui as _Gui
        v = _Gui.ActiveDocument.ActiveView
        v.viewIsometric()
        v.fitAll()
    except Exception:
        pass


def _execute_tooling_split(part_obj, shutoff_objs, parting_surface_obj,
                            parting_line_obj, cav_depth, core_depth, axis):
    """Synchronous entry point (kept for compatibility)."""
    cavity_shape, core_shape = _compute_tooling_shapes(
        part_obj, shutoff_objs, parting_surface_obj, parting_line_obj,
        cav_depth, core_depth, axis)
    _create_tooling_features(cavity_shape, core_shape,
                              part_obj, shutoff_objs,
                              parting_surface_obj, parting_line_obj)


# ── Command ───────────────────────────────────────────────────────────────────

class CommandToolingSplit:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldToolingSplit.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_ToolingSplit", "Tooling Split"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_ToolingSplit",
                        "Create solid Cavity and Core mold bodies by splitting a tool block."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        part_obj, shutoff_objs, parting_surface_obj, parting_line_obj = \
            _scan_document()

        try:
            Gui.Control.closeDialog()
        except Exception:
            pass

        panel = _ToolingSplitPanel(part_obj, shutoff_objs,
                                   parting_surface_obj, parting_line_obj)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_ToolingSplit", CommandToolingSplit())
