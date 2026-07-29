# SPDX-License-Identifier: LGPL-2.1-or-later
"""New CV Curve — click-place control vertices on a work plane. Single-span
discipline: the curve takes exactly degree+1 CVs, then finishes."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui import overlays
from BNCClassA.ui.panels import CreationPanel
from BNCClassA.ui.viewer import ClickPlaceController
from .common import CommandBase, register

_PLANES = {
    "XY (top)": (FreeCAD.Vector(0, 0, 1)),
    "XZ (front)": (FreeCAD.Vector(0, 1, 0)),
    "YZ (side)": (FreeCAD.Vector(1, 0, 0)),
}


class CVCurvePanel(CreationPanel):
    TITLE = "New CV Curve"
    TRANSACTION = "Class-A CV Curve"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.degree = QtWidgets.QComboBox()
        self.degree.addItems(["3", "5", "7"])
        form.addRow("Degree", self.degree)
        self.plane = QtWidgets.QComboBox()
        self.plane.addItems(list(_PLANES.keys()))
        form.addRow("Work plane", self.plane)
        self.offset = QtWidgets.QDoubleSpinBox()
        self.offset.setRange(-100000, 100000)
        self.offset.setSuffix(" mm")
        form.addRow("Plane offset", self.offset)
        undo_btn = QtWidgets.QPushButton("Remove last CV")
        undo_btn.clicked.connect(self._pop_point)
        form.addRow(undo_btn)
        self.layout.addLayout(form)

        self.doc_name = self.doc.Name
        self._points = []
        self.controller = ClickPlaceController(
            self._plane, self._add_point, self._preview, self._try_finish)
        self.controller.install()
        self._update_status()

    def _plane(self):
        normal = _PLANES[self.plane.currentText()]
        return normal * self.offset.value(), normal

    def _needed(self):
        return int(self.degree.currentText()) + 1

    def _update_status(self):
        self.set_status("Click CV %d of %d in the 3D view."
                        % (len(self._points) + 1, self._needed())
                        if len(self._points) < self._needed()
                        else "All CVs placed — press OK.")

    def _add_point(self, p):
        if len(self._points) >= self._needed():
            return
        self._points.append(p)
        self._update_status()
        self._preview(None)
        if len(self._points) == self._needed():
            # all CVs placed: create immediately for Alias-like flow
            self.accept()

    def _pop_point(self):
        if self._points:
            self._points.pop()
            self._update_status()
            self._preview(None)

    def _preview(self, cursor):
        pts = [(p.x, p.y, p.z) for p in self._points]
        if cursor is not None and len(self._points) < self._needed():
            pts = pts + [(cursor.x, cursor.y, cursor.z)]
        if len(pts) < 2:
            overlays.clear(self.doc_name, "cv_curve_place")
            return
        overlays.show(self.doc_name, "cv_curve_place",
                      overlays.lines_node([pts], rgb=(0.35, 0.62, 0.95), width=1.5))

    def _try_finish(self):
        if len(self._points) >= 2:
            self.accept()

    def create(self):
        from BNCClassA.objects.cv_curve import make_cv_curve
        if len(self._points) < 2:
            self.set_status("Place at least 2 CVs first.")
            return False
        make_cv_curve(self.doc, list(self._points), provenance="CV curve")
        return True

    def accept(self):
        result = CreationPanel.accept(self)
        if result:
            self._cleanup()
        return result

    def reject(self):
        self._cleanup()
        return CreationPanel.reject(self)

    def _cleanup(self):
        try:
            self.controller.uninstall()
        except Exception:
            pass
        overlays.clear(self.doc_name, "cv_curve_place")


@register
class CommandCVCurve(CommandBase):
    NAME = "BNCClassA_CVCurve"
    ICON = "ClassACVCurve"
    MENU = "New CV Curve"
    TIP = "Click-place a single-span Bézier CV curve on a work plane"
    PANEL = CVCurvePanel
