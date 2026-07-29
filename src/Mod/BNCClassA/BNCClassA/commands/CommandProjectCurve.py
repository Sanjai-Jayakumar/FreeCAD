# SPDX-License-Identifier: LGPL-2.1-or-later
"""Project Curve — project an edge onto a face (closest point or along a
direction) and fit the result as a CV curve."""
import numpy as np
import FreeCAD
import Part

from BNCClassA.geom import bezier, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import (CreationPanel, DirectionWidget,
                                 selection_subelements)
from .common import CommandBase, register


class ProjectCurvePanel(CreationPanel):
    TITLE = "Project Curve"
    TRANSACTION = "Class-A Project Curve"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Closest point", "Along direction"])
        form.addRow("Mode", self.mode)
        self.direction = DirectionWidget("-Z")
        form.addRow("Direction", self.direction)
        self.degree = QtWidgets.QSpinBox()
        self.degree.setRange(3, 7)
        self.degree.setValue(5)
        form.addRow("Curve degree", self.degree)
        self.samples = QtWidgets.QSpinBox()
        self.samples.setRange(20, 400)
        self.samples.setValue(100)
        form.addRow("Samples", self.samples)
        self.layout.addLayout(form)
        self.set_status("Select the curve edge and the target face.")

    def _pick(self):
        edge, face = None, None
        for (_obj, _sub, sub_obj) in selection_subelements():
            st = getattr(sub_obj, "ShapeType", "")
            if st == "Edge" and edge is None:
                edge = sub_obj
            elif st == "Face" and face is None:
                face = sub_obj
        return edge, face

    def create(self):
        from BNCClassA.objects.cv_curve import make_cv_curve
        edge, face = self._pick()
        if edge is None or face is None:
            self.set_status("Select one edge and one face.")
            return False
        surf = face.Surface
        n = self.samples.value()
        pts = []
        if self.mode.currentIndex() == 0:
            for p in (edge.valueAt(t) for t in
                      np.linspace(edge.FirstParameter, edge.LastParameter, n)):
                try:
                    u, v = surf.parameter(p)
                    q = surf.value(u, v)
                    pts.append((q.x, q.y, q.z))
                except Exception:
                    pass
        else:
            d = self.direction.value()
            bb_diag = face.BoundBox.DiagonalLength or 1000.0
            for p in (edge.valueAt(t) for t in
                      np.linspace(edge.FirstParameter, edge.LastParameter, n)):
                line = Part.makeLine(p - d * bb_diag, p + d * bb_diag)
                try:
                    dist, pairs, _info = line.distToShape(face)
                except Exception:
                    continue
                if dist < 1e-6 and pairs:
                    q = pairs[0][1]
                    pts.append((q.x, q.y, q.z))
        if len(pts) < self.degree.value() + 1:
            self.set_status("Projection produced too few points (%d) — the "
                            "curve may not project onto this face." % len(pts))
            return False
        pts = np.asarray(pts)
        params = np.linspace(0, 1, len(pts))
        deg = self.degree.value()
        poles, dev = bezier.fit_bezier(pts, params, deg,
                                       pinned={0: pts[0], deg: pts[-1]})
        obj = make_cv_curve(self.doc, poles,
                            provenance="Projected curve (fit dev %.4g mm)" % dev)
        FreeCAD.Console.PrintMessage(
            "BNCClassA: %s projection fit deviation %.4g mm\n" % (obj.Label, dev))
        return True


@register
class CommandProjectCurve(CommandBase):
    NAME = "BNCClassA_ProjectCurve"
    ICON = "ClassAProjectCurve"
    MENU = "Project Curve"
    TIP = "Project an edge onto a face and fit the result as a CV curve"
    PANEL = ProjectCurvePanel
