# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _outer_wire_edges(face):
    """Return the outer-boundary edges of a face (multiple fallbacks)."""
    try:
        edges = face.OuterWire.Edges
        if edges:
            return list(edges)
    except Exception:
        pass
    try:
        wires = face.Wires
        if wires:
            best = max(wires, key=lambda w: w.BoundBox.DiagonalLength)
            edges = best.Edges
            if edges:
                return list(edges)
    except Exception:
        pass
    try:
        return list(face.Edges)
    except Exception:
        return []


def _vkey(pt, prec=2):
    f = 10.0 ** prec
    return (int(pt.x * f), int(pt.y * f), int(pt.z * f))


def _group_edges_into_loops(raw_edges):
    """Split a flat list of Part edges into connected components (one per hole)."""
    n = len(raw_edges)
    if n == 0:
        return []
    vtx_map = {}
    for i, e in enumerate(raw_edges):
        try:
            for v in e.Vertexes:
                vtx_map.setdefault(_vkey(v.Point), []).append(i)
        except Exception:
            pass
    adj = [set() for _ in range(n)]
    for lst in vtx_map.values():
        for a in lst:
            for b in lst:
                if a != b:
                    adj[a].add(b)
                    adj[b].add(a)
    visited = [False] * n
    groups = []
    for start in range(n):
        if not visited[start]:
            comp, stack = [], [start]
            while stack:
                node = stack.pop()
                if not visited[node]:
                    visited[node] = True
                    comp.append(node)
                    stack.extend(adj[node])
            groups.append([raw_edges[i] for i in comp])
    return groups


def _try_make_face(edges):
    """Try several strategies to fill a closed edge loop. Returns shape or None."""
    import Part
    edge_list = list(edges)
    if not edge_list:
        return None

    # Strategy 1: Wire → Part.Face  (planar holes)
    try:
        sorted_edges = Part.__sortEdges__(edge_list)
        wire = Part.Wire(sorted_edges)
        if wire.isClosed():
            face = Part.Face(wire)
            if not face.isNull():
                return face
    except Exception:
        pass

    # Strategy 2: makeFilledFace  (slightly non-planar)
    try:
        sorted_edges = Part.__sortEdges__(edge_list)
        wire = Part.Wire(sorted_edges)
        face = Part.makeFilledFace(wire.Edges)
        if not face.isNull():
            return face
    except Exception:
        pass

    return None


# ── Surface creation ──────────────────────────────────────────────────────────

def _create_shutoff_surfaces(face_refs, edge_refs):
    """Create one ShutOff Surface per hole.

    face_refs  — list of (obj, subname) where subname starts with 'Face'
                 Each face becomes one surface via its outer boundary wire.
    edge_refs  — list of (obj, subname) where subname starts with 'Edge'
                 Edges are grouped into connected loops; one surface per loop.

    Returns (n_created, message).
    """
    import Part
    doc = FreeCAD.ActiveDocument
    doc.openTransaction("Shut-Off Surface")
    created = 0
    failures = []

    shapes = []   # collect all hole surfaces — combined into one compound at the end

    # ── Face mode: each selected face → one surface ───────────────────────
    for obj, sub in face_refs:
        try:
            face_shape = obj.Shape.getElement(sub)
            edges = _outer_wire_edges(face_shape)
            shape = _try_make_face(edges) if edges else None
            if shape:
                shapes.append(shape)
                created += 1
            else:
                failures.append(sub)
        except Exception as _e:
            failures.append(f"{sub}: {_e}")

    # ── Edge mode: group connected edges → one surface per loop ──────────
    if edge_refs:
        raw = []
        for obj, sub in edge_refs:
            try:
                raw.append(obj.Shape.getElement(sub))
            except Exception:
                pass
        loops = _group_edges_into_loops(raw)
        for i, loop_edges in enumerate(loops):
            shape = _try_make_face(loop_edges)
            if shape:
                shapes.append(shape)
                created += 1
            else:
                failures.append(f"edge loop {i + 1}")

    if created > 0:
        # All surfaces combined into ONE compound → single model-tree entry
        import Part
        compound = Part.Compound(shapes) if len(shapes) > 1 else shapes[0]
        feat = doc.addObject("Part::Feature", "ShutOffSurface")
        feat.Label = "ShutOff Surface"
        feat.Shape = compound
        try:
            feat.ViewObject.ShapeColor   = (0.5, 0.8, 1.0)
            feat.ViewObject.Transparency = 40
        except Exception:
            pass
        doc.commitTransaction()
        doc.recompute()
        msg = f"Created {created} shut-off surface(s) in one feature."
        if failures:
            msg += f"\n{len(failures)} hole(s) failed: {', '.join(failures[:6])}"
        return True, msg
    else:
        try:
            doc.abortTransaction()
        except Exception:
            pass
        detail = "\n".join(failures[:10])
        return False, (
            "Could not create any shut-off surfaces.\n\n"
            "Tips:\n"
            "• Select faces of the regions to fill\n"
            "• Or select edges that form a closed boundary\n"
            "• Edges must form a complete closed loop\n\n"
            f"Details:\n{detail}"
        )


# ── Selection observer ────────────────────────────────────────────────────────

