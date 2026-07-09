# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 ANVIL CAD                                            *
# *                                                                         *
# *   This file is part of ANVIL CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""ANVIL CAD - Force Workbench Selector Toolbar to Always Show"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

_enforcement_timer = None

def force_workbench_toolbar_visible():
    """Force workbench toolbar to be visible and dropdown to be hidden"""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            return False

        # Find all toolbars
        toolbars = mw.findChildren(QtWidgets.QToolBar)

        workbench_toolbar_found = False
        workbench_combo_found = False

        for toolbar in toolbars:
            toolbar_name = toolbar.objectName()

            # Find and show the workbench selector toolbar (with all the buttons)
            if "workbench" in toolbar_name.lower() and "selector" in toolbar_name.lower():
                if not toolbar.isVisible():
                    toolbar.setVisible(True)
                    toolbar.show()
                    FreeCAD.Console.PrintLog(f"ANVIL CAD: Showed workbench toolbar: {toolbar_name}\n")
                workbench_toolbar_found = True

            # Find and hide the dropdown combobox toolbar if it exists
            if "workbench" in toolbar_name.lower() and "combo" in toolbar_name.lower():
                if toolbar.isVisible():
                    toolbar.setVisible(False)
                    toolbar.hide()
                    FreeCAD.Console.PrintLog(f"ANVIL CAD: Hid workbench dropdown: {toolbar_name}\n")
                workbench_combo_found = True

        # Also find and hide any workbench combo boxes directly
        combos = mw.findChildren(QtWidgets.QComboBox)
        for combo in combos:
            combo_name = combo.objectName()
            if "workbench" in combo_name.lower():
                parent_toolbar = combo.parent()
                if isinstance(parent_toolbar, QtWidgets.QToolBar):
                    if parent_toolbar.isVisible():
                        parent_toolbar.setVisible(False)
                        parent_toolbar.hide()
                        FreeCAD.Console.PrintLog(f"ANVIL CAD: Hid combo parent toolbar: {parent_toolbar.objectName()}\n")

        # Set the preference to toolbar mode
        main_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
        current_type = main_prefs.GetInt("WorkbenchSelectorType", -1)

        if current_type != 1:
            main_prefs.SetInt("WorkbenchSelectorType", 1)

        return workbench_toolbar_found

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error forcing workbench toolbar: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())
        return False

def start_enforcement():
    """Start the enforcement process with multiple attempts"""
    global _enforcement_timer

    # Try immediately
    QtCore.QTimer.singleShot(100, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(500, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(1000, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(2000, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(3000, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(5000, force_workbench_toolbar_visible)
    QtCore.QTimer.singleShot(10000, force_workbench_toolbar_visible)

    # Also set up a recurring timer to check every 30 seconds
    _enforcement_timer = QtCore.QTimer()
    _enforcement_timer.setInterval(30000)  # 30 seconds
    _enforcement_timer.timeout.connect(force_workbench_toolbar_visible)
    _enforcement_timer.start()

    FreeCAD.Console.PrintLog("ANVIL CAD: Workbench toolbar enforcement started\n")

# Start enforcement
start_enforcement()

FreeCAD.Console.PrintLog("ANVIL CAD: Force workbench toolbar module loaded\n")
