# SPDX-License-Identifier: LGPL-2.1-or-later
"""Match Surface — rewrite the boundary CV rows of a CV surface to meet a
target face at G0/G1/G2. The workhorse Class-A operation."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.geom import continuity, match, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import AnalysisPanel, selection_subelements
from .common import CommandBase, register


class MatchSurfacePanel(AnalysisPanel):
    TOOL_KEY = "match_surface"
    TITLE = "Match Surface"

    def build_ui(self):
        info = QtWidgets.QLabel(
            "Pick the edge of the CV surface to modify, then Ctrl-pick the "
            "matching edge on the target face, then press 'Use current "
            "selection'.")
        info.setWordWrap(True)
        self.layout.addWidget(info)

        src_group = QtWidgets.QGroupBox("Selection")
        src_lay = QtWidgets.QVBoxLayout(src_group)
        self.src_label = QtWidgets.QLabel("(nothing captured)")
        self.src_label.setWordWrap(True)
        btn = QtWidgets.QPushButton("Use current selection")
        btn.clicked.connect(self.capture_selection)
        src_lay.addWidget(self.src_label)
        src_lay.addWidget(btn)
        self.layout.addWidget(src_group)

        params = QtWidgets.QGroupBox("Match")
        form = QtWidgets.QFormLayout(params)
        self.order = QtWidgets.QComboBox()
        self.order.addItems(["G0 (position)", "G1 (tangent)", "G2 (curvature)"])
        self.order.setCurrentIndex(2)
        form.addRow("Continuity", self.order)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Minimal change", "Adopt target flow"])
        form.addRow("Mode", self.mode)
        self.tension = QtWidgets.QDoubleSpinBox()
        self.tension.setRange(0.1, 3.0)
        self.tension.setSingleStep(0.1)
        self.tension.setValue(1.0)
        form.addRow("Tension", self.tension)
        self.hold = QtWidgets.QCheckBox("Hold opposite edge")
        self.hold.setChecked(True)
        form.addRow(self.hold)
        apply_btn = QtWidgets.QPushButton("Apply match")
        apply_btn.clicked.connect(self.rebuild)
        form.addRow(apply_btn)
        self.result_label = QtWidgets.QLabel("—")
        self.result_label.setWordWrap(True)
        form.addRow("Achieved", self.result_label)
        self.layout.addWidget(params)

        self._surface_obj = None
        self._boundary = None
        self._target_face = None
        self._target_edge = None
        self.capture_selection()

    def capture_selection(self):
        from BNCClassA.objects.helpers import is_cv_surface
        subs = selection_subelements()
        edges = [(obj, sub_obj) for (obj, _s, sub_obj) in subs
                 if getattr(sub_obj, "ShapeType", "") == "Edge"]
        if len(edges) < 2:
            self.set_status("Pick two edges: one on the CV surface, one on "
                            "the target face.")
            return
        cv_pair = next(((o, e) for (o, e) in edges if is_cv_surface(o)), None)
        tgt_pair = next(((o, e) for (o, e) in edges if not is_cv_surface(o)
                         or (cv_pair and o is not cv_pair[0])), None)
        if cv_pair is None:
            self.set_status("One picked edge must belong to a CV Surface.")
            return
        if tgt_pair is None:
            self.set_status("Pick the matching edge on the target face too.")
            return
        obj, cv_edge = cv_pair
        tgt_obj, tgt_edge = tgt_pair
        hosts = nurbs_io.host_faces_of_edge(tgt_obj.Shape, tgt_edge)
        if not hosts:
            self.set_status("Could not find the target edge's face.")
            return
        from BNCClassA.objects.cv_surface import CVSurface
        try:
            net = CVSurface.pole_array(obj)
            boundary, _rev = nurbs_io.identify_boundary(net, cv_edge, tol=1.0)
        except Exception as exc:
            self.set_status("Cannot identify the picked boundary: %s" % exc)
            return
        self._surface_obj = obj
        self._boundary = boundary
        self._target_face = hosts[0]
        self._target_edge = tgt_edge
        self.src_label.setText("Modify: %s (%s edge)   Target: %s"
                               % (obj.Label, boundary, tgt_obj.Label))
        self.set_status("Ready — press 'Apply match'.")

    def rebuild(self):
        if self._surface_obj is None:
            self.capture_selection()
            if self._surface_obj is None:
                return
        from BNCClassA.objects.cv_surface import CVSurface
        obj = self._surface_obj
        order = self.order.currentIndex()
        mode = "flow" if self.mode.currentIndex() == 1 else "minimal"
        try:
            net = CVSurface.pole_array(obj)
            result = match.match_surface(
                net, self._boundary, self._target_face, self._target_edge,
                order=order, tension=self.tension.value(), mode=mode,
                hold_opposite=self.hold.isChecked())
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.set_status("Match failed: %s" % exc)
            return
        doc = obj.Document
        doc.openTransaction("Match Surface")
        try:
            CVSurface.set_pole_array(obj, result.net)
            obj.MatchContinuity = ("G0", "G1", "G2")[order]
            obj.recompute()
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            self.set_status("Error: %s" % exc)
            return
        # verify with the independent checker on the real geometry
        try:
            face_b = obj.Shape.Faces[0]
            report = continuity.sample_continuity(
                self._target_face, face_b, self._target_edge, n=50)
            self.result_label.setText(
                "G0 %.3g mm   G1 %.3g°   G2 %.3g rel"
                % (report.max_g0, report.max_g1, report.max_g2))
        except Exception:
            self.result_label.setText(result.summary() + " (predicted)")
        self.set_status("Match applied.")


@register
class CommandMatchSurface(CommandBase):
    NAME = "BNCClassA_MatchSurface"
    ICON = "ClassAMatchSurface"
    MENU = "Match Surface"
    TIP = ("Rewrite the boundary CV rows of a CV surface to meet a target "
           "face at G0/G1/G2")
    PANEL = MatchSurfacePanel
