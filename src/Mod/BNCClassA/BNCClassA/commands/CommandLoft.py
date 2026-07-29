# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft — CV surface through profile curves in selection order."""
from BNCClassA.geom import nurbs_io, builders
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selected_edges
from .common import CommandBase, register


class LoftPanel(CreationPanel):
    TITLE = "Class-A Loft"
    TRANSACTION = "Class-A Loft"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.degree = QtWidgets.QSpinBox()
        self.degree.setRange(3, 7)
        self.degree.setValue(5)
        self.degree.setToolTip("Profile-direction degree of the fitted sections")
        form.addRow("Profile degree", self.degree)
        self.layout.addLayout(form)
        edges = selected_edges()
        self.set_status("%d section(s) in selection order." % len(edges)
                        if len(edges) >= 2 else
                        "Select 2 or more section edges (in order).")

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        edges = selected_edges()
        if len(edges) < 2:
            self.set_status("Select 2 or more section edges (in order).")
            return False
        deg = self.degree.value()
        profiles = []
        for (_obj, edge, _label) in edges:
            poles, _dev = nurbs_io.edge_to_bezier(edge, degree=deg)
            profiles.append(poles)
        # align section directions with the first profile
        import numpy as np
        for i in range(1, len(profiles)):
            fwd = np.linalg.norm(profiles[i][0] - profiles[i - 1][0])
            rev = np.linalg.norm(profiles[i][::-1][0] - profiles[i - 1][0])
            if rev < fwd:
                profiles[i] = profiles[i][::-1]
        net = builders.loft_net(profiles)
        make_cv_surface(self.doc, net,
                        provenance="Loft through %d sections" % len(profiles))
        return True


@register
class CommandLoft(CommandBase):
    NAME = "BNCClassA_Loft"
    ICON = "ClassALoft"
    MENU = "Loft Surface"
    TIP = "Loft an editable CV surface through the selected section edges"
    PANEL = LoftPanel
