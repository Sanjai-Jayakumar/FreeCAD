# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extend — grow a CV surface past one boundary by polynomial extrapolation.
The extension is the same polynomial evaluated on a larger interval, so the
result is exactly continuous (G-infinity) with the original — no blend seam."""
import numpy as np
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.geom import bezier, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selection_subelements
from .common import CommandBase, register


class ExtendPanel(CreationPanel):
    TITLE = "Class-A Extend"
    TRANSACTION = "Class-A Extend"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.amount = QtWidgets.QDoubleSpinBox()
        self.amount.setRange(1.0, 100.0)
        self.amount.setValue(20.0)
        self.amount.setSuffix(" %")
        self.amount.setToolTip("Parameter-range extension past the picked edge")
        form.addRow("Extend by", self.amount)
        self.layout.addLayout(form)
        self.set_status("Pick the boundary edge of a CV surface to extend.")

    def _pick(self):
        from BNCClassA.objects.helpers import is_cv_surface
        from BNCClassA.objects.cv_surface import CVSurface
        for (obj, _sub, sub_obj) in selection_subelements():
            if getattr(sub_obj, "ShapeType", "") == "Edge" and is_cv_surface(obj):
                net = CVSurface.pole_array(obj)
                try:
                    boundary, _rev = nurbs_io.identify_boundary(net, sub_obj, tol=1.0)
                except ValueError:
                    continue
                return obj, net, boundary
        return None, None, None

    def create(self):
        from BNCClassA.objects.cv_surface import CVSurface
        obj, net, boundary = self._pick()
        if obj is None:
            self.set_status("Pick a boundary edge of a CV surface.")
            return False
        ext = self.amount.value() / 100.0
        canon = nurbs_io.to_boundary(net, boundary)
        # extrapolation extends past t=1, so flip: the picked boundary (row 0)
        # becomes the far end
        work = canon[::-1]
        nu, nv = work.shape[0], work.shape[1]
        extended = np.empty_like(work)
        for j in range(nv):
            extended[:, j] = bezier.extrapolate(work[:, j], ext)
        new_net = nurbs_io.from_boundary(extended[::-1], boundary)
        CVSurface.set_pole_array(obj, new_net)
        obj.recompute()
        FreeCAD.Console.PrintMessage(
            "BNCClassA: %s extended %.0f%% past its %s edge (exact "
            "polynomial continuation)\n" % (obj.Label, self.amount.value(), boundary))
        return True


@register
class CommandExtend(CommandBase):
    NAME = "BNCClassA_Extend"
    ICON = "ClassAExtend"
    MENU = "Extend Surface"
    TIP = ("Extend a CV surface past a boundary by exact polynomial "
           "extrapolation (no seam)")
    PANEL = ExtendPanel
