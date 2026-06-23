# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import math
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_AXIS_DIRS = {
    "+Z (Up)":    FreeCAD.Vector(0, 0,  1),
    "-Z (Down)":  FreeCAD.Vector(0, 0, -1),
    "+Y":         FreeCAD.Vector(0,  1,  0),
    "-Y":         FreeCAD.Vector(0, -1,  0),
    "+X":         FreeCAD.Vector( 1, 0,  0),
    "-X":         FreeCAD.Vector(-1, 0,  0),
}

_overlays = {}   # doc_name -> (coin_node, list_of_src_objs, edge_switch)


# ─── Threshold-aware mold colour ──────────────────────────────────────────────

def _dot_to_mold_color(dot, dot_threshold=0.052):
    """Saturated mold analysis colour matching Creo 5-band scale:
      Deep blue → medium blue-purple → neutral grey (0°) → light pink → coral red.
      Saturates at ±threshold so scale max = +draft_min, min = -draft_min."""
    t = max(-1.0, min(1.0, float(dot)))
    thr = max(0.001, float(dot_threshold))
    norm = max(-1.0, min(1.0, t / thr))
    EXP = 0.55
    if norm >= 0:
        f = norm ** EXP
        # Neutral grey (0) → medium blue-purple (mid) → deep blue (max)
        r = 0.73 - f * 0.42   # 0.73 → 0.31
        g = 0.73 - f * 0.30   # 0.73 → 0.43
        b = 0.76 + f * 0.10   # 0.76 → 0.86
        return (r, g, b)
    else:
        f = (-norm) ** EXP
        # Neutral grey (0) → light pink (mid) → coral red (max)
        r = 0.73 + f * 0.17   # 0.73 → 0.90
        g = 0.73 - f * 0.43   # 0.73 → 0.30
        b = 0.76 - f * 0.46   # 0.76 → 0.30
        return (r, g, b)

def _dot_to_creo_color(dot):
    return _dot_to_mold_color(dot)




# ─── Face normal ─────────────────────────────────────────────────────────────

def _face_normal_from_shape(face):
    try:
        umin, umax, vmin, vmax = face.ParameterRange
        us, vs = umax - umin, vmax - vmin
        for uf, vf in ((0.5,0.5),(0.25,0.5),(0.5,0.25),(0.75,0.5),(0.5,0.75)):
            try:
                n = face.normalAt(umin + uf*us, vmin + vf*vs)
                if n.Length > 1e-10:
                    return n.normalize()
            except Exception:
                pass
    except Exception:
        pass
    try:
        pts, tris = face.tessellate(1.0)
        for tri in tris:
            if len(tri) < 3:
                continue
            p1, p2, p3 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
            ax,ay,az = p2.x-p1.x,p2.y-p1.y,p2.z-p1.z
            bx,by,bz = p3.x-p1.x,p3.y-p1.y,p3.z-p1.z
            nx=ay*bz-az*by; ny=az*bx-ax*bz; nz=ax*by-ay*bx
            nlen=(nx*nx+ny*ny+nz*nz)**0.5
            if nlen>1e-10:
                return FreeCAD.Vector(nx/nlen,ny/nlen,nz/nlen)
    except Exception:
        pass
    return None


def _extract_face_normal_from_selection():
    try:
        for sel in Gui.Selection.getSelectionEx():
            for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
                st = getattr(sub_obj, "ShapeType", "")
                if st == "Face":
                    n = _face_normal_from_shape(sub_obj)
                    if n:
                        return n, f"{sel.ObjectName} › {sub}"
                if "Face" in str(sub) and st in ("Compound","Shell","Solid",""):
                    try:
                        fname = next(p for p in reversed(str(sub).split("."))
                                     if p.startswith("Face"))
                        face = sub_obj.getElement(fname)
                        if face and getattr(face,"ShapeType","") == "Face":
                            n = _face_normal_from_shape(face)
                            if n:
                                return n, f"{sel.ObjectName} › {fname}"
                    except Exception:
                        pass
            for sub in sel.SubElementNames:
                if "Face" not in str(sub):
                    continue
                fname = next((p for p in reversed(str(sub).split("."))
                              if p.startswith("Face")), None)
                if fname is None:
                    continue
                try:
                    obj = sel.Object
                    src = obj.Tip if (hasattr(obj,"Tip") and obj.Tip) else obj
                    if hasattr(src,"Shape"):
                        face = src.Shape.getElement(fname)
                        n = _face_normal_from_shape(face)
                        if n:
                            return n, f"{sel.ObjectName} › {fname}"
                except Exception:
                    pass
    except Exception:
        pass
    return None, None


# ─── Coin3D overlay ───────────────────────────────────────────────────────────

def _clear_overlay(doc_name):
    if doc_name not in _overlays:
        return
    node, src_objs, _es = _overlays.pop(doc_name)
    try:
        from pivy import coin
        sg = Gui.ActiveDocument.ActiveView.getSceneGraph()
        if sg.findChild(node) >= 0:
            sg.removeChild(node)
    except Exception:
        pass
    for obj in src_objs:
        try:
            obj.ViewObject.Visibility = True
        except Exception:
            pass
    Gui.updateGui()


