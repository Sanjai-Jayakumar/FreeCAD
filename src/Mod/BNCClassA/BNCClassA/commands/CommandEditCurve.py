# SPDX-License-Identifier: LGPL-2.1-or-later
"""Edit CV Curve — drag CVs, raise degree, split, delete a CV (refit)."""
import numpy as np
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.geom import bezier, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from .common import CommandBase, register
from .cv_edit_base import CVEditPanelBase


def _target_curve():
    from BNCClassA.objects.helpers import is_cv_curve
    for obj in Gui.Selection.getSelection():
        if is_cv_curve(obj):
            return obj
    return None


class EditCurvePanel(CVEditPanelBase):
    TITLE = "Edit CV Curve"

    def build_tools_ui(self):
        group = QtWidgets.QGroupBox("Curve tools")
        lay = QtWidgets.QVBoxLayout(group)

        raise_btn = QtWidgets.QPushButton("Raise degree (+2)")
        raise_btn.setToolTip("3 → 5 → 7; the curve shape does not change")
        raise_btn.clicked.connect(self._raise_degree)
        lay.addWidget(raise_btn)

        split_row = QtWidgets.QHBoxLayout()
        self.split_param = QtWidgets.QDoubleSpinBox()
        self.split_param.setRange(0.01, 0.99)
        self.split_param.setSingleStep(0.05)
        self.split_param.setValue(0.5)
        split_btn = QtWidgets.QPushButton("Split at t")
        split_btn.clicked.connect(self._split)
        split_row.addWidget(self.split_param)
        split_row.addWidget(split_btn)
        lay.addLayout(split_row)

        del_btn = QtWidgets.QPushButton("Delete selected CV (refit)")
        del_btn.clicked.connect(self._delete_cv)
        lay.addWidget(del_btn)

        self.layout.addWidget(group)

    def _net(self):
        return nurbs_io.to_np(self.obj.Poles)

    def _raise_degree(self):
        poles = self._net()
        if len(poles) - 1 >= 7:
            self.set_status("Already degree 7 — Class-A practice stops here.")
            return
        self.doc.openTransaction("Raise curve degree")
        try:
            self.set_poles(nurbs_io.to_vectors(bezier.elevate(poles, 2)))
            self.doc.commitTransaction()
            self.set_status("Degree raised to %d." % (len(poles) + 1))
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)

    def _split(self):
        from BNCClassA.objects.cv_curve import make_cv_curve
        t = self.split_param.value()
        left, right = bezier.split(self._net(), t)
        self.doc.openTransaction("Split CV curve")
        try:
            base = self.obj.Label
            make_cv_curve(self.doc, left, provenance="Split of %s [0,%g]" % (base, t))
            make_cv_curve(self.doc, right, provenance="Split of %s [%g,1]" % (base, t))
            name = self.obj.Name
            self.cleanup()
            self.doc.removeObject(name)
            self.doc.commitTransaction()
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)
            return
        Gui.Control.closeDialog()

    def _delete_cv(self):
        idx = self.controller.active_idx
        poles = self._net()
        if idx is None:
            self.set_status("Pick a CV first.")
            return
        if len(poles) <= 3:
            self.set_status("A curve needs at least 3 CVs.")
            return
        # refit the same curve one degree lower, without the deleted CV's
        # influence: sample the current curve and fit
        ts = np.linspace(0, 1, 100)
        pts = bezier.evaluate(poles, ts)
        deg = len(poles) - 2
        new_poles, dev = bezier.fit_bezier(pts, ts, deg,
                                           pinned={0: pts[0], deg: pts[-1]})
        self.doc.openTransaction("Delete CV")
        try:
            self.set_poles(nurbs_io.to_vectors(new_poles))
            self.doc.commitTransaction()
            self.controller.active_idx = None
            self.set_status("Refit at degree %d (dev %.4g mm)." % (deg, dev))
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)


@register
class CommandEditCurve(CommandBase):
    NAME = "BNCClassA_EditCurve"
    ICON = "ClassAEditCurve"
    MENU = "Edit CV Curve"
    TIP = "Drag the control vertices of a CV curve; raise degree, split, delete CVs"

    def IsActive(self):
        return _target_curve() is not None

    def Activated(self):
        obj = _target_curve()
        if obj is None:
            FreeCAD.Console.PrintWarning("BNCClassA: select a CV Curve first\n")
            return
        from BNCClassA.ui.panels import show_panel
        show_panel(EditCurvePanel(obj))
