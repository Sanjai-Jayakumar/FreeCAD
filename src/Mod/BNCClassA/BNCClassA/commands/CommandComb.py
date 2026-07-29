# SPDX-License-Identifier: LGPL-2.1-or-later
"""Curvature comb on edges and surface sections."""
import numpy as np
import FreeCAD

from BNCClassA.geom import combs
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import AnalysisPanel, LogScaleSlider, selected_edges, selected_faces
from .common import CommandBase, register

_AXES = {"X": FreeCAD.Vector(1, 0, 0),
         "Y": FreeCAD.Vector(0, 1, 0),
         "Z": FreeCAD.Vector(0, 0, 1)}


class CombPanel(AnalysisPanel):
    TOOL_KEY = "comb"
    TITLE = "Curvature Comb"

    def build_ui(self):
        src_group = QtWidgets.QGroupBox("Sources")
        src_lay = QtWidgets.QVBoxLayout(src_group)
        self.src_label = QtWidgets.QLabel("(nothing captured)")
        self.src_label.setWordWrap(True)
        btn = QtWidgets.QPushButton("Use current selection")
        btn.clicked.connect(self.capture_selection)
        src_lay.addWidget(self.src_label)
        src_lay.addWidget(btn)
        self.layout.addWidget(src_group)

        group = QtWidgets.QGroupBox("Comb")
        form = QtWidgets.QFormLayout(group)
        self.density = QtWidgets.QSpinBox()
        self.density.setRange(10, 300)
        self.density.setValue(80)
        self.density.valueChanged.connect(self.schedule_rebuild)
        form.addRow("Teeth", self.density)

        self.scale = LogScaleSlider(0.01, 10.0, 1.0)
        self.scale.changed.connect(self.schedule_rebuild)
        form.addRow("Scale ×auto", self.scale)
        self.layout.addWidget(group)

        sect = QtWidgets.QGroupBox("Surface sections (for selected faces)")
        sform = QtWidgets.QFormLayout(sect)
        self.sect_axis = QtWidgets.QComboBox()
        self.sect_axis.addItems(list(_AXES.keys()))
        self.sect_axis.setCurrentIndex(2)
        self.sect_axis.currentIndexChanged.connect(self.schedule_rebuild)
        sform.addRow("Axis", self.sect_axis)
        self.sect_count = QtWidgets.QSpinBox()
        self.sect_count.setRange(1, 40)
        self.sect_count.setValue(7)
        self.sect_count.valueChanged.connect(self.schedule_rebuild)
        sform.addRow("Sections", self.sect_count)
        self.layout.addWidget(sect)

        self._edges = []
        self._faces = []
        self.capture_selection()

    def capture_selection(self):
        edges = selected_edges()
        faces = selected_faces()
        self._edges = [e for (_o, e, _l) in edges]
        self._faces = [f for (_o, f, _l) in faces]
        parts = []
        if self._edges:
            parts.append("%d edge(s)" % len(self._edges))
        if self._faces:
            parts.append("%d face(s) → sections" % len(self._faces))
        self.src_label.setText(", ".join(parts) if parts else "(nothing captured)")
        if not parts:
            self.set_status("Select edges (comb) and/or faces (section combs).")
        self.schedule_rebuild()

    def _section_edges(self):
        out = []
        axis = _AXES[self.sect_axis.currentText()]
        count = self.sect_count.value()
        for face in self._faces:
            bb = face.BoundBox
            span = axis.dot(FreeCAD.Vector(bb.XMax - bb.XMin, bb.YMax - bb.YMin,
                                           bb.ZMax - bb.ZMin))
            base = axis.dot(FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin))
            if abs(span) < 1e-9:
                continue
            positions = [base + span * (i + 1) / (count + 1.0) for i in range(count)]
            try:
                for w in face.slices(axis, positions):
                    out.extend(w.Edges)
            except Exception:
                continue
        return out

    def rebuild(self):
        edges = list(self._edges) + self._section_edges()
        if not edges:
            return
        teeth = []
        envelopes = []
        n = self.density.value()
        for edge in edges:
            scale = combs.auto_scale(edge, n=min(n, 80)) * self.scale.value()
            roots, tips, _k = combs.curve_comb(edge, n=n, scale=scale)
            for r, t in zip(roots, tips):
                teeth.append([(r.x, r.y, r.z), (t.x, t.y, t.z)])
            envelopes.append([(t.x, t.y, t.z) for t in tips])
        node = overlays.group_node([
            overlays.lines_node(teeth, rgb=(0.25, 0.75, 1.0), width=1.0),
            overlays.lines_node(envelopes, rgb=(1.0, 0.75, 0.15), width=2.0),
        ])
        self.show_overlay(node)
        self.set_status("%d comb(s), %d teeth each." % (len(edges), n))


@register
class CommandComb(CommandBase):
    NAME = "BNCClassA_Comb"
    ICON = "ClassAComb"
    MENU = "Curvature Comb"
    TIP = "Curvature comb on selected edges and on planar sections of selected faces"
    PANEL = CombPanel
