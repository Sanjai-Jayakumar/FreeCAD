# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the Class-A smoke-test scene: a bumper-like pair of CV surfaces with
a deliberate continuity defect between them, plus a reference profile curve.

Run in the FreeCAD Python console (with the BNCClassA workbench loaded):
    exec(open(r"<this file>").read())
"""
import numpy as np
import FreeCAD

from BNCClassA.geom import builders
from BNCClassA.objects.cv_curve import make_cv_curve
from BNCClassA.objects.cv_surface import make_cv_surface


def paraboloid_net(x0, x1, y0, y1, jitter=0.0, seed=5):
    grid = np.empty((25, 25, 3))
    for i, y in enumerate(np.linspace(y0, y1, 25)):
        for j, x in enumerate(np.linspace(x0, x1, 25)):
            grid[i, j] = (x, y, 30.0 - (x * x + y * y) / 400.0)
    net, _dev = builders.fit_surface_net(grid, 3, 3)
    if jitter:
        rng = np.random.RandomState(seed)
        net = net + rng.uniform(-jitter, jitter, size=net.shape)
    return net


doc = FreeCAD.ActiveDocument or FreeCAD.newDocument("ClassA_Smoke")

# patch A: the "good" reference surface
net_a = paraboloid_net(-100.0, 100.0, -120.0, 0.0)
surf_a = make_cv_surface(doc, net_a, provenance="Smoke test: reference patch")
surf_a.Label = "PatchA_reference"

# patch B: adjacent, deliberately broken (jittered) -> MatchSurface fixes it
net_b = paraboloid_net(-100.0, 100.0, 0.0, 120.0, jitter=2.0)
surf_b = make_cv_surface(doc, net_b, provenance="Smoke test: broken patch")
surf_b.Label = "PatchB_broken"

# profile curve for extrude/revolve/loft exercises
profile = np.array([[-80.0, 160.0, 0.0], [-30.0, 160.0, 25.0],
                    [30.0, 160.0, 25.0], [80.0, 160.0, 0.0]])
curve = make_cv_curve(doc, profile, provenance="Smoke test: profile")
curve.Label = "Profile"

doc.recompute()
try:
    import FreeCADGui
    FreeCADGui.SendMsgToActiveView("ViewFit")
except Exception:
    pass
print("Smoke scene ready: PatchA_reference, PatchB_broken (jittered), Profile")
