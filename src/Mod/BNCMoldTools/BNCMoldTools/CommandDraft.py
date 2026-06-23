# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_PULL_DIRS = {
    "+Z (Pull Up)":   FreeCAD.Vector(0, 0,  1),
    "-Z (Pull Down)": FreeCAD.Vector(0, 0, -1),
    "+Y":             FreeCAD.Vector(0,  1,  0),
    "-Y":             FreeCAD.Vector(0, -1,  0),
    "+X":             FreeCAD.Vector( 1, 0,  0),
    "-X":             FreeCAD.Vector(-1, 0,  0),
}


class _DraftDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Draft Angle")
        self.resize(360, 230)
        layout = QtWidgets.QFormLayout(self)

        self.angleSpin = QtWidgets.QDoubleSpinBox()
        self.angleSpin.setRange(0.1, 89.9)
        self.angleSpin.setDecimals(1)
        self.angleSpin.setValue(3.0)
        self.angleSpin.setSuffix("  °")
        layout.addRow("Draft Angle:", self.angleSpin)

        self.dirCombo = QtWidgets.QComboBox()
        self.dirCombo.addItems(list(_PULL_DIRS.keys()))
        layout.addRow("Pull Direction:", self.dirCombo)

        self.methodCombo = QtWidgets.QComboBox()
        self.methodCombo.addItems(["Neutral Plane", "Parting Line"])
        layout.addRow("Draft Method:", self.methodCombo)

        info = QtWidgets.QLabel(
            "Select the faces to draft in the 3D view\n"
            "before clicking OK.\n\n"
            "For PartDesign bodies, switch to PartDesign\n"
            "workbench and use Part Design > Draft."
        )
        info.setWordWrap(True)
        layout.addRow(info)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def getValues(self):
        return {
            "angle":     self.angleSpin.value(),
            "direction": _PULL_DIRS[self.dirCombo.currentText()],
            "method":    self.methodCombo.currentText(),
        }


class CommandDraft:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldDraft.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_Draft", "Draft"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_Draft",
                        "Apply taper/draft angle to selected faces for mold ejection."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()

        dlg = _DraftDialog(Gui.getMainWindow())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        vals = dlg.getValues()

        if not sel or not hasattr(sel[0].Object, "Shape"):
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Draft",
                "Select a solid body and face(s) first.\n\n"
                "Tip: Select the solid in the model tree, then\n"
                "Ctrl+click the faces to draft in the 3D view,\n"
                "then run Draft again."
            )
            return

        src_obj = sel[0].Object
        selected_faces = [s for s in sel[0].SubObjects if s.ShapeType == "Face"]

        if not selected_faces:
            selected_faces = src_obj.Shape.Faces[:1]

        try:
            import Part
            import math

            shape = src_obj.Shape
            pull = vals["direction"]
            angle_rad = math.radians(vals["angle"])
            neutral_face = shape.Faces[0]

            drafted = Part.makeDraft(shape, selected_faces, pull, angle_rad, neutral_face, False, 0.01)

            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Mold Draft")
            feat = doc.addObject("Part::Feature", "MoldDraft")
            feat.Label = src_obj.Label + "_Draft"
            feat.Shape = drafted
            src_obj.ViewObject.Visibility = False
            doc.commitTransaction()
            doc.recompute()

        except Exception as e:
            try:
                FreeCAD.ActiveDocument.abortTransaction()
            except Exception:
                pass
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Draft",
                "Draft operation failed:\n" + str(e) + "\n\n"
                "Note: For best results, select specific faces to draft\n"
                "before running this command."
            )


Gui.addCommand("BNCMold_Draft", CommandDraft())
