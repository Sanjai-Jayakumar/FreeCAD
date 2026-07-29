# SPDX-License-Identifier: LGPL-2.1-or-later
"""Blend construction: curves and surfaces joining two references with
prescribed end continuity (G0-G3) and tension.

Everything reduces to generalized Hermite interpolation in Bézier form: the
first k+1 poles of a degree-n Bézier are fixed by the end derivatives
(forward differences), the last k+1 by the far end.
"""
import math
import numpy as np
import FreeCAD

from . import bezier, nurbs_io

Vector = FreeCAD.Vector


def hermite_bezier_poles(derivs_start, derivs_end):
    """Bézier poles matching position/derivatives at both ends.

    derivs_start: [c(0), c'(0), c''(0), ...] (derivatives of the blend curve
    at t=0); derivs_end: same at t=1. Degree = len(start)+len(end)-1.
    """
    da = [np.asarray(d, dtype=float) for d in derivs_start]
    db = [np.asarray(d, dtype=float) for d in derivs_end]
    ka, kb = len(da) - 1, len(db) - 1
    n = ka + kb + 1
    poles = np.zeros((n + 1, 3))

    # forward differences at the start: Delta^j P_0 = D_j (n-j)!/n!
    fd = [da[j] * (math.factorial(n - j) / float(math.factorial(n)))
          for j in range(ka + 1)]
    for i in range(ka + 1):
        poles[i] = sum(math.comb(i, j) * fd[j] for j in range(i + 1))

    # reversed curve Q(s) = c(1-s): dQ/ds^j = (-1)^j D_j at t=1
    bd = [((-1) ** j) * db[j] * (math.factorial(n - j) / float(math.factorial(n)))
          for j in range(kb + 1)]
    for i in range(kb + 1):
        poles[n - i] = sum(math.comb(i, j) * bd[j] for j in range(i + 1))
    return poles


# --------------------------------------------------------------------------
# Blend curve between two edge ends
# --------------------------------------------------------------------------

def _edge_end_derivatives(edge, at_start, k, tension, chord):
    """Blend-curve end derivatives continuing an edge past one of its ends.

    at_start: continue past FirstParameter (else past LastParameter).
    The magnitude is normalized so |c'| = chord * tension, higher derivatives
    scale with the same reparameterization factor.
    """
    t = edge.FirstParameter if at_start else edge.LastParameter
    curve = edge.Curve
    sign = -1.0 if at_start else 1.0     # direction of travel out of the edge
    d1 = curve.getDN(t, 1) * sign
    mag = d1.Length
    if mag < 1e-12:
        raise ValueError("degenerate edge tangent")
    f = (chord * tension) / mag
    p0 = curve.getD0(t)
    derivs = [np.array([p0.x, p0.y, p0.z])]
    for j in range(1, k + 1):
        dj = curve.getDN(t, j)
        derivs.append(np.array([dj.x, dj.y, dj.z]) * ((sign ** j) * (f ** j)))
    return derivs


def blend_curve_poles(edge1, end1_start, k1, tension1,
                      edge2, end2_start, k2, tension2):
    """Blend curve joining an end of edge1 to an end of edge2.

    end*_start: True to attach at the edge's FirstParameter end.
    Continuity per end: 0-3. Returns Bézier poles of degree k1+k2+1.
    """
    p1 = edge1.valueAt(edge1.FirstParameter if end1_start else edge1.LastParameter)
    p2 = edge2.valueAt(edge2.FirstParameter if end2_start else edge2.LastParameter)
    chord = (p2 - p1).Length
    if chord < 1e-9:
        raise ValueError("blend ends coincide")
    da = _edge_end_derivatives(edge1, end1_start, k1, tension1, chord)
    db_out = _edge_end_derivatives(edge2, end2_start, k2, tension2, chord)
    # the blend ARRIVES at edge2: its own derivatives at t=1 continue INTO the
    # edge, i.e. travel opposite to edge2's outgoing direction
    db = [db_out[0]]
    for j in range(1, len(db_out)):
        db.append(db_out[j] * ((-1.0) ** j))
    return hermite_bezier_poles(da, db)


# --------------------------------------------------------------------------
# Blend surface between two face edges
# --------------------------------------------------------------------------

