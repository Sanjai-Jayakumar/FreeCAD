# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mirror — reflect a CV surface across a principal plane, optionally forcing
a G1/G2-clean symmetry seam first (boundary row snapped onto the plane, next
row made perpendicular — the classic Class-A symmetry rule)."""
import numpy as np
import FreeCAD

from BNCClassA.geom import nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel
from .common import CommandBase, register

_PLANES = {
    "XY (z = 0)": np.array([0.0, 0.0, 1.0]),
    "XZ (y = 0)": np.array([0.0, 1.0, 0.0]),
    "YZ (x = 0)": np.array([1.0, 0.0, 0.0]),
}


def _closest_boundary_to_plane(net, normal, offset):
    """Boundary of the net closest to the plane n·p = offset."""
    dists = {
        "u0": net[0], "u1": net[-1], "v0": net[:, 0], "v1": net[:, -1],
    }
    best, best_d = None, None
    for name, row in dists.items():
        d = float(np.abs(row @ normal - offset).mean())
        if best is None or d < best_d:
            best, best_d = name, d
    return best, best_d


class MirrorPanel(CreationPanel):
    TITLE = "Class-A Mirror"
    TRANSACTION = "Class-A Mirror"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.plane = QtWidgets.QComboBox()
        self.plane.addItems(list(_PLANES.keys()))
        self.plane.setCurrentIndex(1)     # XZ — the automotive centerline
        form.addRow("Mirror plane", self.plane)
        self.offset = QtWidgets.QDoubleSpinBox()
        self.offset.setRange(-100000, 100000)
        self.offset.setSuffix(" mm")
        form.addRow("Plane offset", self.offset)
        self.force_seam = QtWidgets.QCheckBox(
            "Force symmetry seam (snap boundary onto plane, make the next CV "
            "row perpendicular — G2 across the seam)")
        self.force_seam.setChecked(True)
        form.addRow(self.force_seam)
        self.layout.addLayout(form)
        self.set_status("Select the CV surface(s) to mirror.")

    def create(self):
        import FreeCADGui as Gui
        from BNCClassA.objects.helpers import is_cv_surface
        from BNCClassA.objects.cv_surface import CVSurface, make_cv_surface
        normal = _PLANES[self.plane.currentText()]
        offset = self.offset.value()
        made = 0
        for obj in Gui.Selection.getSelection():
            if not is_cv_surface(obj):
                continue
            net = CVSurface.pole_array(obj)
            if self.force_seam.isChecked():
                boundary, dist = _closest_boundary_to_plane(net, normal, offset)
                canon = nurbs_io.to_boundary(net, boundary)
                # snap row 0 exactly onto the plane
                canon[0] -= np.outer(canon[0] @ normal - offset, normal)
                # row 1: force (P1 - P0) parallel to the plane normal, keeping
                # the off-plane distance -> surface meets the plane at 90°
                delta = canon[1] - canon[0]
                sign = np.sign(delta @ normal)
                sign[sign == 0] = np.sign((canon[-1] - canon[0]) @ normal).mean() or 1.0
                mag = np.linalg.norm(delta, axis=1)
                canon[1] = canon[0] + np.outer(sign * mag, normal)
                net = nurbs_io.from_boundary(canon, boundary)
                CVSurface.set_pole_array(obj, net)
                obj.recompute()
                self.set_status("Seam fixed on %s (was %.4g mm off-plane)."
                                % (obj.Label, dist))
            # reflect: p' = p - 2 (n·p - offset) n; reverse u to keep orientation
            flat = net.reshape(-1, 3)
            reflected = flat - 2.0 * np.outer(flat @ normal - offset, normal)
            mirror_net = reflected.reshape(net.shape)[::-1]
            make_cv_surface(self.doc, mirror_net,
                            provenance="Mirror of %s" % obj.Label)
            made += 1
        if made == 0:
            self.set_status("Select at least one CV surface.")
            return False
        return True


@register
class CommandMirror(CommandBase):
    NAME = "BNCClassA_Mirror"
    ICON = "ClassAMirror"
    MENU = "Mirror Surface"
    TIP = ("Mirror a CV surface across a principal plane with an optional "
           "G2-clean symmetry seam")
    PANEL = MirrorPanel
