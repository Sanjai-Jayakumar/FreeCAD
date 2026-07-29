# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bézier math on numpy pole arrays.

Curve poles: (n, 3) array, degree = n - 1 (single span).
Surface poles: (nu, nv, 3) array, degrees (nu-1, nv-1).

Pure numpy — no FreeCAD imports, so this module is trivially unit-testable.
"""
import numpy as np
from math import comb as _comb


# --------------------------------------------------------------------------
# Bernstein basis
# --------------------------------------------------------------------------

def bernstein_matrix(degree, params):
    """(len(params), degree+1) matrix of Bernstein polynomials B_i^d(t)."""
    t = np.asarray(params, dtype=float).reshape(-1, 1)
    i = np.arange(degree + 1).reshape(1, -1)
    coeff = np.array([_comb(degree, k) for k in range(degree + 1)], dtype=float)
    # 0^0 = 1 convention handled by np.power on clipped bases
    with np.errstate(invalid="ignore"):
        basis = coeff * np.power(t, i) * np.power(1.0 - t, degree - i)
    return np.nan_to_num(basis)


# --------------------------------------------------------------------------
# Evaluation / subdivision (de Casteljau — valid for any real t, so it also
# performs extrapolation when t is outside [0, 1])
# --------------------------------------------------------------------------

def de_casteljau(poles, t):
    """Point on the Bézier curve at parameter t (any real value)."""
    pts = np.asarray(poles, dtype=float).copy()
    n = len(pts)
    for r in range(1, n):
        pts[:n - r] = (1.0 - t) * pts[:n - r] + t * pts[1:n - r + 1]
    return pts[0]


def split(poles, t):
    """Subdivide at t: pole nets of the same polynomial on [0,t] and [t,1]."""
    pts = np.asarray(poles, dtype=float).copy()
    n = len(pts)
    left = [pts[0].copy()]
    right = [pts[-1].copy()]
    for r in range(1, n):
        pts[:n - r] = (1.0 - t) * pts[:n - r] + t * pts[1:n - r + 1]
        left.append(pts[0].copy())
        right.append(pts[n - r - 1].copy())
    return np.array(left), np.array(right[::-1])


def extrapolate(poles, extension):
    """Pole net of the same polynomial on [0, 1+extension] (exact continuation)."""
    left, _ = split(poles, 1.0 + extension)
    return left


def evaluate(poles, params):
    """Sample curve points at params → (N, 3)."""
    poles = np.asarray(poles, dtype=float)
    return bernstein_matrix(len(poles) - 1, params) @ poles


def evaluate_surface(poles, u, v):
    """Point on a Bézier surface pole net (nu, nv, 3) at (u, v)."""
    poles = np.asarray(poles, dtype=float)
    bu = bernstein_matrix(poles.shape[0] - 1, [u])[0]
    bv = bernstein_matrix(poles.shape[1] - 1, [v])[0]
    return np.einsum("i,j,ijk->k", bu, bv, poles)


# --------------------------------------------------------------------------
# Degree elevation
# --------------------------------------------------------------------------

def elevate(poles, times=1):
    """Raise curve degree without changing the curve."""
    pts = np.asarray(poles, dtype=float)
    for _ in range(times):
        n = len(pts)          # old number of poles, degree n-1
        out = np.empty((n + 1, pts.shape[1]))
        out[0] = pts[0]
        out[n] = pts[-1]
        for i in range(1, n):
            a = i / float(n)
            out[i] = a * pts[i - 1] + (1.0 - a) * pts[i]
        pts = out
    return pts


def elevate_u(poles, times=1):
    """Raise surface degree in u (axis 0)."""
    pts = np.asarray(poles, dtype=float)
    for _ in range(times):
        nu, nv, _d = pts.shape
        out = np.empty((nu + 1, nv, 3))
        out[0] = pts[0]
        out[nu] = pts[-1]
        for i in range(1, nu):
            a = i / float(nu)
            out[i] = a * pts[i - 1] + (1.0 - a) * pts[i]
        pts = out
    return pts


def elevate_v(poles, times=1):
    """Raise surface degree in v (axis 1)."""
    return np.transpose(elevate_u(np.transpose(poles, (1, 0, 2)), times), (1, 0, 2))


# --------------------------------------------------------------------------
# Derivative control nets
# --------------------------------------------------------------------------

def derivative_net(poles):
    """Control net of the curve's first derivative: d·(P[i+1] − P[i])."""
    pts = np.asarray(poles, dtype=float)
    d = len(pts) - 1
    return d * (pts[1:] - pts[:-1])


def cross_derivative_net_u(poles):
    """Control net of S_u for a surface net (nu, nv, 3): m·(P[i+1,j] − P[i,j])."""
    pts = np.asarray(poles, dtype=float)
    m = pts.shape[0] - 1
    return m * (pts[1:] - pts[:-1])


def second_difference_u(poles):
    """Control net of S_uu: m(m−1)(P[i+2] − 2P[i+1] + P[i]) along axis 0."""
    pts = np.asarray(poles, dtype=float)
    m = pts.shape[0] - 1
    return m * (m - 1) * (pts[2:] - 2.0 * pts[1:-1] + pts[:-2])


# --------------------------------------------------------------------------
# Least-squares Bézier fitting (constrained by pinned poles)
# --------------------------------------------------------------------------

def fit_bezier(points, params, degree, pinned=None):
    """Fit a single-span Bézier of `degree` to `points` at `params`.

    pinned: dict {pole_index: (x, y, z)} of poles fixed in advance (e.g. both
    endpoints, or endpoint+tangent poles). Pinned columns move to the RHS and
    the remaining poles solve by linear least squares.

    Returns (poles (degree+1, 3), max_deviation_estimate).
    """
    pts = np.asarray(points, dtype=float)
    phi = bernstein_matrix(degree, params)
    n_poles = degree + 1
    pinned = dict(pinned or {})
    free_idx = [i for i in range(n_poles) if i not in pinned]

    rhs = pts.copy()
    for i, val in pinned.items():
        rhs -= np.outer(phi[:, i], np.asarray(val, dtype=float))

    poles = np.zeros((n_poles, 3))
    for i, val in pinned.items():
        poles[i] = val
    if free_idx:
        sol, *_ = np.linalg.lstsq(phi[:, free_idx], rhs, rcond=None)
        for k, i in enumerate(free_idx):
            poles[i] = sol[k]

    resid = phi @ poles - pts
    max_dev = float(np.sqrt((resid ** 2).sum(axis=1)).max()) if len(resid) else 0.0
    return poles, max_dev
