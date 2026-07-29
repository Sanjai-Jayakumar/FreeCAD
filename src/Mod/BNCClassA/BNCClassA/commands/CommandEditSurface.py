# SPDX-License-Identifier: LGPL-2.1-or-later
"""Edit CV Surface — drag CVs (Shift = whole row/column), insert isoparm
(detach into two single-span patches), raise degree per direction."""
import numpy as np
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.geom import bezier
from BNCClassA.ui.qtcompat import QtWidgets
from .common import CommandBase, register
from .cv_edit_base import CVEditPanelBase


def _target_surface():
    from BNCClassA.objects.helpers import is_cv_surface
    for obj in Gui.Selection.getSelection():
        if is_cv_surface(obj):
            return obj
    return None


class EditSurfacePanel(CVEditPanelBase):
    TITLE = "Edit CV Surface"

    def build_tools_ui(self):
        row_group = QtWidgets.QGroupBox("Row dragging (Shift)")
        rlay = QtWidgets.QFormLayout(row_group)
        self.row_mode = QtWidgets.QComboBox()
        self.row_mode.addItems(["U row (across)", "V column (along)"])
        rlay.addRow("Shift drags", self.row_mode)
        self.layout.addWidget(row_group)

        tools = QtWidgets.QGroupBox("Surface tools")
        lay = QtWidgets.QVBoxLayout(tools)

        raise_row = QtWidgets.QHBoxLayout()
        for label, fn in (("Raise degree U", self._raise_u),
                          ("Raise degree V", self._raise_v)):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(fn)
            raise_row.addWidget(b)
        lay.addLayout(raise_row)

        iso_row = QtWidgets.QHBoxLayout()
        self.iso_dir = QtWidgets.QComboBox()
        self.iso_dir.addItems(["U", "V"])
        self.iso_param = QtWidgets.QDoubleSpinBox()
        self.iso_param.setRange(0.01, 0.99)
        self.iso_param.setSingleStep(0.05)
        self.iso_param.setValue(0.5)
        iso_btn = QtWidgets.QPushButton("Detach at isoparm")
        iso_btn.setToolTip("Split into two single-span patches (Class-A "
                           "discipline instead of inserting knots)")
        iso_btn.clicked.connect(self._detach)
        iso_row.addWidget(self.iso_dir)
        iso_row.addWidget(self.iso_param)
        iso_row.addWidget(iso_btn)
        lay.addLayout(iso_row)

        self.layout.addWidget(tools)

    # -- pole access (flattened row-major over (nu, nv)) ------------------------
    def _shape(self):
        return self.obj.NumPolesU, self.obj.NumPolesV

    def _net(self):
        from BNCClassA.objects.cv_surface import CVSurface
        return CVSurface.pole_array(self.obj)

    def _set_net(self, net):
        from BNCClassA.objects.cv_surface import CVSurface
        CVSurface.set_pole_array(self.obj, net)
        self.obj.recompute()

    def row_of(self, idx):
        nu, nv = self._shape()
        i, j = idx // nv, idx % nv
        if self.row_mode.currentIndex() == 0:
            return [i * nv + jj for jj in range(nv)]
        return [ii * nv + j for ii in range(nu)]

    def describe_index(self, idx):
        _nu, nv = self._shape()
        return "u%d / v%d" % (idx // nv, idx % nv)

    # -- tools ------------------------------------------------------------------
    def _raise_u(self):
        self._raise(bezier.elevate_u, "U")

    def _raise_v(self):
        self._raise(bezier.elevate_v, "V")

    def _raise(self, fn, label):
        net = self._net()
        deg = (net.shape[0] if label == "U" else net.shape[1]) - 1
        if deg >= 7:
            self.set_status("Already degree 7 in %s." % label)
            return
        self.doc.openTransaction("Raise surface degree")
        try:
            self._set_net(fn(net, 1))
            self.doc.commitTransaction()
            self.set_status("Degree %s raised to %d." % (label, deg + 1))
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)

    def _detach(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        net = self._net()
        t = self.iso_param.value()
        along_u = self.iso_dir.currentText() == "U"
        work = net if along_u else np.transpose(net, (1, 0, 2))
        nu, nv = work.shape[0], work.shape[1]
        left = np.empty((nu, nv, 3))
        right = np.empty((nu, nv, 3))
        for j in range(nv):
            l, r = bezier.split(work[:, j], t)
            left[:, j] = l
            right[:, j] = r
        if not along_u:
            left = np.transpose(left, (1, 0, 2))
            right = np.transpose(right, (1, 0, 2))
        self.doc.openTransaction("Detach CV surface")
        try:
            base = self.obj.Label
            make_cv_surface(self.doc, left,
                            provenance="Detach of %s (%s<%g)" % (base, self.iso_dir.currentText(), t))
            make_cv_surface(self.doc, right,
                            provenance="Detach of %s (%s>%g)" % (base, self.iso_dir.currentText(), t))
            name = self.obj.Name
            self.cleanup()
            self.doc.removeObject(name)
            self.doc.commitTransaction()
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)
            return
        Gui.Control.closeDialog()


@register
class CommandEditSurface(CommandBase):
    NAME = "BNCClassA_EditSurface"
    ICON = "ClassAEditSurface"
    MENU = "Edit CV Surface"
    TIP = ("Drag the control net of a CV surface (Shift drags a whole "
           "row/column); raise degree, detach at isoparm")

    def IsActive(self):
        return _target_surface() is not None

    def Activated(self):
        obj = _target_surface()
        if obj is None:
            FreeCAD.Console.PrintWarning("BNCClassA: select a CV Surface first\n")
            return
        from BNCClassA.ui.panels import show_panel
        show_panel(EditSurfacePanel(obj))
