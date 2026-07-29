# SPDX-License-Identifier: LGPL-2.1-or-later
"""Environment reflection map — procedural studio/showroom/sky environments
sphere-mapped onto the selected faces to judge reflection flow."""

from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import MeshCachePanel
from .common import CommandBase, register


class EnvMapPanel(MeshCachePanel):
    TOOL_KEY = "envmap"
    TITLE = "Environment Map"

    def build_params_ui(self):
        group = QtWidgets.QGroupBox("Environment")
        form = QtWidgets.QFormLayout(group)
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems(["Studio softbox", "Showroom windows", "Sky"])
        self.kind.currentIndexChanged.connect(self.schedule_rebuild)
        form.addRow("Scene", self.kind)
        self.layout.addWidget(group)

    def make_node(self, mesh):
        kind = ("studio", "showroom", "sky")[self.kind.currentIndex()]
        return overlays.textured_mesh_node(mesh, overlays.studio_image(kind))


@register
class CommandEnvMap(CommandBase):
    NAME = "BNCClassA_EnvMap"
    ICON = "ClassAEnvMap"
    MENU = "Environment Map"
    TIP = "Reflect a procedural studio environment in the selected faces"
    PANEL = EnvMapPanel
