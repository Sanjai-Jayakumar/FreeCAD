# SPDX-License-Identifier: LGPL-2.1-or-later
"""Core — SolidWorks-style task panel.

All three Selections boxes are interactive:
  • Click the ▶ arrow to activate picking for that box
  • Then click the sketch/face/body in the 3D viewport
  • Right-click a filled box → Delete to clear it
Only one pick mode is active at a time.
"""

import os, math
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore, QtGui
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_NAMED_DIRS = {
    "Auto":   None,
    "+Z":     FreeCAD.Vector(0,  0,  1),
    "-Z":     FreeCAD.Vector(0,  0, -1),
    "+Y":     FreeCAD.Vector(0,  1,  0),
    "-Y":     FreeCAD.Vector(0, -1,  0),
    "+X":     FreeCAD.Vector( 1, 0,  0),
    "-X":     FreeCAD.Vector(-1, 0,  0),
}


# ── Interactive selection box ──────────────────────────────────────────────────

class _PickObserver:
    """Captures the next viewport click and feeds it back to the owning box."""
    def __init__(self, box):
        self._box     = box
        self._pending = False

    def addSelection(self, doc, obj_name, sub_name, pos):
        if self._pending:
            return
        self._pending = True
        # Delay so FreeCAD finishes its own selection handling first
        QtCore.QTimer.singleShot(60, lambda: self._process(doc, obj_name, sub_name))

    def _process(self, doc, obj_name, sub_name):
        self._pending = False
        try:
            obj = FreeCAD.getDocument(doc).getObject(obj_name)
            if obj is None:
                return
            self._box._on_picked(obj, sub_name or "")
        except Exception:
            pass

    def removeSelection(self, *a): pass
    def setSelection(self, *a):    pass
    def clearSelection(self, *a):  pass


class _SelectionBox(QtWidgets.QWidget):
    """Arrow-button + label widget.  Click ▶ to enter pick mode, then click
    a viewport element; right-click the label to delete."""

    # (obj, sub_name) — sub_name is "" for whole-body picks
    picked = QtCore.Signal(object, str)

    PICK_STYLE  = ("QPushButton{background:#2266cc;color:white;font-weight:bold;"
                   "border-radius:3px;border:none;padding:2px 6px;}"
                   "QPushButton:hover{background:#3377dd;}")
    IDLE_STYLE  = ("QPushButton{background:#e0e0e0;color:#333;font-weight:bold;"
                   "border-radius:3px;border:1px solid #aaa;padding:2px 6px;}"
                   "QPushButton:hover{background:#d0d0d0;}")

    def __init__(self, accept, bg_color="#f5f5f5", placeholder="", parent=None):
        """
        accept: set of strings — "Sketch", "Face", "Edge", "Body"
        """
        super().__init__(parent)
        self._accept  = accept
        self._obj     = None
        self._sub     = ""
        self._obs     = None

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._btn = QtWidgets.QPushButton("▶")
        self._btn.setFixedSize(24, 24)
        self._btn.setCheckable(True)
        self._btn.setStyleSheet(self.IDLE_STYLE)
        self._btn.setToolTip("Click to start picking, then click in the 3D view")
        self._btn.toggled.connect(self._on_toggled)
        row.addWidget(self._btn)

        self._lbl = QtWidgets.QLineEdit()
        self._lbl.setReadOnly(True)
        self._lbl.setPlaceholderText(placeholder)
        self._lbl.setStyleSheet(
            f"background:{bg_color};border:1px solid #aaa;"
            f"border-radius:3px;padding:2px;")
        self._lbl.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._lbl.customContextMenuRequested.connect(self._ctx_menu)
        row.addWidget(self._lbl, 1)

    # ── Pick mode ─────────────────────────────────────────────────────────

    def _on_toggled(self, checked):
        if checked:
            self._btn.setStyleSheet(self.PICK_STYLE)
            self._btn.setText("●")
            self._obs = _PickObserver(self)
            Gui.Selection.addObserver(self._obs)
        else:
            self._btn.setStyleSheet(self.IDLE_STYLE)
            self._btn.setText("▶")
            self._deregister()

    def _deregister(self):
        if self._obs:
            try:
                Gui.Selection.removeObserver(self._obs)
            except Exception:
                pass
            self._obs = None

    def deactivate(self):
        """Called by the panel to ensure only one box is active at a time."""
        if self._btn.isChecked():
            self._btn.blockSignals(True)
            self._btn.setChecked(False)
            self._btn.setStyleSheet(self.IDLE_STYLE)
            self._btn.setText("▶")
            self._btn.blockSignals(False)
            self._deregister()

    def _on_picked(self, obj, sub_name):
        """Callback from the pick observer."""
        # Check if this pick matches what we accept
        accepted = False
        label    = ""
        face     = sub_name.split(".")[-1] if sub_name else ""

        if "Sketch" in self._accept and "Sketch" in obj.TypeId:
            accepted = True
            label    = obj.Label
        elif "Face" in self._accept and face.startswith("Face"):
            accepted = True
            label    = f"{obj.Label} › {face}"
        elif "Edge" in self._accept and face.startswith("Edge"):
            accepted = True
            label    = f"{obj.Label} › {face}"
        elif "Body" in self._accept and not face:
            accepted = True
            label    = obj.Label
        elif "Body" in self._accept and face:
            # Clicked sub-element of a body — use the body
            accepted = True
            label    = obj.Label
            sub_name = ""

        if accepted:
            self._obj = obj
            self._sub = sub_name
            self._lbl.setText(label)
            self.deactivate()
            self.picked.emit(obj, sub_name)

    # ── Context-menu delete ───────────────────────────────────────────────

    def _ctx_menu(self, pos):
        if self._obj:
            menu = QtWidgets.QMenu(self)
            act  = menu.addAction("Delete")
            if menu.exec_(self._lbl.mapToGlobal(pos)) == act:
                self._obj = None
                self._sub = ""
                self._lbl.clear()
                self.picked.emit(None, "")

    # ── Accessors ─────────────────────────────────────────────────────────

    def obj(self):  return self._obj
    def sub(self):  return self._sub


