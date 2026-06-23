# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")


class CommandSplitLine:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldSplitLine.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_SplitLine", "Split Line"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_SplitLine",
                        "Project a sketch or surface onto a solid to create additional faces.\n"
                        "Select: 1) the solid body  2) the sketch or cutting surface."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        sel = Gui.Selection.getSelectionEx()

        if len(sel) < 2:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Split Line",
                "Select two objects:\n"
                "  1. The solid body to split\n"
                "  2. The sketch or surface to project\n\n"
                "Then run Split Line again."
            )
            return

        solid_obj = sel[0].Object
        tool_obj  = sel[1].Object

        if not hasattr(solid_obj, "Shape") or not hasattr(tool_obj, "Shape"):
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Split Line",
                "Both selections must have a Shape.")
            return

        try:
            import BOPTools.SplitAPI as SplitAPI
            result = SplitAPI.slice(solid_obj.Shape, [tool_obj.Shape], "Standard", 0.01)

            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Split Line")
            feat = doc.addObject("Part::Feature", "SplitLine")
            feat.Label = solid_obj.Label + "_SplitLine"
            feat.Shape = result
            solid_obj.ViewObject.Visibility = False
            doc.commitTransaction()
            doc.recompute()

        except Exception as e:
            try:
                FreeCAD.ActiveDocument.abortTransaction()
            except Exception:
                pass
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Split Line", "Split Line failed:\n" + str(e))


Gui.addCommand("BNCMold_SplitLine", CommandSplitLine())
