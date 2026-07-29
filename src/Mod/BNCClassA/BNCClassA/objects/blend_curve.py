# SPDX-License-Identifier: LGPL-2.1-or-later
"""ClassA::BlendCurve — parametric blend between two edge ends (G0-G3 per
end). One of the two parametric exceptions in the explicit-first object model;
bake it to a CVCurve when the construction should freeze."""
import FreeCAD

from BNCClassA.geom import blends, nurbs_io


def _resolve_edge(link):
    if not link:
        return None
    obj, subs = link
    if not subs:
        return None
    return obj.Shape.getElement(subs[0])


class BlendCurve(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "ClassA::BlendCurve"
        obj.addProperty("App::PropertyLinkSub", "StartEdge", "ClassA",
                        "Edge the blend starts from")
        obj.addProperty("App::PropertyLinkSub", "EndEdge", "ClassA",
                        "Edge the blend ends on")
        obj.addProperty("App::PropertyBool", "StartAtFirst", "ClassA",
                        "Attach at the start edge's first end")
        obj.addProperty("App::PropertyBool", "EndAtFirst", "ClassA",
                        "Attach at the end edge's first end")
        obj.addProperty("App::PropertyIntegerConstraint", "StartContinuity",
                        "ClassA", "Continuity at the start (0-3)")
        obj.addProperty("App::PropertyIntegerConstraint", "EndContinuity",
                        "ClassA", "Continuity at the end (0-3)")
        obj.addProperty("App::PropertyFloat", "StartTension", "ClassA",
                        "Tension at the start")
        obj.addProperty("App::PropertyFloat", "EndTension", "ClassA",
                        "Tension at the end")
        obj.StartContinuity = (2, 0, 3, 1)
        obj.EndContinuity = (2, 0, 3, 1)
        obj.StartTension = 1.0
        obj.EndTension = 1.0
        obj.StartAtFirst = False
        obj.EndAtFirst = True

    def execute(self, obj):
        e1 = _resolve_edge(obj.StartEdge)
        e2 = _resolve_edge(obj.EndEdge)
        if e1 is None or e2 is None:
            return
        poles = blends.blend_curve_poles(
            e1, obj.StartAtFirst, obj.StartContinuity, obj.StartTension,
            e2, obj.EndAtFirst, obj.EndContinuity, obj.EndTension)
        obj.Shape = nurbs_io.make_bezier_curve(poles).toShape()

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        if state:
            self.Type = state.get("Type", "ClassA::BlendCurve")


class ViewProviderBlendCurve(object):
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        from BNCClassA import icon
        return icon("ClassABlendCurve")

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, _state):
        return None


def make_blend_curve(doc, start_link, end_link, start_at_first, end_at_first):
    obj = doc.addObject("Part::FeaturePython", "BlendCurve")
    BlendCurve(obj)
    if obj.ViewObject is not None:
        ViewProviderBlendCurve(obj.ViewObject)
    obj.StartEdge = start_link
    obj.EndEdge = end_link
    obj.StartAtFirst = start_at_first
    obj.EndAtFirst = end_at_first
    obj.recompute()
    return obj