class _SelObserver:
    """Captures both Face and Edge clicks from the viewport."""

    def __init__(self, panel):
        self._panel = panel

    def addSelection(self, doc, obj_name, sub_name, pos):
        sub = str(sub_name).split(".")[-1]   # handle "Body.Face3" → "Face3"
        if not (sub.startswith("Face") or sub.startswith("Edge")):
            return
        try:
            obj = FreeCAD.getDocument(doc).getObject(obj_name)
            if obj and hasattr(obj, "Shape"):
                self._panel._add_selection(obj, sub)
        except Exception:
            pass

    def removeSelection(self, *a): pass
    def setSelection(self, *a):    pass
    def clearSelection(self, *a):  pass


# ── Task Panel ────────────────────────────────────────────────────────────────

class _ShutOffPanel:

    def __init__(self, src_obj):
        self._src_obj   = src_obj
        self._face_refs = []   # [(obj, subname), ...]  Face* selections
        self._edge_refs = []   # [(obj, subname), ...]  Edge* selections
        self._sel_obs   = None

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Shut-Off Surface")
        layout = QtWidgets.QVBoxLayout(self.form)

        info = QtWidgets.QLabel(
            "Select the faces or edges forming each closed boundary.\n"
            "Hold Ctrl to select multiple regions.\n"
            "One surface will be created per closed loop.")
        info.setWordWrap(True)
        info.setStyleSheet("font-size:11px;color:#333;padding:4px;")
        layout.addWidget(info)

        grp = QtWidgets.QGroupBox("Selected Regions")
        gl  = QtWidgets.QVBoxLayout(grp)
        self._sel_list = QtWidgets.QListWidget()
        self._sel_list.setMaximumHeight(140)
        gl.addWidget(self._sel_list)

        btn_row = QtWidgets.QHBoxLayout()
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        gl.addLayout(btn_row)
        layout.addWidget(grp)

        self._status = QtWidgets.QLabel(
            "Click faces or edges on the part to select closed boundaries.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "font-size:10px;color:#333;background:#ffffcc;"
            "border:1px solid #ccbb00;border-radius:3px;padding:4px;")
        layout.addWidget(self._status)
        layout.addStretch()

        self._sel_obs = _SelObserver(self)
        Gui.Selection.addObserver(self._sel_obs)

    def _add_selection(self, obj, sub_name):
        if sub_name.startswith("Face"):
            ref = (obj, sub_name)
            if ref not in self._face_refs:
                self._face_refs.append(ref)
                self._sel_list.addItem(f"  Face: {sub_name}")
        elif sub_name.startswith("Edge"):
            ref = (obj, sub_name)
            if ref not in self._edge_refs:
                self._edge_refs.append(ref)
                self._sel_list.addItem(f"  Edge: {sub_name}")
        n_faces = len(self._face_refs)
        n_edges = len(self._edge_refs)
        parts = []
        if n_faces:
            parts.append(f"{n_faces} face(s)")
        if n_edges:
            parts.append(f"{n_edges} edge(s)")
        self._status.setText(
            f"{', '.join(parts)} selected. Click OK to create surface(s).")

    def _clear(self):
        self._face_refs = []
        self._edge_refs = []
        self._sel_list.clear()
        self._status.setText("Cleared. Click faces or edges on the part.")

    def isAllowedAlterSelection(self): return True
    def isAllowedAlterView(self):      return True
    def isAllowedAlterDocument(self):  return False

    def accept(self):
        self._cleanup()
        if not self._face_refs and not self._edge_refs:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Shut-Off Surface",
                "Nothing selected.\n"
                "Click the faces or edges forming each closed boundary, then click OK.")
            Gui.Control.closeDialog()
            return
        ok, msg = _create_shutoff_surfaces(self._face_refs, self._edge_refs)
        if not ok:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Shut-Off Surface", msg)
        Gui.Control.closeDialog()

    def reject(self):
        self._cleanup()
        Gui.Control.closeDialog()

    def _cleanup(self):
        if self._sel_obs:
            try:
                Gui.Selection.removeObserver(self._sel_obs)
            except Exception:
                pass
            self._sel_obs = None


# ── Command ───────────────────────────────────────────────────────────────────

class CommandShutOffSurface:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldShutOff.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_ShutOffSurface", "Shut-Off Surface"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_ShutOffSurface",
                        "Create surfaces over open regions to separate core and cavity.\n"
                        "Select faces or edges forming each closed boundary, then click OK."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        # Check for pre-selected faces or edges
        sel = Gui.Selection.getSelectionEx()
        face_refs = []
        edge_refs = []
        src_obj   = None
        for s in sel:
            if not hasattr(s.Object, "Shape"):
                continue
            if not src_obj:
                src_obj = s.Object
            for sub in s.SubElementNames:
                sub_clean = sub.split(".")[-1]
                if sub_clean.startswith("Face"):
                    face_refs.append((s.Object, sub_clean))
                elif sub_clean.startswith("Edge"):
                    edge_refs.append((s.Object, sub_clean))

        if face_refs or edge_refs:
            ok, msg = _create_shutoff_surfaces(face_refs, edge_refs)
            if not ok:
                QtWidgets.QMessageBox.warning(
                    Gui.getMainWindow(), "Shut-Off Surface", msg)
            return

        # No pre-selection — open interactive task panel
        if not src_obj:
            for obj in FreeCAD.ActiveDocument.Objects:
                src = obj.Tip if (hasattr(obj, "Tip") and obj.Tip) else obj
                if hasattr(src, "Shape") and not src.Shape.isNull():
                    src_obj = obj
                    break

        if not src_obj:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Shut-Off Surface",
                "Please open or select a solid body first.")
            return

        try:
            Gui.Control.closeDialog()
        except Exception:
            pass

        panel = _ShutOffPanel(src_obj)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_ShutOffSurface", CommandShutOffSurface())
