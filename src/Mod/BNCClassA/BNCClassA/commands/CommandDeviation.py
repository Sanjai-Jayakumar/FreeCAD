# SPDX-License-Identifier: LGPL-2.1-or-later
"""Deviation map — color the first selected object by its distance to the
second (reference) object. Per-vertex distances are measured against the
reference's tessellated point cloud (fast, resolution-limited); the exact
global minimum comes from distToShape."""
import numpy as np

from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import MeshCachePanel, selected_shapes
from .common import CommandBase, register


class DeviationPanel(MeshCachePanel):
    TOOL_KEY = "deviation"
    TITLE = "Deviation"

    def build_params_ui(self):
        group = QtWidgets.QGroupBox("Scale")
        form = QtWidgets.QFormLayout(group)
        self.max_dev = QtWidgets.QDoubleSpinBox()
        self.max_dev.setDecimals(4)
        self.max_dev.setRange(0.0, 1000.0)
        self.max_dev.setValue(0.0)
        self.max_dev.setToolTip("Distance at which the scale saturates (0 = auto)")
        self.max_dev.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Saturate at (mm)", self.max_dev)
        self.range_label = QtWidgets.QLabel("—")
        form.addRow("Measured", self.range_label)
        self.layout.addWidget(group)
        self._ref_shape = None
        self._ref_label = ""

    def capture_selection(self):
        picked = selected_shapes()
        if len(picked) < 2:
            self.set_status("Select the object to color, then Ctrl-select the "
                            "reference object, then press 'Use current selection'.")
            return
        obj_a, shape_a = picked[0]
        obj_b, shape_b = picked[1]
        self._faces = shape_a.Faces
        self._objs = [obj_a]
        self._ref_shape = shape_b
        self._ref_label = obj_b.Label
        self.src_label.setText("Color: %s   Reference: %s"
                               % (obj_a.Label, obj_b.Label))
        self.invalidate_mesh()

    def augment_mesh(self, mesh):
        if self._ref_shape is None:
            return mesh
        # reference point cloud at matching resolution
        ref_pts = []
        tol = overlays.quality_to_tol(self.quality.value())
        for f in self._ref_shape.Faces:
            try:
                pts, _tris = f.tessellate(tol)
                ref_pts.extend((p.x, p.y, p.z) for p in pts)
            except Exception:
                pass
        for e in ([] if self._ref_shape.Faces else self._ref_shape.Edges):
            try:
                ref_pts.extend((p.x, p.y, p.z)
                               for p in e.discretize(Distance=max(tol, 0.05)))
            except Exception:
                pass
        if not ref_pts:
            mesh["dist"] = np.zeros(len(mesh["verts"]))
            return mesh
        ref = np.asarray(ref_pts)
        verts = np.asarray(mesh["verts"])
        dist = np.empty(len(verts))
        chunk = 2000
        for i in range(0, len(verts), chunk):
            block = verts[i:i + chunk]
            d2 = ((block[:, None, :] - ref[None, :, :]) ** 2).sum(axis=2)
            dist[i:i + chunk] = np.sqrt(d2.min(axis=1))
        mesh["dist"] = dist
        return mesh

    def make_node(self, mesh):
        dist = mesh.get("dist")
        if dist is None:
            return overlays.group_node([])
        sat = self.max_dev.value()
        if sat <= 0.0:
            sat = float(np.percentile(dist, 98)) or 1.0
        self.range_label.setText("min %.4g / max %.4g mm (cloud-sampled)"
                                 % (float(dist.min()), float(dist.max())))
        ts = np.clip(dist / max(sat, 1e-12), 0.0, 1.0)
        colors = [overlays.rainbow_color(t) for t in ts]
        return overlays.colored_mesh_node(mesh, colors)


@register
class CommandDeviation(CommandBase):
    NAME = "BNCClassA_Deviation"
    ICON = "ClassADeviation"
    MENU = "Deviation Map"
    TIP = "Color one object by its distance to a reference object"
    PANEL = DeviationPanel
