"""
BNC GSD Workbench — GUI init.
FreeCAD loads this only when a GUI is present.
FreeCAD 1.1.x executes InitGui.py via exec() so __file__ may be undefined.
"""
import sys
import os

# Resolve workbench root path robustly.
try:
    _BNCGSD_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _BNCGSD_ROOT = None
    for _p in sys.path:
        if os.path.isfile(os.path.join(_p, "BNCGSDWorkbench.py")):
            _BNCGSD_ROOT = _p
            break
    if _BNCGSD_ROOT is None:
        try:
            import FreeCAD as _FC
            _BNCGSD_ROOT = os.path.join(_FC.getUserAppDataDir(), "Mod", "BNCGSD")
            if not os.path.isdir(_BNCGSD_ROOT):
                _BNCGSD_ROOT = os.path.join(_FC.getResourceDir(), "..", "Mod", "BNCGSD")
        except Exception:
            _BNCGSD_ROOT = os.path.dirname(os.path.abspath(
                sys.argv[0] if sys.argv else "."))

if _BNCGSD_ROOT not in sys.path:
    sys.path.insert(0, _BNCGSD_ROOT)

import FreeCAD as App
import FreeCADGui as Gui

try:
    from BNCGSDWorkbench import BNCGSDWorkbench
    Gui.addWorkbench(BNCGSDWorkbench())
except Exception as _exc:
    App.Console.PrintError(
        f"BNC GSD Workbench failed to load: {_exc}\n"
        "Check Mod/BNC GSD/ for import errors.\n"
    )
