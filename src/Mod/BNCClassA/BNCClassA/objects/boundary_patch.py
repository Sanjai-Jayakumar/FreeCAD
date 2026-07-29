# SPDX-License-Identifier: LGPL-2.1-or-later
"""ClassA::BoundaryPatch — the flagship Class-A 'square' tool: a patch from
4 boundary edges with per-edge continuity (G0/G1/G2) against the faces the
edges belong to.

Pipeline: order the edges into a loop -> rebuild each as degree-5 Bézier ->
discrete Coons patch (exact G0) -> per edge with continuity > G0, run the
match solver against its host face -> damped Gauss-Seidel sweeps reconcile
the conflicting corner assignments between adjacent edges.
"""
import numpy as np
import FreeCAD
import Part

from BNCClassA.geom import bezier, builders, match, nurbs_io

_CONTINUITIES = ["G0", "G1", "G2"]
_EDGE_KEYS = ("Edge1", "Edge2", "Edge3", "Edge4")
# picked-edge index (after loop ordering) -> patch boundary
_BOUNDARY_OF = ("u0", "v1", "u1", "v0")     # south, east, north, west


def _order_loop(edges, tol=0.5):
    """Order 4 edges into a closed loop; returns list of (edge, reversed)."""
    remaining = list(edges)
    first = remaining.pop(0)
    loop = [(first, False)]
    end = first.valueAt(first.LastParameter)
    while remaining:
        best = None
        for e in remaining:
            p0 = e.valueAt(e.FirstParameter)
            p1 = e.valueAt(e.LastParameter)
            for rev, p in ((False, p0), (True, p1)):
                d = (p - end).Length
                if best is None or d < best[0]:
                    best = (d, e, rev)
        d, e, rev = best
        if d > tol:
            raise ValueError("boundary edges do not form a closed loop "
                             "(gap %.3f mm)" % d)
        loop.append((e, rev))
        end = e.valueAt(e.FirstParameter if rev else e.LastParameter)
        remaining.remove(e)
    start = first.valueAt(first.FirstParameter)
    if (end - start).Length > tol:
        raise ValueError("boundary loop does not close (gap %.3f mm)"
                         % (end - start).Length)
    return loop


class BoundaryPatch(object):
    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "ClassA::BoundaryPatch"
        obj.addProperty("App::PropertyLinkSubList", "Boundaries", "ClassA",
                        "Four boundary edges")
        for key in _EDGE_KEYS:
            obj.addProperty("App::PropertyEnumeration", "Continuity" + key,
                            "ClassA", "Continuity along picked edge " + key[-1])
            setattr(obj, "Continuity" + key, _CONTINUITIES)
        obj.addProperty("App::PropertyInteger", "Sweeps", "ClassA",
                        "Corner reconciliation sweeps")
        obj.addProperty("App::PropertyBool", "UseOCCTFilling", "ClassA",
                        "Start from OCCT Filling instead of a Coons patch")
        obj.addProperty("App::PropertyFloat", "Damping", "ClassA",
                        "Gauss-Seidel damping (0-1)")
        obj.Sweeps = 2
        obj.Damping = 0.5

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _edges_and_hosts(obj):
        out = []
        for link, subs in (obj.Boundaries or []):
            for sub in subs:
                edge = link.Shape.getElement(sub)
                if edge.ShapeType != "Edge":
                    continue
                hosts = nurbs_io.host_faces_of_edge(link.Shape, edge)
                out.append((edge, hosts[0] if hosts else None))
        return out

    def execute(self, obj):
        picked = self._edges_and_hosts(obj)
        if len(picked) != 4:
            if picked:
                FreeCAD.Console.PrintWarning(
                    "%s: needs exactly 4 edges (%d given)\n" % (obj.Name, len(picked)))
            return
        loop = _order_loop([e for (e, _h) in picked])
        # keep host/continuity attached to the ordered edges
        conts, hosts, edges = [], [], []
        for (edge, _rev) in loop:
            for i, (pe, host) in enumerate(picked):
                if pe.isSame(edge) or (pe.Length == edge.Length
                                       and (pe.CenterOfMass - edge.CenterOfMass).Length < 1e-7):
                    conts.append(_CONTINUITIES.index(
                        getattr(obj, "Continuity" + _EDGE_KEYS[i])))
                    hosts.append(host)
                    edges.append(pe)
                    break
            else:
                conts.append(0)
                hosts.append(None)
                edges.append(edge)

        # Bézier boundary rows in loop orientation
        rows = []
        for (edge, rev) in loop:
            poles, _dev = nurbs_io.edge_to_bezier(edge, degree=5)
            start = edge.valueAt(edge.FirstParameter)
            if (np.linalg.norm(poles[0] - [start.x, start.y, start.z])
                    > np.linalg.norm(poles[-1] - [start.x, start.y, start.z])):
                poles = poles[::-1]
            if rev:
                poles = poles[::-1]
            rows.append(poles)

        south, east, north_rev, west_rev = rows
        north = north_rev[::-1]
        west = west_rev[::-1]

        if obj.UseOCCTFilling:
            net = self._occt_start(loop)
        else:
            net = builders.coons_net(south, north, west, east)

        # match passes against the host faces
        for _sweep in range(max(0, obj.Sweeps)):
            for i in range(4):
                if conts[i] < 1 or hosts[i] is None:
                    continue
                result = match.match_surface(
                    net, _BOUNDARY_OF[i], hosts[i], edges[i],
                    order=conts[i], mode="minimal",
                    hold_opposite=False, pin_corners=True)
                d = max(0.0, min(1.0, obj.Damping))
                net = net + d * (result.net - net)

        obj.Shape = nurbs_io.make_bezier_surface(net).toShape()

    @staticmethod
    def _occt_start(loop):
        """OCCT Filling as the base patch, refit as a single-span Bézier."""
        edges = []
        for (edge, _rev) in loop:
            edges.append(edge)
        face = Part.makeFilledFace(edges)
        grid = builders.sample_face_grid(face, 40, 40)
        net, _dev = builders.fit_surface_net(grid, 5, 5)
        return net

    def dumps(self):
        return {"Type": self.Type}

    def loads(self, state):
        if state:
            self.Type = state.get("Type", "ClassA::BoundaryPatch")


class ViewProviderBoundaryPatch(object):
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        from BNCClassA import icon
        return icon("ClassASquarePatch")

    def dumps(self):
        return None

    def loads(self, _state):
        return None


def make_boundary_patch(doc, links):
    """links: LinkSubList value [(obj, ("EdgeN",)), ...] with 4 edges total."""
    obj = doc.addObject("Part::FeaturePython", "SquarePatch")
    BoundaryPatch(obj)
    if obj.ViewObject is not None:
        ViewProviderBoundaryPatch(obj.ViewObject)
        try:
            obj.ViewObject.DisplayMode = "Shaded"
        except Exception:
            pass
    obj.Boundaries = links
    obj.recompute()
    return obj
