# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""BNC CAD - Enforce Workbench Selector as Toolbar Buttons"""

import FreeCAD
import FreeCADGui
from PySide import QtCore

def enforce_workbench_selector():
    """Enforce workbench selector to show toolbar buttons style"""
    try:
        # Wait for GUI to be ready
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, enforce_workbench_selector)
            return

        # Get MainWindow preferences
        main_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")

        # Get current selector type
        current_type = main_prefs.GetInt("WorkbenchSelectorType", -1)

        # Force it to toolbar button style (type 1) if not already set
        if current_type != 1:
            main_prefs.SetInt("WorkbenchSelectorType", 1)
            FreeCAD.Console.PrintLog("BNC CAD: Workbench selector set to toolbar buttons style\n")

            # Try to apply the change immediately
            try:
                # Refresh the workbench selector UI
                from PySide import QtWidgets
                workbench_selector = mw.findChild(QtWidgets.QToolBar, "Workbench selector toolbar")
                if workbench_selector:
                    workbench_selector.setVisible(True)
                    FreeCAD.Console.PrintLog("BNC CAD: Workbench toolbar visibility refreshed\n")
            except Exception as e:
                FreeCAD.Console.PrintLog(f"BNC CAD: Could not refresh workbench selector: {e}\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error enforcing workbench selector: {str(e)}\n")

# Enforce on startup with delay to ensure GUI is ready
QtCore.QTimer.singleShot(1500, enforce_workbench_selector)

# Also enforce repeatedly in the first 10 seconds to catch any resets
QtCore.QTimer.singleShot(3000, enforce_workbench_selector)
QtCore.QTimer.singleShot(5000, enforce_workbench_selector)
QtCore.QTimer.singleShot(10000, enforce_workbench_selector)

FreeCAD.Console.PrintLog("BNC CAD: Workbench selector enforcement module loaded\n")
