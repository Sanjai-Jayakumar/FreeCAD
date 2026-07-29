# SPDX-License-Identifier: LGPL-2.1-or-later
"""Blend Curve — parametric G0-G3 blend between two edge ends. The attach
ends are chosen from where the edges were picked; continuity and tension are
edited in the property view (or via Bake to freeze)."""
import FreeCAD
import FreeCADGui as Gui

from .common import CommandBase, register


def _picked_edges_with_points():
    """[(obj, subname, edge, picked_point)] for edge picks in selection order."""
    out = []
    for sel in Gui.Selection.getSelectionEx():
        picked = list(sel.PickedPoints)
        for i, (sub, sub_obj) in enumerate(zip(sel.SubElementNames, sel.SubObjects)):
            if getattr(sub_obj, "ShapeType", "") != "Edge":
                continue
            point = picked[i] if i < len(picked) else None
            out.append((sel.Object, sub, sub_obj, point))
    return out


def _near_first_end(edge, point):
    if point is None:
        return False
    d_first = (edge.valueAt(edge.FirstParameter) - point).Length
    d_last = (edge.valueAt(edge.LastParameter) - point).Length
    return d_first < d_last


@register
class CommandBlendCurve(CommandBase):
    NAME = "BNCClassA_BlendCurve"
    ICON = "ClassABlendCurve"
    MENU = "Blend Curve"
    TIP = ("Blend two edge ends with per-end G0-G3 continuity — pick each "
           "edge near the end to attach")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from BNCClassA.objects.blend_curve import make_blend_curve
        picks = _picked_edges_with_points()
        if len(picks) < 2:
            FreeCAD.Console.PrintWarning(
                "BNCClassA: pick two edges (near the ends to blend)\n")
            return
        (o1, s1, e1, p1), (o2, s2, e2, p2) = picks[0], picks[1]
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Blend Curve")
        try:
            obj = make_blend_curve(doc, (o1, (s1,)), (o2, (s2,)),
                                   _near_first_end(e1, p1),
                                   _near_first_end(e2, p2))
            doc.commitTransaction()
            FreeCAD.Console.PrintMessage(
                "BNCClassA: %s created (G2/G2 — edit continuity/tension in "
                "the property view)\n" % obj.Label)
        except Exception as exc:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("BNCClassA: blend failed — %s\n" % exc)
        doc.recompute()
