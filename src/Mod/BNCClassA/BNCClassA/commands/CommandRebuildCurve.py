# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rebuild Curve — reapproximate any edge as a single-span Bézier CV curve
with a deviation report before committing."""
from BNCClassA.geom import nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selected_edges
from .common import CommandBase, register


class RebuildCurvePanel(CreationPanel):
    TITLE = "Rebuild Curve"
    TRANSACTION = "Class-A Rebuild Curve"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.degree = QtWidgets.QComboBox()
        self.degree.addItems(["3", "5", "7"])
        self.degree.setCurrentIndex(1)
        self.degree.currentIndexChanged.connect(self._update_preview)
        form.addRow("Degree", self.degree)
        self.dev_label = QtWidgets.QLabel("—")
        form.addRow("Max deviation", self.dev_label)
        self.layout.addLayout(form)
        self._update_preview()

    def _update_preview(self, *_args):
        edges = selected_edges()
        if not edges:
            self.set_status("Select one or more edges.")
            return
        deg = int(self.degree.currentText())
        devs = []
        for (_o, edge, _l) in edges:
            _poles, dev = nurbs_io.edge_to_bezier(edge, degree=deg, samples=200)
            devs.append(dev)
        self.dev_label.setText(", ".join("%.4g mm" % d for d in devs))
        self.set_status("%d edge(s) → degree %d single-span Bézier." %
                        (len(edges), deg))

    def create(self):
        from BNCClassA.objects.cv_curve import make_cv_curve
        edges = selected_edges()
        if not edges:
            return False
        deg = int(self.degree.currentText())
        for (_o, edge, label) in edges:
            poles, dev = nurbs_io.edge_to_bezier(edge, degree=deg, samples=200)
            make_cv_curve(self.doc, poles,
                          provenance="Rebuilt from %s (dev %.4g mm)" % (label, dev))
        return True


@register
class CommandRebuildCurve(CommandBase):
    NAME = "BNCClassA_RebuildCurve"
    ICON = "ClassARebuildCurve"
    MENU = "Rebuild Curve"
    TIP = "Reapproximate an edge as a single-span Bézier CV curve (deviation shown)"
    PANEL = RebuildCurvePanel
