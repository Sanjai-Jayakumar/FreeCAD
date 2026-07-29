# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coin3D overlay engine for the Class-A analysis tools.

Follows the proven BNCMoldTools/CommandDraftAnalysis.py approach: analysis
visuals are self-contained scenegraph overlays added to the 3D view root and
tracked in a registry — document objects are never touched (in particular
DiffuseColor, which is broken on Part::Feature in this fork).

Registry key is (doc_name, tool_key) so several analysis overlays can be
active at once (e.g. zebra + continuity ticks).
"""
import math
import numpy as np
import FreeCAD
import FreeCADGui as Gui

_overlays = {}   # (doc_name, tool_key) -> {"node": SoSeparator, "hidden": [obj names]}

VERTEX_CAP = 500_000


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

def _scene_graph():
    view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
    return view.getSceneGraph() if view else None


def show(doc_name, tool_key, node, hide_objects=None):
    """Install `node` as the overlay for (doc, tool), replacing any previous one."""
    clear(doc_name, tool_key)
    sg = _scene_graph()
    if sg is None:
        return
    hidden = []
    doc = FreeCAD.getDocument(doc_name)
    for obj in (hide_objects or []):
        try:
            if obj.ViewObject.Visibility:
                obj.ViewObject.Visibility = False
                hidden.append(obj.Name)
        except Exception:
            pass
    sg.addChild(node)
    _overlays[(doc_name, tool_key)] = {"node": node, "hidden": hidden}
    Gui.updateGui()


def clear(doc_name, tool_key):
    entry = _overlays.pop((doc_name, tool_key), None)
    if entry is None:
        return
    sg = _scene_graph()
    try:
        if sg is not None and sg.findChild(entry["node"]) >= 0:
            sg.removeChild(entry["node"])
    except Exception:
        pass
    try:
        doc = FreeCAD.getDocument(doc_name)
        for name in entry["hidden"]:
            obj = doc.getObject(name)
            if obj is not None:
                obj.ViewObject.Visibility = True
    except Exception:
        pass
    Gui.updateGui()


def clear_all(doc_name=None):
    for key in [k for k in _overlays if doc_name is None or k[0] == doc_name]:
        clear(*key)


# --------------------------------------------------------------------------
# Tessellation with exact surface normals
# --------------------------------------------------------------------------

def quality_to_tol(quality):
    """Map the 1-10 quality slider to a tessellation deviation (mm).

    Finer than draft analysis — reflections expose facets brutally."""
    q = max(1, min(10, int(quality)))
    return max(0.02, 0.8 - q * 0.078)


def tessellate(faces, quality=7, vertex_cap=VERTEX_CAP):
    """Tessellate faces into one indexed mesh with per-vertex normals.

    Normals come from the exact surface (Surface.parameter + Face.normalAt)
    and fall back to triangle-accumulated averages where the projection fails.
    Returns dict with: verts [(x,y,z)], normals [(x,y,z)], coord_idx (with -1
    separators), face_ranges [(face, first_vertex, count)], capped (bool).
    """
    tol = quality_to_tol(quality)
    verts, normals, coord_idx, face_ranges = [], [], [], []
    v_offset = 0
    capped = False

    for face in faces:
        try:
            pts, tris = face.tessellate(tol)
        except Exception:
            continue
        if not pts or not tris:
            continue
        n_pts = len(pts)

        # reference normal for orientation of the fallback normals
        ref = None
        try:
            umin, umax, vmin, vmax = face.ParameterRange
            ref = face.normalAt(0.5 * (umin + umax), 0.5 * (vmin + vmax))
            if ref.Length > 1e-10:
                ref = ref.normalize()
            else:
                ref = None
        except Exception:
            ref = None

        # triangle-accumulated fallback normals
        acc = np.zeros((n_pts, 3))
        p_arr = np.array([[p.x, p.y, p.z] for p in pts])
        for tri in tris:
            if len(tri) < 3:
                continue
            a, b, c = p_arr[tri[0]], p_arr[tri[1]], p_arr[tri[2]]
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln < 1e-12:
                continue
            n /= ln
            if ref is not None and (n[0] * ref.x + n[1] * ref.y + n[2] * ref.z) < 0:
                n = -n
            for vi in tri:
                acc[vi] += n

        surf = face.Surface
        face_normals = []
        for i in range(n_pts):
            n = None
            try:
                u, v = surf.parameter(pts[i])
                nv = face.normalAt(u, v)
                if nv.Length > 1e-10:
                    nv = nv.normalize()
                    n = (nv.x, nv.y, nv.z)
            except Exception:
                n = None
            if n is None:
                a = acc[i]
                ln = np.linalg.norm(a)
                if ln > 1e-12:
                    a = a / ln
                    n = (float(a[0]), float(a[1]), float(a[2]))
                elif ref is not None:
                    n = (ref.x, ref.y, ref.z)
                else:
                    n = (0.0, 0.0, 1.0)
            face_normals.append(n)

        for i in range(n_pts):
            verts.append((pts[i].x, pts[i].y, pts[i].z))
        normals.extend(face_normals)
        for tri in tris:
            if len(tri) < 3:
                continue
            coord_idx.extend([v_offset + tri[0], v_offset + tri[1],
                              v_offset + tri[2], -1])
        face_ranges.append((face, v_offset, n_pts))
        v_offset += n_pts
        if v_offset > vertex_cap:
            capped = True
            break

    return {"verts": verts, "normals": normals, "coord_idx": coord_idx,
            "face_ranges": face_ranges, "capped": capped}


# --------------------------------------------------------------------------
# Node builders
# --------------------------------------------------------------------------

def colored_mesh_node(mesh, colors):
    """Unlit mesh colored per vertex — DraftAnalysis-style false-color map."""
    from pivy import coin
    root = coin.SoSeparator()
    lm = coin.SoLightModel()
    lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    root.addChild(lm)
    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    root.addChild(hints)
    poff = coin.SoPolygonOffset()
    poff.styles.setValue(coin.SoPolygonOffset.FILLED)
    poff.factor.setValue(10.0)
    poff.units.setValue(10.0)
    root.addChild(poff)
    bc = coin.SoBaseColor()
    bc.rgb.setValues(0, len(colors), colors)
    root.addChild(bc)
    mb = coin.SoMaterialBinding()
    mb.value.setValue(coin.SoMaterialBinding.PER_VERTEX_INDEXED)
    root.addChild(mb)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(mesh["verts"]), mesh["verts"])
    root.addChild(coords)
    ifs = coin.SoIndexedFaceSet()
    ifs.coordIndex.setValues(0, len(mesh["coord_idx"]), mesh["coord_idx"])
    ifs.materialIndex.setValues(0, len(mesh["coord_idx"]), mesh["coord_idx"])
    root.addChild(ifs)
    return root


def textured_mesh_node(mesh, image):
    """Lit white mesh with a sphere-mapped environment texture (zebra/env map).

    `image` = (width, height, bytes_rgb). SoTextureCoordinateEnvironment
    computes eye-space reflection coordinates per frame, so the stripes flow
    over the surface as the camera moves — the Class-A zebra behavior.
    """
    from pivy import coin
    root = coin.SoSeparator()

    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.COUNTERCLOCKWISE)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    root.addChild(hints)
    poff = coin.SoPolygonOffset()
    poff.styles.setValue(coin.SoPolygonOffset.FILLED)
    poff.factor.setValue(10.0)
    poff.units.setValue(10.0)
    root.addChild(poff)

    mat = coin.SoMaterial()
    mat.diffuseColor.setValue(1.0, 1.0, 1.0)
    mat.specularColor.setValue(0.1, 0.1, 0.1)
    mat.shininess.setValue(0.6)
    root.addChild(mat)

    w, h, data = image
    tex = coin.SoTexture2()
    tex.image.setValue(coin.SbVec2s(w, h), 3, data)
    tex.model.setValue(coin.SoTexture2.MODULATE)
    root.addChild(tex)
    root.addChild(coin.SoTextureCoordinateEnvironment())

    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(mesh["verts"]), mesh["verts"])
    root.addChild(coords)
    nrm = coin.SoNormal()
    nrm.vector.setValues(0, len(mesh["normals"]), mesh["normals"])
    root.addChild(nrm)
    nb = coin.SoNormalBinding()
    nb.value.setValue(coin.SoNormalBinding.PER_VERTEX_INDEXED)
    root.addChild(nb)

    ifs = coin.SoIndexedFaceSet()
    ifs.coordIndex.setValues(0, len(mesh["coord_idx"]), mesh["coord_idx"])
    ifs.normalIndex.setValues(0, len(mesh["coord_idx"]), mesh["coord_idx"])
    root.addChild(ifs)
    return root


def lines_node(polylines, rgb=(1.0, 1.0, 1.0), width=1.5):
    """Unlit polyline bundle. polylines = list of lists of (x,y,z)."""
    from pivy import coin
    root = coin.SoSeparator()
    lm = coin.SoLightModel()
    lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    root.addChild(lm)
    bc = coin.SoBaseColor()
    bc.rgb.setValue(*rgb)
    root.addChild(bc)
    ds = coin.SoDrawStyle()
    ds.lineWidth.setValue(width)
    root.addChild(ds)
    pts, counts = [], []
    for line in polylines:
        if len(line) < 2:
            continue
        pts.extend(line)
        counts.append(len(line))
    if pts:
        c = coin.SoCoordinate3()
        c.point.setValues(0, len(pts), pts)
        root.addChild(c)
        ls = coin.SoLineSet()
        ls.numVertices.setValues(0, len(counts), counts)
        root.addChild(ls)
    return root


def text_label_node(position, text, rgb=(1.0, 0.85, 0.2)):
    """Small screen-aligned text label at a 3D position."""
    from pivy import coin
    sep = coin.SoSeparator()
    lm = coin.SoLightModel()
    lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    sep.addChild(lm)
    bc = coin.SoBaseColor()
    bc.rgb.setValue(*rgb)
    sep.addChild(bc)
    tr = coin.SoTranslation()
    tr.translation.setValue(*position)
    sep.addChild(tr)
    txt = coin.SoText2()
    txt.string.setValue(text)
    sep.addChild(txt)
    return sep


def group_node(children):
    from pivy import coin
    root = coin.SoSeparator()
    for c in children:
        root.addChild(c)
    return root


# --------------------------------------------------------------------------
# Procedural textures (bytes, RGB8)
# --------------------------------------------------------------------------

def stripe_image(count=12, width_frac=0.5, angle_deg=0.0, sharp=True, size=512):
    """Black/white zebra stripe texture.

    count stripes across the image, rotated by angle_deg; width_frac is the
    black duty cycle; sharp=False antialiases the edges for smoother stripes.
    """
    y, x = np.meshgrid(np.linspace(0, 1, size), np.linspace(0, 1, size),
                       indexing="ij")
    a = math.radians(angle_deg)
    coord = x * math.cos(a) + y * math.sin(a)
    phase = (coord * count) % 1.0
    if sharp:
        val = np.where(phase < width_frac, 0.0, 1.0)
    else:
        edge = 0.06
        up = np.clip(phase / edge, 0, 1)
        down = np.clip((width_frac + edge - phase) / edge, 0, 1)
        inside = np.minimum(up, down)
        val = np.where(phase < width_frac + edge, 1.0 - inside, 1.0)
    img = (np.repeat(val[:, :, None], 3, axis=2) * 255).astype(np.uint8)
    return size, size, img.tobytes()


def studio_image(kind="studio", size=512):
    """Procedural environment textures for reflection evaluation."""
    y = np.linspace(0, 1, size).reshape(-1, 1)
    x = np.linspace(0, 1, size).reshape(1, -1)
    if kind == "sky":
        # blue sky above fading to warm ground
        r = 0.85 - 0.55 * y
        g = 0.90 - 0.40 * y
        b = 1.00 - 0.15 * y
        rgb = np.stack([np.broadcast_to(c, (size, size)) for c in (r, g, b)], axis=2)
    elif kind == "showroom":
        # dark room with bright rectangular window bands
        base = np.full((size, size), 0.12)
        for cy, hh in ((0.25, 0.06), (0.5, 0.10), (0.75, 0.06)):
            band = np.exp(-((y - cy) / hh) ** 4)
            base = np.maximum(base, np.broadcast_to(band, (size, size)) * 0.95)
        rgb = np.repeat(base[:, :, None], 3, axis=2)
    else:
        # soft studio: smooth vertical falloff + one wide softbox
        base = 0.25 + 0.35 * (1.0 - y)
        soft = 0.75 * np.exp(-((y - 0.35) / 0.18) ** 2)
        val = np.broadcast_to(base + soft, (size, size))
        val = np.clip(val, 0, 1)
        rgb = np.repeat(val[:, :, None], 3, axis=2)
    img = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    return size, size, img.tobytes()


# --------------------------------------------------------------------------
# Color maps
# --------------------------------------------------------------------------

def diverging_color(t):
    """t in [-1, 1] → blue-grey-red diverging color (Creo-like)."""
    t = max(-1.0, min(1.0, float(t)))
    f = abs(t) ** 0.55
    if t >= 0:
        return (0.73 + f * 0.17, 0.73 - f * 0.43, 0.76 - f * 0.46)   # grey → red
    return (0.73 - f * 0.42, 0.73 - f * 0.30, 0.76 + f * 0.10)       # grey → blue


def rainbow_color(t):
    """t in [0, 1] → blue → cyan → green → yellow → red."""
    t = max(0.0, min(1.0, float(t)))
    seg = t * 4.0
    if seg < 1.0:
        return (0.0, seg, 1.0)
    if seg < 2.0:
        return (0.0, 1.0, 2.0 - seg)
    if seg < 3.0:
        return (seg - 2.0, 1.0, 0.0)
    return (1.0, 4.0 - seg, 0.0)