# ── Helpers ───────────────────────────────────────────────────────────────────

def _face_normal(obj, face_sub):
    try:
        fi   = int(face_sub[4:]) - 1
        face = obj.Shape.Faces[fi]
        umin, umax, vmin, vmax = face.ParameterRange
        n = face.normalAt((umin+umax)/2, (vmin+vmax)/2)
        if n.Length > 1e-10:
            return n.normalize()
    except Exception:
        pass
    return None


def _sketch_default_dir(sketch_obj):
    try:
        sup = getattr(sketch_obj, "AttachmentSupport", None) \
              or getattr(sketch_obj, "Support", None)
        if sup and len(sup) > 0:
            obj_ref, subs = sup[0]
            if subs and subs[0].startswith("Face"):
                n = _face_normal(obj_ref, subs[0])
                if n:
                    return n, f"{obj_ref.Label} › {subs[0]}", True
    except Exception:
        pass
    try:
        n = sketch_obj.Placement.Rotation.multVec(FreeCAD.Vector(0,0,1))
        if n.Length > 1e-10:
            return n.normalize(), "Sketch normal (InertialCS)", False
    except Exception:
        pass
    return FreeCAD.Vector(0,0,1), "+Z (default)", False


def _find_doc_feature(keywords):
    doc = FreeCAD.ActiveDocument
    if not doc: return None
    for obj in reversed(doc.Objects):
        lbl = obj.Label.lower(); nm = obj.Name.lower()
        if any(k in lbl or k in nm for k in keywords):
            return obj
    return None


def _compute_core_shape(sketch_obj, extrude_dir, depth):
    import Part
    wires = sketch_obj.Shape.Wires
    if not wires:
        raise ValueError("Sketch has no wires — make sure it is closed.")
    wire  = Part.Wire(Part.__sortEdges__(sketch_obj.Shape.Edges)) \
            if len(wires) > 1 else Part.Wire(wires[0])
    face  = Part.Face(wire)
    if face.isNull():
        raise ValueError("Cannot build face from sketch — check it is closed.")
    ev  = extrude_dir.normalize()
    return face.extrude(FreeCAD.Vector(ev.x*depth, ev.y*depth, ev.z*depth))


