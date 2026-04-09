# -*- coding: utf-8 -*-
"""BNC CAD Login Scheduler — separate module to avoid exec() GC issues in InitGui.py."""

import FreeCAD
from PySide import QtCore

_login_retries = [0]


def _show_login():
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow() if hasattr(FreeCADGui, "getMainWindow") else None
        # Retry up to 20 times (every 500ms) until main window is visible
        if mw is None or not mw.isVisible():
            _login_retries[0] += 1
            if _login_retries[0] <= 20:
                FreeCAD.Console.PrintLog(
                    f"BNC CAD: Main window not ready, retry {_login_retries[0]}/20\n"
                )
                QtCore.QTimer.singleShot(500, _show_login)
                return
            FreeCAD.Console.PrintWarning("BNC CAD: Main window not ready after retries, showing anyway\n")

        FreeCAD.Console.PrintMessage("BNC CAD: Login timer fired\n")
        # Check internet before showing login
        import BNCNetworkCheck
        if not BNCNetworkCheck.check_startup():
            return  # user chose Exit
        BNCNetworkCheck.start_periodic_check()

        import BNCLoginDialog
        BNCLoginDialog.show_login_if_needed()
    except Exception as exc:
        import traceback
        FreeCAD.Console.PrintError(f"BNC CAD: Login dialog error: {exc}\n")
        FreeCAD.Console.PrintError(traceback.format_exc() + "\n")


def schedule():
    """Schedule the login dialog to appear after 2 seconds."""
    _login_retries[0] = 0
    QtCore.QTimer.singleShot(2000, _show_login)
    FreeCAD.Console.PrintLog("BNC CAD: Login dialog scheduled (singleShot 2s)\n")