def _station_derivatives(face, point, toward, k, tension, chord):
    """Derivatives of the blend in the cross direction at a station on a face
    edge: exact directional derivatives of the host surface (getDN) along the
    tangent-plane direction pointing toward the other edge."""
    surf = face.Surface
    u, v = surf.parameter(Vector(*point))
    n = surf.normal(u, v)
    w = Vector(*toward)
    w = w - n * w.dot(n)
    if w.Length < 1e-9:
        raise ValueError("cross direction degenerates at a station")
    w.normalize()

    su = surf.getDN(u, v, 1, 0)
    sv = surf.getDN(u, v, 0, 1)
    a_mat = np.array([[su.x, sv.x], [su.y, sv.y], [su.z, sv.z]])
    ab, *_ = np.linalg.lstsq(a_mat, np.array([w.x, w.y, w.z]), rcond=None)
    a, b = float(ab[0]), float(ab[1])

    f = chord * tension
    derivs = [np.asarray(point, dtype=float)]
    if k >= 1:
        d1 = su * a + sv * b            # ~ unit vector w
        derivs.append(np.array([d1.x, d1.y, d1.z]) * f)
    if k >= 2:
        suu = surf.getDN(u, v, 2, 0)
        suv = surf.getDN(u, v, 1, 1)
        svv = surf.getDN(u, v, 0, 2)
        d2 = (suu * (a * a) + suv * (2 * a * b) + svv * (b * b))
        derivs.append(np.array([d2.x, d2.y, d2.z]) * (f * f))
    if k >= 3:
        s30 = surf.getDN(u, v, 3, 0)
        s21 = surf.getDN(u, v, 2, 1)
        s12 = surf.getDN(u, v, 1, 2)
        s03 = surf.getDN(u, v, 0, 3)
        d3 = (s30 * (a ** 3) + s21 * (3 * a * a * b)
              + s12 * (3 * a * b * b) + s03 * (b ** 3))
        derivs.append(np.array([d3.x, d3.y, d3.z]) * (f ** 3))
    return derivs


def blend_surface_net(face1, edge1, k1, tension1, face2, edge2, k2, tension2,
                      stations=24, degree_v=5):
    """Bézier net blending from edge1 (on face1) to edge2 (on face2).

    Rows (u) run across the blend, degree k1+k2+1; columns (v) run along the
    edges, degree degree_v. Returns (net, max_fit_deviation).
    """
    poles1, _d1 = nurbs_io.edge_to_bezier(edge1, degree=degree_v)
    poles2, _d2 = nurbs_io.edge_to_bezier(edge2, degree=degree_v)
    # orient edge2 with edge1
    if (np.linalg.norm(poles2[0] - poles1[0]) + np.linalg.norm(poles2[-1] - poles1[-1])
            > np.linalg.norm(poles2[-1] - poles1[0]) + np.linalg.norm(poles2[0] - poles1[-1])):
        poles2 = poles2[::-1]

    v_params = np.linspace(0.0, 1.0, stations)
    pts1 = bezier.evaluate(poles1, v_params)
    pts2 = bezier.evaluate(poles2, v_params)
    degree_u = k1 + k2 + 1

    station_poles = []
    for s in range(stations):
        q1, q2 = pts1[s], pts2[s]
        chord = float(np.linalg.norm(q2 - q1))
        if chord < 1e-9:
            raise ValueError("edges touch at station %d" % s)
        da = _station_derivatives(face1, q1, q2 - q1, k1, tension1, chord)
        db_out = _station_derivatives(face2, q2, q1 - q2, k2, tension2, chord)
        db = [db_out[0]]
        for j in range(1, len(db_out)):
            db.append(db_out[j] * ((-1.0) ** j))
        station_poles.append(hermite_bezier_poles(da, db))
    station_poles = np.asarray(station_poles)     # (stations, degree_u+1, 3)

    # fit each blend-direction pole row along v
    net = np.empty((degree_u + 1, degree_v + 1, 3))
    dev = 0.0
    for i in range(degree_u + 1):
        pts = station_poles[:, i, :]
        row, d = bezier.fit_bezier(pts, v_params, degree_v,
                                   pinned={0: pts[0], degree_v: pts[-1]})
        net[i] = row
        dev = max(dev, d)
    # exact boundaries: keep the Bézier reps of the edges as rows 0 / n
    net[0] = poles1
    net[-1] = poles2
    return net, dev