# ── Task Panel ────────────────────────────────────────────────────────────────

class _CorePanel:

    def __init__(self, sketch_obj, tooling_obj, extrude_dir, face_label,
                 is_face_normal, initial_status=None):
        self._extrude_dir  = extrude_dir
        self._preview_feat = None

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Core")
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.setSpacing(5)

        # ── Selections ────────────────────────────────────────────────────
        grp_sel = QtWidgets.QGroupBox("Selections")
        gl_sel  = QtWidgets.QFormLayout(grp_sel)
        gl_sel.setSpacing(6)

        self._sk_box = _SelectionBox(
            {"Sketch"}, "#fffde7", "Click ▶ then pick a sketch")
        if sketch_obj:
            self._sk_box._obj = sketch_obj
            self._sk_box._lbl.setText(sketch_obj.Label)
        self._sk_box.picked.connect(self._on_sketch_picked)
        self._sk_box._btn.toggled.connect(
            lambda c: self._deactivate_others(self._sk_box) if c else None)
        gl_sel.addRow("Sketch:", self._sk_box)

        self._fe_box = _SelectionBox(
            {"Face","Edge"}, "#e8f5e9", "Click ▶ then pick a face/edge")
        if face_label:
            self._fe_box._lbl.setText(face_label)
        self._fe_box.picked.connect(self._on_face_edge_picked)
        self._fe_box._btn.toggled.connect(
            lambda c: self._deactivate_others(self._fe_box) if c else None)
        gl_sel.addRow("Face / Edge:", self._fe_box)

        self._ts_box = _SelectionBox(
            {"Body"}, "#fce4ec", "Click ▶ then pick Core or Cavity body")
        if tooling_obj:
            self._ts_box._obj = tooling_obj
            self._ts_box._lbl.setText(tooling_obj.Label)
        self._ts_box._btn.toggled.connect(
            lambda c: self._deactivate_others(self._ts_box) if c else None)
        gl_sel.addRow("Tooling Split:", self._ts_box)

        layout.addWidget(grp_sel)

        # ── Direction + Flip ──────────────────────────────────────────────
        grp_dir     = QtWidgets.QGroupBox("Direction")
        warn_layout = QtWidgets.QVBoxLayout(grp_dir)   # grp_dir's real layout
        warn_layout.setSpacing(4)

        dir_row = QtWidgets.QHBoxLayout()              # no parent — added via addLayout
        dir_row.setSpacing(6)

        self._dir_combo = QtWidgets.QComboBox()
        self._dir_combo.addItems(list(_NAMED_DIRS.keys()))
        self._dir_combo.setToolTip(
            "Override direction.  Auto = from sketch or face.\n"
            "For InertialCS sketches use -Z or Flip ↕.")
        dir_row.addWidget(self._dir_combo, 1)

        self._flip_btn = QtWidgets.QPushButton("Flip ↕")
        self._flip_btn.setStyleSheet(
            "QPushButton{background:#cc4400;color:white;font-weight:bold;"
            "border-radius:4px;padding:4px 12px;}"
            "QPushButton:hover{background:#ee5500;}")
        self._flip_btn.setToolTip(
            "Reverse the extrusion direction.\n"
            "Click if the core appears on the wrong side.")
        self._flip_btn.clicked.connect(self._flip)
        dir_row.addWidget(self._flip_btn)

        warn_layout.addLayout(dir_row)
        if not is_face_normal:
            warn = QtWidgets.QLabel("⚠  InertialCS mode — Flip likely needed")
            warn.setStyleSheet("font-size:10px;color:#885500;")
            warn_layout.addWidget(warn)
        layout.addWidget(grp_dir)

        # ── Parameters ────────────────────────────────────────────────────
        grp_par = QtWidgets.QGroupBox("Parameters")
        gl_par  = QtWidgets.QFormLayout(grp_par)
        gl_par.setSpacing(5)

        self._draft_spin = QtWidgets.QDoubleSpinBox()
        self._draft_spin.setRange(0.0, 89.0); self._draft_spin.setDecimals(2)
        self._draft_spin.setValue(2.0); self._draft_spin.setSuffix("deg")
        gl_par.addRow("Draft:", self._draft_spin)

        self._draft_out = QtWidgets.QCheckBox("Draft outward")
        gl_par.addRow(self._draft_out)

        self._type1 = QtWidgets.QComboBox()
        self._type1.addItems(["Blind", "Through All"])
        self._type1.currentIndexChanged.connect(
            lambda i: self._depth_spin.setEnabled(
                self._type1.currentText() == "Blind"))
        gl_par.addRow("Type:", self._type1)

        self._depth_spin = QtWidgets.QDoubleSpinBox()
        self._depth_spin.setRange(0.1, 5000.0); self._depth_spin.setDecimals(2)
        self._depth_spin.setValue(10.0); self._depth_spin.setSuffix(" mm")
        gl_par.addRow("Depth (D1):", self._depth_spin)

        self._cap_ends = QtWidgets.QCheckBox("Cap ends")
        self._cap_ends.setChecked(True)
        gl_par.addRow(self._cap_ends)

        layout.addWidget(grp_par)

        # ── Mirror ────────────────────────────────────────────────────────
        grp_mir = QtWidgets.QGroupBox("Mirror")
        gl_mir  = QtWidgets.QVBoxLayout(grp_mir)
        self._mirror_chk = QtWidgets.QCheckBox("Mirror feature")
        self._mirror_chk.toggled.connect(
            lambda c: self._mirror_combo.setEnabled(c))
        gl_mir.addWidget(self._mirror_chk)
        mr = QtWidgets.QHBoxLayout()
        mr.addWidget(QtWidgets.QLabel("Plane:"))
        self._mirror_combo = QtWidgets.QComboBox()
        self._mirror_combo.addItems(["XY Plane", "XZ Plane", "YZ Plane"])
        self._mirror_combo.setEnabled(False)
        mr.addWidget(self._mirror_combo)
        gl_mir.addLayout(mr)
        layout.addWidget(grp_mir)

        # ── Preview ───────────────────────────────────────────────────────
        grp_pre = QtWidgets.QGroupBox("Preview")
        gl_pre  = QtWidgets.QVBoxLayout(grp_pre)
        self._preview_chk = QtWidgets.QCheckBox("Show preview in 3D view")
        self._preview_chk.setToolTip(
            "Shows a translucent orange preview of the core.\n"
            "Auto-removed on OK or Cancel.")
        self._preview_chk.toggled.connect(self._toggle_preview)
        gl_pre.addWidget(self._preview_chk)
        layout.addWidget(grp_pre)

        # ── Status ────────────────────────────────────────────────────────
        if initial_status:
            _default_msg = initial_status
        elif sketch_obj:
            _default_msg = (f"Sketch: {sketch_obj.Label}. "
                            "Click OK to create the core.")
        else:
            _default_msg = ("No sketch found — Core needs a closed sketch profile.\n"
                            "Click ▶ next to Sketch and pick a sketch in the 3D view.")
        self._status = QtWidgets.QLabel(_default_msg)
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "font-size:10px;color:#333;background:#ffffcc;"
            "border:1px solid #ccbb00;border-radius:3px;padding:4px;")
        layout.addWidget(self._status)
        layout.addStretch()

    # ── Selection callbacks ───────────────────────────────────────────────

    def _deactivate_others(self, active_box):
        """Ensure only one pick button is active at a time."""
        for box in (self._sk_box, self._fe_box, self._ts_box):
            if box is not active_box:
                box.deactivate()

    def _on_sketch_picked(self, obj, sub):
        if obj:
            # Update extrude direction from sketch
            n, lbl, is_face = _sketch_default_dir(obj)
            self._extrude_dir = n
            self._status.setText(f"Sketch set: {obj.Label}. Direction: {lbl}")

    def _on_face_edge_picked(self, obj, sub):
        if obj and sub and sub.startswith("Face"):
            n = _face_normal(obj, sub.split(".")[-1])
            if n:
                self._extrude_dir = n
                self._status.setText(
                    f"Direction set from {obj.Label} › {sub.split('.')[-1]}")
                if self._preview_chk.isChecked():
                    self._toggle_preview(True)

    # ── Direction helpers ─────────────────────────────────────────────────

    def _resolve_dir(self):
        key = self._dir_combo.currentText()
        if key == "Auto" or _NAMED_DIRS.get(key) is None:
            return self._extrude_dir
        return _NAMED_DIRS[key]

    def _flip(self):
        ev = self._extrude_dir
        self._extrude_dir = FreeCAD.Vector(-ev.x, -ev.y, -ev.z)
        self._status.setText(
            f"Direction flipped → ({self._extrude_dir.x:.2f}, "
            f"{self._extrude_dir.y:.2f}, {self._extrude_dir.z:.2f})")
        if self._preview_chk.isChecked():
            self._toggle_preview(True)

    # ── Preview ───────────────────────────────────────────────────────────

    def _toggle_preview(self, checked):
        self._remove_preview()
        sk = self._sk_box.obj()
        if checked and sk:
            try:
                depth = self._depth_spin.value() \
                        if self._type1.currentText() == "Blind" else 200.0
                shape = _compute_core_shape(sk, self._resolve_dir(), depth)
                doc = FreeCAD.ActiveDocument
                self._preview_feat = doc.addObject("Part::Feature", "_CorePreview")
                self._preview_feat.Shape = shape
                try:
                    self._preview_feat.ViewObject.ShapeColor  = (1.0, 0.55, 0.2)
                    self._preview_feat.ViewObject.Transparency = 65
                    self._preview_feat.ViewObject.LineColor    = (0.8, 0.3, 0.0)
                except Exception:
                    pass
                doc.recompute()
                self._status.setText("Preview shown — orange translucent solid.")
            except Exception as e:
                self._status.setText(f"Preview failed: {e}")

    def _remove_preview(self):
        if self._preview_feat:
            try:
                FreeCAD.ActiveDocument.removeObject(self._preview_feat.Name)
                FreeCAD.ActiveDocument.recompute()
            except Exception:
                pass
            self._preview_feat = None

    # ── Task panel interface ──────────────────────────────────────────────

    def isAllowedAlterSelection(self): return True
    def isAllowedAlterView(self):      return True
    def isAllowedAlterDocument(self):  return False

    def accept(self):
        self._remove_preview()
        # Deactivate all pick modes before closing
        for box in (self._sk_box, self._fe_box, self._ts_box):
            box.deactivate()

        sk = self._sk_box.obj()
        if not sk:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Core",
                "No sketch selected.\n"
                "Click ▶ next to Sketch, then click the sketch in the 3D view.")
            Gui.Control.closeDialog()
            return

        depth     = self._depth_spin.value() \
                    if self._type1.currentText() == "Blind" else None
        do_mirror = self._mirror_chk.isChecked()
        mirror_pl = self._mirror_combo.currentText() if do_mirror else None

        try:
            _execute_core(
                sk, self._resolve_dir(),
                depth, self._draft_spin.value(),
                self._draft_out.isChecked(),
                do_mirror, mirror_pl)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Core", f"Core creation failed:\n{e}")
        Gui.Control.closeDialog()

    def reject(self):
        self._remove_preview()
        for box in (self._sk_box, self._fe_box, self._ts_box):
            box.deactivate()
        Gui.Control.closeDialog()


