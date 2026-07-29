# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude — CV surface from a profile curve swept along a direction."""
from BNCClassA.geom import nurbs_io
from BNCClassA.geom import builders
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, DirectionWidget, selected_edges
from .common import CommandBase, register


class ExtrudePanel(CreationPanel):
    TITLE = "Class-A Extrude"
    TRANSACTION = "Class-A Extrude"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.direction = DirectionWidget("+Z")
        form.addRow("Direction", self.direction)
        self.length = QtWidgets.QDoubleSpinBox()
        self.length.setRange(0.001, 100000)
        self.length.setValue(50.0)
        self.length.setSuffix(" mm")
        form.addRow("Length", self.length)
        self.symmetric = QtWidgets.QCheckBox("Symmetric about the profile")
        form.addRow(self.symmetric)
        self.layout.addLayout(form)
        edges = selected_edges()
        self.set_status("%d profile edge(s) selected." % len(edges)
                        if edges else "Select a profile edge first.")

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        edges = selected_edges()
        if not edges:
            self.set_status("Select a profile edge first.")
            return False
        d = self.direction.value()
        made = 0
        for (_obj, edge, label) in edges:
            poles, dev = nurbs_io.edge_to_bezier(edge, degree=5)
            net = builders.extrude_net(poles, (d.x, d.y, d.z),
                                       self.length.value(),
                                       self.symmetric.isChecked())
            make_cv_surface(self.doc, net, provenance="Extrude of %s" % label)
            made += 1
        return made > 0


@register
class CommandExtrude(CommandBase):
    NAME = "BNCClassA_Extrude"
    ICON = "ClassAExtrude"
    MENU = "Extrude Surface"
    TIP = "Extrude the selected profile edge into an editable CV surface"
    PANEL = ExtrudePanel