def _build_overlay(shapes, pull_dir, draft_min_deg, quality=7):
    from pivy import coin
    from PySide.QtWidgets import QApplication
    px, py, pz = pull_dir.x, pull_dir.y, pull_dir.z
    plen = (px*px + py*py + pz*pz) ** 0.5
    if plen > 1e-10:
        px /= plen; py /= plen; pz /= plen

    tol = max(0.5, 4.0 - quality * 0.35)
    dot_thr = math.sin(math.radians(draft_min_deg))

    all_verts = []; vert_colors = []; coord_idx = []; mat_idx = []
    v_offset = 0; face_processed = 0

    for shape in shapes:
        for face in shape.Faces:
            try:
                pts, tris = face.tessellate(tol)
                if not pts or not tris:
                    continue
                n_pts = len(pts)

                # ── Per-vertex normals from tessellation triangles ──────────
                # Uses the face's own triangles (always inside trimmed boundary).
                # Face-center normal used as orientation reference so all vertex
                # normals stay consistent — no cross-face blending, no UV
                # out-of-bounds artefacts on trimmed/NURBS faces.
                ref_nx = ref_ny = ref_nz = 0.0
                ref_dot = 0.0
                try:
                    umin, umax, vmin, vmax = face.ParameterRange
                    for uf, vf in ((0.5,0.5),(0.3,0.5),(0.5,0.3),(0.7,0.5),(0.5,0.7)):
                        try:
                            rn = face.normalAt(umin+uf*(umax-umin),
                                               vmin+vf*(vmax-vmin))
                            if rn.Length > 1e-10:
                                rn = rn.normalize()
                                ref_nx, ref_ny, ref_nz = rn.x, rn.y, rn.z
                                ref_dot = max(-1.0, min(1.0,
                                    rn.x*px + rn.y*py + rn.z*pz))
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

                # Accumulate per-vertex normals from triangle cross-products
                v_nx = [0.0]*n_pts; v_ny = [0.0]*n_pts; v_nz = [0.0]*n_pts
                v_cnt = [0]*n_pts
                for tri in tris:
                    if len(tri) < 3:
                        continue
                    p1, p2, p3 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
                    ax = p2.x-p1.x; ay = p2.y-p1.y; az = p2.z-p1.z
                    bx = p3.x-p1.x; by = p3.y-p1.y; bz = p3.z-p1.z
                    nx = ay*bz-az*by; ny = az*bx-ax*bz; nz = ax*by-ay*bx
                    nlen = (nx*nx+ny*ny+nz*nz)**0.5
                    if nlen < 1e-10:
                        continue
                    nx /= nlen; ny /= nlen; nz /= nlen
                    # Flip to match face centre reference
                    if ref_nx*nx + ref_ny*ny + ref_nz*nz < 0:
                        nx = -nx; ny = -ny; nz = -nz
                    for vi in tri:
                        v_nx[vi] += nx; v_ny[vi] += ny; v_nz[vi] += nz
                        v_cnt[vi] += 1

                local_start = len(vert_colors)
                for i in range(n_pts):
                    all_verts.append((pts[i].x, pts[i].y, pts[i].z))
                    cnt = v_cnt[i]
                    if cnt > 0:
                        nx = v_nx[i]/cnt; ny = v_ny[i]/cnt; nz = v_nz[i]/cnt
                        nlen = (nx*nx+ny*ny+nz*nz)**0.5
                        if nlen > 1e-10:
                            nx /= nlen; ny /= nlen; nz /= nlen
                        dot = max(-1.0, min(1.0, nx*px+ny*py+nz*pz))
                        vert_colors.append(_dot_to_mold_color(dot, dot_thr))
                    else:
                        vert_colors.append(_dot_to_mold_color(ref_dot, dot_thr))

                for tri in tris:
                    if len(tri) < 3:
                        continue
                    i0 = v_offset + tri[0]; i1 = v_offset + tri[1]; i2 = v_offset + tri[2]
                    coord_idx.extend([i0, i1, i2, -1])
                    mat_idx.extend([local_start+tri[0], local_start+tri[1],
                                    local_start+tri[2], -1])
                v_offset += n_pts
                face_processed += 1
                if face_processed % 50 == 0:
                    QApplication.processEvents()
                if v_offset > 200_000:
                    break
            except Exception:
                pass
        if v_offset > 200_000:
            break

    if not all_verts:
        return coin.SoSeparator()

    root=coin.SoSeparator()
    lm=coin.SoLightModel(); lm.model.setValue(coin.SoLightModel.BASE_COLOR); root.addChild(lm)
    hints=coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    root.addChild(hints)
    poff=coin.SoPolygonOffset()
    poff.styles.setValue(coin.SoPolygonOffset.FILLED)
    poff.factor.setValue(10.0); poff.units.setValue(10.0)
    root.addChild(poff)
    bc=coin.SoBaseColor()
    bc.rgb.setValues(0,len(vert_colors),vert_colors)
    root.addChild(bc)
    mb=coin.SoMaterialBinding()
    mb.value.setValue(coin.SoMaterialBinding.PER_VERTEX_INDEXED)
    root.addChild(mb)
    coords=coin.SoCoordinate3()
    coords.point.setValues(0,len(all_verts),all_verts)
    root.addChild(coords)
    ifs=coin.SoIndexedFaceSet()
    ifs.coordIndex.setValues(0,len(coord_idx),coord_idx)
    ifs.materialIndex.setValues(0,len(mat_idx),mat_idx)
    root.addChild(ifs)

    # ── Geometric edge lines — shape.Edges only, white for contrast ──────
    # Only the real BRep feature edges (same as FreeCAD Flat Lines shows).
    # White is visible against both blue (negative) and red (positive) faces.
    # Scale 1.003 from BBox centre pushes edges just outside the face surface
    # to prevent z-fighting without any polygon offset tricks.
    edge_switch = coin.SoSwitch()
    edge_switch.whichChild.setValue(-1)   # -1 = SO_SWITCH_NONE, OFF by default

    esep = coin.SoSeparator()
    elm  = coin.SoLightModel(); elm.model.setValue(coin.SoLightModel.BASE_COLOR)
    esep.addChild(elm)

    # Dark lines — visible on all 5 colour bands including white/yellow
    ebc = coin.SoBaseColor(); ebc.rgb.setValue(0.15, 0.15, 0.15)
    esep.addChild(ebc)
    eds = coin.SoDrawStyle(); eds.lineWidth.setValue(1.5)
    esep.addChild(eds)

    # Scale slightly outward from BBox centre to avoid z-fighting
    all_bb = [s.BoundBox for s in shapes]
    cx = sum(b.Center.x for b in all_bb) / len(all_bb) if all_bb else 0.0
    cy = sum(b.Center.y for b in all_bb) / len(all_bb) if all_bb else 0.0
    cz = sum(b.Center.z for b in all_bb) / len(all_bb) if all_bb else 0.0
    etrans = coin.SoTransform()
    etrans.center.setValue(cx, cy, cz)
    etrans.scaleFactor.setValue(1.003, 1.003, 1.003)
    esep.addChild(etrans)

    # discretize() is reliable for all edge types (lines, circles, splines)
    all_ep = []; edge_ns = []
    n_pts = max(8, int(20 / max(tol, 0.5)))   # more points for finer quality
    for shape in shapes:
        for edge in shape.Edges:
            try:
                epts = edge.discretize(Number=n_pts)
                if not epts:
                    epts = [edge.Vertexes[0].Point, edge.Vertexes[-1].Point]
                if len(epts) >= 2:
                    for v in epts: all_ep.append((v.x, v.y, v.z))
                    edge_ns.append(len(epts))
            except Exception:
                pass

    if all_ep:
        ec = coin.SoCoordinate3(); ec.point.setValues(0, len(all_ep), all_ep)
        esep.addChild(ec)
        els = coin.SoLineSet(); els.numVertices.setValues(0, len(edge_ns), edge_ns)
        esep.addChild(els)

    edge_switch.addChild(esep)
    root.addChild(edge_switch)
    return root, edge_switch