# ── Core creation ─────────────────────────────────────────────────────────────

def _execute_core(sketch_obj, extrude_dir, depth, draft_deg, draft_out,
                  do_mirror, mirror_plane_name):
    import Part
    doc = FreeCAD.ActiveDocument
    if depth is None:
        bb = sketch_obj.Shape.BoundBox
        depth = max(bb.DiagonalLength * 2, 200.0)

    shape = _compute_core_shape(sketch_obj, extrude_dir, depth)

    if draft_deg > 0.01:
        try:
            ev = extrude_dir.normalize()
            shape = shape.makeDraft(
                [shape.Faces[0]],
                FreeCAD.Vector(-ev.x, -ev.y, -ev.z),
                math.radians(draft_deg),
                FreeCAD.Vector(0, 0, 0),
                not draft_out)
        except Exception:
            pass

    doc.openTransaction("Core")

    feat = doc.addObject("Part::Feature", "MoldCore")
    feat.Label = "Core"
    feat.Shape = shape
    try:
        feat.ViewObject.ShapeColor  = (1.0, 0.65, 0.35)
        feat.ViewObject.Transparency = 30
    except Exception:
        pass

    if do_mirror and mirror_plane_name:
        try:
            if "XY" in mirror_plane_name:
                mp, mn = FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1)
            elif "XZ" in mirror_plane_name:
                mp, mn = FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,1,0)
            else:
                mp, mn = FreeCAD.Vector(0,0,0), FreeCAD.Vector(1,0,0)
            mf = doc.addObject("Part::Feature", "MoldCore_Mirror")
            mf.Label = "Core (Mirrored)"
            mf.Shape = shape.mirror(mp, mn)
            try:
                mf.ViewObject.ShapeColor  = (1.0, 0.65, 0.35)
                mf.ViewObject.Transparency = 30
            except Exception:
                pass
        except Exception:
            pass

    doc.commitTransaction()
    doc.recompute()


