# SPDX-License-Identifier: LGPL-2.1-or-later
"""Row-displacement fairing for the match solver: decay the boundary-row
corrections smoothly into the patch interior so the opposite edge stays put."""
import numpy as np


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def decay_weights(num_rows, constrained_rows, hold_rows=1):
    """Per-row weight (1 → apply full displacement, 0 → untouched).

    Rows 0..constrained_rows-1 get weight 1 (they carry the continuity
    conditions). The last `hold_rows` rows get 0. In between, a smoothstep
    fade from 1 to 0.
    """
    w = np.zeros(num_rows)
    w[:constrained_rows] = 1.0
    first_free = constrained_rows
    last_free = num_rows - hold_rows - 1
    span = last_free - first_free + 1
    if span > 0:
        for k, i in enumerate(range(first_free, last_free + 1)):
            w[i] = 1.0 - _smoothstep((k + 1) / float(span + 1))
    return w


def propagate(poles, row_displacements, constrained_rows, hold_rows=1):
    """Apply boundary-row displacements with interior decay.

    poles: (nu, nv, 3) boundary-canonical net (row 0 = matched edge).
    row_displacements: (constrained_rows, nv, 3) — the corrections the solver
    computed for rows 0..k. Interior rows follow the last constrained row's
    displacement scaled by the decay weight.
    """
    poles = np.asarray(poles, dtype=float).copy()
    disp = np.asarray(row_displacements, dtype=float)
    k = disp.shape[0]
    nu = poles.shape[0]
    w = decay_weights(nu, k, hold_rows)
    poles[:k] += disp
    tail = disp[-1]
    for i in range(k, nu):
        if w[i] > 0.0:
            poles[i] += tail * w[i]
    return poles
