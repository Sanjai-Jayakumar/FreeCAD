# SPDX-License-Identifier: LGPL-2.1-or-later
# ANVIL CAD: Creo-style auto-snap for datum feature symbols.
#
# Drag a datum symbol (a DrawViewSymbol whose Label starts with "Datum")
# near a view's geometry and it magnetically snaps onto the nearest edge
# LINE, auto-rotates so the triangle sits perpendicular on that edge (box
# pointing outward), and attaches to the view (Owner) so it moves with the
# drawing.  No pre-selection, no steps.

import os
import FreeCAD as App

_SNAP_THRESHOLD = 28.0
_VIEW_TIDS = ("TechDraw::DrawViewPart", "TechDraw::DrawProjGroupItem")
_LOG = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                    "bnc_datum_snap.log")

_snapping = False
_pending = set()


def _log(msg):
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def _is_datum(obj):
    try:
        return (obj.TypeId == "TechDraw::DrawViewSymbol"
                and str(obj.Label).startswith("Datum"))
    except Exception:
        return False


def _page_of(obj):
    for p in getattr(obj, "InList", []):
        if p.TypeId == "TechDraw::DrawPage":
            return p
    try:
        for o in obj.Document.Objects:
            if o.TypeId == "TechDraw::DrawPage" and obj in o.Views:
                return o
    except Exception:
        pass
    return None


def _view_page_center(view):
    """TRUE page-coordinate centre of a view. A ProjGroupItem's X/Y is
    relative to its parent ProjGroup, so add the group's position."""
    x, y = float(view.X), float(view.Y)
    if view.TypeId == "TechDraw::DrawProjGroupItem":
        for g in getattr(view, "InList", []):
            if g.TypeId == "TechDraw::DrawProjGroup":
                return x + float(g.X), y + float(g.Y)
    return x, y


def _views_on_page(page):
    out = []
    for v in getattr(page, "Views", []):
        if v.TypeId in _VIEW_TIDS:
            out.append(v)
        elif v.TypeId == "TechDraw::DrawProjGroup":
            for c in getattr(v, "Views", []):
                if c.TypeId in _VIEW_TIDS:
                    out.append(c)
    return out


def _sym_page_pos(sym):
    """Datum symbol centre in PAGE coordinates (handles owned/free)."""
    x, y = float(sym.X), float(sym.Y)
    owner = getattr(sym, "Owner", None)
    if owner is not None and owner.TypeId in _VIEW_TIDS:
        ox, oy = _view_page_center(owner)
        return x + ox, y + oy
    return x, y


def _nearest_edge(sym):
    import Part
    from FreeCAD import Vector
    page = _page_of(sym)
    if not page:
        _log("  no page for symbol")
        return None
    px, py = _sym_page_pos(sym)
    best = None
    nviews = 0
    for view in _views_on_page(page):
        nviews += 1
        vx, vy = _view_page_center(view)
        local = Vector(px - vx, py - vy, 0.0)
        probe = Part.Vertex(local)
        try:
            edges = view.getVisibleEdges() or []
        except Exception:
            edges = []
        for e in edges:
            try:
                d, pts, _ = e.distToShape(probe)
                if best is None or d < best[3]:
                    best = (view, e, pts[0][0], d)
            except Exception:
                pass
    _log("  scanned {} views; best dist={}".format(
        nviews, round(best[3], 2) if best else None))
    return best


def _symbol_height(sym):
    import re
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', sym.Symbol or "")
    return float(m.group(2)) if m else 14.0


# ── datum symbol builder (letter stays UPRIGHT; orientation chosen so the
#    box sits on the outward side and no whole-symbol rotation is needed) ──
_B, _FS, _TB, _TH, _S, _LW = 7.0, 4.0, 5.0, 4.0, 3.0, 0.4


def _d_box(x, y, letter):
    cx = x + _B / 2.0
    # vertical centre = box centre + ~0.35*font (cap-height/2) so the glyph is
    # visually centred without relying on dominant-baseline (Qt SVG ignores it)
    by = y + _B / 2.0 + _FS * 0.35
    return ('<rect x="{x:.2f}" y="{y:.2f}" width="{b:.2f}" height="{b:.2f}" '
            'fill="white" stroke="#000" stroke-width="{lw}"/>'
            '<text x="{cx:.2f}" y="{by:.2f}" font-family="osifont" font-size="{fs}" '
            'text-anchor="middle" fill="#000">{L}</text>'
            ).format(x=x, y=y, b=_B, lw=_LW, cx=cx, by=by, fs=_FS, L=letter)


def _d_line(x1, y1, x2, y2):
    return ('<line x1="{:.2f}" y1="{:.2f}" x2="{:.2f}" y2="{:.2f}" stroke="#000" '
            'stroke-width="{}"/>'.format(x1, y1, x2, y2, _LW))


def _d_tri(pts):
    p = " ".join("{:.2f},{:.2f}".format(px, py) for px, py in pts)
    return '<polygon points="{}" fill="#000" stroke="#000" stroke-width="{}"/>'.format(p, _LW)


