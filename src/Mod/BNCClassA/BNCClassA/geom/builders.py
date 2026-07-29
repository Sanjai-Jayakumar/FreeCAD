# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pole-net generators: extrude, revolve (non-rational arc approximation),
loft, birail sweep, discrete Coons patch, and surface rebuild fitting.

All functions return numpy pole nets (nu, nv, 3); axis 0 (u) is the
"across" direction (extrusion/loft/sweep direction), axis 1 (v) runs along
the profile curves.
"""
import numpy as np

from . import bezier


# --------------------------------------------------------------------------
# Extrude / revolve
# --------------------------------------------------------------------------

def extrude_net(profile_poles, direction, length, symmetric=False, degree_u=3):
    """Linear extrusion of a profile pole row, degree-elevated in u so the
    result is immediately CV-editable."""
    p = np.asarray(profile_poles, dtype=float)
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    start = p - d * (length * 0.5) if symmetric else p
    net = np.stack([start, start + d * length])       # degree 1 in u
    return bezier.elevate_u(net, max(0, degree_u - 1))


def unit_arc_poles(angle_rad, degree=5, samples=200, corrections=3):
    """Bézier approximation of the unit circular arc [0, angle] in the plane:
    returns ((degree+1, 2) poles of (cos, sin), max_radial_error).

    After the initial least-squares fit, a few parameter-correction passes
    (re-projecting the arc samples onto the current curve, then refitting)
    bring the fit close to the geometrically optimal approximation.
    """
    ts = np.linspace(0.0, 1.0, samples)
    pts = np.stack([np.cos(ts * angle_rad), np.sin(ts * angle_rad)], axis=1)
    pts3 = np.concatenate([pts, np.zeros((samples, 1))], axis=1)
    pinned = {0: pts3[0], degree: pts3[-1]}
    params = ts
    poles3, _dev = bezier.fit_bezier(pts3, params, degree, pinned)
    dense_t = np.linspace(0.0, 1.0, 2048)
    for _ in range(corrections):
        dense = bezier.evaluate(poles3, dense_t)
        d2 = ((pts3[:, None, :2] - dense[None, :, :2]) ** 2).sum(axis=2)
        params = dense_t[np.argmin(d2, axis=1)]
        params[0], params[-1] = 0.0, 1.0
        poles3, _dev = bezier.fit_bezier(pts3, params, degree, pinned)
    # measure the true radial error of the approximation
    fine = bezier.evaluate(poles3, np.linspace(0, 1, 1000))
    radial = np.abs(np.sqrt((fine[:, :2] ** 2).sum(axis=1)) - 1.0)
    return poles3[:, :2], float(radial.max())


def revolve_net(profile_poles, axis_point, axis_dir, angle_deg, degree_u=5):
    """Surface of revolution as a single-span non-rational Bézier.

    The rotation is applied through a Bézier approximation of (cos, sin), so
    the result is polynomial (Class-A discipline). Returns (net, max_error_mm)
    where the error is the arc approximation error scaled by the largest
    radius. Callers should warn above ~120 degrees.
    """
    p = np.asarray(profile_poles, dtype=float)
    o = np.asarray(axis_point, dtype=float)
    a = np.asarray(axis_dir, dtype=float)
    a = a / np.linalg.norm(a)
    angle = np.radians(angle_deg)
    arc, radial_err = unit_arc_poles(angle, degree=degree_u)

    # local cylindrical frame per profile pole
    rel = p - o
    axial = rel @ a
    radial_vec = rel - np.outer(axial, a)
    r = np.linalg.norm(radial_vec, axis=1)
    # basis vectors: e1 = radial direction, e2 = a x e1
    with np.errstate(invalid="ignore", divide="ignore"):
        e1 = np.where(r[:, None] > 1e-12, radial_vec / np.maximum(r, 1e-300)[:, None], 0.0)
    e2 = np.cross(a, e1)

    net = np.empty((len(arc), len(p), 3))
    for i, (c, s) in enumerate(arc):
        net[i] = (o + np.outer(axial, a)
                  + (e1 * c + e2 * s) * r[:, None])
    return net, radial_err * float(r.max() if len(r) else 0.0)


# --------------------------------------------------------------------------
# Loft / birail
# --------------------------------------------------------------------------

def _common_degree(profiles):
    """Elevate all profile pole rows to a common degree."""
    target = max(len(p) for p in profiles) - 1
    out = []
    for p in profiles:
        p = np.asarray(p, dtype=float)
        if len(p) - 1 < target:
            p = bezier.elevate(p, target - (len(p) - 1))
        out.append(p)
    return out, target


def loft_params(profiles):
    """Centripetal u-parameters assigned to the profiles by loft_net."""
    stack = np.stack([np.asarray(p, dtype=float) for p in profiles])
    diffs = np.sqrt(((stack[1:] - stack[:-1]) ** 2).sum(axis=2)).mean(axis=1)
    params = np.concatenate([[0.0], np.cumsum(np.sqrt(diffs))])
    return params / (params[-1] if params[-1] > 0 else 1.0)


def loft_net(profiles, degree_u=None):
    """Loft through profile pole rows (2 -> ruled elevated to cubic; 3+ ->
    the u-direction interpolates the profiles at centripetal parameters)."""
    profiles, _dv = _common_degree(profiles)
    stack = np.stack(profiles)               # (k, nv, 3)
    k = stack.shape[0]
    if k == 2:
        return bezier.elevate_u(stack, 2)

    params = loft_params(profiles)
    du = min(k - 1, 7) if degree_u is None else degree_u
    phi = bezier.bernstein_matrix(du, params)
    nv = stack.shape[1]
    net = np.empty((du + 1, nv, 3))
    for j in range(nv):
        pts = stack[:, j, :]
        if k == du + 1:
            net[:, j, :] = np.linalg.solve(phi, pts)
        else:
            pinned_rows, _dev = bezier.fit_bezier(pts, params, du,
                                                  pinned={0: pts[0], du: pts[-1]})
            net[:, j, :] = pinned_rows
    return net


def birail_net(profile_poles, rail1, rail2, stations=16, degree_u=5):
    """Sweep a profile along two rail edges.

    The profile is rigidly framed on (rail1(t), rail1->rail2 direction,
    averaged rail tangent) and scaled so it always spans the two rails, then
    the station profiles are lofted. rail1/rail2 are Part edges.
    Returns (net, max_fit_deviation).
    """
    import FreeCAD
    p = np.asarray(profile_poles, dtype=float)

    def frame(rail_a, rail_b, t):
        ta = rail_a.FirstParameter + t * (rail_a.LastParameter - rail_a.FirstParameter)
        tb = rail_b.FirstParameter + t * (rail_b.LastParameter - rail_b.FirstParameter)
        o = rail_a.valueAt(ta)
        q = rail_b.valueAt(tb)
        x = q - o
        span = x.Length
        if span < 1e-9:
            raise ValueError("rails touch at t=%.3f" % t)
        x = x / span
        tan = rail_a.tangentAt(ta) + rail_b.tangentAt(tb)
        z = tan - x * tan.dot(x)
        if z.Length < 1e-9:
            z = FreeCAD.Vector(0, 0, 1) - x * x.z
        z.normalize()
        y = z.cross(x)
        return (np.array([o.x, o.y, o.z]),
                np.stack([np.array([v.x, v.y, v.z]) for v in (x, y, z)]).T,
                span)

    o0, m0, span0 = frame(rail1, rail2, 0.0)
    local = (p - o0) @ m0            # profile in the start frame
    local /= span0                    # normalize by start span

    profs = []
    for t in np.linspace(0.0, 1.0, stations):
        o, m, span = frame(rail1, rail2, float(t))
        profs.append(o + (local * span) @ m.T)
    net = loft_net(profs, degree_u=degree_u)
    # deviation of the fitted loft against every station at its own parameter
    params = loft_params(profs)
    dev = 0.0
    for prof, t in zip(profs, params):
        nv = len(prof)
        fitted = np.array([bezier.evaluate_surface(net, float(t), j / (nv - 1.0))
                           for j in range(nv)])
        station_pts = bezier.evaluate(prof, np.linspace(0, 1, nv))
        dev = max(dev, float(np.sqrt(((fitted - station_pts) ** 2)
                                     .sum(axis=1)).max()))
    return net, dev


# --------------------------------------------------------------------------
# Discrete Coons patch
# --------------------------------------------------------------------------

def coons_net(south, north, west, east):
    """Discrete Coons patch on Bézier pole nets.

    south/north: (nv, 3) pole rows at u=0 / u=1 (running in +v);
    west/east:   (nu, 3) pole columns at v=0 / v=1 (running in +u).
    Corners must agree: south[0]==west[0], south[-1]==east[0],
    north[0]==west[-1], north[-1]==east[-1] (within tolerance).
    """
    s = np.asarray(south, dtype=float)
    n = np.asarray(north, dtype=float)
    w = np.asarray(west, dtype=float)
    e = np.asarray(east, dtype=float)
    nv, nu = len(s), len(w)
    if len(n) != nv or len(e) != nu:
        raise ValueError("opposite boundaries must have equal pole counts")
    for pair, tol_pt in ((s[0], w[0]), (s[-1], e[0]), (n[0], w[-1]), (n[-1], e[-1])):
        if np.linalg.norm(pair - tol_pt) > 1e-4:
            raise ValueError("boundary corners do not meet (gap %.4g)"
                             % float(np.linalg.norm(pair - tol_pt)))
    net = np.empty((nu, nv, 3))
    for i in range(nu):
        a = i / (nu - 1.0)
        for j in range(nv):
            b = j / (nv - 1.0)
            ruled_u = (1 - a) * s[j] + a * n[j]
            ruled_v = (1 - b) * w[i] + b * e[i]
            bilin = ((1 - a) * (1 - b) * s[0] + (1 - a) * b * s[-1]
                     + a * (1 - b) * n[0] + a * b * n[-1])
            net[i, j] = ruled_u + ruled_v - bilin
    return net


# --------------------------------------------------------------------------
# Surface rebuild (grid fit)
# --------------------------------------------------------------------------

def fit_surface_net(sample_grid, degree_u, degree_v):
    """Fit a single-span Bézier net to an (N, M, 3) sample grid (uniform
    parameters). Separable least squares. Returns (net, max_deviation)."""
    q = np.asarray(sample_grid, dtype=float)
    n_samp, m_samp = q.shape[0], q.shape[1]
    phi_u = bezier.bernstein_matrix(degree_u, np.linspace(0, 1, n_samp))
    phi_v = bezier.bernstein_matrix(degree_v, np.linspace(0, 1, m_samp))
    # solve phi_u @ X = Q  (per v-sample and coordinate)
    x, *_ = np.linalg.lstsq(phi_u, q.reshape(n_samp, -1), rcond=None)
    x = x.reshape(degree_u + 1, m_samp, 3)
    # solve phi_v @ P^T = X^T per u-pole row
    net = np.empty((degree_u + 1, degree_v + 1, 3))
    for i in range(degree_u + 1):
        sol, *_ = np.linalg.lstsq(phi_v, x[i], rcond=None)
        net[i] = sol
    # deviation on the sample grid
    rec = np.einsum("ni,ijk,mj->nmk", phi_u, net, phi_v)
    dev = float(np.sqrt(((rec - q) ** 2).sum(axis=2)).max())
    return net, dev


def sample_face_grid(face, n=50, m=50):
    """(n, m, 3) grid of points on the face's underlying surface, uniform in
    the surface parameter range (trims are ignored — rebuild covers the
    untrimmed surface)."""
    surf = face.Surface
    umin, umax, vmin, vmax = face.ParameterRange
    out = np.empty((n, m, 3))
    for i, u in enumerate(np.linspace(umin, umax, n)):
        for j, v in enumerate(np.linspace(vmin, vmax, m)):
            p = surf.value(float(u), float(v))
            out[i, j] = (p.x, p.y, p.z)
    return out
