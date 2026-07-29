# SPDX-License-Identifier: LGPL-2.1-or-later
"""Freeform Blend — parametric blend surface between two face edges with
per-side G0-G3 continuity and tension (edited in the property view)."""
import FreeCAD
import FreeCADGui as Gui

from .common import CommandBase, register


def _picked_edge_links():
    out = []
    for sel in Gui.Selection.getSelectionEx():
        for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
            if getattr(sub_obj, "ShapeType", "") == "Edge":
                out.append((sel.Object, sub))
    return out


@register
class CommandFreeformBlend(CommandBase):
    NAME = "BNCClassA_FreeformBlend"
    ICON = "ClassAFreeformBlend"
    MENU = "Freeform Blend"
    TIP = ("Blend surface between two face edges with per-side G0-G3 "
           "continuity and tension")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from BNCClassA.objects.blend_surface import make_blend_surface
        links = _picked_edge_links()
        if len(links) < 2:
            FreeCAD.Console.PrintWarning(
                "BNCClassA: pick one edge on each surface to blend between\n")
            return
        (o1, s1), (o2, s2) = links[0], links[1]
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Freeform Blend")
        try:
            obj = make_blend_surface(doc, (o1, (s1,)), (o2, (s2,)))
            doc.commitTransaction()
            FreeCAD.Console.PrintMessage(
                "BNCClassA: %s created (G2/G2, fit dev %.4g mm — edit "
                "continuity/tension in the property view)\n"
                % (obj.Label, obj.FitDeviation))
        except Exception as exc:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("BNCClassA: blend failed — %s\n" % exc)
        doc.recompute()
