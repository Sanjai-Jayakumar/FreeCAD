# -*- coding: utf-8 -*-
"""ANVIL CAD: Pipe Bending toolbar — visible ONLY in Part Design workbench.

Imported from InitGui.py.  Lives in its own module so that all objects
survive FreeCAD's exec() scope cleanup.
"""

import os
import FreeCAD
from PySide import QtCore, QtGui

_toolbar = None  # singleton QToolBar reference


def _ensure_toolbar():
    """Create the Pipe Bending toolbar (once) and return it."""
    global _toolbar
    if _toolbar is not None:
        return _toolbar

    import FreeCADGui
    mw = FreeCADGui.getMainWindow()
    if mw is None:
        return None

    _toolbar = mw.addToolBar("Pipe Bending")
    _toolbar.setObjectName("BNC_PipeBending_Toolbar")
    _toolbar.setAllowedAreas(QtCore.Qt.TopToolBarArea | QtCore.Qt.BottomToolBarArea)
    mw.addToolBar(QtCore.Qt.TopToolBarArea, _toolbar)

    action = QtGui.QAction(mw)
    action.setToolTip(
        "Create bent pipe designs\n"
        "Define outer radius, wall thickness, bend radius and angle"
    )
    action.setObjectName("BNC_PipeBending_Action")

    # Load icon
    icon_dirs = [
        os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
        os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
    ]
    for d in icon_dirs:
        p = os.path.join(d, "pipe_bending.svg")
        if os.path.exists(p):
            action.setIcon(QtGui.QIcon(p))
            break

    def _run_pipe_bending():
        try:
            import sys
            bnc_path = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools")
            if bnc_path not in sys.path:
                sys.path.insert(0, bnc_path)
            from BNCCustomTools.PipeBendingDialog import PipeBendingDialog, create_bent_pipe
            dlg = PipeBendingDialog()
            if dlg.exec_():
                outer_r = dlg.outer_radius.value()
                wall_t = dlg.wall_thickness.value()
                bend_r = dlg.bend_radius.value()
                bend_a = dlg.bend_angle.value()
                l1 = dlg.length1.value()
                l2 = dlg.length2.value()
                if wall_t >= outer_r:
                    QtGui.QMessageBox.warning(
                        None, "Invalid Parameters",
                        "Wall thickness must be less than outer radius!")
                else:
                    create_bent_pipe(outer_r, wall_t, bend_r, bend_a, l1, l2)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"Pipe Bending error: {exc}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc())

    action.triggered.connect(_run_pipe_bending)
    _toolbar.addAction(action)
    FreeCAD.Console.PrintLog("ANVIL CAD: Pipe Bending toolbar created\n")
    return _toolbar


def _on_workbench_changed(*args, **kwargs):
    """Show toolbar only when Part Design is active."""
    try:
        import FreeCADGui
        tb = _ensure_toolbar()
        if tb is None:
            return
        active = FreeCADGui.activeWorkbench()
        is_pd = active and active.__class__.__name__ == "PartDesignWorkbench"
        tb.setVisible(is_pd)
    except Exception:
        pass


def init():
    """Called once from InitGui.py via QTimer to set up toolbar + observer."""
    try:
        import FreeCADGui
        tb = _ensure_toolbar()
        if tb:
            active = FreeCADGui.activeWorkbench()
            is_pd = active and active.__class__.__name__ == "PartDesignWorkbench"
            tb.setVisible(is_pd)
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.workbenchActivated.connect(_on_workbench_changed)
        FreeCAD.Console.PrintLog("ANVIL CAD: Pipe Bending workbench observer registered\n")
    except Exception as exc:
        FreeCAD.Console.PrintError(f"ANVIL CAD: Pipe Bending init error: {exc}\n")
