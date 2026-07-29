# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared CV-editing task panel: drag controller lifecycle, throttled pole
writes inside one undo transaction per drag, XYZ spin boxes, axis-constraint
status. Subclasses supply pole access and extra tool buttons."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.ui.qtcompat import QtWidgets, QtCore, BTN_CLOSE
from BNCClassA.ui.viewer import DragController

_WRITE_THROTTLE_MS = 60


class CVEditPanelBase(object):
    TITLE = "Edit CVs"

    def __init__(self, obj):
        self.obj = obj
        self.doc = obj.Document
        self._pending = None            # poles awaiting the throttled write
        self._in_transaction = False

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.TITLE)
        self.layout = QtWidgets.QVBoxLayout(self.form)

        info = QtWidgets.QLabel(
            "Drag CVs in the 3D view. Shift = whole row, X/Y/Z = axis lock "
            "(press again to release), arrows/PgUp/PgDn = nudge.")
        info.setWordWrap(True)
        self.layout.addWidget(info)

        sel_group = QtWidgets.QGroupBox("Selected CV")
        form = QtWidgets.QFormLayout(sel_group)
        self.idx_label = QtWidgets.QLabel("—")
        form.addRow("Index", self.idx_label)
        self.spins = []
        for c in "XYZ":
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(-1e6, 1e6)
            sp.setDecimals(4)
            sp.editingFinished.connect(self._apply_spins)
            self.spins.append(sp)
            form.addRow(c, sp)
        self.step = QtWidgets.QDoubleSpinBox()
        self.step.setRange(0.001, 100)
        self.step.setValue(0.5)
        self.step.setSuffix(" mm")
        form.addRow("Nudge step", self.step)
        self.layout.addWidget(sel_group)

        self.build_tools_ui()

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.layout.addStretch(1)

        self._show_hull_state = self._enable_hull_display(True)

        self._write_timer = QtCore.QTimer()
        self._write_timer.setSingleShot(True)
        self._write_timer.setInterval(_WRITE_THROTTLE_MS)
        self._write_timer.timeout.connect(self._flush_pending)

        self.controller = DragController(
            get_points=self.get_poles,
            on_pick=self._on_pick,
            on_drag=self._on_drag,
            on_release=self._on_release,
            row_of=self.row_of)
        self.controller.nudge_step = self.step.value()
        self.step.valueChanged.connect(
            lambda v: setattr(self.controller, "nudge_step", v))
        self.controller.install()

    # -- subclass API ----------------------------------------------------------
    def get_poles(self):
        """Current pole positions as a flat list of FreeCAD.Vector."""
        return list(self.obj.Poles)

    def set_poles(self, poles):
        self.obj.Poles = poles
        self.obj.recompute()

    def row_of(self, idx):
        return [idx]

    def build_tools_ui(self):
        pass

    def describe_index(self, idx):
        return str(idx)

    # -- hull display -----------------------------------------------------------
    def _enable_hull_display(self, on):
        prev = (None, None)
        try:
            vo = self.obj.ViewObject
            prev = (vo.ShowCVs, vo.ShowHull)
            vo.ShowCVs = True
            vo.ShowHull = True
        except Exception:
            pass
        return prev

    def _restore_hull_display(self):
        try:
            vo = self.obj.ViewObject
            if self._show_hull_state[0] is not None:
                vo.ShowCVs, vo.ShowHull = self._show_hull_state
        except Exception:
            pass

    def _highlight(self, indices):
        try:
            hull = self.obj.ViewObject.Proxy.hull
            pts = self.get_poles()
            hull.highlight([(pts[i].x, pts[i].y, pts[i].z) for i in indices])
        except Exception:
            pass

    # -- drag plumbing -----------------------------------------------------------
    def _on_pick(self, idx):
        self.idx_label.setText(self.describe_index(idx))
        p = self.get_poles()[idx]
        for sp, val in zip(self.spins, (p.x, p.y, p.z)):
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)
        self._highlight([idx])
        if not self._in_transaction:
            self.doc.openTransaction("Move CV")
            self._in_transaction = True

    def _on_drag(self, indices, positions):
        poles = self.get_poles()
        for i, p in zip(indices, positions):
            poles[i] = p
        self._pending = poles
        if not self._write_timer.isActive():
            self._write_timer.start()
        if self.controller.active_idx is not None \
                and self.controller.active_idx in indices:
            p = positions[indices.index(self.controller.active_idx)]
            for sp, val in zip(self.spins, (p.x, p.y, p.z)):
                sp.blockSignals(True)
                sp.setValue(val)
                sp.blockSignals(False)
        self.set_status("Dragging %d CV(s) [%s]"
                        % (len(indices), self.controller.axis_label))

    def _flush_pending(self):
        if self._pending is None:
            return
        poles, self._pending = self._pending, None
        try:
            self.set_poles(poles)
        except Exception as exc:
            self.set_status("Error: %s" % exc)

    def _on_release(self):
        self._write_timer.stop()
        self._flush_pending()
        if self._in_transaction:
            self.doc.commitTransaction()
            self._in_transaction = False
        self.set_status("")

    def _apply_spins(self):
        idx = self.controller.active_idx
        if idx is None:
            return
        poles = self.get_poles()
        poles[idx] = FreeCAD.Vector(*[sp.value() for sp in self.spins])
        self.doc.openTransaction("Move CV")
        try:
            self.set_poles(poles)
            self.doc.commitTransaction()
        except Exception as exc:
            self.doc.abortTransaction()
            self.set_status("Error: %s" % exc)
        self._highlight([idx])

    def set_status(self, text):
        self.status.setText(text)

    # -- task dialog protocol ------------------------------------------------------
    def getStandardButtons(self):
        return int(BTN_CLOSE)

    def reject(self):
        self.cleanup()
        Gui.Control.closeDialog()
        return True

    def accept(self):
        return self.reject()

    def cleanup(self):
        self._write_timer.stop()
        self._flush_pending()
        if self._in_transaction:
            self.doc.commitTransaction()
            self._in_transaction = False
        try:
            self.controller.uninstall()
        except Exception:
            pass
        self._highlight([])
        self._restore_hull_display()
