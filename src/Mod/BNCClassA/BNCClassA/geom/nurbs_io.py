# SPDX-License-Identifier: LGPL-2.1-or-later
"""Conversions between FreeCAD Part B-splines and numpy pole arrays, plus
edge/face resolution helpers shared by the Class-A tools.

Convention: surface pole arrays are (nu, nv, 3), index order matching
Part.BSplineSurface.getPoles() (first index = u).
"""
import numpy as np
import FreeCAD
import Part

from . import bezier

Vector = FreeCAD.Vector


# --------------------------------------------------------------------------
# numpy <-> FreeCAD
# --------------------------------------------------------------------------

def to_np(vectors):
    return np.array([[v.x, v.y, v.z] for v in vectors], dtype=float)


def to_vectors(arr):
    return [Vector(float(p[0]), float(p[1]), float(p[2])) for p in np.asarray(arr).reshape(-1, 3)]


def curve_poles(bs):
    """(n, 3) pole array of a Part.BSplineCurve / BezierCurve."""
    return to_np(bs.getPoles())


def surface_poles(bs):
    """(nu, nv, 3) pole array of a Part.BSplineSurface."""
    rows = bs.getPoles()
    return np.array([[[v.x, v.y, v.z] for v in row] for row in rows], dtype=float)


def make_bezier_curve(poles):
    """Single-span non-rational Bézier curve from an (n, 3) pole array."""
    poles = np.asarray(poles, dtype=float)
    degree = len(poles) - 1
    bs = Part.BSplineCurve()
    bs.buildFromPolesMultsKnots(
        to_vectors(poles),
        mults=[degree + 1, degree + 1],
        knots=[0.0, 1.0],
        periodic=False,
        degree=degree,
    )
    return bs


def make_bezier_surface(poles):
    """Single-span non-rational Bézier surface from an (nu, nv, 3) pole array."""
    poles = np.asarray(poles, dtype=float)
    nu, nv = poles.shape[0], poles.shape[1]
    du, dv = nu - 1, nv - 1
    grid = [[Vector(*[float(c) for c in poles[i, j]]) for j in range(nv)]
            for i in range(nu)]
    bs = Part.BSplineSurface()
    bs.buildFromPolesMultsKnots(
        grid,
        umults=[du + 1, du + 1],
        vmults=[dv + 1, dv + 1],
        uknots=[0.0, 1.0],
        vknots=[0.0, 1.0],
        uperiodic=False,
        vperiodic=False,
        udegree=du,
        vdegree=dv,
    )
    return bs


def is_single_span_bezier(geom):
    """True if a BSpline curve/surface is single-span and non-rational."""
    try:
        if hasattr(geom, "NbUKnots"):
            return (geom.NbUKnots == 2 and geom.NbVKnots == 2
                    and not geom.isURational() and not geom.isVRational())
        return geom.NbKnots == 2 and not geom.isRational()
    except Exception:
        return False


# --------------------------------------------------------------------------
# Edge -> Bézier pole net
# --------------------------------------------------------------------------

def edge_samples(edge, n):
    """(n, 3) points sampled uniformly in parameter over the edge."""
    t0, t1 = edge.FirstParameter, edge.LastParameter
    params = np.linspace(t0, t1, n)
    return np.array([[p.x, p.y, p.z] for p in (edge.valueAt(t) for t in params)])


def edge_to_bezier(edge, degree=5, samples=100):
    """Represent an edge as a single-span Bézier pole net.

    Exact when the underlying curve already is one (of degree <= requested);
    otherwise a constrained least-squares fit with pinned endpoints.
    Returns (poles (d+1, 3), max_deviation).
    """
    curve = edge.Curve
    try:
        trimmed = curve.copy()
        if hasattr(trimmed, "segment"):
            trimmed.segment(edge.FirstParameter, edge.LastParameter)
        bs = trimmed.toBSpline() if not isinstance(trimmed, Part.BSplineCurve) else trimmed
        if is_single_span_bezier(bs) and bs.Degree <= degree:
            poles = curve_poles(bs)
            if bs.Degree < degree:
                poles = bezier.elevate(poles, degree - bs.Degree)
            return poles, 0.0
    except Exception:
        pass

    pts = edge_samples(edge, samples)
    params = _chord_length_params(pts)
    pinned = {0: pts[0], degree: pts[-1]}
    return bezier.fit_bezier(pts, params, degree, pinned)


