# SPDX-License-Identifier: LGPL-2.1-or-later
"""ClassA::CVSurface — explicit single-span Bézier patch whose pole net IS the
data. Trims are kept as a property so CV editing survives trimming."""
import numpy as np
import FreeCAD
import Part

from BNCClassA.geom import nurbs_io


class CVSurface(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "ClassA::CVSurface"
        obj.addProperty("App::PropertyVectorList", "Poles", "ClassA",
                        "Control net, flattened row-major (u-major)")
        obj.addProperty("App::PropertyInteger", "NumPolesU", "ClassA",
                        "Pole count in U (degree U = count - 1)")
        obj.addProperty("App::PropertyInteger", "NumPolesV", "ClassA",
                        "Pole count in V (degree V = count - 1)")
        obj.addProperty("App::PropertyLinkSubList", "TrimWires", "ClassA",
                        "Closed curves on the surface bounding the trimmed face")
        obj.addProperty("App::PropertyLinkSub", "MatchTarget", "ClassA",
                        "Edge/face this surface was last matched against")
        obj.addProperty("App::PropertyEnumeration", "MatchContinuity", "ClassA",
                        "Continuity used by the last Match operation")
        obj.addProperty("App::PropertyString", "Provenance", "ClassA",
                        "How this surface was created")
        obj.setEditorMode("Provenance", 1)
        obj.MatchContinuity = ["G0", "G1", "G2"]
        obj.NumPolesU = 0
        obj.NumPolesV = 0

    # -- pole-net access ------------------------------------------------------
    @staticmethod
    def pole_array(obj):
        """(nu, nv, 3) numpy view of the Poles property."""
        nu, nv = obj.NumPolesU, obj.NumPolesV
        if nu * nv != len(obj.Poles) or nu < 2 or nv < 2:
            raise ValueError("%s: inconsistent pole net (%d x %d vs %d poles)"
                             % (obj.Name, nu, nv, len(obj.Poles)))
        arr = np.array([[p.x, p.y, p.z] for p in obj.Poles])
        return arr.reshape(nu, nv, 3)

    @staticmethod
    def set_pole_array(obj, arr):
        arr = np.asarray(arr, dtype=float)
        obj.NumPolesU = int(arr.shape[0])
        obj.NumPolesV = int(arr.shape[1])
        obj.Poles = [FreeCAD.Vector(*[float(c) for c in p])
                     for p in arr.reshape(-1, 3)]

    def execute(self, obj):
        try:
            net = self.pole_array(obj)
        except ValueError:
            return
        surf = nurbs_io.make_bezier_surface(net)
        face = None
        wires = self._trim_wires(obj)
        if wires:
            try:
                face = Part.Face(surf, wires)
                if not face.isValid():
                    face.fix(1e-6, 1e-6, 1e-6)
                if not face.isValid():
                    face = None
            except Exception:
                face = None
            if face is None:
                FreeCAD.Console.PrintWarning(
                    "%s: trim failed — showing untrimmed surface\n" % obj.Name)
        if face is None:
            face = surf.toShape()
        obj.Shape = face

    @staticmethod
    def _trim_wires(obj):
        """Collect all linked trim edges and chain them into closed wires."""
        edges = []
        try:
            for link, subs in (obj.TrimWires or []):
                for sub in subs:
                    el = link.Shape.getElement(sub) if sub else link.Shape
                    edges.extend(el.Edges)
                if not subs:
                    edges.extend(link.Shape.Edges)
        except Exception:
            return []
        if not edges:
            return []
        wires = []
        try:
            for group in Part.sortEdges(edges):
                wires.append(Part.Wire(group))
        except Exception:
            try:
                wires = [Part.Wire(edges)]
            except Exception:
                return []
        return wires

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        if state:
            self.Type = state.get("Type", "ClassA::CVSurface")


class ViewProviderCVSurface(object):
    def __init__(self, vobj):
        vobj.Proxy = self
        vobj.addProperty("App::PropertyBool", "ShowCVs", "ClassA",
                         "Show the control net vertices")
        vobj.addProperty("App::PropertyBool", "ShowHull", "ClassA",
                         "Show the control net grid")
        vobj.ShowCVs = False
        vobj.ShowHull = False

    def attach(self, vobj):
        from .hull_display import HullDisplay
        self.vobj = vobj
        self.hull = HullDisplay()
        vobj.RootNode.addChild(self.hull.switch)
        self.hull.set_visible(True)
        self.onChanged(vobj, "ShowCVs")
        self.onChanged(vobj, "ShowHull")
        self._refresh(vobj.Object)

    def _refresh(self, obj):
        if getattr(self, "hull", None) is None:
            return
        try:
            net = CVSurface.pole_array(obj)
        except Exception:
            return
        from .hull_display import surface_hull_data
        pts, lines = surface_hull_data(net)
        self.hull.update(pts, lines)

    def updateData(self, obj, prop):
        if prop in ("Poles", "NumPolesU", "NumPolesV"):
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
        return icon("ClassACVSurface")

    def doubleClicked(self, vobj):
        try:
            import FreeCADGui as Gui
            Gui.runCommand("BNCClassA_EditSurface", 0)
            return True
        except Exception:
            return False

    def dumps(self):
        return None

    def loads(self, _state):
        return None


def make_cv_surface(doc, pole_net, provenance="CV surface"):
    """Create a CVSurface from an (nu, nv, 3) array-like pole net."""
    obj = doc.addObject("Part::FeaturePython", "CVSurface")
    CVSurface(obj)
    if obj.ViewObject is not None:
        ViewProviderCVSurface(obj.ViewObject)
        obj.ViewObject.DisplayMode = "Shaded" \
            if "Shaded" in obj.ViewObject.listDisplayModes() else obj.ViewObject.DisplayMode
    CVSurface.set_pole_array(obj, np.asarray(pole_net, dtype=float))
    obj.Provenance = provenance
    obj.recompute()
    return obj
