# SPDX-License-Identifier: LGPL-2.1-or-later
"""Class-A Fillet — a curvature-clean fillet as a separate blend patch
(OCCT fillets are G1, rational and multi-span — the opposite of Class-A).

Construction: offset both faces by the radius, intersect the offsets to get
the rolling-ball center spine, project the spine back to each face to get the
contact curves, then run a freeform blend between the contact curves."""
import numpy as np
import FreeCAD
import Part

from BNCClassA.geom import bezier, blends, nurbs_io
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selected_faces
from .common import CommandBase, register


class FilletPanel(CreationPanel):
    TITLE = "Class-A Fillet"
    TRANSACTION = "Class-A Fillet"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.radius = QtWidgets.QDoubleSpinBox()
        self.radius.setRange(0.01, 10000)
        self.radius.setValue(5.0)
        self.radius.setSuffix(" mm")
        form.addRow("Radius", self.radius)
        self.continuity = QtWidgets.QComboBox()
        self.continuity.addItems(["G1 (tangent)", "G2 (curvature)"])
        self.continuity.setCurrentIndex(1)
        form.addRow("Continuity", self.continuity)
        self.samples = QtWidgets.QSpinBox()
        self.samples.setRange(8, 80)
        self.samples.setValue(24)
        form.addRow("Stations", self.samples)
        self.flip_a = QtWidgets.QCheckBox("Flip offset side A")
        form.addRow(self.flip_a)
        self.flip_b = QtWidgets.QCheckBox("Flip offset side B")
        form.addRow(self.flip_b)
        self.layout.addLayout(form)
        picked = selected_faces()
        self.set_status("%d face(s) selected — need exactly 2." % len(picked))

    def _contact_curve(self, face, spine_pts, degree=5):
        """Fit the projection of the spine points onto the face."""
        surf = face.Surface
        proj = []
        for p in spine_pts:
            try:
                u, v = surf.parameter(FreeCAD.Vector(*p))
                q = surf.value(u, v)
                proj.append((q.x, q.y, q.z))
            except Exception:
                pass
        if len(proj) < degree + 1:
            raise ValueError("could not project the fillet spine onto a face")
        proj = np.asarray(proj)
        params = np.linspace(0, 1, len(proj))
        poles, _dev = bezier.fit_bezier(proj, params, degree,
                                        pinned={0: proj[0], degree: proj[-1]})
        return poles

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        picked = selected_faces()
        if len(picked) != 2:
            self.set_status("Select exactly two faces.")
            return False
        (_o1, face_a, label_a), (_o2, face_b, label_b) = picked
        r = self.radius.value()
        ra = -r if self.flip_a.isChecked() else r
        rb = -r if self.flip_b.isChecked() else r
        try:
            off_a = face_a.makeOffsetShape(ra, 1e-4)
            off_b = face_b.makeOffsetShape(rb, 1e-4)
            spine = off_a.section(off_b)
        except Exception as exc:
            self.set_status("Offset/intersection failed: %s" % exc)
            return False
        if not spine.Edges:
            self.set_status("The offset surfaces do not intersect — try "
                            "flipping an offset side or a smaller radius.")
            return False
        spine_edge = max(spine.Edges, key=lambda e: e.Length)
        spine_pts = [(p.x, p.y, p.z)
                     for p in spine_edge.discretize(Number=self.samples.value())]

        contact_a = self._contact_curve(face_a, spine_pts)
        contact_b = self._contact_curve(face_b, spine_pts)
        k = 1 if self.continuity.currentIndex() == 0 else 2
        edge_a = nurbs_io.make_bezier_curve(contact_a).toShape().Edges[0]
        edge_b = nurbs_io.make_bezier_curve(contact_b).toShape().Edges[0]
        net, dev = blends.blend_surface_net(
            face_a, edge_a, k, 1.0, face_b, edge_b, k, 1.0,
            stations=self.samples.value())
        make_cv_surface(self.doc, net,
                        provenance="Fillet r%g between %s and %s (fit dev %.4g mm)"
                                   % (r, label_a, label_b, dev))
        return True


@register
class CommandFillet(CommandBase):
    NAME = "BNCClassA_Fillet"
    ICON = "ClassAFillet"
    MENU = "Class-A Fillet"
    TIP = ("Curvature-clean fillet as a separate blend patch between two "
           "faces (rolling-ball contact curves + freeform blend)")
    PANEL = FilletPanel
