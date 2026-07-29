# SPDX-License-Identifier: LGPL-2.1-or-later
"""Continuity checker — sampled G0/G1/G2 report between two faces along their
shared boundary, with tick-bar overlay and CSV export."""
import FreeCAD

from BNCClassA.geom import continuity
from BNCClassA.ui.qtcompat import QtWidgets, QtGui
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import AnalysisPanel, selection_subelements
from .common import CommandBase, register

_LEVELS = ("G0", "G1", "G2")


class ContinuityCheckPanel(AnalysisPanel):
    TOOL_KEY = "continuity_check"
    TITLE = "Continuity Check"

    def build_ui(self):
        src_group = QtWidgets.QGroupBox("Faces")
        src_lay = QtWidgets.QVBoxLayout(src_group)
        self.src_label = QtWidgets.QLabel(
            "Select two faces (and optionally their shared edge), then press "
            "'Use current selection'.")
        self.src_label.setWordWrap(True)
        btn = QtWidgets.QPushButton("Use current selection")
        btn.clicked.connect(self.capture_selection)
        src_lay.addWidget(self.src_label)
        src_lay.addWidget(btn)
        self.layout.addWidget(src_group)

        params = QtWidgets.QGroupBox("Sampling / tolerances")
        form = QtWidgets.QFormLayout(params)
        self.samples = QtWidgets.QSpinBox()
        self.samples.setRange(5, 400)
        self.samples.setValue(60)
        form.addRow("Stations", self.samples)
        self.tol_g0 = QtWidgets.QDoubleSpinBox()
        self.tol_g0.setDecimals(4)
        self.tol_g0.setRange(0.0001, 10.0)
        self.tol_g0.setValue(continuity.G0_TOL_MM)
        form.addRow("G0 tol (mm)", self.tol_g0)
        self.tol_g1 = QtWidgets.QDoubleSpinBox()
        self.tol_g1.setDecimals(4)
        self.tol_g1.setRange(0.0001, 45.0)
        self.tol_g1.setValue(continuity.G1_TOL_DEG)
        form.addRow("G1 tol (°)", self.tol_g1)
        self.tol_g2 = QtWidgets.QDoubleSpinBox()
        self.tol_g2.setDecimals(4)
        self.tol_g2.setRange(0.0001, 1.0)
        self.tol_g2.setValue(continuity.G2_TOL_REL)
        form.addRow("G2 tol (rel)", self.tol_g2)
        self.display_level = QtWidgets.QComboBox()
        self.display_level.addItems(list(_LEVELS))
        self.display_level.setCurrentIndex(1)
        self.display_level.currentIndexChanged.connect(self._refresh_overlay)
        form.addRow("Show ticks for", self.display_level)
        run = QtWidgets.QPushButton("Check continuity")
        run.clicked.connect(self.rebuild)
        form.addRow(run)
        self.layout.addWidget(params)

        self.table = QtWidgets.QTableWidget(3, 4)
        self.table.setHorizontalHeaderLabels(["min", "max", "mean", "status"])
        self.table.setVerticalHeaderLabels(list(_LEVELS))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers
                                   if hasattr(QtWidgets.QAbstractItemView, "NoEditTriggers")
                                   else QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFixedHeight(140)
        self.layout.addWidget(self.table)

        export = QtWidgets.QPushButton("Export CSV…")
        export.clicked.connect(self.export_csv)
        self.layout.addWidget(export)

        self._face_a = None
        self._face_b = None
        self._edge = None
        self._report = None
        self.capture_selection()

    def capture_selection(self):
        faces, edge = [], None
        for (_obj, sub, sub_obj) in selection_subelements():
            st = getattr(sub_obj, "ShapeType", "")
            if st == "Face" and len(faces) < 2:
                faces.append((sub, sub_obj))
            elif st == "Edge" and edge is None:
                edge = sub_obj
        if len(faces) < 2:
            self.set_status("Need two faces selected (Ctrl-click the second).")
            return
        self._face_a, self._face_b = faces[0][1], faces[1][1]
        self._edge = edge
        self.src_label.setText("A: %s   B: %s   edge: %s"
                               % (faces[0][0], faces[1][0],
                                  "picked" if edge is not None else "auto"))
        self.set_status("Ready — press 'Check continuity'.")

    def rebuild(self):
        if self._face_a is None or self._face_b is None:
            self.capture_selection()
            if self._face_a is None:
                return
        edge = self._edge
        try:
            if edge is None:
                edge = continuity.find_shared_edge(self._face_a, self._face_b)
            self._report = continuity.sample_continuity(
                self._face_a, self._face_b, edge, n=self.samples.value())
        except Exception as exc:
            self.set_status("Error: %s" % exc)
            return
        self._fill_table()
        self._refresh_overlay()

    def _tolerances(self):
        return (self.tol_g0.value(), self.tol_g1.value(), self.tol_g2.value())

    def _fill_table(self):
        rep = self._report
        if rep is None:
            return
        tols = self._tolerances()
        passed = rep.passes(*tols)
        summary = rep.summary()
        units = ("mm", "°", "")
        for row, level in enumerate(_LEVELS):
            lo, hi, mean = summary[level]
            for col, val in enumerate((lo, hi, mean)):
                item = QtWidgets.QTableWidgetItem("%.5g %s" % (val, units[row]))
                self.table.setItem(row, col, item)
            status = QtWidgets.QTableWidgetItem("PASS" if passed[row] else "FAIL")
            status.setForeground(QtGui.QBrush(
                QtGui.QColor(60, 190, 90) if passed[row] else QtGui.QColor(220, 70, 60)))
            self.table.setItem(row, 3, status)
        ok = ["%s %s" % (lvl, "ok" if p else "FAIL")
              for lvl, p in zip(_LEVELS, passed)]
        self.set_status("  ".join(ok))

    def _refresh_overlay(self, *_args):
        rep = self._report
        if rep is None:
            return
        level = self.display_level.currentText()
        vals = {"G0": rep.g0, "G1": rep.g1, "G2": rep.g2}[level]
        tol = dict(zip(_LEVELS, self._tolerances()))[level]
        if not vals:
            return
        vmax = max(max(vals), 1e-12)
        # tick length: 8% of the sampled span
        pts = rep.points
        span = (pts[0] - pts[-1]).Length or 1.0
        tick_len = span * 0.08
        surf = self._face_a.Surface
        good, bad = [], []
        for p, v in zip(pts, vals):
            try:
                u, vv = surf.parameter(p)
                n = surf.normal(u, vv)
            except Exception:
                n = FreeCAD.Vector(0, 0, 1)
            tip = p + n * (tick_len * (v / vmax))
            seg = [(p.x, p.y, p.z), (tip.x, tip.y, tip.z)]
            (bad if v > tol else good).append(seg)
        children = [overlays.lines_node(good, rgb=(0.2, 0.9, 0.3), width=2.0),
                    overlays.lines_node(bad, rgb=(1.0, 0.25, 0.2), width=2.5)]
        worst = rep.worst_station(level)
        if worst is not None:
            _t, wp, wv = worst
            unit = {"G0": "mm", "G1": "°", "G2": ""}[level]
            children.append(overlays.text_label_node(
                (wp.x, wp.y, wp.z), "%s max %.5g %s" % (level, wv, unit)))
        self.show_overlay(overlays.group_node(children))

    def export_csv(self):
        rep = self._report
        if rep is None:
            self.set_status("Run the check first.")
            return
        path, _f = QtWidgets.QFileDialog.getSaveFileName(
            self.form, "Export continuity report", "continuity.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w") as fh:
            fh.write("param,x,y,z,G0_mm,G1_deg,G2_rel\n")
            for t, p, g0, g1, g2 in zip(rep.params, rep.points, rep.g0, rep.g1, rep.g2):
                fh.write("%.6g,%.6g,%.6g,%.6g,%.8g,%.8g,%.8g\n"
                         % (t, p.x, p.y, p.z, g0, g1, g2))
        self.set_status("Exported %d stations to %s" % (len(rep.params), path))


@register
class CommandContinuityCheck(CommandBase):
    NAME = "BNCClassA_ContinuityCheck"
    ICON = "ClassAContinuityCheck"
    MENU = "Continuity Check"
    TIP = ("Sampled G0/G1/G2 report between two faces along their shared "
           "boundary, with pass/fail ticks in the 3D view")
    PANEL = ContinuityCheckPanel
