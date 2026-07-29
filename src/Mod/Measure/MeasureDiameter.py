# SPDX-License-Identifier: LGPL-2.1-or-later
# ANVIL CAD - Diameter measurement type
#
# Adds a "Diameter" entry to the Measure tool's Mode list. Selecting a FULL
# circle (or cylindrical / spherical face) reports the DIAMETER; selecting an
# ARC (partial circle) reports the RADIUS. Registered from Python via
# FreeCAD.MeasureManager.addMeasureType (see Measure/InitGui.py) - no C++.

import FreeCAD
from FreeCAD import Units, Placement
from UtilsMeasure import MeasureBasePython
from PySide.QtCore import QT_TRANSLATE_NOOP

__title__ = "Measure Diameter"
__author__ = "ANVIL CAD"


def _point_on_edge(edge):
    """A point lying on a circular edge (used to place the annotation at the
    edge, like the Radius measure, rather than at the centre)."""
    try:
        return edge.valueAt(edge.FirstParameter)
    except Exception:
        try:
            return edge.Vertexes[0].Point
        except Exception:
            return None


def _point_on_circle(center, axis, radius):
    """Fallback edge point: centre + radius * (a direction perpendicular to the
    circle axis)."""
    try:
        ref = FreeCAD.Vector(1, 0, 0)
        if abs(axis.dot(ref)) > 0.9:
            ref = FreeCAD.Vector(0, 1, 0)
        perp = axis.cross(ref)
        perp.normalize()
        return center + perp.multiply(radius)
    except Exception:
        return center


def _circle_info(sub):
    """Return (radius, edge_point, is_full) for a circular sub-element, else
    None. edge_point is a point ON the circumference (for placing the label at
    the edge). is_full is True for a closed circle / cylinder / sphere, False
    for an arc."""
    if sub is None:
        return None
    try:
        st = getattr(sub, "ShapeType", "")
    except Exception:
        st = ""
    # --- circular edge (full circle or arc) ---
    if st == "Edge":
        try:
            curve = sub.Curve
        except Exception:
            curve = None
        if curve is not None and hasattr(curve, "Radius") \
                and not hasattr(curve, "MajorRadius"):   # circle, not ellipse
            try:
                full = bool(sub.isClosed())
            except Exception:
                full = False
            pt = _point_on_edge(sub)
            if pt is None:
                center = getattr(curve, "Center", None)
                axis = getattr(curve, "Axis", FreeCAD.Vector(0, 0, 1))
                pt = _point_on_circle(center, axis, float(curve.Radius)) \
                    if center is not None else None
            return (float(curve.Radius), pt, full)
        return None
    # --- cylindrical / spherical face -> diameter ---
    if st == "Face":
        try:
            surf = sub.Surface
        except Exception:
            surf = None
        if surf is not None and hasattr(surf, "Radius") \
                and not hasattr(surf, "MajorRadius"):
            r = float(surf.Radius)
            pt = None
            try:
                for e in sub.Edges:
                    c = getattr(e, "Curve", None)
                    if c is not None and hasattr(c, "Radius") \
                            and not hasattr(c, "MajorRadius"):
                        pt = _point_on_edge(e)
                        break
            except Exception:
                pt = None
            if pt is None:
                center = getattr(surf, "Center", None)
                axis = getattr(surf, "Axis", FreeCAD.Vector(0, 0, 1))
                pt = _point_on_circle(center, axis, r) if center is not None else None
            return (r, pt, True)
    return None


def _sub_of(selection_item):
    ob = selection_item.get("object")
    subName = selection_item.get("subName", "")
    if not ob:
        return None
    try:
        return ob.getSubObject(subName)
    except Exception:
        return None


class MeasureDiameter(MeasureBasePython):
    """Diameter/Radius measurement of circular geometry."""

    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty(
            "App::PropertyLinkSubGlobal", "Element", "",
            QT_TRANSLATE_NOOP("App::Property", "Element to measure"),
            locked=True)
        obj.addProperty(
            "App::PropertyLength", "Result", "",
            QT_TRANSLATE_NOOP("App::Property", "The measured value"),
            locked=True)
        self._is_diameter = True

    @classmethod
    def isValidSelection(cls, selection):
        if len(selection) != 1:
            return False
        return _circle_info(_sub_of(selection[0])) is not None

    @classmethod
    def isPrioritySelection(cls, selection):
        return False

    @classmethod
    def getInputProps(cls):
        return ("Element",)

    def getSubject(self, obj):
        el = obj.Element
        if not el or not el[0]:
            return ()
        return (el[0],)

    def parseSelection(self, obj, selection):
        item = selection[0]
        obj.Element = (item["object"], item["subName"])

    def _compute(self, obj):
        el = obj.Element
        if not el or not el[0]:
            return None
        ob = el[0]
        subs = el[1]
        subName = subs[0] if subs else ""
        try:
            sub = ob.getSubObject(subName)
        except Exception:
            return None
        info = _circle_info(sub)
        if info is None:
            return None
        radius, edge_point, full = info
        value = 2.0 * radius if full else radius
        return (value, edge_point, full)

    def execute(self, obj):
        res = self._compute(obj)
        if res is None:
            return
        value, edge_point, is_dia = res
        obj.Result = value
        self._is_diameter = bool(is_dia)
        if edge_point is not None:
            # anchor the annotation ON the circle edge (like the Radius measure),
            # not at the centre
            pl = Placement()
            pl.Base = edge_point
            obj.Placement = pl

    def getResultString(self, obj):
        try:
            s = obj.Result.UserString
        except Exception:
            try:
                s = Units.Quantity(float(obj.Result), Units.Length).UserString
            except Exception:
                s = "{:.2f} mm".format(float(obj.Result))
        prefix = "Ø " if getattr(self, "_is_diameter", True) else "R "
        return prefix + s

    def onChanged(self, obj, prop):
        if prop == "Element":
            self.execute(obj)
