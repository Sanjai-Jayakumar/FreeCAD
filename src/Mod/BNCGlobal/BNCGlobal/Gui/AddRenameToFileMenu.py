# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Add Rename command to global File menu"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore

def add_rename_to_file_menu():
    """Add the Std_VersionRename command to the File menu for global access"""
    try:
        # Get the main window
        mw = Gui.getMainWindow()
        if not mw:
            App.Console.PrintWarning("BNC CAD: Could not get main window for Rename menu integration\n")
            return

        # Get the menu bar
        menubar = mw.menuBar()
        if not menubar:
            App.Console.PrintWarning("BNC CAD: Could not get menu bar for Rename menu integration\n")
            return

        # Find the File menu
        file_menu = None
        for action in menubar.actions():
            if action.text() == "&File" or action.text() == "File":
                file_menu = action.menu()
                break

        if not file_menu:
            App.Console.PrintWarning("BNC CAD: Could not find File menu for Rename integration\n")
            return

        # Check if Rename action already exists
        for action in file_menu.actions():
            if action.objectName() == "Std_VersionRename":
                App.Console.PrintLog("BNC CAD: Rename already in File menu\n")
                return

        # Find position to insert - after "Save As" or before first separator
        insert_before_action = None
        found_save_as = False
        for action in file_menu.actions():
            if "Save As" in action.text() or "SaveAs" in action.objectName():
                found_save_as = True
                continue
            if found_save_as:
                insert_before_action = action
                break

        # Create the Rename action
        rename_action = QtGui.QAction(mw)
        rename_action.setText("Rename")
        rename_action.setToolTip("Advanced rename (document / linked / internal)")
        rename_action.setShortcut(QtGui.QKeySequence("F2"))
        rename_action.setObjectName("Std_VersionRename")

        # Load icon
        try:
            import os
            icon_path = os.path.join(App.getHomePath(), "Mod", "BNCGlobal", "Gui", "Resources", "icons", "Rename.svg")
            if os.path.exists(icon_path):
                rename_action.setIcon(QtGui.QIcon(icon_path))
        except:
            pass

        # Connect to the FreeCAD command
        rename_action.triggered.connect(lambda: Gui.runCommand('Std_VersionRename'))

        # Insert into File menu
        if insert_before_action:
            file_menu.insertAction(insert_before_action, rename_action)
        else:
            file_menu.addAction(rename_action)

        App.Console.PrintMessage("✓ BNC CAD: Rename command added to File menu (F2)\n")

    except Exception as e:
        App.Console.PrintError(f"BNC CAD: Failed to add Rename to File menu: {str(e)}\n")

# Execute after a short delay to ensure UI is fully initialized
QtCore.QTimer.singleShot(1000, add_rename_to_file_menu)
