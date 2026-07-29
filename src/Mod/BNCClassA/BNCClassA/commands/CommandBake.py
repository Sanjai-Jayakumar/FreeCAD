# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bake — convert parametric blend/patch objects (or any single-span Bézier
face) into editable CVSurface objects."""
import FreeCAD
import FreeCADGui as Gui

from .common import CommandBase, register


@register
class CommandBake(CommandBase):
    NAME = "BNCClassA_Bake"
    ICON = "ClassABake"
    MENU = "Convert to CV Surface"
    TIP = ("Replace the selected parametric surface(s) by editable CV "
           "surfaces (poles become the data)")

    def IsActive(self):
        return bool(Gui.Selection.getSelection())

    def Activated(self):
        from BNCClassA.objects.helpers import bake_to_cv_surface
        doc = FreeCAD.ActiveDocument
        sel = Gui.Selection.getSelection()
        doc.openTransaction("Bake to CV Surface")
        try:
            for obj in sel:
                try:
                    new = bake_to_cv_surface(obj)
                    FreeCAD.Console.PrintMessage(
                        "BNCClassA: baked %s\n" % new.Label)
                except ValueError as exc:
                    FreeCAD.Console.PrintWarning("BNCClassA: %s\n" % exc)
            doc.commitTransaction()
        except Exception:
            doc.abortTransaction()
            raise
        doc.recompute()
