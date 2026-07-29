# SPDX-License-Identifier: LGPL-2.1-or-later
"""Square Patch — boundary patch from 4 edges with per-edge continuity
against the faces the edges belong to (the flagship Class-A tool)."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA.geom import nurbs_io
from .common import CommandBase, register


def _picked_edge_links():
    out = []
    for sel in Gui.Selection.getSelectionEx():
        for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
            if getattr(sub_obj, "ShapeType", "") == "Edge":
                out.append((sel.Object, sub, sub_obj))
    return out


@register
class CommandSquarePatch(CommandBase):
    NAME = "BNCClassA_SquarePatch"
    ICON = "ClassASquarePatch"
    MENU = "Square Patch"
    TIP = ("Boundary patch from 4 edges with per-edge G0/G1/G2 continuity "
           "to the neighboring surfaces")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from BNCClassA.objects.boundary_patch import make_boundary_patch
        picks = _picked_edge_links()
        if len(picks) != 4:
            FreeCAD.Console.PrintWarning(
                "BNCClassA: pick exactly 4 boundary edges (%d picked)\n"
                % len(picks))
            return
        doc = FreeCAD.ActiveDocument
        links = [(obj, (sub,)) for (obj, sub, _e) in picks]
        doc.openTransaction("Square Patch")
        try:
            obj = make_boundary_patch(doc, links)
            # default: G1 wherever the picked edge belongs to a face
            from BNCClassA.objects.boundary_patch import _EDGE_KEYS
            for i, (sobj, _sub, edge) in enumerate(picks):
                hosts = nurbs_io.host_faces_of_edge(sobj.Shape, edge)
                setattr(obj, "Continuity" + _EDGE_KEYS[i],
                        "G1" if hosts else "G0")
            obj.recompute()
            doc.commitTransaction()
            FreeCAD.Console.PrintMessage(
                "BNCClassA: %s created — set per-edge continuity (G0/G1/G2) "
                "in the property view\n" % obj.Label)
        except Exception as exc:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("BNCClassA: square patch failed — %s\n" % exc)
        doc.recompute()