# ── Command ───────────────────────────────────────────────────────────────────

class CommandCore:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldCore.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_Core", "Core"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_Core",
                        "Create a core pin or side-core from a bounding sketch."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument

        # ── Auto-detect sketch from selection, then document ──────────────
        sketch_obj = None
        for s in Gui.Selection.getSelectionEx():
            if "Sketch" in s.Object.TypeId and not s.Object.Shape.isNull():
                sketch_obj = s.Object; break
        if sketch_obj is None and doc:
            for obj in reversed(doc.Objects):
                if "Sketch" in obj.TypeId and not obj.Shape.isNull():
                    sketch_obj = obj; break

        extrude_dir    = FreeCAD.Vector(0, 0, 1)
        face_label     = None
        is_face_normal = False
        if sketch_obj:
            extrude_dir, face_label, is_face_normal = \
                _sketch_default_dir(sketch_obj)

        # ── Auto-detect tooling body: cavity/core → scale → any solid ─────
        tooling_obj = _find_doc_feature(
            ["moldcavity", "moldcore", "cavity", "core",
             "toolingsplit", "tooling split"])
        if tooling_obj is None:
            tooling_obj = _find_doc_feature(
                ["moldscale", "moldscale", "mold scale", "scale"])
        if tooling_obj is None and doc:
            # Fall back to the first solid body in the document
            for obj in reversed(doc.Objects):
                src = obj.Tip if (hasattr(obj, "Tip") and obj.Tip) else obj
                if hasattr(src, "Shape") and not src.Shape.isNull() \
                        and src.Shape.Volume > 0 \
                        and "Sketch" not in obj.TypeId \
                        and "Parting" not in obj.Label \
                        and "ShutOff" not in obj.Label:
                    tooling_obj = obj; break

        # Build an informative startup message
        parts = []
        if sketch_obj:
            parts.append(f"Sketch: {sketch_obj.Label}")
        else:
            parts.append("No sketch — click ▶ next to Sketch to pick one")
        if tooling_obj:
            parts.append(f"Body: {tooling_obj.Label} (auto-detected)")
        status_msg = "\n".join(parts)

        try:
            Gui.Control.closeDialog()
        except Exception:
            pass

        panel = _CorePanel(sketch_obj, tooling_obj, extrude_dir,
                           face_label, is_face_normal,
                           initial_status=status_msg)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_Core", CommandCore())
