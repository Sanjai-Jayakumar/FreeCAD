# SPDX-License-Identifier: LGPL-2.1-or-later
"""Birail — sweep a profile along two rails (select profile, rail 1, rail 2)."""
from BNCClassA.geom import nurbs_io, builders
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selected_edges
from .common import CommandBase, register


class BirailPanel(CreationPanel):
    TITLE = "Class-A Birail"
    TRANSACTION = "Class-A Birail"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.stations = QtWidgets.QSpinBox()
        self.stations.setRange(4, 60)
        self.stations.setValue(16)
        form.addRow("Stations", self.stations)
        self.degree = QtWidgets.QSpinBox()
        self.degree.setRange(3, 7)
        self.degree.setValue(5)
        form.addRow("Sweep degree", self.degree)
        self.layout.addLayout(form)
        edges = selected_edges()
        self.set_status("Selection order: profile, rail 1, rail 2 "
                        "(%d selected)." % len(edges))

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        edges = selected_edges()
        if len(edges) != 3:
            self.set_status("Select exactly 3 edges: profile, rail 1, rail 2.")
            return False
        (_o1, profile, plabel), (_o2, rail1, _l2), (_o3, rail2, _l3) = edges
        poles, _dev = nurbs_io.edge_to_bezier(profile, degree=5)
        net, dev = builders.birail_net(poles, rail1, rail2,
                                       stations=self.stations.value(),
                                       degree_u=self.degree.value())
        make_cv_surface(self.doc, net,
                        provenance="Birail of %s (fit dev %.4g mm)" % (plabel, dev))
        self.set_status("Sweep fit deviation: %.4g mm" % dev)
        return True


@register
class CommandBirail(CommandBase):
    NAME = "BNCClassA_Birail"
    ICON = "ClassABirail"
    MENU = "Birail Sweep"
    TIP = "Sweep a profile along two rails into an editable CV surface"
    PANEL = BirailPanel
