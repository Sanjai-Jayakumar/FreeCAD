# SPDX-License-Identifier: LGPL-2.1-or-later
"""Highlight lines — HLR reflection lines (Shape.reflectLines) from an array
of parallel line lights, the classic Class-A 'light tube' evaluation."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import AnalysisPanel, selected_shapes
from .common import CommandBase, register

_DIRS = {
    "Current view": None,
    "+Z (top)": FreeCAD.Vector(0, 0, -1),
    "+Y (front)": FreeCAD.Vector(0, -1, 0),
    "+X (side)": FreeCAD.Vector(-1, 0, 0),
}


class HighlightPanel(AnalysisPanel):
    TOOL_KEY = "highlight"
    TITLE = "Highlight Lines"

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

        group = QtWidgets.QGroupBox("Light array")
        form = QtWidgets.QFormLayout(group)
        self.direction = QtWidgets.QComboBox()
        self.direction.addItems(list(_DIRS.keys()))
        form.addRow("View from", self.direction)
        self.count = QtWidgets.QSpinBox()
        self.count.setRange(1, 25)
        self.count.setValue(7)
        form.addRow("Lines", self.count)
        run = QtWidgets.QPushButton("Compute highlight lines")
        run.clicked.connect(self.rebuild)
        form.addRow(run)
        self.layout.addWidget(group)

        self._shapes = []
        self.capture_selection()

    def capture_selection(self):
        picked = selected_shapes()
        self._shapes = [s for (_o, s) in picked]
        self.src_label.setText(", ".join(o.Label for (o, _s) in picked)
                               if picked else "(nothing captured)")
        if not picked:
            self.set_status("Select one or more objects.")

    def _view_setup(self):
        choice = self.direction.currentText()
        vdir = _DIRS[choice]
        if vdir is None:
            try:
                vdir = Gui.ActiveDocument.ActiveView.getViewDirection()
            except Exception:
                vdir = FreeCAD.Vector(0, 0, -1)
        vdir = FreeCAD.Vector(vdir)
        vdir.normalize()
        # any up-vector not parallel to the view direction
        up = FreeCAD.Vector(0, 0, 1)
        if abs(vdir.dot(up)) > 0.9:
            up = FreeCAD.Vector(0, 1, 0)
        up = (up - vdir * up.dot(vdir)).normalize()
        return vdir, up

    def rebuild(self):
        if not self._shapes:
            self.capture_selection()
            if not self._shapes:
                return
        vdir, up = self._view_setup()
        shapes = list(self._shapes)
        count = self.count.value()

        def work():
            polylines = []
            for shape in shapes:
                bb = shape.BoundBox
                center = bb.Center
                diag = bb.DiagonalLength or 1.0
                lateral = vdir.cross(up)
                for k in range(count):
                    frac = (k - (count - 1) / 2.0) / max(count, 1)
                    pos = center - vdir * diag + lateral * (frac * diag * 0.8)
                    try:
                        res = shape.reflectLines(ViewDir=vdir, ViewPos=pos, UpDir=up)
                    except Exception:
                        continue
                    for edge in res.Edges:
                        try:
                            pts = edge.discretize(Number=40)
                            polylines.append([(p.x, p.y, p.z) for p in pts])
                        except Exception:
                            pass
            return polylines

        self.set_status("Computing HLR reflection lines…")
        self.run_async(work, self._on_done)

    def _on_done(self, polylines):
        if not polylines:
            self.set_status("No reflection lines found for this direction.")
            return
        self.show_overlay(overlays.lines_node(polylines, rgb=(1.0, 1.0, 1.0), width=2.0))
        self.set_status("%d highlight curve(s)." % len(polylines))


@register
class CommandHighlight(CommandBase):
    NAME = "BNCClassA_Highlight"
    ICON = "ClassAHighlight"
    MENU = "Highlight Lines"
    TIP = "HLR reflection lines from an array of parallel line lights"
    PANEL = HighlightPanel
