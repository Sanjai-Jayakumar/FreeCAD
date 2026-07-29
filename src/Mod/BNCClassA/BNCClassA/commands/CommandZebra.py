# SPDX-License-Identifier: LGPL-2.1-or-later
"""Zebra stripe analysis — environment-mapped stripe texture on a tessellated
overlay copy. Stripes flow over the surfaces as the camera orbits; kinks and
jumps in the stripes expose G1/G0 defects, curvature of the stripe flow
exposes G2 behavior."""

from BNCClassA.ui.qtcompat import QtWidgets, HORIZONTAL
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import MeshCachePanel
from .common import CommandBase, register


class ZebraPanel(MeshCachePanel):
    TOOL_KEY = "zebra"
    TITLE = "Zebra Analysis"

    def build_params_ui(self):
        group = QtWidgets.QGroupBox("Stripes")
        form = QtWidgets.QFormLayout(group)

        self.count = QtWidgets.QSpinBox()
        self.count.setRange(2, 60)
        self.count.setValue(12)
        self.count.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Count", self.count)

        self.width = QtWidgets.QSlider(HORIZONTAL)
        self.width.setRange(10, 90)
        self.width.setValue(50)
        self.width.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Width %", self.width)

        self.angle = QtWidgets.QSpinBox()
        self.angle.setRange(0, 180)
        self.angle.setSingleStep(15)
        self.angle.setValue(0)
        self.angle.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Angle °", self.angle)

        self.sharp = QtWidgets.QCheckBox("Sharp stripe edges")
        self.sharp.setChecked(False)
        self.sharp.toggled.connect(self.schedule_rebuild)
        form.addRow(self.sharp)

        self.layout.addWidget(group)

    def make_node(self, mesh):
        image = overlays.stripe_image(
            count=self.count.value(),
            width_frac=self.width.value() / 100.0,
            angle_deg=float(self.angle.value()),
            sharp=self.sharp.isChecked(),
        )
        return overlays.textured_mesh_node(mesh, image)


@register
class CommandZebra(CommandBase):
    NAME = "BNCClassA_Zebra"
    ICON = "ClassAZebra"
    MENU = "Zebra Analysis"
    TIP = ("Environment-mapped zebra stripes on the selected faces — "
           "stripe kinks reveal G1 breaks, stripe jumps reveal G0 gaps")
    PANEL = ZebraPanel
