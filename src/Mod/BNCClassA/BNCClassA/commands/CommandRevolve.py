# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve — non-rational (polynomial) surface of revolution. Class-A
discipline: the rotation is a Bézier approximation, so the result stays a
single-span non-rational patch; the approximation error is reported."""
import FreeCAD

from BNCClassA.geom import nurbs_io, builders
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, DirectionWidget, selected_edges
from .common import CommandBase, register


class RevolvePanel(CreationPanel):
    TITLE = "Class-A Revolve"
    TRANSACTION = "Class-A Revolve"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.axis_dir = DirectionWidget("+Z")
        form.addRow("Axis direction", self.axis_dir)
        self.axis_pt = []
        pt_row = QtWidgets.QHBoxLayout()
        for c in "XYZ":
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(-100000, 100000)
            sp.setDecimals(3)
            sp.setPrefix(c.lower() + " ")
            self.axis_pt.append(sp)
            pt_row.addWidget(sp)
        form.addRow("Axis point", pt_row)
        self.angle = QtWidgets.QDoubleSpinBox()
        self.angle.setRange(1.0, 180.0)
        self.angle.setValue(90.0)
        self.angle.setSuffix(" °")
        self.angle.valueChanged.connect(self._warn_angle)
        form.addRow("Sweep angle", self.angle)
        self.layout.addLayout(form)
        edges = selected_edges()
        self.set_status("%d profile edge(s) selected." % len(edges)
                        if edges else "Select a profile edge first.")

    def _warn_angle(self, v):
        if v > 120.0:
            self.set_status("Above 120° the single-span approximation degrades "
                            "— consider two segments.")

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        edges = selected_edges()
        if not edges:
            self.set_status("Select a profile edge first.")
            return False
        axis_d = self.axis_dir.value()
        axis_p = FreeCAD.Vector(*[sp.value() for sp in self.axis_pt])
        made = 0
        for (_obj, edge, label) in edges:
            poles, _dev = nurbs_io.edge_to_bezier(edge, degree=5)
            net, err = builders.revolve_net(
                poles, (axis_p.x, axis_p.y, axis_p.z),
                (axis_d.x, axis_d.y, axis_d.z), self.angle.value())
            obj = make_cv_surface(self.doc, net,
                                  provenance="Revolve of %s (%g°, approx err %.4g mm)"
                                             % (label, self.angle.value(), err))
            FreeCAD.Console.PrintMessage(
                "BNCClassA: %s arc approximation error %.4g mm\n" % (obj.Label, err))
            made += 1
        return made > 0


@register
class CommandRevolve(CommandBase):
    NAME = "BNCClassA_Revolve"
    ICON = "ClassARevolve"
    MENU = "Revolve Surface"
    TIP = ("Revolve the selected profile into a polynomial (non-rational) "
           "CV surface — approximation error is reported")
    PANEL = RevolvePanel
