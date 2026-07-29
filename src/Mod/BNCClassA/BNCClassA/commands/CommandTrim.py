# SPDX-License-Identifier: LGPL-2.1-or-later
"""Trim / Untrim — trims are stored as a property of the CV surface, so the
pole net stays intact and CV editing keeps working on trimmed surfaces."""
import FreeCAD
import FreeCADGui as Gui

from .common import CommandBase, register


def _selected_cv_surface_and_curves():
    from BNCClassA.objects.helpers import is_cv_surface
    surface, curves = None, []
    for obj in Gui.Selection.getSelection():
        if is_cv_surface(obj) and surface is None:
            surface = obj
        elif hasattr(obj, "Shape") and obj.Shape.Edges and not obj.Shape.Solids:
            curves.append(obj)
    return surface, curves


@register
class CommandTrim(CommandBase):
    NAME = "BNCClassA_Trim"
    ICON = "ClassATrim"
    MENU = "Trim Surface"
    TIP = ("Trim a CV surface with closed curves lying on it (the pole net "
           "is kept — CV editing still works)")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        surface, curves = _selected_cv_surface_and_curves()
        if surface is None or not curves:
            FreeCAD.Console.PrintWarning(
                "BNCClassA: select a CV surface and the closed boundary "
                "curve(s) on it\n")
            return
        doc = surface.Document
        doc.openTransaction("Trim CV Surface")
        try:
            surface.TrimWires = [(c, ("",)) for c in curves]
            surface.recompute()
            doc.commitTransaction()
            for c in curves:
                try:
                    c.ViewObject.Visibility = False
                except Exception:
                    pass
        except Exception as exc:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("BNCClassA: trim failed — %s\n" % exc)
        doc.recompute()


@register
class CommandUntrim(CommandBase):
    NAME = "BNCClassA_Untrim"
    ICON = "ClassAUntrim"
    MENU = "Untrim Surface"
    TIP = "Remove all trims from a CV surface (restores the full patch)"

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from BNCClassA.objects.helpers import is_cv_surface
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Untrim CV Surface")
        try:
            n = 0
            for obj in Gui.Selection.getSelection():
                if is_cv_surface(obj) and obj.TrimWires:
                    obj.TrimWires = []
                    obj.recompute()
                    n += 1
            doc.commitTransaction()
            if n == 0:
                FreeCAD.Console.PrintWarning(
                    "BNCClassA: select a trimmed CV surface\n")
        except Exception as exc:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("BNCClassA: untrim failed — %s\n" % exc)
        doc.recompute()