def _chord_length_params(pts):
    d = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(axis=1))
    cum = np.concatenate([[0.0], np.cumsum(d)])
    total = cum[-1]
    return cum / total if total > 0 else np.linspace(0.0, 1.0, len(pts))


# --------------------------------------------------------------------------
# Boundary canonicalization for the match solver
# --------------------------------------------------------------------------
# Boundaries named "u0" (u=0 row), "u1", "v0", "v1". `to_boundary` reorients a
# pole array so the named boundary becomes row 0 (axis 0 = cross direction);
# `from_boundary` is the exact inverse.

def to_boundary(poles, boundary):
    p = np.asarray(poles, dtype=float)
    if boundary == "u0":
        return p.copy()
    if boundary == "u1":
        return p[::-1].copy()
    if boundary == "v0":
        return np.transpose(p, (1, 0, 2)).copy()
    if boundary == "v1":
        return np.transpose(p, (1, 0, 2))[::-1].copy()
    raise ValueError("unknown boundary %r" % boundary)


def from_boundary(poles, boundary):
    p = np.asarray(poles, dtype=float)
    if boundary == "u0":
        return p.copy()
    if boundary == "u1":
        return p[::-1].copy()
    if boundary == "v0":
        return np.transpose(p, (1, 0, 2)).copy()
    if boundary == "v1":
        return np.transpose(p[::-1], (1, 0, 2)).copy()
    raise ValueError("unknown boundary %r" % boundary)


def identify_boundary(poles, edge, tol=1e-4):
    """Which boundary ("u0"/"u1"/"v0"/"v1") of a pole net lies on `edge`.

    Compares sampled boundary-curve points against the edge; returns
    (boundary, reversed) where reversed=True means the boundary runs
    antiparallel to the edge parameterization. Raises ValueError if none match.
    """
    p = np.asarray(poles, dtype=float)
    candidates = {
        "u0": p[0], "u1": p[-1], "v0": p[:, 0], "v1": p[:, -1],
    }
    ts = np.linspace(0.0, 1.0, 7)
    best = None
    for name, bpoles in candidates.items():
        pts = bezier.evaluate(bpoles, ts)
        dist = max(Part.Vertex(Vector(*pt)).distToShape(edge)[0] for pt in pts)
        if best is None or dist < best[1]:
            best = (name, dist, bpoles)
    name, dist, bpoles = best
    if dist > max(tol, 1e-7 * float(np.abs(p).max() + 1.0)):
        raise ValueError("edge does not lie on any surface boundary (dist=%g)" % dist)

    e0 = edge.valueAt(edge.FirstParameter)
    start = bezier.evaluate(bpoles, [0.0])[0]
    end = bezier.evaluate(bpoles, [1.0])[0]
    d_start = np.linalg.norm(start - np.array([e0.x, e0.y, e0.z]))
    d_end = np.linalg.norm(end - np.array([e0.x, e0.y, e0.z]))
    return name, d_end < d_start


def flip_along(poles):
    """Reverse the along-edge direction (axis 1) of a boundary-canonical net."""
    return np.asarray(poles, dtype=float)[:, ::-1].copy()


# --------------------------------------------------------------------------
# Selection helpers
# --------------------------------------------------------------------------

def host_faces_of_edge(shape, edge):
    """Faces of `shape` that contain `edge` (isSame comparison)."""
    return [f for f in shape.Faces if any(e.isSame(edge) for e in f.Edges)]


def face_uv(face, point):
    """(u, v) of `point` on the face's underlying surface."""
    return face.Surface.parameter(point)
