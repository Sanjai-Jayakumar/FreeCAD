# -*- coding: utf-8 -*-
# ANVIL CAD Custom Tools - GUI Initialization
# This file is loaded when FreeCAD GUI starts

import FreeCAD
import FreeCADGui
import os
from PySide import QtCore, QtGui

# Get the icons directory path
ICON_PATH = os.path.join(os.path.dirname(__file__), "Resources", "icons")

FreeCADGui.addIconPath(ICON_PATH)


# =============================================================================
# GLOBAL TOOLBAR REGISTRATION
# This adds the BNC tools to all workbenches without creating a new workbench
# =============================================================================

def add_bnc_tools_globally():
    """Add BNC tools to the File toolbar inline with existing buttons"""
    try:
        # We now use the Std_* commands from Start module instead of BNC_* commands
        # These commands are already registered in Start/InitGui.py:
        # - Std_SetWorkingDirectory
        # - Std_VersionSave
        # - Std_VersionOpen
        # - Std_VersionSaveAs

        # CRITICAL: Clear cached toolbar positions to prevent PersistentToolbarsGui interference
        # This ensures our toolbar always appears ungrouped on every startup
        try:
            pUser = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/User")
            pSystem = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/System")

            # Clear all saved toolbar positions
            for group in pUser.GetGroups():
                pUser.RemGroup(group)
            for group in pSystem.GetGroups():
                pSystem.RemGroup(group)

            FreeCAD.Console.PrintMessage("✓ Cleared cached toolbar positions\n")
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not clear toolbar cache: {e}\n")

        # Get main window
        mw = FreeCADGui.getMainWindow()

        # Find the existing File toolbar
        file_toolbar = None
        for toolbar in mw.findChildren(QtGui.QToolBar):
            if toolbar.objectName() == "File":
                file_toolbar = toolbar
                FreeCAD.Console.PrintMessage(f"✓ Found File toolbar: {toolbar.windowTitle()}\n")
                break

        if not file_toolbar:
            FreeCAD.Console.PrintWarning("File toolbar not found, creating standalone BNC toolbar\n")
            # Fallback: create standalone toolbar
            file_toolbar = QtGui.QToolBar("BNC Tools", mw)
            file_toolbar.setObjectName("BNC_Tools")
            mw.addToolBar(QtCore.Qt.TopToolBarArea, file_toolbar)

        # Icon base paths for finding icons
        icon_base_paths = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            ICON_PATH
        ]

        # Add the 4 BNC commands to the File toolbar
        command_list = [
            "Std_SetWorkingDirectory",
            "Std_VersionSave",
            "Std_VersionOpen",
            "Std_VersionSaveAs"
        ]

        for cmd_name in command_list:
            # Create action from command
            action = QtGui.QAction(mw)
            action.triggered.connect(lambda checked=False, c=cmd_name: FreeCADGui.runCommand(c))

            # Get command info for icon and tooltip
            try:
                cmd = FreeCADGui.Command.get(cmd_name)
                if cmd:
                    res = cmd.GetResources()
                    if 'MenuText' in res:
                        action.setText(res['MenuText'])
                    if 'ToolTip' in res:
                        action.setToolTip(res['ToolTip'])
                    if 'Pixmap' in res:
                        icon_name = res['Pixmap']
                        # Try to find icon in multiple locations
                        for base_path in icon_base_paths:
                            icon_file = os.path.join(base_path, f"{icon_name}.svg")
                            if os.path.exists(icon_file):
                                action.setIcon(QtGui.QIcon(icon_file))
                                FreeCAD.Console.PrintLog(f"✓ Loaded icon: {icon_name} from {icon_file}\n")
                                break
            except Exception as ex:
                FreeCAD.Console.PrintWarning(f"Error loading command resources: {str(ex)}\n")

            file_toolbar.addAction(action)

        FreeCAD.Console.PrintMessage("✓ BNC Custom Tools added to File toolbar successfully\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error adding BNC tools: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


# Call the function when the GUI is ready
# Use 3000ms delay to ensure Start module commands are registered first
# DISABLED: Toolbar creation is now handled by Start/AddSetWDButton.py to avoid duplication
# QtCore.QTimer.singleShot(3000, add_bnc_tools_globally)

