# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface matching — the core Class-A operation.

Rewrites the first k+1 CV rows of a Bézier patch so its boundary meets a
target face at G0/G1/G2, then fades the corrections into the interior so the
opposite edge can stay fixed.

Approach (per row):
  G0  row 0 <- Bézier representation of the target edge.
  G1  the boundary cross-derivative S_u(0,v) has control points
      m·(P1j − P0j); sample the desired derivative at N stations and solve
      the Bernstein system by least squares.
  G2  S_uu(0,v) has control points m(m−1)(P2j − 2P1j + P0j); only its normal
      component is constrained (normal curvature match via Euler's theorem),
      the tangential part keeps the current shape.
"""
import math
import numpy as np
import FreeCAD

from . import bezier, continuity, fairing, nurbs_io

Vector = FreeCAD.Vector


class MatchResult(object):
    def __init__(self, net, g0, g1, g2):
        self.net = net          # full pole net, original orientation
        self.g0 = g0            # predicted max gap (mm)
        self.g1 = g1            # predicted max tangent deviation (deg)
        self.g2 = g2            # predicted max curvature deviation (rel)

    def summary(self):
        return ("G0 %.3g mm, G1 %.3g°, G2 %.3g rel"
                % (self.g0, self.g1, self.g2))


def _row_curve_points(row_poles, params):
    return bezier.evaluate(row_poles, params)


def _cross_derivative(canon, v_params):
    """S_u(0, v) sampled at v_params for a boundary-canonical net."""
    m = canon.shape[0] - 1
    delta = m * (canon[1] - canon[0])          # (nv, 3) derivative ctrl points
    return bezier.evaluate(delta, v_params)


def match_surface(net, boundary, target_face, target_edge, order=2,
                  tension=1.0, mode="minimal", stations=60,
                  hold_opposite=True, pin_corners=False):
    """Match one boundary of a Bézier pole net against a target face.

    net: (nu, nv, 3) pole array; boundary: "u0"/"u1"/"v0"/"v1" (the side of
    `net` lying near `target_edge`); order: 0/1/2 for G0/G1/G2; tension:
    scales the cross-derivative magnitude in flow mode; mode: "minimal"
    (smallest change achieving continuity) or "flow" (adopt the target's
    cross flow direction). Returns MatchResult.
    """
    surf = target_face.Surface
    canon = nurbs_io.to_boundary(np.asarray(net, dtype=float), boundary)

    # enough rows for the constrained ones + one free + held opposite edge
    needed_rows = (order + 1) + 1 + (1 if hold_opposite else 0)
    if canon.shape[0] < needed_rows:
        canon = bezier.elevate_u(canon, needed_rows - canon.shape[0])

    nu, nv = canon.shape[0], canon.shape[1]
    original = canon.copy()

    # ---- G0: row 0 from the target edge --------------------------------------
    row0_new = canon[0].copy()
    edge_poles, _fit_dev = nurbs_io.edge_to_bezier(target_edge, degree=nv - 1)
    # orient the fitted edge like the current boundary
    if (np.linalg.norm(edge_poles[0] - canon[0][0])
            > np.linalg.norm(edge_poles[-1] - canon[0][0])):
        edge_poles = edge_poles[::-1]
    row0_new = edge_poles.copy()
    if pin_corners:
        row0_new[0] = canon[0][0]
        row0_new[-1] = canon[0][-1]

    rows = [row0_new]
    v_params = np.linspace(0.0, 1.0, stations)
    phi = bezier.bernstein_matrix(nv - 1, v_params)
    m = nu - 1

    # station data on the target surface, evaluated at the NEW boundary
    q_pts = _row_curve_points(row0_new, v_params)
    normals, uvs = [], []
    for q in q_pts:
        u, v = surf.parameter(Vector(*q))
        uvs.append((u, v))
        n = surf.normal(u, v)
        normals.append(np.array([n.x, n.y, n.z]))
    normals = np.asarray(normals)

    if order >= 1:
        # The G1 condition is scalar: n(v)·S_u(0,v) = 0 along the boundary.
        # Prescribing a full desired vector per station over-constrains the
        # low-degree row (normalized fields are not polynomial), so we impose
        # only the scalar conditions and regularize toward a preference field
        # (minimal change or target flow). An exact polynomial solution exists
        # (S_u = α·S_u^target), so the constraints solve to ~machine zero.
        cur = _cross_derivative(np.concatenate([[row0_new], canon[1:]]), v_params)
        prefer = np.empty_like(cur)
        for s in range(stations):
            n = normals[s]
            c = cur[s]
            mag = np.linalg.norm(c)
            if mag < 1e-12:
                mag = float(np.linalg.norm(canon[1] - canon[0], axis=1).mean()) * m
            if mode == "flow":
                tangent = _row_curve_points(
                    bezier.derivative_net(row0_new), [v_params[s]])[0]
                t_norm = np.linalg.norm(tangent)
                w = np.cross(n, tangent / t_norm) if t_norm > 1e-12 else c
                if np.dot(w, c) < 0:
                    w = -w
                prefer[s] = w / max(np.linalg.norm(w), 1e-12) * (mag * tension)
            else:
                d = c - n * np.dot(n, c)
                dl = np.linalg.norm(d)
                if dl < 1e-12:
                    d = np.cross(n, [1.0, 0.0, 0.0])
                    dl = np.linalg.norm(d)
                prefer[s] = d / dl * (mag * tension)
        target_delta = _solve_rows(phi, prefer / m, {})
        pinned = {}
        if pin_corners:
            pinned = {0: canon[1][0] - row0_new[0],
                      nv - 1: canon[1][-1] - row0_new[-1]}
        delta = _solve_scalar_constrained(
            phi, normals, np.zeros(stations), target_delta, pinned)
        rows.append(row0_new + delta)

    if order >= 2:
        row1_new = rows[1]
        # actual new cross derivative (defines the section direction)
        d_new = m * (bezier.evaluate(row1_new - row0_new, v_params))
        # G2 condition (scalar): n·S_uu(0,v) = kappa_n(target)·|S_u(0,v)|^2.
        # Tangential shape of S_uu stays free (regularized to current).
        cur_net = np.concatenate([[row0_new], [row1_new], canon[2:]])
        suu_ctrl = bezier.second_difference_u(cur_net)     # (nu-2, nv, 3)
        cur_suu = bezier.evaluate(suu_ctrl[0], v_params)   # S_uu(0, v) samples
        rhs = np.empty(stations)
        for s in range(stations):
            u, v = uvs[s]
            kappa = continuity.normal_curvature(surf, u, v, Vector(*d_new[s]))
            su2 = float(np.dot(d_new[s], d_new[s]))
            rhs[s] = kappa * su2 / (m * (m - 1))
        target_w = canon[2] - 2 * row1_new + row0_new      # current W as preference
        pinned = {}
        if pin_corners:
            pinned = {0: canon[2][0] - 2 * row1_new[0] + row0_new[0],
                      nv - 1: canon[2][-1] - 2 * row1_new[-1] + row0_new[-1]}
        w = _solve_scalar_constrained(phi, normals, rhs, target_w, pinned)
        rows.append(w + 2 * row1_new - row0_new)

    # ---- fair the corrections into the interior --------------------------------
    k = len(rows)
    disp = np.stack([rows[i] - original[i] for i in range(k)])
    hold = 1 if hold_opposite and nu > k + 1 else 0
    new_canon = fairing.propagate(original, disp, k, hold_rows=hold)

    result_net = nurbs_io.from_boundary(new_canon, boundary)

    # ---- predicted residuals -----------------------------------------------------
    g0, g1, g2 = _predict_residuals(new_canon, surf, stations * 2)
    return MatchResult(result_net, g0, g1, g2)


def _solve_scalar_constrained(phi, normals, rhs, target, pinned, reg=1e-4):
    """Solve for a pole row X (nv, 3) from scalar boundary conditions.

    Constraints (one per station s):  n_s · Σ_j phi[s,j] X_j = rhs_s
    plus a weak regularization pulling X toward `target` (the preference
    field). `pinned` fixes individual poles {j: (x,y,z)} exactly.
    """
    stations, nv = phi.shape
    target = np.asarray(target, dtype=float)

    # constraint matrix over flattened unknowns X[j, c] -> col j*3+c
    a = np.zeros((stations, nv * 3))
    b = np.asarray(rhs, dtype=float).copy()
    for s in range(stations):
        for c in range(3):
            a[s, c::3] = 0.0
        for j in range(nv):
            for c in range(3):
                a[s, j * 3 + c] = phi[s, j] * normals[s][c]
    # apply pins by substitution
    free = [j for j in range(nv) if j not in pinned]
    for j, val in pinned.items():
        for c in range(3):
            b -= a[:, j * 3 + c] * float(val[c])
    free_cols = [j * 3 + c for j in free for c in range(3)]

    n_free = len(free_cols)
    stacked_a = np.vstack([a[:, free_cols], np.eye(n_free) * reg])
    target_flat = np.array([target[j][c] for j in free for c in range(3)])
    stacked_b = np.concatenate([b, target_flat * reg])
    sol, *_ = np.linalg.lstsq(stacked_a, stacked_b, rcond=None)

    x = np.zeros((nv, 3))
    for j, val in pinned.items():
        x[j] = val
    for k_, col in enumerate(free_cols):
        x[col // 3][col % 3] = sol[k_]
    return x


def _solve_rows(phi, rhs, pinned):
    """Least-squares solve Phi @ X = rhs with some rows of X pinned."""
    n_poles = phi.shape[1]
    free = [i for i in range(n_poles) if i not in pinned]
    b = rhs.copy()
    for i, val in pinned.items():
        b = b - np.outer(phi[:, i], np.asarray(val, dtype=float))
    x = np.zeros((n_poles, 3))
    for i, val in pinned.items():
        x[i] = val
    if free:
        sol, *_ = np.linalg.lstsq(phi[:, free], b, rcond=None)
        for k_, i in enumerate(free):
            x[i] = sol[k_]
    return x


def _predict_residuals(canon, surf, stations):
    """Sampled G0/G1/G2 of a boundary-canonical net against the target surface."""
    v_params = np.linspace(0.0, 1.0, stations)
    m = canon.shape[0] - 1
    row0, row1 = canon[0], canon[1]
    pts = bezier.evaluate(row0, v_params)
    d_cross = m * bezier.evaluate(row1 - row0, v_params)
    suu = bezier.evaluate(bezier.second_difference_u(canon)[0], v_params) \
        if canon.shape[0] >= 3 else None

    g0 = g1 = g2 = 0.0
    for s, p in enumerate(pts):
        try:
            u, v = surf.parameter(Vector(*p))
        except Exception:
            continue
        q = surf.value(u, v)
        g0 = max(g0, float(np.linalg.norm(p - [q.x, q.y, q.z])))
        n = surf.normal(u, v)
        n = np.array([n.x, n.y, n.z])
        d = d_cross[s]
        dl = np.linalg.norm(d)
        if dl > 1e-12:
            sin_angle = abs(float(np.dot(n, d / dl)))
            g1 = max(g1, math.degrees(math.asin(min(1.0, sin_angle))))
        if suu is not None and dl > 1e-12:
            kappa_target = continuity.normal_curvature(surf, u, v, Vector(*d))
            kappa_b = float(np.dot(n, suu[s])) / (dl * dl)
            denom = max(abs(kappa_target), abs(kappa_b), 1e-9)
            g2 = max(g2, abs(kappa_target - kappa_b) / denom)
    return g0, g1, g2
