# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extract Iso — isoparametric curve of a face as a CV curve, with live
preview while the parameter slider moves."""
import numpy as np

from BNCClassA.geom import bezier, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets, HORIZONTAL
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import CreationPanel, selected_faces
from .common import CommandBase, register


class ExtractIsoPanel(CreationPanel):
    TITLE = "Extract Isoparm"
    TRANSACTION = "Class-A Extract Iso"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.direction = QtWidgets.QComboBox()
        self.direction.addItems(["U (iso at fixed u)", "V (iso at fixed v)"])
        self.direction.currentIndexChanged.connect(self._preview)
        form.addRow("Direction", self.direction)
        self.param = QtWidgets.QSlider(HORIZONTAL)
        self.param.setRange(0, 1000)
        self.param.setValue(500)
        self.param.valueChanged.connect(self._preview)
        form.addRow("Parameter", self.param)
        self.degree = QtWidgets.QSpinBox()
        self.degree.setRange(3, 7)
        self.degree.setValue(5)
        form.addRow("Curve degree", self.degree)
        self.layout.addLayout(form)

        picked = selected_faces()
        self._face = picked[0][1] if picked else None
        self.doc_name = self.doc.Name
        if self._face is None:
            self.set_status("Select a face first.")
        else:
            self._preview()

    def _iso_curve(self):
        if self._face is None:
            return None
        surf = self._face.Surface
        umin, umax, vmin, vmax = self._face.ParameterRange
        t = self.param.value() / 1000.0
        if self.direction.currentIndex() == 0:
            return surf.uIso(umin + t * (umax - umin))
        return surf.vIso(vmin + t * (vmax - vmin))

    def _preview(self, *_args):
        curve = self._iso_curve()
        if curve is None:
            return
        edge = curve.toShape()
        pts = edge.discretize(Number=60)
        overlays.show(self.doc_name, "extract_iso",
                      overlays.lines_node([[(p.x, p.y, p.z) for p in pts]],
                                          rgb=(1.0, 0.75, 0.15), width=2.5))

    def create(self):
        from BNCClassA.objects.cv_curve import make_cv_curve
        curve = self._iso_curve()
        if curve is None:
            return False
        edge = curve.toShape()
        poles, dev = nurbs_io.edge_to_bezier(edge, degree=self.degree.value())
        make_cv_curve(self.doc, poles,
                      provenance="Isoparm (fit dev %.4g mm)" % dev)
        overlays.clear(self.doc_name, "extract_iso")
        return True

    def reject(self):
        overlays.clear(self.doc_name, "extract_iso")
        return CreationPanel.reject(self)


@register
class CommandExtractIso(CommandBase):
    NAME = "BNCClassA_ExtractIso"
    ICON = "ClassAExtractIso"
    MENU = "Extract Isoparm"
    TIP = "Extract an isoparametric curve of a face as a CV curve"
    PANEL = ExtractIsoPanel
