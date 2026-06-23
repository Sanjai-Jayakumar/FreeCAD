# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parting Line — SolidWorks-style task panel with draft analysis, pull-direction
arrow, coloured face overlay and automatic edge detection."""

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

_pl_overlays = {}   # doc_name → coin_node


# ── SolidWorks-style 3-colour scheme ─────────────────────────────────────────
def _sw_color(dot, dot_threshold):
    if dot >= dot_threshold:
        return (0.08, 0.80, 0.08)    # Green  — adequate positive draft
    elif dot >= 0.0:
        return (1.00, 0.80, 0.00)    # Yellow — insufficient positive
    elif dot >= -dot_threshold:
        return (1.00, 0.60, 0.10)    # Orange — slight negative
    else:
        return (0.88, 0.08, 0.08)    # Red    — negative draft


# ── Coin3D overlay + pull-direction arrow ─────────────────────────────────────

def _compute_pl_geometry(shapes, pull_dir, draft_deg, quality=7):
    """Compute tessellation + colour data (no Coin3D — safe in a thread)."""
    px, py, pz = pull_dir.x, pull_dir.y, pull_dir.z
    plen = (px*px + py*py + pz*pz) ** 0.5
    if plen > 1e-10:
        px /= plen; py /= plen; pz /= plen

    tol = max(0.5, 4.0 - quality * 0.35)
    dot_thr = math.sin(math.radians(draft_deg))

    all_verts = []; vert_colors = []; coord_idx = []; mat_idx = []
    v_offset = 0

    for shape in shapes:
        for face in shape.Faces:
            try:
                pts, tris = face.tessellate(tol)
                if not pts or not tris:
                    continue
                n_pts = len(pts)
                ref_nx = ref_ny = ref_nz = ref_dot = 0.0
                try:
                    umin, umax, vmin, vmax = face.ParameterRange
                    rn = face.normalAt((umin + umax) / 2, (vmin + vmax) / 2)
                    if rn.Length > 1e-10:
                        rn = rn.normalize()
                        ref_nx, ref_ny, ref_nz = rn.x, rn.y, rn.z
                        ref_dot = max(-1.0, min(1.0,
                                      rn.x*px + rn.y*py + rn.z*pz))
                except Exception:
                    pass
                v_nx = [0.0]*n_pts; v_ny = [0.0]*n_pts
                v_nz = [0.0]*n_pts; v_cnt = [0]*n_pts
                for tri in tris:
                    if len(tri) < 3: continue
                    p1, p2, p3 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
                    ax=p2.x-p1.x; ay=p2.y-p1.y; az=p2.z-p1.z
                    bx=p3.x-p1.x; by=p3.y-p1.y; bz=p3.z-p1.z
                    nx=ay*bz-az*by; ny=az*bx-ax*bz; nz=ax*by-ay*bx
                    nl=(nx*nx+ny*ny+nz*nz)**0.5
                    if nl<1e-10: continue
                    nx/=nl; ny/=nl; nz/=nl
                    if ref_nx*nx+ref_ny*ny+ref_nz*nz < 0:
                        nx=-nx; ny=-ny; nz=-nz
                    for vi in tri:
                        v_nx[vi]+=nx; v_ny[vi]+=ny; v_nz[vi]+=nz; v_cnt[vi]+=1
                local_start = len(vert_colors)
                for i in range(n_pts):
                    all_verts.append((pts[i].x, pts[i].y, pts[i].z))
                    cnt = v_cnt[i]
                    if cnt > 0:
                        nx=v_nx[i]/cnt; ny=v_ny[i]/cnt; nz=v_nz[i]/cnt
                        nl=(nx*nx+ny*ny+nz*nz)**0.5
                        if nl>1e-10: nx/=nl; ny/=nl; nz/=nl
                        dot=max(-1.0,min(1.0, nx*px+ny*py+nz*pz))
                        vert_colors.append(_sw_color(dot, dot_thr))
                    else:
                        vert_colors.append(_sw_color(ref_dot, dot_thr))
                for tri in tris:
                    if len(tri)<3: continue
                    i0=v_offset+tri[0]; i1=v_offset+tri[1]; i2=v_offset+tri[2]
                    coord_idx.extend([i0,i1,i2,-1])
                    mat_idx.extend([local_start+tri[0], local_start+tri[1],
                                    local_start+tri[2], -1])
                v_offset += n_pts
                if v_offset > 200_000: break
            except Exception:
                pass
        if v_offset > 200_000:
            break

    # Edge lines data
    n_ep = max(8, int(20 / max(tol, 0.5)))
    all_ep = []; edge_ns = []
    for shape in shapes:
        for edge in shape.Edges:
            try:
                epts = edge.discretize(Number=n_ep)
                if epts and len(epts) >= 2:
                    for v in epts: all_ep.append((v.x, v.y, v.z))
                    edge_ns.append(len(epts))
            except Exception:
                pass

    # Arrow data
    all_bb = [s.BoundBox for s in shapes]
    cx = sum(b.Center.x for b in all_bb) / len(all_bb)
    cy = sum(b.Center.y for b in all_bb) / len(all_bb)
    cz = sum(b.Center.z for b in all_bb) / len(all_bb)
    diag = max(b.DiagonalLength for b in all_bb)
    alen = diag * 0.38

    return dict(
        all_verts=all_verts, vert_colors=vert_colors,
        coord_idx=coord_idx, mat_idx=mat_idx,
        all_ep=all_ep, edge_ns=edge_ns,
        arrow_origin=(cx, cy, cz), arrow_len=alen,
        pull=(px, py, pz),
    )


def _build_coin_nodes(geom, pull_dir):
    """Build Coin3D scene graph from precomputed geometry (main thread only)."""
    from pivy import coin

    all_verts   = geom["all_verts"]
    vert_colors = geom["vert_colors"]
    coord_idx   = geom["coord_idx"]
    mat_idx     = geom["mat_idx"]
    all_ep      = geom["all_ep"]
    edge_ns     = geom["edge_ns"]
    cx, cy, cz  = geom["arrow_origin"]
    alen        = geom["arrow_len"]
    px, py, pz  = geom["pull"]

    root = coin.SoSeparator()
    if not all_verts:
        return root, coin.SoSwitch(), coin.SoSwitch(), coin.SoSwitch()

    # ── Coloured face overlay ────────────────────────────────────────────
    faces_switch = coin.SoSwitch(); faces_switch.whichChild.setValue(0)
    fsep = coin.SoSeparator()
    lm = coin.SoLightModel(); lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    fsep.addChild(lm)
    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    fsep.addChild(hints)
    poff = coin.SoPolygonOffset()
    poff.styles.setValue(coin.SoPolygonOffset.FILLED)
    poff.factor.setValue(10.0); poff.units.setValue(10.0)
    fsep.addChild(poff)
    bc = coin.SoBaseColor(); bc.rgb.setValues(0, len(vert_colors), vert_colors)
    fsep.addChild(bc)
    mb = coin.SoMaterialBinding()
    mb.value.setValue(coin.SoMaterialBinding.PER_VERTEX_INDEXED)
    fsep.addChild(mb)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(all_verts), all_verts)
    fsep.addChild(coords)
    ifs = coin.SoIndexedFaceSet()
    ifs.coordIndex.setValues(0, len(coord_idx), coord_idx)
    ifs.materialIndex.setValues(0, len(mat_idx), mat_idx)
    fsep.addChild(ifs)
    faces_switch.addChild(fsep)
    root.addChild(faces_switch)

    # ── Pull direction arrow ─────────────────────────────────────────────
    arrow = coin.SoSeparator()
    alm = coin.SoLightModel(); alm.model.setValue(coin.SoLightModel.BASE_COLOR)
    arrow.addChild(alm)
    abc = coin.SoBaseColor(); abc.rgb.setValue(0.05, 0.55, 1.0)
    arrow.addChild(abc)
    atr = coin.SoTransform()
    atr.translation.setValue(cx+px*alen*0.5, cy+py*alen*0.5, cz+pz*alen*0.5)
    rot = coin.SbRotation(coin.SbVec3f(0,1,0), coin.SbVec3f(px,py,pz))
    atr.rotation.setValue(rot)
    arrow.addChild(atr)
    shaft = coin.SoSeparator()
    shaft.addChild(coin.SoTransform())
    cyl = coin.SoCylinder(); cyl.radius.setValue(alen*0.020); cyl.height.setValue(alen*0.72)
    shaft.addChild(cyl); arrow.addChild(shaft)
    head = coin.SoSeparator()
    htr = coin.SoTransform(); htr.translation.setValue(0, alen*0.46, 0)
    head.addChild(htr)
    cone = coin.SoCone(); cone.bottomRadius.setValue(alen*0.065); cone.height.setValue(alen*0.28)
    head.addChild(cone); arrow.addChild(head)
    root.addChild(arrow)

    # ── Edge lines ───────────────────────────────────────────────────────
    edge_switch = coin.SoSwitch(); edge_switch.whichChild.setValue(-1)
    esep = coin.SoSeparator()
    elm = coin.SoLightModel(); elm.model.setValue(coin.SoLightModel.BASE_COLOR); esep.addChild(elm)
    ebc = coin.SoBaseColor(); ebc.rgb.setValue(0.1,0.1,0.1); esep.addChild(ebc)
    eds = coin.SoDrawStyle(); eds.lineWidth.setValue(1.2); esep.addChild(eds)
    etrans = coin.SoTransform(); etrans.center.setValue(cx,cy,cz)
    etrans.scaleFactor.setValue(1.003,1.003,1.003); esep.addChild(etrans)
    if all_ep:
        ec = coin.SoCoordinate3(); ec.point.setValues(0, len(all_ep), all_ep); esep.addChild(ec)
        els = coin.SoLineSet(); els.numVertices.setValues(0, len(edge_ns), edge_ns); esep.addChild(els)
    edge_switch.addChild(esep); root.addChild(edge_switch)

    # ── Highlight switch ─────────────────────────────────────────────────
    hl_switch = coin.SoSwitch(); hl_switch.whichChild.setValue(-1)
    root.addChild(hl_switch)

    return root, edge_switch, hl_switch, faces_switch

def _build_pl_overlay(shapes, pull_dir, draft_deg, quality=7):
    from pivy import coin
    from PySide.QtWidgets import QApplication

    px, py, pz = pull_dir.x, pull_dir.y, pull_dir.z
    plen = (px*px + py*py + pz*pz) ** 0.5
    if plen > 1e-10:
        px /= plen; py /= plen; pz /= plen

    tol     = max(0.5, 4.0 - quality * 0.35)
    dot_thr = math.sin(math.radians(draft_deg))

    all_verts = []; vert_colors = []; coord_idx = []; mat_idx = []
    v_offset = 0

    for shape in shapes:
        for face in shape.Faces:
            try:
                pts, tris = face.tessellate(tol)
                if not pts or not tris:
                    continue
                n_pts = len(pts)

                ref_nx = ref_ny = ref_nz = ref_dot = 0.0
                try:
                    umin, umax, vmin, vmax = face.ParameterRange
                    rn = face.normalAt((umin + umax) / 2, (vmin + vmax) / 2)
                    if rn.Length > 1e-10:
                        rn = rn.normalize()
                        ref_nx, ref_ny, ref_nz = rn.x, rn.y, rn.z
                        ref_dot = max(-1.0, min(1.0,
                                      rn.x*px + rn.y*py + rn.z*pz))
                except Exception:
                    pass

                v_nx = [0.0]*n_pts; v_ny = [0.0]*n_pts
                v_nz = [0.0]*n_pts; v_cnt = [0]*n_pts
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
                    if ref_nx*nx + ref_ny*ny + ref_nz*nz < 0:
                        nx = -nx; ny = -ny; nz = -nz
                    for vi in tri:
                        v_nx[vi] += nx; v_ny[vi] += ny
                        v_nz[vi] += nz; v_cnt[vi] += 1

                local_start = len(vert_colors)
                for i in range(n_pts):
                    all_verts.append((pts[i].x, pts[i].y, pts[i].z))
                    cnt = v_cnt[i]
                    if cnt > 0:
                        nx = v_nx[i]/cnt; ny = v_ny[i]/cnt; nz = v_nz[i]/cnt
                        nl = (nx*nx+ny*ny+nz*nz)**0.5
                        if nl > 1e-10:
                            nx /= nl; ny /= nl; nz /= nl
                        dot = max(-1.0, min(1.0, nx*px + ny*py + nz*pz))
                        vert_colors.append(_sw_color(dot, dot_thr))
                    else:
                        vert_colors.append(_sw_color(ref_dot, dot_thr))

                for tri in tris:
                    if len(tri) < 3:
                        continue
                    i0 = v_offset+tri[0]; i1 = v_offset+tri[1]; i2 = v_offset+tri[2]
                    coord_idx.extend([i0, i1, i2, -1])
                    mat_idx.extend([local_start+tri[0],
                                    local_start+tri[1],
                                    local_start+tri[2], -1])
                v_offset += n_pts
                if v_offset > 200_000:
                    break
            except Exception:
                pass
        if v_offset > 200_000:
            break

    root = coin.SoSeparator()
    if not all_verts:
        return root

    # ── Face colour overlay — wrapped in a switch so it can be hidden ─────
    faces_switch = coin.SoSwitch()
    faces_switch.whichChild.setValue(0)   # visible by default
    fsep = coin.SoSeparator()

    lm = coin.SoLightModel()
    lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    fsep.addChild(lm)
    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    fsep.addChild(hints)
    poff = coin.SoPolygonOffset()
    poff.styles.setValue(coin.SoPolygonOffset.FILLED)
    poff.factor.setValue(10.0); poff.units.setValue(10.0)
    fsep.addChild(poff)
    bc = coin.SoBaseColor()
    bc.rgb.setValues(0, len(vert_colors), vert_colors)
    fsep.addChild(bc)
    mb = coin.SoMaterialBinding()
    mb.value.setValue(coin.SoMaterialBinding.PER_VERTEX_INDEXED)
    fsep.addChild(mb)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(all_verts), all_verts)
    fsep.addChild(coords)
    ifs = coin.SoIndexedFaceSet()
    ifs.coordIndex.setValues(0, len(coord_idx), coord_idx)
    ifs.materialIndex.setValues(0, len(mat_idx), mat_idx)
    fsep.addChild(ifs)

    faces_switch.addChild(fsep)
    root.addChild(faces_switch)

    # ── Pull-direction arrow ──────────────────────────────────────────────
    all_bb = [s.BoundBox for s in shapes]
    cx = sum(b.Center.x for b in all_bb) / len(all_bb)
    cy = sum(b.Center.y for b in all_bb) / len(all_bb)
    cz = sum(b.Center.z for b in all_bb) / len(all_bb)
    diag = max(b.DiagonalLength for b in all_bb)
    alen = diag * 0.38

    arrow = coin.SoSeparator()
    alm = coin.SoLightModel(); alm.model.setValue(coin.SoLightModel.BASE_COLOR)
    arrow.addChild(alm)
    abc = coin.SoBaseColor(); abc.rgb.setValue(0.05, 0.55, 1.0)
    arrow.addChild(abc)

    atr = coin.SoTransform()
    atr.translation.setValue(cx + px*alen*0.5,
                              cy + py*alen*0.5,
                              cz + pz*alen*0.5)
    rot = coin.SbRotation(coin.SbVec3f(0, 1, 0),
                           coin.SbVec3f(px, py, pz))
    atr.rotation.setValue(rot)
    arrow.addChild(atr)

    shaft = coin.SoSeparator()
    sht = coin.SoTransform(); sht.translation.setValue(0, 0, 0)
    shaft.addChild(sht)
    cyl = coin.SoCylinder()
    cyl.radius.setValue(alen * 0.020)
    cyl.height.setValue(alen * 0.72)
    shaft.addChild(cyl)
    arrow.addChild(shaft)

    head = coin.SoSeparator()
    htr = coin.SoTransform(); htr.translation.setValue(0, alen * 0.46, 0)
    head.addChild(htr)
    cone = coin.SoCone()
    cone.bottomRadius.setValue(alen * 0.065)
    cone.height.setValue(alen * 0.28)
    head.addChild(cone)
    arrow.addChild(head)

    root.addChild(arrow)

    # ── Edge lines (hidden by default, toggled by checkbox) ───────────────
    edge_switch = coin.SoSwitch()
    edge_switch.whichChild.setValue(-1)   # off by default

    esep = coin.SoSeparator()
    elm  = coin.SoLightModel(); elm.model.setValue(coin.SoLightModel.BASE_COLOR)
    esep.addChild(elm)
    ebc  = coin.SoBaseColor(); ebc.rgb.setValue(0.1, 0.1, 0.1)
    esep.addChild(ebc)
    eds  = coin.SoDrawStyle(); eds.lineWidth.setValue(1.2)
    esep.addChild(eds)

    all_bb = [s.BoundBox for s in shapes]
    cx = sum(b.Center.x for b in all_bb) / len(all_bb)
    cy = sum(b.Center.y for b in all_bb) / len(all_bb)
    cz = sum(b.Center.z for b in all_bb) / len(all_bb)
    etrans = coin.SoTransform()
    etrans.center.setValue(cx, cy, cz)
    etrans.scaleFactor.setValue(1.003, 1.003, 1.003)
    esep.addChild(etrans)

    n_pts_e = max(8, int(20 / max(tol, 0.5)))
    all_ep = []; edge_ns = []
    for shape in shapes:
        for edge in shape.Edges:
            try:
                epts = edge.discretize(Number=n_pts_e)
                if epts and len(epts) >= 2:
                    for v in epts:
                        all_ep.append((v.x, v.y, v.z))
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

    # ── Highlight switch — updated per edge-list selection ─────────────────
    highlight_switch = coin.SoSwitch()
    highlight_switch.whichChild.setValue(-1)
    root.addChild(highlight_switch)

    return root, edge_switch, highlight_switch, faces_switch


def _clear_pl_overlay(doc_name):
    if doc_name not in _pl_overlays:
        return
    node, _es, _hs, _fs = _pl_overlays.pop(doc_name)
    try:
        sg = Gui.ActiveDocument.ActiveView.getSceneGraph()
        if sg.findChild(node) >= 0:
            sg.removeChild(node)
    except Exception:
        pass
    Gui.updateGui()


# ── Parting edge detection ────────────────────────────────────────────────────

def _outer_wire_edges(face):
    """Return the outer-boundary edges of a face, trying multiple fallbacks."""
    # 1. OuterWire (most reliable for simple faces)
    try:
        edges = face.OuterWire.Edges
        if edges:
            return edges
    except Exception:
        pass
    # 2. Pick the wire with the largest bounding-box diagonal (= outer loop)
    try:
        wires = face.Wires
        if wires:
            best = max(wires, key=lambda w: w.BoundBox.DiagonalLength)
            edges = best.Edges
            if edges:
                return edges
    except Exception:
        pass
    # 3. All face edges (last resort)
    try:
        return list(face.Edges)
    except Exception:
        return []


def _edge_midpoint(edge):
    """Return the mid-point of an edge as a FreeCAD.Vector."""
    try:
        pts = edge.discretize(Number=3)
        p = pts[1]
        return FreeCAD.Vector(p.x, p.y, p.z)
    except Exception:
        try:
            a = edge.Vertexes[0].Point
            b = edge.Vertexes[-1].Point
            return FreeCAD.Vector((a.x+b.x)/2, (a.y+b.y)/2, (a.z+b.z)/2)
        except Exception:
            return FreeCAD.Vector(0, 0, 0)


def _largest_connected_loop(edges, pull_dir=None, bbox_center=None, tol=0.15):
    """Return the connected component that represents the outer parting loop.

    Strategy: pick the component with the LARGEST average radial distance
    from the shape centre projected perpendicular to the pull direction.
    Outer parting edges are always further from the centre than inner
    pocket/groove edges — this correctly handles hollow parts where the
    inner loop may be longer in total arc-length than the outer loop.
    Falls back to largest-total-length when pull_dir is not supplied.
    """
    if not edges:
        return []
    n = len(edges)

    # ── Build adjacency via vertex-key grouping (O(N) not O(N²)) ────────
    vtx_to_edges = {}
    for i, edge in enumerate(edges):
        try:
            for v in edge.Vertexes:
                k = _vkey(v)
                vtx_to_edges.setdefault(k, []).append(i)
        except Exception:
            pass
    adj = [set() for _ in range(n)]
    for idx_list in vtx_to_edges.values():
        for a in idx_list:
            for b in idx_list:
                if a != b:
                    adj[a].add(b)
                    adj[b].add(a)

    # ── Find connected components ────────────────────────────────────────
    visited = [False] * n
    components = []
    for start in range(n):
        if not visited[start]:
            comp, stack = [], [start]
            while stack:
                node = stack.pop()
                if not visited[node]:
                    visited[node] = True
                    comp.append(node)
                    stack.extend(adj[node])
            components.append(comp)

    # ── Score each component ─────────────────────────────────────────────
    if pull_dir is not None and bbox_center is not None:
        # Radial distance from shape centre in the plane ⊥ pull (outer wins)
        px, py, pz = pull_dir.x, pull_dir.y, pull_dir.z
        plen = (px*px + py*py + pz*pz) ** 0.5
        if plen > 1e-10:
            px /= plen; py /= plen; pz /= plen
        cx, cy, cz = bbox_center.x, bbox_center.y, bbox_center.z

        def avg_radial(comp):
            total = 0.0
            for i in comp:
                mp = _edge_midpoint(edges[i])
                fx = mp.x - cx; fy = mp.y - cy; fz = mp.z - cz
                # remove component along pull
                d = fx*px + fy*py + fz*pz
                rx = fx - d*px; ry = fy - d*py; rz = fz - d*pz
                total += (rx*rx + ry*ry + rz*rz) ** 0.5
            return total / len(comp) if comp else 0.0

        best = max(components, key=avg_radial)
    else:
        # Fallback: largest total arc-length
        def total_len(comp):
            s = 0.0
            for i in comp:
                try: s += edges[i].Length
                except Exception: pass
            return s
        best = max(components, key=total_len)

    return [edges[i] for i in best]


def _vkey(v, prec=2):
    """Round vertex coordinates to a tuple key for fast lookup."""
    f = 10.0 ** prec
    return (int(v.Point.x * f), int(v.Point.y * f), int(v.Point.z * f))


def _all_connected_components(edges):
    """Split edges into connected groups (shared vertices)."""
    n = len(edges)
    if n == 0:
        return []
    vtx_to_edges = {}
    for i, e in enumerate(edges):
        try:
            for v in e.Vertexes:
                vtx_to_edges.setdefault(_vkey(v), []).append(i)
        except Exception:
            pass
    adj = [set() for _ in range(n)]
    for idx_list in vtx_to_edges.values():
        for a in idx_list:
            for b in idx_list:
                if a != b:
                    adj[a].add(b); adj[b].add(a)
    visited = [False] * n
    components = []
    for start in range(n):
        if not visited[start]:
            comp, stack = [], [start]
            while stack:
                node = stack.pop()
                if not visited[node]:
                    visited[node] = True
                    comp.append(node)
                    stack.extend(adj[node])
            components.append(comp)
    return components


def _find_parting_edges(shape, pull_dir, threshold_deg, ref_face=None,
                        ref_faces=None, method="face_boundary"):
    """Parting line detection — reliable for all part types.

    Face Boundary mode: returns the outer perimeter of the selected face(s)
    directly, with no sign-change computation.  Always works regardless of
    draft angles or sign-change availability.

    Draft Analysis mode: finds edges where the dot-product with the pull
    direction changes sign (positive ↔ negative draft).  Picks the outermost
    connected loop, biased toward the selected face when one is given.
    """
    if ref_faces is None:
        ref_faces = [ref_face] if ref_face is not None else []

    # ── Face Boundary mode — completely independent of sign-change ────────────
    # Runs FIRST so it always returns the selected face's perimeter, even when
    # there are no sign-change edges (e.g. all faces have positive draft).
    if method == "face_boundary":
        all_edges = []; seen = set()
        for rf in ref_faces:
            for e in _outer_wire_edges(rf):
                try:
                    k = tuple(sorted(_vkey(v) for v in e.Vertexes))
                    if k not in seen:
                        seen.add(k); all_edges.append(e)
                except Exception:
                    pass
        if all_edges:
            return all_edges
        # No face selected yet — fall through to generic sign-change below

    # ── Sign-change computation (Draft Analysis mode or no-face fallback) ─────
    pull = pull_dir.normalize()

    def face_dot(face):
        try:
            umin, umax, vmin, vmax = face.ParameterRange
            n = face.normalAt((umin + umax) / 2, (vmin + vmax) / 2)
            if n.Length > 1e-10:
                return n.normalize().dot(pull)
        except Exception:
            pass
        return 0.0

    faces = list(shape.Faces)
    dots  = [face_dot(f) for f in faces]

    edge_face_map = {}
    for fi, face in enumerate(faces):
        for fe in face.Edges:
            try:
                key = tuple(sorted(_vkey(v) for v in fe.Vertexes))
                edge_face_map.setdefault(key, []).append(fi)
            except Exception:
                pass

    candidates = []
    for edge in shape.Edges:
        try:
            if edge.isClosed():
                continue
            key = tuple(sorted(_vkey(v) for v in edge.Vertexes))
        except Exception:
            continue
        adj = edge_face_map.get(key, [])
        if len(adj) >= 2:
            ad = [dots[i] for i in adj]
            if any(d > 0.0 for d in ad) and any(d < 0.0 for d in ad):
                candidates.append(edge)

    if not candidates:
        return []

    comps = _all_connected_components(candidates)

    if ref_faces and method == "draft_analysis":
        # Pick the sign-change loop closest to the selected face, then
        # prefer the one with the largest outer radius.
        try:
            centers = []
            for rf in ref_faces:
                try: centers.append(rf.BoundBox.Center)
                except Exception: pass
            if not centers:
                raise ValueError("no valid faces")
            rx = sum(c.x for c in centers) / len(centers)
            ry = sum(c.y for c in centers) / len(centers)
            rz = sum(c.z for c in centers) / len(centers)

            def avg_dist_to_face(comp):
                s = 0.0
                for i in comp:
                    mp = _edge_midpoint(candidates[i])
                    dx = mp.x-rx; dy = mp.y-ry; dz = mp.z-rz
                    s += (dx*dx+dy*dy+dz*dz)**0.5
                return s / len(comp) if comp else 1e9

            dists  = [avg_dist_to_face(c) for c in comps]
            min_d  = min(dists) if dists else 0.0
            nearby = [c for c, d in zip(comps, dists) if d <= max(min_d * 3.0, 1.0)]
            if not nearby:
                nearby = comps

            try:
                bbc = shape.BoundBox.Center
                bcx, bcy, bcz = bbc.x, bbc.y, bbc.z
            except Exception:
                bcx = bcy = bcz = 0.0

            def max_radial(comp):
                max_r = 0.0
                for i in comp:
                    mp = _edge_midpoint(candidates[i])
                    dx = mp.x-bcx; dy = mp.y-bcy; dz = mp.z-bcz
                    r = (dx*dx+dy*dy+dz*dz)**0.5
                    if r > max_r:
                        max_r = r
                return max_r

            best = max(nearby, key=max_radial)
            return [candidates[i] for i in best]
        except Exception:
            pass

    try:
        bbox_center = shape.BoundBox.Center
    except Exception:
        bbox_center = None

    return _largest_connected_loop(candidates, pull_dir=pull_dir,
                                   bbox_center=bbox_center)


# ── Always-on face-click observer ─────────────────────────────────────────────

class _PLAnalysisWorker(QtCore.QThread):
    """Background thread: tessellate + colour faces + detect parting edges.
    Coin3D node creation happens on the main thread after this finishes."""

    finished       = QtCore.Signal(dict, list)   # geom_data, parting_edges
    error_occurred = QtCore.Signal(str)

    def __init__(self, shapes, pull_dir, draft_deg, quality=7,
                 ref_faces=None, method="face_boundary"):
        super().__init__()
        self._shapes    = shapes
        self._pull_dir  = pull_dir
        self._draft_deg = draft_deg
        self._quality   = quality
        self._ref_faces = ref_faces or []
        self._method    = method

    def run(self):
        try:
            geom   = _compute_pl_geometry(self._shapes, self._pull_dir,
                                          self._draft_deg, self._quality)
            pedges = _find_parting_edges(self._shapes[0], self._pull_dir,
                                         self._draft_deg,
                                         ref_faces=self._ref_faces,
                                         method=self._method)
            self.finished.emit(geom, pedges)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class _FaceDirObserver:
    """Captures face clicks by storing addSelection args directly —
    avoids getSelectionEx() which loses SubElements when the body is also selected."""
    def __init__(self, panel):
        self._panel   = panel
        self._pending = False
        self._queued  = None   # (doc_name, obj_name, sub_name)

    def addSelection(self, doc, obj_name, sub_name, pos):
        if self._pending:
            return
        face_part = str(sub_name).split(".")[-1]
        if not face_part.startswith("Face"):
            return
        # Capture Ctrl modifier NOW (before the 50ms timer fires)
        ctrl = bool(QtWidgets.QApplication.keyboardModifiers()
                    & QtCore.Qt.ControlModifier)
        self._queued  = (doc, obj_name, face_part, ctrl)
        self._pending = True
        QtCore.QTimer.singleShot(50, self._process)

    def _process(self):
        self._pending = False
        if self._queued is None:
            return
        doc_name, obj_name, face_name, ctrl_held = self._queued
        self._queued = None
        try:
            doc = FreeCAD.getDocument(doc_name)
            if doc is None:
                return
            obj = doc.getObject(obj_name)
            if obj is None:
                return
            src = obj.Tip if (hasattr(obj, "Tip") and obj.Tip) else obj
            if not hasattr(src, "Shape") or src.Shape.isNull():
                return
            fi = int(face_name[4:]) - 1
            faces = src.Shape.Faces
            if fi < 0 or fi >= len(faces):
                return
            face = faces[fi]
            umin, umax, vmin, vmax = face.ParameterRange
            n = face.normalAt((umin + umax) / 2, (vmin + vmax) / 2)
            if n.Length > 1e-10:
                # Pass the actual face object for the face-boundary edge detection
                self._panel._set_direction(
                    n.normalize(),
                    f"{obj.Label} › {face_name}",
                    ref_face=face,
                    ctrl_held=ctrl_held)
        except Exception:
            pass

    def removeSelection(self, *a): pass
    def setSelection(self, *a):    pass
    def clearSelection(self, *a):  pass


# ── Task Panel ────────────────────────────────────────────────────────────────
class _PartingLinePanel:
    def __init__(self, src_obj, doc_name):
        self._src_obj   = src_obj
        self._doc_name  = doc_name
        self._pull_dir   = FreeCAD.Vector(0, 0, 1)
        self._flipped    = False
        self._face_obs   = None
        self._ref_faces  = []     # list — Ctrl+click adds; plain click replaces
        self._parting_edges = []

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Parting Line")
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.setSpacing(6)

        # ── Mold Parameters ───────────────────────────────────────────────
        grp = QtWidgets.QGroupBox("Mold Parameters")
        gl  = QtWidgets.QFormLayout(grp)
        gl.setSpacing(5)

        dir_row = QtWidgets.QHBoxLayout()
        self._dir_edit = QtWidgets.QLineEdit()
        self._dir_edit.setReadOnly(True)
        self._dir_edit.setPlaceholderText("Click any face to set direction…")
        self._dir_edit.setStyleSheet(
            "background:#d0eeff;border:1px solid #0070c0;border-radius:3px;padding:2px;")
        dir_row.addWidget(self._dir_edit)
        self._flip_btn = QtWidgets.QPushButton("Flip")
        self._flip_btn.setFixedWidth(40)
        self._flip_btn.clicked.connect(self._flip)
        dir_row.addWidget(self._flip_btn)
        gl.addRow("Direction:", dir_row)

        self._axis_combo = QtWidgets.QComboBox()
        self._axis_combo.addItems(list(_AXIS_DIRS.keys()))
        self._axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        gl.addRow("Or axis:", self._axis_combo)

        self._angle_spin = QtWidgets.QDoubleSpinBox()
        self._angle_spin.setRange(0.0, 45.0)
        self._angle_spin.setDecimals(2)
        self._angle_spin.setValue(3.00)
        self._angle_spin.setSuffix("deg")
        gl.addRow("Draft:", self._angle_spin)

        layout.addWidget(grp)

        # ── Detection Method ──────────────────────────────────────────────
        grp_m = QtWidgets.QGroupBox("Detection Method")
        gl_m  = QtWidgets.QVBoxLayout(grp_m)
        gl_m.setSpacing(4)

        self._method_combo = QtWidgets.QComboBox()
        self._method_combo.addItems([
            "Face Boundary  (use selected face's outer edges)",
            "Draft Analysis  (sign-change at parting plane)",
        ])
        self._method_combo.setCurrentIndex(0)
        gl_m.addWidget(self._method_combo)

        self._method_help = QtWidgets.QLabel(
            "Face Boundary: parting line = outer perimeter of the face you clicked.\n"
            "Best for flat rim / flange faces (basket, box lid, housing).\n\n"
            "Draft Analysis: parting line = edges where draft sign changes.\n"
            "Best for parts where no single face marks the exact split.")
        self._method_help.setWordWrap(True)
        self._method_help.setStyleSheet(
            "font-size:10px;color:#444;background:#f5f5ff;"
            "border:1px solid #ccc;border-radius:3px;padding:4px;")
        gl_m.addWidget(self._method_help)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)

        layout.addWidget(grp_m)

        # ── Draft Analysis button ─────────────────────────────────────────
        self._analyze_btn = QtWidgets.QPushButton("  Draft Analysis")
        self._analyze_btn.setMinimumHeight(32)
        self._analyze_btn.setStyleSheet(
            "QPushButton{background:#1a5cb4;color:white;font-weight:bold;"
            "border-radius:4px;padding:4px 10px;font-size:12px;}"
            "QPushButton:hover{background:#2368cc;}"
            "QPushButton:pressed{background:#0f3d7a;}")
        self._analyze_btn.clicked.connect(self._run_analysis)
        layout.addWidget(self._analyze_btn)

        # ── Colour legend ─────────────────────────────────────────────────
        leg = QtWidgets.QHBoxLayout()
        leg.setSpacing(4)
        for hex_clr, label in (
            ("#14cc14", "Positive"),
            ("#ffcc00", "Transition"),
            ("#e01414", "Negative"),
        ):
            sq = QtWidgets.QLabel()
            sq.setFixedSize(16, 16)
            sq.setStyleSheet(
                f"background:{hex_clr};border:1px solid #555;border-radius:2px;")
            sq.setToolTip(label)
            tx = QtWidgets.QLabel(label)
            tx.setStyleSheet("font-size:10px;")
            leg.addWidget(sq); leg.addWidget(tx)
            leg.addSpacing(4)
        leg.addStretch()
        layout.addLayout(leg)

        # ── Status message ────────────────────────────────────────────────
        self._msg = QtWidgets.QLabel(
            "Please select the pull direction and click 'Draft Analysis'.")
        self._msg.setWordWrap(True)
        self._msg.setStyleSheet(
            "font-size:10px;color:#333;background:#ffffcc;"
            "border:1px solid #ccbb00;border-radius:3px;padding:4px;")
        layout.addWidget(self._msg)

        # ── Parting Lines list ────────────────────────────────────────────
        grp_pl = QtWidgets.QGroupBox("Parting Lines")
        pl_vlay = QtWidgets.QVBoxLayout(grp_pl)
        self._edge_list = QtWidgets.QListWidget()
        self._edge_list.setFixedHeight(100)
        self._edge_list.setStyleSheet("font-size:11px;")
        self._edge_list.currentRowChanged.connect(self._on_edge_selected)
        pl_vlay.addWidget(self._edge_list)
        layout.addWidget(grp_pl)

        # ── Options ───────────────────────────────────────────────────────
        self._lines_chk = QtWidgets.QCheckBox("Show edge lines")
        self._lines_chk.setChecked(False)
        self._lines_chk.toggled.connect(self._toggle_lines)
        layout.addWidget(self._lines_chk)

        self._core_cavity_chk = QtWidgets.QCheckBox("Use for Core/Cavity Split")
        self._core_cavity_chk.setChecked(True)
        layout.addWidget(self._core_cavity_chk)
        layout.addStretch()

        # Register always-on face observer + default +Z
        self._face_obs = _FaceDirObserver(self)
        Gui.Selection.addObserver(self._face_obs)

        self._axis_combo.blockSignals(True)
        self._axis_combo.setCurrentIndex(0)
        self._axis_combo.blockSignals(False)
        self._pull_dir = _AXIS_DIRS["+Z (Up)"]
        self._dir_edit.setText("+Z (Up)")
        self._dir_edit.setStyleSheet(
            "background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_direction(self, n, label, ref_face=None, ctrl_held=False):
        if ctrl_held and ref_face is not None:
            # Ctrl+click: ADD to list, update pull_dir to average of all normals
            if ref_face not in self._ref_faces:
                self._ref_faces.append(ref_face)
            # Recompute average pull direction from all selected faces
            try:
                avg = FreeCAD.Vector(0, 0, 0)
                for rf in self._ref_faces:
                    umin, umax, vmin, vmax = rf.ParameterRange
                    fn = rf.normalAt((umin+umax)/2, (vmin+vmax)/2)
                    if fn.Length > 1e-10:
                        avg = avg + fn.normalize()
                if avg.Length > 1e-10:
                    self._pull_dir = avg.normalize()
            except Exception:
                self._pull_dir = n
            count = len(self._ref_faces)
            display = f"{label} (+{count-1} more)" if count > 1 else label
        else:
            # Plain click: replace list with single face
            self._ref_faces = [ref_face] if ref_face is not None else []
            self._pull_dir  = n
            display = label

        self._dir_edit.setText(display)
        self._dir_edit.setStyleSheet(
            "background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")
        self._msg.setText(
            f"Direction: {display}. "
            f"{'Ctrl+click to add more faces.  ' if not ctrl_held else ''}"
            "Click 'Draft Analysis' to analyse.")

    def _flip(self):
        self._pull_dir = FreeCAD.Vector(
            -self._pull_dir.x, -self._pull_dir.y, -self._pull_dir.z)
        t = self._dir_edit.text()
        self._dir_edit.setText(
            t[:-10] if t.endswith(" [Flipped]") else t + " [Flipped]")

    def _on_method_changed(self, idx):
        hints = [
            "Face Boundary selected: click the rim/flange face, then run Draft Analysis.\n"
            "The parting line will be the outer perimeter of that exact face.",
            "Draft Analysis selected: parting line is computed from where draft\n"
            "transitions from positive to negative — may differ from face boundary.",
        ]
        self._method_help.setText(hints[idx])

    def _on_axis_changed(self):
        key = self._axis_combo.currentText()
        self._pull_dir = _AXIS_DIRS[key]
        self._ref_faces = []   # axis-based: no reference faces, use generic detection
        self._dir_edit.setText(key)
        self._dir_edit.setStyleSheet(
            "background:#c8ffc8;border:1px solid #007700;border-radius:3px;padding:2px;")

    # ── Draft Analysis ────────────────────────────────────────────────────────
    def _run_analysis(self):
        src = (self._src_obj.Tip
               if (hasattr(self._src_obj, "Tip") and self._src_obj.Tip)
               else self._src_obj)
        if not hasattr(src, "Shape") or src.Shape.isNull():
            self._msg.setText("No shape found on the selected object.")
            return

        _clear_pl_overlay(self._doc_name)

        # Hide original object
        try:
            self._src_obj.ViewObject.Visibility = False
        except Exception:
            pass

        # Show computing status + disable button
        self._msg.setText("Computing analysis — please wait...")
        self._msg.setStyleSheet(
            "font-size:10px;color:#333;background:#ffffcc;"
            "border:1px solid #ccbb00;border-radius:3px;padding:4px;")
        self._analyze_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        # Launch background worker — pass all selected faces + detection method
        method = "face_boundary" if self._method_combo.currentIndex() == 0 \
                 else "draft_analysis"
        self._worker = _PLAnalysisWorker(
            [src.Shape], self._pull_dir, self._angle_spin.value(),
            ref_faces=self._ref_faces if self._ref_faces else None,
            method=method)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error_occurred.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_done(self, geom, parting_edges):
        """Called on main thread when the worker finishes."""
        self._analyze_btn.setEnabled(True)
        try:
            # Build Coin3D nodes on the main thread
            node, edge_switch, hl_switch, faces_switch = _build_coin_nodes(
                geom, self._pull_dir)
            Gui.ActiveDocument.ActiveView.getSceneGraph().addChild(node)
            _pl_overlays[self._doc_name] = (node, edge_switch, hl_switch, faces_switch)
            self._toggle_lines(self._lines_chk.isChecked())
            Gui.updateGui()
        except Exception as e:
            try:
                self._src_obj.ViewObject.Visibility = True
            except Exception:
                pass
            self._msg.setText(f"Overlay error: {e}")
            return

        self._parting_edges = parting_edges
        self._edge_list.clear()
        for i in range(len(parting_edges)):
            item = QtWidgets.QListWidgetItem(f"Edge<{i + 1}>")
            item.setForeground(QtGui.QColor("#cc0077"))
            self._edge_list.addItem(item)

        if parting_edges:
            method_lbl = "face boundary" \
                if self._method_combo.currentIndex() == 0 else "draft analysis"
            self._msg.setText(
                f"Parting line: {len(parting_edges)} edge(s) detected ({method_lbl}).\n"
                "Click OK to create the parting line in the document.")
            self._msg.setStyleSheet(
                "font-size:10px;color:#005500;background:#ccffcc;"
                "border:1px solid #007700;border-radius:3px;padding:4px;")
        else:
            method_idx = self._method_combo.currentIndex()
            if method_idx == 0:
                hint = ("No face selected yet — click any face first,\n"
                        "then click Draft Analysis.")
            else:
                hint = ("No sign-change edges found.\n"
                        "Try flipping the direction, selecting a face, or\n"
                        "switching to Face Boundary method.")
            self._msg.setText(hint)
            self._msg.setStyleSheet(
                "font-size:10px;color:#880000;background:#ffdddd;"
                "border:1px solid #cc0000;border-radius:3px;padding:4px;")

    def _on_analysis_error(self, error_msg):
        self._analyze_btn.setEnabled(True)
        try:
            self._src_obj.ViewObject.Visibility = True
        except Exception:
            pass
        self._msg.setText(f"Analysis failed: {error_msg}")
        self._msg.setStyleSheet(
            "font-size:10px;color:#880000;background:#ffdddd;"
            "border:1px solid #cc0000;border-radius:3px;padding:4px;")

    def _toggle_lines(self, checked):
        if self._doc_name not in _pl_overlays:
            return
        try:
            _, edge_switch, _hs, _fs = _pl_overlays[self._doc_name]
            edge_switch.whichChild.setValue(0 if checked else -1)
            Gui.updateGui()
        except Exception:
            pass

    def _on_edge_selected(self, idx):
        """When an edge is clicked in the list:
        - Hide the draft-analysis colour overlay
        - Restore original object visibility
        - Show only the thick yellow highlight on that edge."""
        if self._doc_name not in _pl_overlays:
            return
        try:
            from pivy import coin
            _, _es, hl_switch, faces_switch = _pl_overlays[self._doc_name]

            # Remove previous highlight geometry
            while hl_switch.getNumChildren() > 0:
                hl_switch.removeChild(0)

            if idx < 0 or idx >= len(self._parting_edges):
                # No selection → show color overlay, hide original, hide highlight
                faces_switch.whichChild.setValue(0)
                hl_switch.whichChild.setValue(-1)
                try:
                    self._src_obj.ViewObject.Visibility = False
                except Exception:
                    pass
                Gui.updateGui()
                return

            # Edge selected →
            #   hide colored overlay + show original object + show highlight only
            faces_switch.whichChild.setValue(-1)
            try:
                self._src_obj.ViewObject.Visibility = True
            except Exception:
                pass

            edge = self._parting_edges[idx]

            # Build highlight: thick yellow line with slight offset
            hsep = coin.SoSeparator()
            hlm  = coin.SoLightModel()
            hlm.model.setValue(coin.SoLightModel.BASE_COLOR)
            hsep.addChild(hlm)
            hbc  = coin.SoBaseColor()
            hbc.rgb.setValue(1.0, 0.90, 0.0)   # bright yellow
            hsep.addChild(hbc)
            hds  = coin.SoDrawStyle()
            hds.lineWidth.setValue(5.0)
            hsep.addChild(hds)

            try:
                pts = edge.discretize(Number=80)
                if pts and len(pts) >= 2:
                    ep = [(p.x, p.y, p.z) for p in pts]
                    coords = coin.SoCoordinate3()
                    coords.point.setValues(0, len(ep), ep)
                    hsep.addChild(coords)
                    ls = coin.SoLineSet()
                    ls.numVertices.setValue(len(pts))
                    hsep.addChild(ls)
            except Exception:
                pass

            hl_switch.addChild(hsep)
            hl_switch.whichChild.setValue(0)
            Gui.updateGui()
        except Exception:
            pass

    # ── Task panel interface ──────────────────────────────────────────────────
    def isAllowedAlterSelection(self): return True
    def isAllowedAlterView(self):      return True
    def isAllowedAlterDocument(self):  return False

    def accept(self):
        self._cleanup()
        _clear_pl_overlay(self._doc_name)

        if not self._parting_edges:
            src = (self._src_obj.Tip
                   if (hasattr(self._src_obj, "Tip") and self._src_obj.Tip)
                   else self._src_obj)
            if hasattr(src, "Shape") and not src.Shape.isNull():
                self._parting_edges = _find_parting_edges(
                    src.Shape, self._pull_dir, self._angle_spin.value())

        if not self._parting_edges:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Parting Line",
                "No parting edges found.\n\n"
                "Run 'Draft Analysis' first, or try flipping the direction.")
            Gui.Control.closeDialog()
            return

        try:
            import Part
            compound = Part.Compound(self._parting_edges)
            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Parting Line")
            feat = doc.addObject("Part::Feature", "PartingLine")
            feat.Label = "Parting Line"
            feat.Shape = compound
            try:
                feat.ViewObject.LineColor  = (1.0, 0.18, 0.58)  # pink/magenta
                feat.ViewObject.LineWidth  = 3.0
                feat.ViewObject.PointColor = (1.0, 0.18, 0.58)
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
                Gui.getMainWindow(), "Parting Line", f"Failed:\n{e}")
        finally:
            Gui.Control.closeDialog()

    def reject(self):
        self._cleanup()
        _clear_pl_overlay(self._doc_name)
        Gui.Control.closeDialog()

    def _cleanup(self):
        # Restore original object visibility
        try:
            self._src_obj.ViewObject.Visibility = True
        except Exception:
            pass
        if self._face_obs:
            try:
                Gui.Selection.removeObserver(self._face_obs)
            except Exception:
                pass
            self._face_obs = None


# ── Command ───────────────────────────────────────────────────────────────────
class CommandPartingLine:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldPartingLine.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_PartingLine", "Parting Line"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_PartingLine",
                        "Detect parting line using draft analysis (SolidWorks-style)."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc_name = FreeCAD.ActiveDocument.Name

        # Toggle off if already open
        if doc_name in _pl_overlays:
            _clear_pl_overlay(doc_name)
            try:
                Gui.Control.closeDialog()
            except Exception:
                pass
            return

        # Find a solid object
        src_obj = None
        for sel in Gui.Selection.getSelectionEx():
            o = sel.Object
            src = o.Tip if (hasattr(o, "Tip") and o.Tip) else o
            if hasattr(src, "Shape") and not src.Shape.isNull():
                src_obj = o
                break
        if src_obj is None:
            for obj in FreeCAD.ActiveDocument.Objects:
                src = obj.Tip if (hasattr(obj, "Tip") and obj.Tip) else obj
                if hasattr(src, "Shape") and not src.Shape.isNull():
                    src_obj = obj
                    break

        if src_obj is None:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Parting Line",
                "Please open or select a solid body first.")
            return

        try:
            Gui.Control.closeDialog()
        except Exception:
            pass

        panel = _PartingLinePanel(src_obj, doc_name)
        Gui.Control.showDialog(panel)


Gui.addCommand("BNCMold_PartingLine", CommandPartingLine())
