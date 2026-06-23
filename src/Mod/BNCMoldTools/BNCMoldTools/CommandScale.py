# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_MATERIALS = {
    "ABS":           1.005,
    "Nylon (PA)":    1.015,
    "PP":            1.020,
    "PE":            1.020,
    "POM (Acetal)":  1.020,
    "PC":            1.006,
    "PVC":           1.010,
    "Custom":        1.000,
}


# ── Background worker ─────────────────────────────────────────────────────────

class _ScaleWorker(QtCore.QThread):
    """Runs transformGeometry off the main thread to avoid UI freeze."""

    finished      = QtCore.Signal(object)   # scaled shape
    error_occurred = QtCore.Signal(str)

    def __init__(self, shape, matrix):
        super().__init__()
        self._shape  = shape
        self._matrix = matrix

    def run(self):
        try:
            result = self._shape.transformGeometry(self._matrix)
            self.finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ── Dialog ────────────────────────────────────────────────────────────────────

class _ScaleDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale for Mold Shrinkage")
        self.resize(360, 230)
        layout = QtWidgets.QFormLayout(self)

        self.centerCombo = QtWidgets.QComboBox()
        self.centerCombo.addItems(["Centroid", "Origin"])
        layout.addRow("Scale Center:", self.centerCombo)

        self.materialCombo = QtWidgets.QComboBox()
        self.materialCombo.addItems(list(_MATERIALS.keys()))
        self.materialCombo.currentIndexChanged.connect(self._onMaterial)
        layout.addRow("Material Preset:", self.materialCombo)

        self.factorSpin = QtWidgets.QDoubleSpinBox()
        self.factorSpin.setRange(0.01, 100.0)
        self.factorSpin.setDecimals(4)
        self.factorSpin.setSingleStep(0.001)
        self.factorSpin.setValue(1.005)
        layout.addRow("Scale Factor:", self.factorSpin)

        note = QtWidgets.QLabel(
            "Factor > 1 enlarges the part to compensate for shrinkage.\n"
            "Complex parts may take a few seconds — a progress bar will appear.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 10px; color: #555;")
        layout.addRow(note)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        self._onMaterial(0)

    def _onMaterial(self, _idx):
        self.factorSpin.setValue(
            _MATERIALS.get(self.materialCombo.currentText(), 1.0))

    def getValues(self):
        return {
            "center": self.centerCombo.currentText(),
            "factor": self.factorSpin.value(),
        }


# ── Progress dialog shown while the worker runs ───────────────────────────────

class _ProgressDlg(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scaling…")
        self.setWindowFlags(
            QtCore.Qt.Dialog |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint)
        self.setFixedSize(320, 90)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Scaling geometry — please wait…"))
        self._bar = QtWidgets.QProgressBar()
        self._bar.setRange(0, 0)   # indeterminate / marquee
        layout.addWidget(self._bar)

    def closeEvent(self, ev):
        ev.ignore()   # cannot close manually


# ── Command ───────────────────────────────────────────────────────────────────

class CommandScale:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldScale.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_Scale", "Scale"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_Scale",
                        "Scale part to compensate for material shrinkage."),
        }

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        return bool(sel and hasattr(sel[0].Object, "Shape"))

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()
        if not sel or not hasattr(sel[0].Object, "Shape"):
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Scale", "Select a solid body first.")
            return

        src_obj = sel[0].Object
        dlg = _ScaleDialog(Gui.getMainWindow())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        vals = dlg.getValues()
        f    = vals["factor"]
        use_centroid = (vals["center"] == "Centroid")

        shape = src_obj.Shape
        bb    = shape.BoundBox
        cx, cy, cz = (bb.Center.x, bb.Center.y, bb.Center.z) \
                      if use_centroid else (0.0, 0.0, 0.0)

        # Scale matrix: translate to origin → scale → translate back
        m = FreeCAD.Matrix(
            f, 0, 0, cx * (1 - f),
            0, f, 0, cy * (1 - f),
            0, 0, f, cz * (1 - f),
            0, 0, 0, 1,
        )

        # Show progress dialog and run the heavy transform in a worker thread
        prog = _ProgressDlg(Gui.getMainWindow())
        worker = _ScaleWorker(shape, m)

        def _on_done(scaled_shape):
            prog.accept()
            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Mold Scale")
            try:
                feat = doc.addObject("Part::Feature", "MoldScale")
                feat.Label = src_obj.Label + " (MoldScale)"
                feat.Shape = scaled_shape
                src_obj.ViewObject.Visibility = False
                doc.commitTransaction()
                doc.recompute()
                Gui.Selection.clearSelection()
            except Exception as e:
                try: doc.abortTransaction()
                except Exception: pass
                QtWidgets.QMessageBox.warning(
                    Gui.getMainWindow(), "Scale",
                    f"Failed to add scaled feature:\n{e}")

        def _on_error(msg):
            prog.accept()
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Scale",
                f"Scale computation failed:\n{msg}")

        worker.finished.connect(_on_done)
        worker.error_occurred.connect(_on_error)
        worker.start()

        prog.exec_()   # blocks UI (but worker runs on another thread)


Gui.addCommand("BNCMold_Scale", CommandScale())
