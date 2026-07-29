# SPDX-License-Identifier: LGPL-2.1-or-later
"""Object-level utilities shared by the Class-A commands."""
import FreeCAD

from BNCClassA.geom import nurbs_io
from .cv_curve import make_cv_curve
from .cv_surface import CVSurface, make_cv_surface


def proxy_type(obj):
    return getattr(getattr(obj, "Proxy", None), "Type", "")


def is_cv_surface(obj):
    return proxy_type(obj) == "ClassA::CVSurface"


def is_cv_curve(obj):
    return proxy_type(obj) == "ClassA::CVCurve"


def surface_net_of(obj):
    """(nu, nv, 3) pole net of a CVSurface object."""
    return CVSurface.pole_array(obj)


def set_surface_net(obj, net, transaction=None):
    """Write a pole net back into a CVSurface inside an undo transaction."""
    doc = obj.Document
    if transaction:
        doc.openTransaction(transaction)
    try:
        CVSurface.set_pole_array(obj, net)
        obj.recompute()
    finally:
        if transaction:
            doc.commitTransaction()


def bake_to_cv_surface(obj):
    """Replace a parametric surface object (BlendSurface/BoundaryPatch, or any
    single-face object with a single-span Bézier surface) by an editable
    CVSurface. Returns the new object or raises ValueError."""
    shape = obj.Shape
    if len(shape.Faces) != 1:
        raise ValueError("%s: expected exactly one face" % obj.Label)
    surf = shape.Faces[0].Surface
    try:
        bs = surf if hasattr(surf, "getPoles") else surf.toBSpline()
    except Exception:
        raise ValueError("%s: surface cannot be converted to B-spline" % obj.Label)
    if not nurbs_io.is_single_span_bezier(bs):
        raise ValueError(
            "%s: not a single-span Bézier — use Rebuild Surface first" % obj.Label)
    net = nurbs_io.surface_poles(bs)
    doc = obj.Document
    new = make_cv_surface(doc, net, provenance="Baked from %s" % obj.Label)
    new.Label = obj.Label
    try:
        new.ViewObject.ShapeColor = obj.ViewObject.ShapeColor
    except Exception:
        pass
    doc.removeObject(obj.Name)
    return new
