# SPDX-License-Identifier: LGPL-2.1-or-later
"""G0/G1/G2 continuity sampling between two faces along a shared boundary.

G0 = positional gap (mm), G1 = normal angle (degrees), G2 = relative deviation
of the normal curvature taken in the cross-boundary direction (0..1).
"""
import math
import numpy as np
import FreeCAD
import Part

Vector = FreeCAD.Vector

# Default Class-A acceptance presets (editable in the checker panel)
G0_TOL_MM = 0.01
G1_TOL_DEG = 0.05
G2_TOL_REL = 0.02


def normal_curvature(surf, u, v, direction):
    """Normal curvature of `surf` at (u,v) in tangent direction `direction`.

    Euler's theorem: kn(theta) = k1*cos^2(theta) + k2*sin^2(theta), theta
    measured from the principal direction of k1. The direction is projected
    into the tangent plane first.
    """
    n = surf.normal(u, v)
    d = Vector(direction)
    d = d - n * d.dot(n)          # project into tangent plane
    if d.Length < 1e-12:
        return 0.0
    d.normalize()
    k1 = surf.curvature(u, v, "Max")
    k2 = surf.curvature(u, v, "Min")
    try:
        dir_max, _dir_min = surf.curvatureDirections(u, v)
    except Exception:
        # Umbilic or degenerate point: any direction has the same curvature
        return k1
    c = max(-1.0, min(1.0, d.dot(dir_max)))
    cos2 = c * c
    return k1 * cos2 + k2 * (1.0 - cos2)


class ContinuityReport(object):
    """Sampled continuity numbers along a shared edge."""

    def __init__(self, params, points, g0, g1, g2):
        self.params = list(params)
        self.points = list(points)   # FreeCAD.Vector per station
        self.g0 = list(g0)           # mm
        self.g1 = list(g1)           # degrees
        self.g2 = list(g2)           # relative (0..1)

    @property
    def max_g0(self):
        return max(self.g0) if self.g0 else 0.0

    @property
    def max_g1(self):
        return max(self.g1) if self.g1 else 0.0

    @property
    def max_g2(self):
        return max(self.g2) if self.g2 else 0.0

    def worst_station(self, level):
        vals = {"G0": self.g0, "G1": self.g1, "G2": self.g2}[level]
        if not vals:
            return None
        i = int(np.argmax(vals))
        return self.params[i], self.points[i], vals[i]

    def summary(self):
        def stats(vals):
            if not vals:
                return (0.0, 0.0, 0.0)
            return (min(vals), max(vals), sum(vals) / len(vals))
        return {"G0": stats(self.g0), "G1": stats(self.g1), "G2": stats(self.g2)}

    def passes(self, g0_tol=G0_TOL_MM, g1_tol=G1_TOL_DEG, g2_tol=G2_TOL_REL):
        return (self.max_g0 <= g0_tol, self.max_g1 <= g1_tol, self.max_g2 <= g2_tol)


def sample_continuity(face_a, face_b, edge, n=40, eps_curvature=1e-9):
    """Sample G0/G1/G2 between two faces along `edge` at n stations.

    The edge only defines the sampling stations — each face is evaluated at
    its own closest point, so the measurement works whether or not the two
    faces share identical boundary geometry.
    """
    surf_a, surf_b = face_a.Surface, face_b.Surface
    t0, t1 = edge.FirstParameter, edge.LastParameter
    params, points, g0s, g1s, g2s = [], [], [], [], []

    for t in np.linspace(t0, t1, n):
        q = edge.valueAt(float(t))
        try:
            ua, va = surf_a.parameter(q)
            ub, vb = surf_b.parameter(q)
        except Exception:
            continue
        pa, pb = surf_a.value(ua, va), surf_b.value(ub, vb)
        g0 = (pa - pb).Length

        na, nb = surf_a.normal(ua, va), surf_b.normal(ub, vb)
        flip = na.dot(nb) < 0.0
        if flip:
            nb = nb * -1.0
        dot = max(-1.0, min(1.0, na.dot(nb)))
        g1 = math.degrees(math.acos(dot))

        # cross-boundary direction: perpendicular to the edge tangent within
        # the (averaged) tangent plane
        tangent = edge.tangentAt(float(t))
        d = tangent.cross(na)
        ka = normal_curvature(surf_a, ua, va, d)
        kb = normal_curvature(surf_b, ub, vb, d)
        if flip:
            kb = -kb
        denom = max(abs(ka), abs(kb), eps_curvature)
        g2 = abs(ka - kb) / denom if denom > eps_curvature else 0.0

        params.append(float(t))
        points.append(q)
        g0s.append(g0)
        g1s.append(g1)
        g2s.append(g2)

    return ContinuityReport(params, points, g0s, g1s, g2s)


def find_shared_edge(face_a, face_b, tol=0.5):
    """Best candidate for the shared boundary between two faces.

    Returns the edge of face_a whose sampled points lie closest to face_b's
    nearest edge. Raises ValueError if nothing comes within `tol`.
    """
    best = None
    for ea in face_a.Edges:
        ts = np.linspace(ea.FirstParameter, ea.LastParameter, 5)
        pts = [ea.valueAt(float(t)) for t in ts]
        for eb in face_b.Edges:
            dist = max(Part.Vertex(p).distToShape(eb)[0] for p in pts)
            if best is None or dist < best[1]:
                best = (ea, dist)
    if best is None or best[1] > tol:
        raise ValueError("faces do not appear to share a boundary "
                         "(closest edge distance %.3f mm)" % (best[1] if best else -1))
    return best[0]
