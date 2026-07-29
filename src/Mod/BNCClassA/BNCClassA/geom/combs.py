# SPDX-License-Identifier: LGPL-2.1-or-later
"""Curvature-comb math for edges and surface sections."""
import numpy as np
import FreeCAD

Vector = FreeCAD.Vector


def curve_comb(edge, n=60, scale=1.0):
    """Comb teeth for an edge.

    Returns (roots, tips, kappas): per-station curve point, tooth tip
    (root − principal_normal · κ · scale, i.e. teeth point away from the
    center of curvature, Alias convention), and curvature value.
    Straight regions (κ ≈ 0) get zero-length teeth.
    """
    t0, t1 = edge.FirstParameter, edge.LastParameter
    roots, tips, kappas = [], [], []
    for t in np.linspace(t0, t1, n):
        t = float(t)
        p = edge.valueAt(t)
        try:
            k = edge.curvatureAt(t)
        except Exception:
            k = 0.0
        tip = p
        if k > 1e-12:
            try:
                nrm = edge.normalAt(t)     # principal normal, toward the center
                tip = p - nrm * (k * scale)
            except Exception:
                k = 0.0
        roots.append(p)
        tips.append(tip)
        kappas.append(k)
    return roots, tips, kappas


def auto_scale(edge, n=60, target_fraction=0.25):
    """Comb scale so the tallest tooth is ~target_fraction of the edge length."""
    t0, t1 = edge.FirstParameter, edge.LastParameter
    kmax = 0.0
    for t in np.linspace(t0, t1, n):
        try:
            kmax = max(kmax, edge.curvatureAt(float(t)))
        except Exception:
            pass
    if kmax <= 1e-12:
        return 1.0
    return (edge.Length * target_fraction) / kmax
