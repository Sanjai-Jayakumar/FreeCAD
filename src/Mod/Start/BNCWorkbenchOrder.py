# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
ANVIL CAD — Default workbench tab order.

Sets the FreeCAD tab-bar workbench order on first launch only.
After that the user can freely reorder tabs; we never override again.
"""

import FreeCAD
import FreeCADGui

try:
    from PySide import QtCore
except ImportError:
    from PySide2 import QtCore

# ---------------------------------------------------------------------------
# Desired tab order
# ---------------------------------------------------------------------------

# These appear as tabs in the workbench bar (left → right).
_VISIBLE = [
    "SketcherWorkbench",
    "PartDesignWorkbench",
    "SheetMetalWorkbench",
    "AssemblyWorkbench",
    "TechDrawWorkbench",
    "BNCGSDWorkbench",        # Surface, Curves & CurvedShapes are inside BNC GSD
    "PartWorkbench",
    "BNCMCPAddonWorkbench",
    "FreeCADAIWorkbench",
    "FastenersWorkbench",
    "BNCMoldToolsWorkbench",
    "CablesWorkbench",
]

# These are hidden behind the "+" overflow button.
_HIDDEN = [
    "SurfaceWorkbench",       # tools available via BNC GSD
    "CurvesWorkbench",        # tools available via BNC GSD
    "CurvedShapesWB",         # tools available via BNC GSD (class name is CurvedShapesWB)
    "BIMWorkbench",
    "CAMWorkbench",
    "PathWorkbench",          # CAM in older FreeCAD builds
    "DraftWorkbench",
    "FemWorkbench",
    "InspectionWorkbench",
    "MaterialWorkbench",
    "MeshWorkbench",
    "OpenSCADWorkbench",
    "PointsWorkbench",
    "ReverseEngineeringWorkbench",
    "RobotWorkbench",
    "SpreadsheetWorkbench",
    "TestWorkbench",
    "ArchWorkbench",          # legacy BIM name
    "StartWorkbench",
    "NoneWorkbench",
]

_ORDER_VERSION = "6"          # bump this to force re-apply after list changes
_GUARD_KEY     = "WorkbenchOrderVersion"
_PREFS_PATH    = "User parameter:BaseApp/Preferences/Workbenches"


def _apply_order():
    """Apply the default workbench tab order — runs once per install."""
    try:
        wb_prefs = FreeCAD.ParamGet(_PREFS_PATH)

        # Already applied this version — don't override user customisations.
        if wb_prefs.GetString(_GUARD_KEY, "") == _ORDER_VERSION:
            return

        # Workbenches registered right now (may not include late-loading addons).
        try:
            registered = set(FreeCADGui.listWorkbenches().keys())
        except Exception:
            registered = set()

        # --- Ordered (visible tab list) ---
        # Use the full _VISIBLE list regardless of registration state.
        # FreeCAD skips unregistered entries gracefully; when they register
        # later they will appear in the correct position automatically.
        known = set(_VISIBLE) | set(_HIDDEN)
        # Any registered workbench not explicitly listed → visible at the end.
        extras = sorted(w for w in registered if w not in known)
        ordered = _VISIBLE + extras

        # --- Disabled ---
        # Use the full _HIDDEN list, NOT filtered by registered.
        # This prevents late-registering workbenches (e.g. Curves, CurvedShapes
        # that load after the 3-second mark) from appearing in the tab bar.
        # getDisabledWorkbenches() in C++ filters to currently-registered
        # workbenches at read-time, so unknown names are silently ignored.
        disabled = list(set(_HIDDEN) | (set(registered) - set(ordered)))

        wb_prefs.SetString("Ordered",  ",".join(ordered))
        wb_prefs.SetString("Disabled", ",".join(disabled))

        # Mark this version done so we don't override again until next bump.
        wb_prefs.SetString(_GUARD_KEY, _ORDER_VERSION)

        # ---------------------------------------------------------------
        # Force the live tab bar to rebuild NOW.
        # The only way from Python to call Application::signalRefreshWorkbenches()
        # (which triggers WorkbenchGroup::refreshWorkbenchList → reads our new
        # Ordered/Disabled params → emits workbenchListRefreshed → tab bar rebuilds)
        # is via addWorkbench / removeWorkbench.  We add a harmless dummy, then
        # immediately remove it: two refreshes, clean final state.
        #
        # IMPORTANT: FreeCAD keys the workbench dict by __class__.__name__, NOT
        # by MenuText.  We use type() so the class name equals the removal key.
        # ---------------------------------------------------------------
        _DUMMY = "_BNCWbRefresh_"
        try:
            _DummyWb = type(_DUMMY, (FreeCADGui.Workbench,), {
                "MenuText": _DUMMY,
                "ToolTip":  "",
                "Icon":     "",
                "Initialize":   lambda self: None,
                "GetClassName": lambda self: "Gui::PythonWorkbench",
            })
            FreeCADGui.addWorkbench(_DummyWb())
        except Exception:
            pass
        try:
            FreeCADGui.removeWorkbench(_DUMMY)
        except Exception:
            pass

        FreeCAD.Console.PrintLog(
            "ANVIL CAD: Default workbench order applied.\n")

    except Exception as exc:
        FreeCAD.Console.PrintWarning(
            f"ANVIL CAD: Could not set workbench order: {exc}\n")


# ---------------------------------------------------------------------------
# Hide Surface / Curves / Curved Shapes from the "+" overflow dropdown.
# FreeCAD puts all Disabled workbenches into that menu; we suppress the three
# that are already exposed through BNC GSD.  The QAction objects are cached
# by WorkbenchGroup, so setVisible(False) persists across menu rebuilds.
# We also hook aboutToShow as a safety net.
# ---------------------------------------------------------------------------

_MORE_HIDE = {
    "Surface", "Curves", "Curved Shapes",
    "Reverse Engineering", "Robot", "Test Framework",
}


def _setup_more_menu_filter():
    """Permanently hide Surface/Curves/Curved Shapes from the + overflow menu."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            return

        try:
            from PySide2 import QtWidgets as _W
        except ImportError:
            from PySide6 import QtWidgets as _W

        more_btn = mw.findChild(_W.QToolButton, "WbTabBarMore")
        if not more_btn:
            return

        menu = more_btn.menu()
        if not menu:
            return

        def _filter():
            for action in menu.actions():
                if action.text() in _MORE_HIDE:
                    action.setVisible(False)

        # Connect so the filter re-applies every time the menu opens
        # (buildPrefMenu re-adds actions; setVisible(False) on the cached
        # QAction object persists, but aboutToShow is a belt-and-suspenders guard).
        menu.aboutToShow.connect(_filter)
        _filter()  # apply immediately to current menu state

        FreeCAD.Console.PrintLog("ANVIL CAD: More-menu filter installed.\n")
    except Exception as exc:
        FreeCAD.Console.PrintWarning(
            f"ANVIL CAD: Could not set up more-menu filter: {exc}\n")


# Delay until all workbenches have registered (3 s) then apply order.
# More-menu filter runs at 4 s, after the order apply has finished.
QtCore.QTimer.singleShot(3000, _apply_order)
QtCore.QTimer.singleShot(4000, _setup_more_menu_filter)

FreeCAD.Console.PrintLog("ANVIL CAD: Workbench order module loaded.\n")
