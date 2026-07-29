# SPDX-License-Identifier: LGPL-2.1-or-later
"""ClassA::BlendSurface — parametric freeform blend between two face edges
with per-side continuity (G0-G3) and tension. Bake to CVSurface to freeze."""
import FreeCAD

from BNCClassA.geom import blends, nurbs_io

_CONTINUITIES = ["G0", "G1", "G2", "G3"]


def _resolve(link):
    """(edge, host_face) from a LinkSub pointing at an edge."""
    if not link:
        return None, None
    obj, subs = link
    if not subs:
        return None, None
    edge = obj.Shape.getElement(subs[0])
    hosts = nurbs_io.host_faces_of_edge(obj.Shape, edge)
    return edge, (hosts[0] if hosts else None)


class BlendSurface(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "ClassA::BlendSurface"
        obj.addProperty("App::PropertyLinkSub", "EdgeA", "ClassA",
                        "First face edge")
        obj.addProperty("App::PropertyLinkSub", "EdgeB", "ClassA",
                        "Second face edge")
        obj.addProperty("App::PropertyEnumeration", "ContinuityA", "ClassA",
                        "Continuity against face A")
        obj.addProperty("App::PropertyEnumeration", "ContinuityB", "ClassA",
                        "Continuity against face B")
        obj.addProperty("App::PropertyFloat", "TensionA", "ClassA",
                        "Fullness toward side A")
        obj.addProperty("App::PropertyFloat", "TensionB", "ClassA",
                        "Fullness toward side B")
        obj.addProperty("App::PropertyInteger", "Samples", "ClassA",
                        "Stations along the edges")
        obj.addProperty("App::PropertyInteger", "DegreeAlong", "ClassA",
                        "Degree along the edges")
        obj.addProperty("App::PropertyFloat", "FitDeviation", "ClassA",
                        "Fit deviation of the last recompute (mm)")
        obj.setEditorMode("FitDeviation", 1)
        obj.ContinuityA = _CONTINUITIES
        obj.ContinuityB = _CONTINUITIES
        obj.ContinuityA = "G2"
        obj.ContinuityB = "G2"
        obj.TensionA = 1.0
        obj.TensionB = 1.0
        obj.Samples = 24
        obj.DegreeAlong = 5

    def execute(self, obj):
        edge_a, face_a = _resolve(obj.EdgeA)
        edge_b, face_b = _resolve(obj.EdgeB)
        if edge_a is None or edge_b is None:
            return
        if face_a is None or face_b is None:
            raise ValueError("%s: blend edges must belong to faces" % obj.Name)
        ka = _CONTINUITIES.index(obj.ContinuityA)
        kb = _CONTINUITIES.index(obj.ContinuityB)
        net, dev = blends.blend_surface_net(
            face_a, edge_a, ka, obj.TensionA,
            face_b, edge_b, kb, obj.TensionB,
            stations=max(8, obj.Samples), degree_v=max(3, obj.DegreeAlong))
        obj.FitDeviation = float(dev)
        obj.Shape = nurbs_io.make_bezier_surface(net).toShape()

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        if state:
            self.Type = state.get("Type", "ClassA::BlendSurface")


class ViewProviderBlendSurface(object):
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        from BNCClassA import icon
        return icon("ClassAFreeformBlend")

    def dumps(self):
        return None

    def loads(self, _state):
        return None


def make_blend_surface(doc, link_a, link_b):
    obj = doc.addObject("Part::FeaturePython", "BlendSurface")
    BlendSurface(obj)
    if obj.ViewObject is not None:
        ViewProviderBlendSurface(obj.ViewObject)
        try:
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
    obj.EdgeA = link_a
    obj.EdgeB = link_b
    obj.recompute()
    return obj
