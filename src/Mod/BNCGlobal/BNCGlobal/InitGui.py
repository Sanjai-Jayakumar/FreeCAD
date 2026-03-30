# -*- coding: utf-8 -*-
# BNC Global Commands - GUI Initialization
# This file is loaded when FreeCAD GUI starts

import FreeCAD
import FreeCADGui
import os
import sys
from PySide import QtCore, QtGui

# =============================================================================
# SET WORKBENCH SELECTOR DEFAULT - RUN IMMEDIATELY
# Force Tab mode on EVERY launch to ensure it persists
# =============================================================================

# Set the default workbench selector style immediately at import time
# ALWAYS set to Tab mode on every launch to ensure it persists
try:
    param_group = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")

    # ALWAYS set WorkbenchSelector to 1 (Tab selector) on every launch
    # 0 = Combo/List selector (dropdown), 1 = Tab selector (buttons)
    param_group.SetInt("WorkbenchSelector", 1)
    FreeCAD.Console.PrintMessage("✓ Workbench selector forced to Tab mode\n")

except Exception as e:
    FreeCAD.Console.PrintError(f"Error setting workbench selector at import: {str(e)}\n")

# Get the icons directory path
ICON_PATH = os.path.join(FreeCAD.getResourceDir(), "Mod", "BNCGlobal", "Resources", "icons")

# Capture module directory at load time (when __file__ is available)
_BNC_GLOBAL_DIR = os.path.dirname(os.path.abspath(__file__))

# Add icon path to FreeCAD's icon search paths
FreeCADGui.addIconPath(ICON_PATH)

FreeCAD.Console.PrintMessage("BNC Global module loaded\n")


def remove_help_menu():
    """Remove the Help menu from the menu bar"""
    try:
        mw = FreeCADGui.getMainWindow()
        menubar = mw.menuBar()

        # Find and remove Help menu
        help_menu_action = None
        for menu_action in menubar.actions():
            menu = menu_action.menu()
            if menu and "Help" in menu.title():
                help_menu_action = menu_action
                FreeCAD.Console.PrintMessage(f"✓ Found Help menu: {menu.title()}\n")
                break

        if help_menu_action:
            # Remove the Help menu from the menu bar
            menubar.removeAction(help_menu_action)
            FreeCAD.Console.PrintMessage("✓ Help menu removed successfully\n")
        else:
            FreeCAD.Console.PrintWarning("Help menu not found\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error removing Help menu: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


def set_workbench_selector_style():
    """Force Tab mode and refresh workbench selector GUI"""
    try:
        from PySide import QtCore, QtGui

        # ALWAYS force WorkbenchSelector to 1 (Tab mode)
        param_group = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        param_group.SetInt("WorkbenchSelector", 1)

        FreeCAD.Console.PrintMessage("✓ Workbench selector forced to Tab mode (delayed)\n")

        # Force the main window to refresh the workbench selector
        mw = FreeCADGui.getMainWindow()

        # Find and configure the workbench selector toolbar
        all_toolbars = mw.findChildren(QtGui.QToolBar)

        for toolbar in all_toolbars:
            toolbar_name = toolbar.objectName()
            toolbar_title = toolbar.windowTitle()

            # Look for workbench selector toolbar
            if "workbench" in toolbar_name.lower() or "Workbenches" in toolbar_title:
                FreeCAD.Console.PrintMessage(f"✓ Found workbench toolbar: {toolbar_name} ({toolbar_title})\n")

                # Ensure toolbar is visible and using icon+text style
                toolbar.setVisible(True)
                toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

                FreeCAD.Console.PrintMessage("✓ Workbench selector toolbar refreshed\n")
                break

        FreeCAD.Console.PrintMessage("✓ Workbench selector GUI refresh complete\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error refreshing workbench selector: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


def add_bnc_model_toolbar():
    """Create the BNC Model toolbar with Save and Model Parameters buttons."""
    try:
        sys.path.insert(0, _BNC_GLOBAL_DIR)
        import CommandStdVersionSave
        import CommandStdModelParameters

        mw = FreeCADGui.getMainWindow()

        # Avoid duplicate toolbar
        for tb in mw.findChildren(QtGui.QToolBar):
            if tb.objectName() == "BNC_Model":
                return

        toolbar = mw.addToolBar("BNC Model")
        toolbar.setObjectName("BNC_Model")
        toolbar.addAction(FreeCADGui.Command.get("BNC_VersionSave").getAction()[0])
        toolbar.addAction(FreeCADGui.Command.get("BNC_ModelParameters").getAction()[0])
        toolbar.setVisible(True)
        toolbar.show()

        FreeCAD.Console.PrintMessage("✓ BNC Model toolbar created\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error creating BNC Model toolbar: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


# Call the function when the GUI is ready (delayed to ensure UI is loaded)
QtCore.QTimer.singleShot(2000, add_bnc_model_toolbar)
QtCore.QTimer.singleShot(3000, remove_help_menu)
QtCore.QTimer.singleShot(3500, set_workbench_selector_style)
