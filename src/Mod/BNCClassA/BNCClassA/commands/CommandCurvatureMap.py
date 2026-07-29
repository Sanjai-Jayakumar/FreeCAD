# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface curvature false-color map — Gaussian / Mean / Max / Min principal
curvature (or radius) sampled per tessellation vertex on the exact surface."""
import numpy as np

from BNCClassA.ui.qtcompat import QtWidgets, HORIZONTAL
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import MeshCachePanel
from .common import CommandBase, register

_MODES = ["Gaussian", "Mean", "Max principal", "Min principal", "Radius (min abs)"]


class CurvatureMapPanel(MeshCachePanel):
    TOOL_KEY = "curvature_map"
    TITLE = "Curvature Map"

    def build_params_ui(self):
        group = QtWidgets.QGroupBox("Curvature")
        form = QtWidgets.QFormLayout(group)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(_MODES)
        self.mode.currentIndexChanged.connect(self.schedule_rebuild)
        form.addRow("Mode", self.mode)

        self.clip = QtWidgets.QSlider(HORIZONTAL)
        self.clip.setRange(50, 100)
        self.clip.setValue(95)
        self.clip.setToolTip("Percentile at which the color scale saturates")
        self.clip.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Range %", self.clip)

        self.range_label = QtWidgets.QLabel("—")
        form.addRow("Scale", self.range_label)
        self.layout.addWidget(group)

    def augment_mesh(self, mesh):
        """Worker thread: sample Max/Min principal curvature per vertex; the
        other modes derive from those two."""
        n = len(mesh["verts"])
        kmax = np.zeros(n)
        kmin = np.zeros(n)
        verts = mesh["verts"]
        import FreeCAD
        for face, start, count in mesh["face_ranges"]:
            surf = face.Surface
            for i in range(start, start + count):
                p = FreeCAD.Vector(*verts[i])
                try:
                    u, v = surf.parameter(p)
                    kmax[i] = surf.curvature(u, v, "Max")
                    kmin[i] = surf.curvature(u, v, "Min")
                except Exception:
                    pass
        mesh["kmax"] = kmax
        mesh["kmin"] = kmin
        return mesh

    def make_node(self, mesh):
        kmax, kmin = mesh["kmax"], mesh["kmin"]
        mode = self.mode.currentIndex()
        if mode == 0:
            vals = kmax * kmin
        elif mode == 1:
            vals = 0.5 * (kmax + kmin)
        elif mode == 2:
            vals = kmax
        elif mode == 3:
            vals = kmin
        else:
            kabs = np.maximum(np.abs(kmax), np.abs(kmin))
            vals = np.where(kabs > 1e-12, 1.0 / np.maximum(kabs, 1e-12), 0.0)

        pct = self.clip.value()
        if mode == 4:
            lo, hi = 0.0, float(np.percentile(vals, pct)) or 1.0
            self.range_label.setText("0 … %.4g mm" % hi)
            ts = np.clip(vals / max(hi, 1e-12), 0.0, 1.0)
            colors = [overlays.rainbow_color(t) for t in ts]
        else:
            sat = float(np.percentile(np.abs(vals), pct))
            sat = sat if sat > 1e-12 else 1.0
            self.range_label.setText(u"±%.4g 1/mm" % sat)
            ts = np.clip(vals / sat, -1.0, 1.0)
            colors = [overlays.diverging_color(t) for t in ts]
        return overlays.colored_mesh_node(mesh, colors)


@register
class CommandCurvatureMap(CommandBase):
    NAME = "BNCClassA_CurvatureMap"
    ICON = "ClassACurvatureMap"
    MENU = "Curvature Map"
    TIP = "False-color Gaussian/mean/principal curvature shading of the selected faces"
    PANEL = CurvatureMapPanel