def _build_datum(letter, orient):
    o = []
    if orient in ("Bottom", "Top"):
        W, Hh, cx = _B, _B + _S + _TH, _B / 2.0
        if orient == "Bottom":
            o.append(_d_box(0, 0, letter))
            o.append(_d_line(cx, _B, cx, _B + _S))
            o.append(_d_tri([(cx, _B + _S), (cx - _TB / 2.0, _B + _S + _TH),
                             (cx + _TB / 2.0, _B + _S + _TH)]))
        else:
            o.append(_d_box(0, _TH + _S, letter))
            o.append(_d_line(cx, _TH + _S, cx, _TH))
            o.append(_d_tri([(cx, _TH), (cx - _TB / 2.0, 0), (cx + _TB / 2.0, 0)]))
    else:
        W, Hh, cy = _B + _S + _TH, _B, _B / 2.0
        if orient == "Right":
            o.append(_d_box(0, 0, letter))
            o.append(_d_line(_B, cy, _B + _S, cy))
            o.append(_d_tri([(_B + _S, cy), (_B + _S + _TH, cy - _TB / 2.0),
                             (_B + _S + _TH, cy + _TB / 2.0)]))
        else:  # Left
            o.append(_d_box(_TH + _S, 0, letter))
            o.append(_d_line(_TH + _S, cy, _TH, cy))
            o.append(_d_tri([(_TH, cy), (0, cy - _TB / 2.0), (0, cy + _TB / 2.0)]))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
           'width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.2f} {h:.2f}">{b}</svg>'
           ).format(w=W, h=Hh, b="".join(o))
    return svg, W, Hh


def _letter_of(sym):
    lbl = str(sym.Label)
    return lbl.split("_", 1)[1] if "_" in lbl else "A"


def _do_snap(name):
    global _snapping
    if _snapping:
        return
    try:
        import math
        from FreeCAD import Vector
        doc = App.ActiveDocument
        sym = doc.getObject(name) if doc else None
        if sym is None or not _is_datum(sym):
            return
        _log("do_snap {}: page_pos={}".format(name, _sym_page_pos(sym)))
        res = _nearest_edge(sym)
        if not res:
            return
        view, edge, P, dist = res
        if dist > _SNAP_THRESHOLD:
            _log("  too far ({:.1f} > {}) — no snap".format(dist, _SNAP_THRESHOLD))
            return
        # outward normal at the snap point (away from the view centre = origin)
        try:
            param = edge.Curve.parameter(P)
            tv = edge.tangentAt(param)
            tangent = Vector(tv.x, tv.y, 0.0)
        except Exception:
            tangent = Vector(1.0, 0.0, 0.0)
        if tangent.Length < 1e-6:
            tangent = Vector(1.0, 0.0, 0.0)
        tangent.normalize()
        normal = Vector(-tangent.y, tangent.x, 0.0)
        if normal.dot(Vector(P.x, P.y, 0.0)) < 0:
            normal = Vector(tangent.y, -tangent.x, 0.0)
        if normal.Length < 1e-6:
            normal = Vector(0.0, 1.0, 0.0)
        normal.normalize()

        # Pick the pre-built orientation whose BOX sits on the outward side,
        # so the datum letter stays UPRIGHT (no whole-symbol rotation -> no
        # upside-down letter).  Snap to the nearest of the 4 axes.
        if abs(normal.y) >= abs(normal.x):
            orient = "Bottom" if normal.y > 0 else "Top"
        else:
            orient = "Left" if normal.x > 0 else "Right"

        letter = _letter_of(sym)
        new_svg, _w, _h = _build_datum(letter, orient)
        # base sits on the edge point P; centre is half the long dim (7mm)
        # toward the box (outward = +normal)
        cx = P.x + normal.x * 7.0
        cy = P.y + normal.y * 7.0

        _snapping = True
        try:
            if getattr(sym, "Owner", None) is not view:
                sym.Owner = view
            sym.Symbol = new_svg          # rebuilt upright in the right orientation
            sym.Rotation = 0.0            # never rotate the whole symbol
            sym.X = float(cx)
            sym.Y = float(cy)
            doc.recompute([sym, view, _page_of(sym)])
        finally:
            _snapping = False
        _log("  SNAPPED to {} at ({:.1f},{:.1f}) orient={} (upright)".format(
            view.Label, P.x, P.y, orient))
    except Exception as e:
        _snapping = False
        _log("  ERROR: {}".format(e))


def _run_pending():
    names = list(_pending)
    _pending.clear()
    for n in names:
        _do_snap(n)


class _DatumSnapObserver:
    def slotChangedObject(self, obj, prop):
        if _snapping:
            return
        try:
            if prop in ("X", "Y") and _is_datum(obj):
                _log("changed {} .{}".format(obj.Name, prop))
                _pending.add(obj.Name)
                from PySide import QtCore
                QtCore.QTimer.singleShot(250, _run_pending)
        except Exception:
            pass


_observer = _DatumSnapObserver()


def install():
    try:
        with open(_LOG, "w", encoding="utf-8") as f:
            f.write("=== datum auto-snap installed ===\n")
    except Exception:
        pass
    App.addDocumentObserver(_observer)


install()
