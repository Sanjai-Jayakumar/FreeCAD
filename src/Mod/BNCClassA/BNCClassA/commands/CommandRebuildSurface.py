# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rebuild Surface — refit any face as a single-span Bézier CV surface.
This is the 'make imported geometry Class-A' tool (OCCT fillets, STEP data,
Filling output all arrive as high-degree multi-span surfaces)."""
from BNCClassA.geom import builders
from BNCClassA.ui.qtcompat import QtWidgets
from BNCClassA.ui.panels import CreationPanel, selected_faces
from .common import CommandBase, register


class RebuildSurfacePanel(CreationPanel):
    TITLE = "Rebuild Surface"
    TRANSACTION = "Class-A Rebuild Surface"

    def build_ui(self):
        form = QtWidgets.QFormLayout()
        self.degree_u = QtWidgets.QSpinBox()
        self.degree_u.setRange(3, 7)
        self.degree_u.setValue(5)
        self.degree_u.valueChanged.connect(self._invalidate)
        form.addRow("Degree U", self.degree_u)
        self.degree_v = QtWidgets.QSpinBox()
        self.degree_v.setRange(3, 7)
        self.degree_v.setValue(5)
        self.degree_v.valueChanged.connect(self._invalidate)
        form.addRow("Degree V", self.degree_v)
        self.dev_label = QtWidgets.QLabel("—")
        form.addRow("Max deviation", self.dev_label)
        check = QtWidgets.QPushButton("Check deviation")
        check.clicked.connect(self._check)
        form.addRow(check)
        self.layout.addLayout(form)
        note = QtWidgets.QLabel("Note: trims are ignored — the rebuild covers "
                                "the untrimmed surface.")
        note.setWordWrap(True)
        self.layout.addWidget(note)
        picked = selected_faces()
        self.set_status("%d face(s) selected." % len(picked)
                        if picked else "Select one or more faces.")

    def _invalidate(self, *_args):
        self.dev_label.setText("—")

    def _fit(self, face):
        grid = builders.sample_face_grid(face, 50, 50)
        return builders.fit_surface_net(grid, self.degree_u.value(),
                                        self.degree_v.value())

    def _check(self):
        picked = selected_faces()
        if not picked:
            self.set_status("Select one or more faces.")
            return
        devs = []
        for (_o, face, _l) in picked:
            _net, dev = self._fit(face)
            devs.append(dev)
        self.dev_label.setText(", ".join("%.4g mm" % d for d in devs))

    def create(self):
        from BNCClassA.objects.cv_surface import make_cv_surface
        picked = selected_faces()
        if not picked:
            return False
        for (_o, face, label) in picked:
            net, dev = self._fit(face)
            make_cv_surface(self.doc, net,
                            provenance="Rebuilt from %s (dev %.4g mm)" % (label, dev))
        return True


@register
class CommandRebuildSurface(CommandBase):
    NAME = "BNCClassA_RebuildSurface"
    ICON = "ClassARebuildSurface"
    MENU = "Rebuild Surface"
    TIP = "Refit a face as a single-span Bézier CV surface (deviation shown)"
    PANEL = RebuildSurfacePanel