def _compute_stats(shapes, pull_dir, draft_min):
    """Fast stats — one normal sample per BRep face, no tessellation."""
    px,py,pz=pull_dir.x,pull_dir.y,pull_dir.z
    plen=(px*px+py*py+pz*pz)**0.5
    if plen>1e-10: px/=plen; py/=plen; pz/=plen
    total=adequate=0; mn=mx=0.0
    for shape in shapes:
        for face in shape.Faces:
            try:
                umin,umax,vmin,vmax=face.ParameterRange
                n=face.normalAt((umin+umax)/2,(vmin+vmax)/2)
                if n.Length<1e-10: continue
                n=n.normalize()
            except Exception:
                continue
            dot=max(-1.0,min(1.0,n.x*px+n.y*py+n.z*pz))
            d=90.0-math.degrees(math.acos(dot))
            total+=1
            if d>=draft_min: adequate+=1
            mn=min(mn,d); mx=max(mx,d)
    pct=(adequate/total*100.0) if total else 0.0
    return pct,mn,mx


def _run_analysis(src_objs, shapes, pull_dir, draft_min, quality, doc_name):
    try:
        from pivy import coin
    except ImportError:
        return None,None,None
    if doc_name in _overlays:
        old_node, _, _es = _overlays.pop(doc_name)
        try:
            sg=Gui.ActiveDocument.ActiveView.getSceneGraph()
            if sg.findChild(old_node)>=0: sg.removeChild(old_node)
        except Exception:
            pass
    try:
        # Keep objects VISIBLE — required so FreeCAD face-picking works for hover
        node, edge_switch = _build_overlay(shapes, pull_dir, draft_min, quality)
        Gui.ActiveDocument.ActiveView.getSceneGraph().addChild(node)
        _overlays[doc_name] = (node, list(src_objs), edge_switch)
        Gui.updateGui()
        pct, mn, mx = _compute_stats(shapes, pull_dir, draft_min)
        return pct, mn, mx
    except Exception:
        return None, None, None


# ─── Selection observers ──────────────────────────────────────────────────────

class _SurfaceObserver:
    def __init__(self, panel):
        self._panel = panel
    def addSelection(self, doc, obj_name, sub_name, pos):
        try:
            obj=FreeCAD.getDocument(doc).getObject(obj_name)
            shape_src=obj.Tip if (hasattr(obj,"Tip") and obj.Tip) else obj
            if hasattr(shape_src,"Shape") and not shape_src.Shape.isNull():
                self._panel._on_surface_picked(obj)
        except Exception:
            pass
    def removeSelection(self,*a): pass
    def setSelection(self,*a): pass
    def clearSelection(self,*a): pass


class _DirectionObserver:
    def __init__(self, panel):
        self._panel=panel; self._pending=False
    def addSelection(self, doc, obj_name, sub_name, pos):
        if self._pending: return
        self._pending=True
        QtCore.QTimer.singleShot(50,self._process)
    def _process(self):
        self._pending=False
        n,label=_extract_face_normal_from_selection()
        if n:
            try:
                self._panel._dir_btn.blockSignals(True)
                self._panel._dir_btn.setChecked(False)
                self._panel._dir_btn.setText("Select")
                self._panel._dir_btn.blockSignals(False)
                self._panel._dir_active=False
                for obj in self._panel._src_objs:
                    try: obj.ViewObject.Visibility=False
                    except Exception: pass
            except Exception:
                pass
            self._panel._stop_dir_obs()
            self._panel._set_direction(n, label)
    def removeSelection(self,*a): pass
    def setSelection(self,*a): pass
    def clearSelection(self,*a): pass


# ─── Always-on direction observer ────────────────────────────────────────────

class _AlwaysOnDirObserver:
    """Any face click in the viewport auto-sets the pull direction.
    Active as long as the Draft Analysis panel is open.
    Skips if an explicit surf/dir Select mode is already active."""
    def __init__(self, panel):
        self._panel = panel
        self._pending = False

    def addSelection(self, doc, obj_name, sub_name, pos):
        if self._pending:
            return
        # Defer to explicit observers if active
        if self._panel._surf_obs is not None or self._panel._dir_obs is not None:
            return
        if "Face" not in str(sub_name):
            return
        self._pending = True
        QtCore.QTimer.singleShot(50, self._process)

    def _process(self):
        self._pending = False
        n, label = _extract_face_normal_from_selection()
        if n:
            self._panel._set_direction(n, label)

    def removeSelection(self, *a): pass
    def setSelection(self, *a):    pass
    def clearSelection(self, *a):  pass


