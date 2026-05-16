# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Renames Origin sub-features to BNC naming convention the moment they
are created (Part, PartDesign Body, Assembly, or any other container).

C++ internal names  →  BNC display labels
  X_Axis            →  X-axis
  Y_Axis            →  Y-axis
  Z_Axis            →  Z-axis
  XY_Plane          →  XY-TOP
  XZ_Plane          →  XZ-FRONT
  YZ_Plane          →  YZ-RIGHT
"""
import FreeCAD

_NAME_MAP = {
    "X_Axis":   "X-axis",
    "Y_Axis":   "Y-axis",
    "Z_Axis":   "Z-axis",
    "XY_Plane": "XY-TOP",
    "XZ_Plane": "XZ-FRONT",
    "YZ_Plane": "YZ-RIGHT",
}


def _relabel_origin(origin):
    try:
        for feat in origin.OriginFeatures:
            new_label = _NAME_MAP.get(feat.Name)
            if new_label and feat.Label != new_label:
                feat.Label = new_label
    except Exception as exc:
        FreeCAD.Console.PrintError(f"BNC: Origin relabel error: {exc}\n")


class _OriginObserver:
    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId == "App::Origin":
                _relabel_origin(obj)
        except Exception:
            pass


_observer = _OriginObserver()
FreeCAD.addDocumentObserver(_observer)
FreeCAD.Console.PrintLog("BNC: Origin label observer installed\n")
