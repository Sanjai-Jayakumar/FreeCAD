# SPDX-License-Identifier: LGPL-2.1-or-later
"""ClassA::CVCurve — explicit single-span Bézier curve whose poles ARE the data."""
import FreeCAD

from BNCClassA.geom import nurbs_io


class CVCurve(object):
    """Document-object proxy. The Poles property is authoritative; execute()
    only rebuilds the OCCT shape from it."""

    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "ClassA::CVCurve"
        obj.addProperty("App::PropertyVectorList", "Poles", "ClassA",
                        "Control vertices (single span: count = Degree + 1)")
        obj.addProperty("App::PropertyInteger", "Degree", "ClassA",
                        "Curve degree (Class-A practice: 3, 5 or 7)")
        obj.addProperty("App::PropertyString", "Provenance", "ClassA",
                        "How this curve was created")
        obj.setEditorMode("Provenance", 1)   # read-only
        obj.Degree = 3

    def execute(self, obj):
        poles = obj.Poles
        if len(poles) < 2:
            return
        # single-span discipline: degree follows the pole count
        degree = len(poles) - 1
        if obj.Degree != degree:
            obj.Degree = degree
        bs = nurbs_io.make_bezier_curve(nurbs_io.to_np(poles))
        obj.Shape = bs.toShape()

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        if state:
            self.Type = state.get("Type", "ClassA::CVCurve")


class ViewProviderCVCurve(object):
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addProperty("App::PropertyBool", "ShowCVs", "ClassA",
                         "Show the control vertices")
        vobj.addProperty("App::PropertyBool", "ShowHull", "ClassA",
                         "Show the control polygon")
        vobj.ShowCVs = True
        vobj.ShowHull = True

    def attach(self, vobj):
        from .hull_display import HullDisplay
        self.vobj = vobj
        self.hull = HullDisplay()
        vobj.RootNode.addChild(self.hull.switch)
        self.hull.set_visible(True)
        self._refresh(vobj.Object)

    def _refresh(self, obj):
        from .hull_display import curve_hull_data
        if getattr(self, "hull", None) is None:
            return
        pts, lines = curve_hull_data(obj.Poles)
        self.hull.update(pts, lines)

    def updateData(self, obj, prop):
        if prop == "Poles":
            self._refresh(obj)

    def onChanged(self, vobj, prop):
        if getattr(self, "hull", None) is None:
            return
        if prop == "ShowCVs":
            self.hull.show_cvs(vobj.ShowCVs)
        elif prop == "ShowHull":
            self.hull.show_hull(vobj.ShowHull)
        elif prop == "Visibility":
            self.hull.set_visible(vobj.Visibility)

    def getIcon(self):
        from BNCClassA import icon
        return icon("ClassACVCurve")

    def setupContextMenu(self, vobj, menu):
        return False

    def doubleClicked(self, vobj):
        try:
            import FreeCADGui as Gui
            Gui.runCommand("BNCClassA_EditCurve", 0)
            return True
        except Exception:
            return False

    def dumps(self):
        return None

    def loads(self, _state):
        return None


def make_cv_curve(doc, poles, provenance="CV curve"):
    """Create a CVCurve document object from FreeCAD.Vector (or ndarray) poles."""
    obj = doc.addObject("Part::FeaturePython", "CVCurve")
    CVCurve(obj)
    if obj.ViewObject is not None:
        ViewProviderCVCurve(obj.ViewObject)
    vecs = []
    for p in (poles.tolist() if hasattr(poles, "tolist") else poles):
        vecs.append(p if hasattr(p, "x") else FreeCAD.Vector(*[float(c) for c in p]))
    obj.Poles = vecs
    obj.Provenance = provenance
    obj.recompute()
    return obj