# ─── Task Panel ───────────────────────────────────────────────────────────────

def _compute_face_draft(face, pull_dir):
    """Return draft angle in degrees for a single BRep face."""
    try:
        umin, umax, vmin, vmax = face.ParameterRange
        n = face.normalAt((umin + umax) / 2, (vmin + vmax) / 2)
        if n.Length < 1e-10:
            return None
        n = n.normalize()
        pd = pull_dir
        plen = (pd.x**2 + pd.y**2 + pd.z**2) ** 0.5
        if plen < 1e-10:
            return None
        dot = max(-1.0, min(1.0,
                  (n.x*pd.x + n.y*pd.y + n.z*pd.z) / plen))
        return math.degrees(math.asin(dot))
    except Exception:
        return None


class _DraftAnalysisPanel:
    def __init__(self, initial_objs, doc_name):
        self._doc_name=doc_name
        self._src_objs=list(initial_objs)
        self._shapes=self._resolve_shapes(self._src_objs)
        self._pull_dir=FreeCAD.Vector(0,0,1)
        self._flipped=False
        self._surf_obs=None; self._dir_obs=None; self._dir_active=False
        self._always_dir_obs=None
        self._preview_timer=QtCore.QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._run_preview)

        self.form=QtWidgets.QWidget()
        self.form.setWindowTitle("Draft Analysis")
        layout=QtWidgets.QVBoxLayout(self.form)

        grp_s=QtWidgets.QGroupBox("Surface")
        gl_s=QtWidgets.QFormLayout(grp_s)
        srow=QtWidgets.QHBoxLayout()
        self._surf_edit=QtWidgets.QLineEdit()
        self._surf_edit.setPlaceholderText("Select items")
        self._surf_edit.setReadOnly(True)
        self._surf_edit.setStyleSheet("background:#d0eeff;border:1px solid #0070c0;border-radius:3px;padding:2px;")
        srow.addWidget(self._surf_edit)
        self._surf_btn=QtWidgets.QPushButton("Select")
        self._surf_btn.setCheckable(True)
        self._surf_btn.toggled.connect(self._toggle_surf)
        srow.addWidget(self._surf_btn)
        gl_s.addRow("Surface:",srow)
        layout.addWidget(grp_s)
        if self._src_objs:
            self._surf_edit.setText(", ".join(o.Label for o in self._src_objs))
            self._surf_edit.setStyleSheet("background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")

        grp_d=QtWidgets.QGroupBox("Direction")
        gl_d=QtWidgets.QFormLayout(grp_d)
        drow=QtWidgets.QHBoxLayout()
        self._dir_edit=QtWidgets.QLineEdit()
        self._dir_edit.setPlaceholderText("Click any face in the 3D view…")
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setStyleSheet("background:#d0eeff;border:1px solid #0070c0;border-radius:3px;padding:2px;")
        drow.addWidget(self._dir_edit)
        self._flip_btn=QtWidgets.QPushButton("Flip"); self._flip_btn.clicked.connect(self._flip)
        drow.addWidget(self._flip_btn)
        self._dir_btn=QtWidgets.QPushButton("Select")
        self._dir_btn.setCheckable(True)
        self._dir_btn.toggled.connect(self._toggle_dir)
        drow.addWidget(self._dir_btn)
        gl_d.addRow("Direction:",drow)
        self._axis_combo=QtWidgets.QComboBox()
        self._axis_combo.addItems(list(_AXIS_DIRS.keys()))
        self._axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        gl_d.addRow("Or axis:",self._axis_combo)

        # Hint label
        _hint=QtWidgets.QLabel(
            "Click any face to set pull direction  |  Use axis dropdown for +Z/-Z mold directions")
        _hint.setStyleSheet(
            "color:#555;font-size:10px;font-style:italic;padding:1px 0;")
        _hint.setWordWrap(True)
        gl_d.addRow(_hint)
        layout.addWidget(grp_d)

        # ── Default: +Z (Up) axis so analysis is meaningful on first open ──
        # Silently block the signal so we don't trigger _on_axis_changed before
        # the rest of the UI is built.
        self._axis_combo.blockSignals(True)
        default_idx = list(_AXIS_DIRS.keys()).index("+Z (Up)")
        self._axis_combo.setCurrentIndex(default_idx)
        self._axis_combo.blockSignals(False)
        self._pull_dir = _AXIS_DIRS["+Z (Up)"]
        self._dir_edit.setText("+Z (Up)")
        self._dir_edit.setStyleSheet(
            "background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")

        grp_p=QtWidgets.QGroupBox("Parameters")
        gl_p=QtWidgets.QFormLayout(grp_p)
        self._draft_spin=QtWidgets.QDoubleSpinBox()
        self._draft_spin.setRange(0.0,89.9); self._draft_spin.setDecimals(2)
        self._draft_spin.setValue(3.0)
        self._draft_spin.valueChanged.connect(self._on_param_changed)
        gl_p.addRow("Draft:",self._draft_spin)
        self._sample_combo=QtWidgets.QComboBox()
        self._sample_combo.addItems(["Quick","Quality"])
        self._sample_combo.setCurrentIndex(1)
        self._sample_combo.currentIndexChanged.connect(self._on_param_changed)
        gl_p.addRow("Sample:",self._sample_combo)
        qrow=QtWidgets.QHBoxLayout()
        self._qual_slider=QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._qual_slider.setRange(1,10); self._qual_slider.setValue(7)
        self._qual_slider.valueChanged.connect(self._on_quality_changed)
        qrow.addWidget(self._qual_slider)
        self._qual_lbl=QtWidgets.QLabel("7.00"); self._qual_lbl.setFixedWidth(36)
        qrow.addWidget(self._qual_lbl)
        gl_p.addRow("Quality:",qrow)
        self._auto_chk = QtWidgets.QCheckBox("Auto-update"); self._auto_chk.setChecked(True)
        gl_p.addRow(self._auto_chk)

        self._lines_chk = QtWidgets.QCheckBox("Show edge lines")
        self._lines_chk.setChecked(False)
        self._lines_chk.toggled.connect(self._toggle_lines)
        gl_p.addRow(self._lines_chk)

        layout.addWidget(grp_p)

        self._results = QtWidgets.QTextEdit()
        self._results.setReadOnly(True); self._results.setFixedHeight(65)
        self._results.setPlaceholderText("Run analysis to see results…")
        layout.addWidget(self._results)

        # ── Dynamic colour scale (updates with Draft threshold) ────────────
        from PySide.QtGui import QPixmap, QPainter, QColor, QLinearGradient
        from PySide.QtCore import QRectF

        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 0, 0)
        scale_row.setSpacing(4)

        self._scale_bar_lbl = QtWidgets.QLabel()
        self._scale_bar_lbl.setFixedWidth(22)
        scale_row.addWidget(self._scale_bar_lbl)

        self._scale_tick_col = QtWidgets.QWidget()
        self._scale_tick_layout = QtWidgets.QVBoxLayout(self._scale_tick_col)
        self._scale_tick_layout.setSpacing(0)
        self._scale_tick_layout.setContentsMargins(0, 0, 0, 0)
        scale_row.addWidget(self._scale_tick_col)
        scale_row.addStretch()
        layout.addLayout(scale_row)

        self._redraw_scale(self._draft_spin.value())
        self._draft_spin.valueChanged.connect(self._redraw_scale)

        # ── Hover draft label ───────────────────────────────────────────────
        self._hover_lbl = QtWidgets.QLabel(
            "<i>Hover over part to see draft angle</i>")
        self._hover_lbl.setStyleSheet(
            "font-size: 11px; color: #333; padding: 3px 6px;"
            " background: #f5f5f5; border: 1px solid #ccc;"
            " border-radius: 3px;")
        self._hover_lbl.setWordWrap(True)
        layout.addWidget(self._hover_lbl)
        self._hover_obs = None
        layout.addStretch()

        # Register always-on direction observer (face click → set direction)
        self._always_dir_obs = _AlwaysOnDirObserver(self)
        Gui.Selection.addObserver(self._always_dir_obs)

        if not self._src_objs:
            QtCore.QTimer.singleShot(10,self._pick_preselected_surface)
        elif self._shapes:
            self._run_preview()

    @staticmethod
    def _resolve_shapes(objs):
        shapes=[]
        for obj in objs:
            src=obj.Tip if (hasattr(obj,"Tip") and obj.Tip) else obj
            if hasattr(src,"Shape") and not src.Shape.isNull():
                shapes.append(src.Shape)
        return shapes

    def _toggle_surf(self, checked):
        if checked:
            self._surf_btn.setText("Done")
            self._dir_btn.setChecked(False)
            self._surf_obs=_SurfaceObserver(self)
            Gui.Selection.addObserver(self._surf_obs)
            QtCore.QTimer.singleShot(10,self._pick_preselected_surface)
        else:
            self._surf_btn.setText("Select")
            if self._surf_obs:
                try: Gui.Selection.removeObserver(self._surf_obs)
                except Exception: pass
                self._surf_obs=None

    def _pick_preselected_surface(self):
        for sel in Gui.Selection.getSelectionEx():
            obj=sel.Object
            shape_src=obj.Tip if (hasattr(obj,"Tip") and obj.Tip) else obj
            if hasattr(shape_src,"Shape") and not shape_src.Shape.isNull():
                self._on_surface_picked(obj); return
        try:
            doc=FreeCAD.ActiveDocument
            if doc:
                solids=[o for o in doc.Objects
                        if hasattr((o.Tip if (hasattr(o,"Tip") and o.Tip) else o),"Shape")]
                if len(solids)==1: self._on_surface_picked(solids[0])
        except Exception:
            pass

    def _on_surface_picked(self, obj):
        if obj not in self._src_objs: self._src_objs.append(obj)
        self._shapes=self._resolve_shapes(self._src_objs)
        self._surf_edit.setText(", ".join(o.Label for o in self._src_objs))
        self._surf_edit.setStyleSheet("background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")
        if self._surf_btn.isChecked():
            self._surf_btn.blockSignals(True)
            self._surf_btn.setChecked(False); self._surf_btn.setText("Select")
            self._surf_btn.blockSignals(False)
            if self._surf_obs:
                try: Gui.Selection.removeObserver(self._surf_obs)
                except Exception: pass
                self._surf_obs=None
        self._schedule_preview()

    def _toggle_dir(self, checked):
        if checked:
            self._dir_btn.setText("× Cancel")
            self._surf_btn.setChecked(False)
            self._dir_active=True
            self._dir_edit.setPlaceholderText("Click any face on the part…")
            self._dir_edit.setStyleSheet("background:#fff8d0;border:1px solid #cc8800;border-radius:3px;padding:2px;")
            for obj in self._src_objs:
                try: obj.ViewObject.Visibility=True
                except Exception: pass
            self._dir_obs=_DirectionObserver(self)
            Gui.Selection.addObserver(self._dir_obs)
        else:
            self._dir_btn.setText("Select"); self._dir_active=False
            self._stop_dir_obs()
            for obj in self._src_objs:
                try: obj.ViewObject.Visibility=False
                except Exception: pass
            if not self._dir_edit.text():
                self._dir_edit.setStyleSheet("background:#d0eeff;border:1px solid #0070c0;border-radius:3px;padding:2px;")

    def _stop_dir_obs(self):
        if self._dir_obs:
            try: Gui.Selection.removeObserver(self._dir_obs)
            except Exception: pass
            self._dir_obs=None

    def _set_direction(self, n, label):
        if self._flipped: n=FreeCAD.Vector(-n.x,-n.y,-n.z)
        self._pull_dir=n
        self._dir_edit.setText(label+(" [Flipped]" if self._flipped else ""))
        self._dir_edit.setStyleSheet("background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")
        self._schedule_preview()

    def _flip(self):
        self._flipped=not self._flipped
        self._pull_dir=FreeCAD.Vector(-self._pull_dir.x,-self._pull_dir.y,-self._pull_dir.z)
        txt=self._dir_edit.text()
        self._dir_edit.setText(txt[:-10] if txt.endswith(" [Flipped]") else txt+" [Flipped]")
        self._schedule_preview()

    def _on_axis_changed(self):
        v=_AXIS_DIRS[self._axis_combo.currentText()]
        self._pull_dir=FreeCAD.Vector(-v.x,-v.y,-v.z) if self._flipped else v
        self._dir_edit.clear()
        self._dir_edit.setStyleSheet("background:#d0eeff;border:1px solid #0070c0;border-radius:3px;padding:2px;")
        self._schedule_preview()

    def _toggle_profile_select(self, checked):
        """Activate/deactivate face-click mode for Profile Undercut."""
        if checked:
            self._profile_btn.setText("× Cancel  (click a face…)")
            # Show original objects so face is clickable
            for obj in self._src_objs:
                try: obj.ViewObject.Visibility = True
                except Exception: pass

            class _ProfileObserver:
                def __init__(self_, panel):
                    self_._panel = panel
                    self_._pending = False
                def addSelection(self_, doc, obj_name, sub_name, pos):
                    if self_._pending: return
                    self_._pending = True
                    QtCore.QTimer.singleShot(50, self_._process)
                def _process(self_):
                    self_._pending = False
                    n, label = _extract_face_normal_from_selection()
                    if n:
                        # Deactivate button (block signals so we don't recurse)
                        self_._panel._profile_btn.blockSignals(True)
                        self_._panel._profile_btn.setChecked(False)
                        self_._panel._profile_btn.setText("Profile Undercut  (select face)")
                        self_._panel._profile_btn.blockSignals(False)
                        # Re-hide original objects
                        for obj in self_._panel._src_objs:
                            try: obj.ViewObject.Visibility = False
                            except Exception: pass
                        if self_._panel._profile_obs:
                            try: Gui.Selection.removeObserver(self_._panel._profile_obs)
                            except Exception: pass
                            self_._panel._profile_obs = None
                        # Run undercut with this face's normal as pull direction
                        self_._panel._run_undercut(pull_override=n, label=label)
                def removeSelection(self_, *a): pass
                def setSelection(self_, *a):    pass
                def clearSelection(self_, *a):  pass

            self._profile_obs = _ProfileObserver(self)
            Gui.Selection.addObserver(self._profile_obs)
        else:
            self._profile_btn.setText("Profile Undercut  (select face)")
            if self._profile_obs:
                try: Gui.Selection.removeObserver(self._profile_obs)
                except Exception: pass
                self._profile_obs = None
            # Re-hide objects if overlay is active
            if self._doc_name in _overlays:
                for obj in self._src_objs:
                    try: obj.ViewObject.Visibility = False
                    except Exception: pass

    def _run_undercut(self, pull_override=None, label=None):
        """Build undercut overlay: light green = clear, light red = trapped.
        pull_override: use this vector instead of self._pull_dir (from Profile Undercut)."""
        if not self._shapes:
            return
        try:
            from pivy import coin
        except ImportError:
            return

        pull = (pull_override if pull_override else self._pull_dir).normalize()
        px, py, pz = pull.x, pull.y, pull.z

        # Build Coin3D overlay with undercut colors
        from PySide.QtWidgets import QApplication
        tol = max(0.5, 4.0 - self._qual_slider.value() * 0.35)

        root = coin.SoSeparator()
        lm   = coin.SoLightModel(); lm.model.setValue(coin.SoLightModel.BASE_COLOR)
        root.addChild(lm)
        hints = coin.SoShapeHints()
        hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
        hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
        root.addChild(hints)
        poff = coin.SoPolygonOffset()
        poff.styles.setValue(coin.SoPolygonOffset.FILLED)
        poff.factor.setValue(10.0); poff.units.setValue(10.0)
        root.addChild(poff)

        all_verts=[]; vert_colors=[]; coord_idx=[]; mat_idx=[]; v_off=0

        for shape in self._shapes:
            for fi, face in enumerate(shape.Faces):
                try:
                    pts, tris = face.tessellate(tol)
                    if not pts or not tris:
                        continue
                    n_pts = len(pts)
                    # Reference normal
                    ref_nx=ref_ny=ref_nz=None
                    try:
                        umin,umax,vmin,vmax=face.ParameterRange
                        us,vs=umax-umin,vmax-vmin
                        rn=face.normalAt(umin+0.5*us,vmin+0.5*vs)
                        if rn.Length>1e-10:
                            rl=rn.Length
                            ref_nx,ref_ny,ref_nz=rn.x/rl,rn.y/rl,rn.z/rl
                    except Exception:
                        pass

                    local_start = len(vert_colors)
                    for i,pt in enumerate(pts):
                        all_verts.append((pt.x,pt.y,pt.z))
                        # Average from adjacent triangles
                        nx=ny=nz=cnt=0
                        for tri in tris:
                            if i in tri:
                                p1,p2,p3=pts[tri[0]],pts[tri[1]],pts[tri[2]]
                                ax=p2.x-p1.x;ay=p2.y-p1.y;az=p2.z-p1.z
                                bx=p3.x-p1.x;by=p3.y-p1.y;bz=p3.z-p1.z
                                tnx=ay*bz-az*by;tny=az*bx-ax*bz;tnz=ax*by-ay*bx
                                tl=(tnx*tnx+tny*tny+tnz*tnz)**0.5
                                if tl>1e-10:
                                    if ref_nx and (tnx*ref_nx+tny*ref_ny+tnz*ref_nz)<0:
                                        tnx=-tnx;tny=-tny;tnz=-tnz
                                    nx+=tnx/tl;ny+=tny/tl;nz+=tnz/tl;cnt+=1
                        if cnt>0:
                            nlen=(nx*nx+ny*ny+nz*nz)**0.5
                            if nlen>1e-10: nx/=nlen;ny/=nlen;nz/=nlen
                            dot=nx*px+ny*py+nz*pz
                            if dot < -0.01:
                                vert_colors.append((1.0, 0.55, 0.55))  # light red = undercut
                            else:
                                vert_colors.append((0.55, 0.92, 0.55)) # light green = clear
                        else:
                            vert_colors.append((0.55,0.55,0.55))

                    for tri in tris:
                        if len(tri)<3: continue
                        i0,i1,i2=v_off+tri[0],v_off+tri[1],v_off+tri[2]
                        coord_idx.extend([i0,i1,i2,-1])
                        mat_idx.extend([local_start+tri[0],local_start+tri[1],local_start+tri[2],-1])
                    v_off+=n_pts
                    if fi%50==0: QApplication.processEvents()
                    if v_off>200_000: break
                except Exception:
                    pass

        if not all_verts:
            return

        bc=coin.SoBaseColor()
        bc.rgb.setValues(0,len(vert_colors),vert_colors)
        root.addChild(bc)
        mb=coin.SoMaterialBinding()
        mb.value.setValue(coin.SoMaterialBinding.PER_VERTEX_INDEXED)
        root.addChild(mb)
        coords=coin.SoCoordinate3()
        coords.point.setValues(0,len(all_verts),all_verts)
        root.addChild(coords)
        ifs=coin.SoIndexedFaceSet()
        ifs.coordIndex.setValues(0,len(coord_idx),coord_idx)
        ifs.materialIndex.setValues(0,len(mat_idx),mat_idx)
        root.addChild(ifs)

        # Add placeholder edge switch
        es=coin.SoSwitch(); es.whichChild.setValue(-1); root.addChild(es)

        # Swap overlay
        doc_name=self._doc_name
        if doc_name in _overlays:
            old_node,_,_ = _overlays.pop(doc_name)
            try:
                sg=Gui.ActiveDocument.ActiveView.getSceneGraph()
                if sg.findChild(old_node)>=0: sg.removeChild(old_node)
            except Exception:
                pass

        for obj in self._src_objs:
            try: obj.ViewObject.Visibility=False
            except Exception: pass

        Gui.ActiveDocument.ActiveView.getSceneGraph().addChild(root)
        _overlays[doc_name]=(root,list(self._src_objs),es)
        Gui.updateGui()

        self._undercut_btn.setVisible(False)
        self._profile_btn.setVisible(False)
        self._draft_btn.setVisible(True)
        src = f"Profile: {label}" if label else "Direction pull"
        self._results.setHtml(
            f"<b>Undercut Analysis active.</b><br>"
            f"<i>{src}</i><br>"
            "<span style='color:#cc4444'>■</span> Light red = trapped undercut&nbsp;&nbsp;"
            "<span style='color:#44aa44'>■</span> Light green = releases cleanly")

    def _toggle_lines(self, checked):
        """Toggle geometric edge lines on the Coin3D overlay."""
        if self._doc_name not in _overlays:
            return
        try:
            _, _, edge_switch = _overlays[self._doc_name]
            # Use integer literals: 0 = show child 0, -1 = show nothing
            edge_switch.whichChild.setValue(0 if checked else -1)
            Gui.updateGui()
        except Exception:
            pass

    def _schedule_preview(self):
        if self._auto_chk.isChecked() and self._shapes:
            self._preview_timer.stop(); self._preview_timer.start(600)

    def _on_param_changed(self): self._schedule_preview()

    def _on_quality_changed(self, val):
        self._qual_lbl.setText(f"{val:.2f}"); self._schedule_preview()

    def _run_preview(self):
        if not self._shapes: return
        quality = self._qual_slider.value() if self._sample_combo.currentText() == "Quality" else 3
        pct, mn, mx = _run_analysis(self._src_objs, self._shapes, self._pull_dir,
                                    self._draft_spin.value(), quality, self._doc_name)
        if pct is not None:
            self._results.setHtml(
                f"<b>Adequate draft area:</b> {pct:.1f}%<br>"
                f"<b>Max negative draft:</b> {mn:.2f}°<br>"
                f"<b>Max positive draft:</b> {mx:.2f}°")
        if self._lines_chk.isChecked():
            self._toggle_lines(True)
        # Start viewport hover callback
        self._start_hover()

    def isAllowedAlterSelection(self): return True
    def isAllowedAlterView(self): return True
    def isAllowedAlterDocument(self): return False

    def accept(self):
        self._cleanup()
        # Remove the Coin3D overlay and restore the original part so viewport
        # modes (Flat Lines, Shaded, etc.) work normally after closing.
        _clear_overlay(self._doc_name)
        Gui.Control.closeDialog()

    def reject(self):
        self._cleanup()
        _clear_overlay(self._doc_name)
        Gui.Control.closeDialog()

    def _redraw_scale(self, draft_min_deg=3.0):
        """Regenerate colour scale: range = ±draft_min_deg (no ±90 labels)."""
        from PySide.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QPen
        from PySide.QtCore import QRectF
        H = 180; W = 22

        pm = QPixmap(W, H)
        p  = QPainter(pm)

        # Creo-style 5-band: deep blue → mid purple-blue → grey(0) → light pink → coral red
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.00, QColor( 79, 110, 219))   # deep blue  (+max)
        grad.setColorAt(0.35, QColor(145, 150, 210))   # mid blue-purple
        grad.setColorAt(0.50, QColor(186, 186, 193))   # neutral grey (0)
        grad.setColorAt(0.65, QColor(220, 160, 160))   # light pink
        grad.setColorAt(1.00, QColor(229,  77,  77))   # coral red  (-max)
        p.fillRect(QRectF(0, 0, W, H), grad)

        # Zero line in the middle
        p.setPen(QPen(QColor(120, 120, 120), 1))
        p.drawLine(0, H // 2, W, H // 2)
        p.end()

        self._scale_bar_lbl.setFixedSize(W, H)
        self._scale_bar_lbl.setPixmap(pm)

        # Rebuild tick labels: only ±draft_min and 0
        while self._scale_tick_layout.count():
            item = self._scale_tick_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        top_lbl = QtWidgets.QLabel(f"+{draft_min_deg:.1f}°")
        top_lbl.setStyleSheet("font-size:10px;color:#0000cc;font-family:monospace;font-weight:bold;")
        top_lbl.setFixedHeight(20)

        mid_sp = QtWidgets.QWidget(); mid_sp.setFixedHeight(H // 2 - 30)
        zero_lbl = QtWidgets.QLabel("0°  (parting)")
        zero_lbl.setStyleSheet("font-size:10px;color:#666666;font-family:monospace;")
        zero_lbl.setFixedHeight(20)

        bot_sp = QtWidgets.QWidget(); bot_sp.setFixedHeight(H // 2 - 30)
        bot_lbl = QtWidgets.QLabel(f"-{draft_min_deg:.1f}°")
        bot_lbl.setStyleSheet("font-size:10px;color:#cc0000;font-family:monospace;font-weight:bold;")
        bot_lbl.setFixedHeight(20)

        for w in (top_lbl, mid_sp, zero_lbl, bot_sp, bot_lbl):
            self._scale_tick_layout.addWidget(w)
        self._scale_tick_layout.addStretch()

    def _start_hover(self):
        """Start SoLocation2Event viewport callback for hover draft value."""
        self._stop_hover()
        try:
            self._hover_obs = Gui.ActiveDocument.ActiveView.addEventCallback(
                "SoLocation2Event", self._on_hover_move)
        except Exception:
            self._hover_obs = None

    def _stop_hover(self):
        if self._hover_obs is not None:
            try:
                Gui.ActiveDocument.ActiveView.removeEventCallback(
                    "SoLocation2Event", self._hover_obs)
            except Exception:
                pass
            self._hover_obs = None

    def _on_hover_move(self, info):
        """Called every mouse-move: find face under cursor, show draft angle."""
        try:
            pos = info.get("Position")
            if pos is None:
                return
            obj_info = Gui.ActiveDocument.ActiveView.getObjectInfo(
                (int(pos[0]), int(pos[1])))
            if not obj_info:
                self._hover_lbl.setText(
                    "<i>Hover over part to see draft angle</i>")
                return
            face_name = obj_info.get("Component", "")
            obj_name  = obj_info.get("Object", "")
            if not face_name.startswith("Face"):
                return
            doc = FreeCAD.ActiveDocument
            if not doc:
                return
            obj = doc.getObject(obj_name)
            if not obj:
                return
            src = obj.Tip if (hasattr(obj, "Tip") and obj.Tip) else obj
            if not hasattr(src, "Shape"):
                return
            fi = int(face_name[4:]) - 1
            faces = src.Shape.Faces
            if fi < 0 or fi >= len(faces):
                return
            deg = _compute_face_draft(faces[fi], self._pull_dir)
            if deg is None:
                return
            if deg > 0.4:
                clr = "#0000bb"; note = "positive draft"
            elif deg < -0.4:
                clr = "#cc0000"; note = "negative draft"
            else:
                clr = "#007700"
                note = "zero draft — face is perpendicular to pull direction"
            self._hover_lbl.setText(
                f"<b>{face_name}</b>: "
                f"<span style='color:{clr};font-weight:bold;'>{deg:.2f}°</span>"
                f"  <span style='color:#666;font-size:10px;'>({note})</span>")
        except Exception:
            pass

    def _cleanup(self):
        self._stop_hover()
        if self._always_dir_obs:
            try: Gui.Selection.removeObserver(self._always_dir_obs)
            except Exception: pass
            self._always_dir_obs = None
        if self._surf_obs:
            try: Gui.Selection.removeObserver(self._surf_obs)
            except Exception: pass
            self._surf_obs=None
        self._stop_dir_obs()
        if self._profile_obs:
            try: Gui.Selection.removeObserver(self._profile_obs)
            except Exception: pass
            self._profile_obs=None


# ─── Command ─────────────────────────────────────────────────────────────────

class CommandDraftAnalysis:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldDraftAnalysis.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_DraftAnalysis", "Draft Analysis"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_DraftAnalysis",
                        "Creo-style gradient draft analysis."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc_name=FreeCAD.ActiveDocument.Name
        if doc_name in _overlays:
            _clear_overlay(doc_name)
            try: Gui.Control.closeDialog()
            except Exception: pass
            return
        sel=Gui.Selection.getSelectionEx()
        initial=[s.Object for s in sel
                 if hasattr(s.Object,"Shape") or (hasattr(s.Object,"Tip") and s.Object.Tip)]
        try: Gui.Control.closeDialog()
        except Exception: pass
        panel=_DraftAnalysisPanel(initial,doc_name)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_DraftAnalysis", CommandDraftAnalysis())
