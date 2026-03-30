# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# *   BNC CAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   BNC CAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with BNC CAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Set Working Directory command for BNC CAD"""

import FreeCAD
import FreeCADGui
from PySide import QtGui, QtCore
import os

__title__ = "BNC CAD - Set Working Directory Command"
__author__ = "BNC CAD"
__url__ = ""


class Std_SetWorkingDirectory:
    """
    Set Working Directory - Standard FreeCAD Command

    This command allows users to set a global working directory that persists
    across sessions and updates the window title to reflect the current directory.
    """

    def GetResources(self):
        """Return command resources (icon, menu text, tooltip)"""
        return {
            'Pixmap': 'SET_WD',  # Icon name (will look for SET_WD.svg)
            'MenuText': 'Set Working Directory',
            'Accel': 'Ctrl+Shift+W',  # Optional keyboard shortcut
            'ToolTip': 'Set the working directory for file operations.\nThe selected directory will be used as the default location for opening and saving files.',
            'CmdType': 'ForEdit'
        }

    def IsActive(self):
        """Command is always active"""
        return True

    def Activated(self):
        """
        Execute the Set Working Directory command

        Opens a folder selection dialog, sets the working directory,
        and updates the window title to show the current directory.
        """
        # Get current working directory from user parameters
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        start_dir = params.GetString("WorkingDirectory", os.path.expanduser("~"))

        # Open folder selection dialog
        folder = QtGui.QFileDialog.getExistingDirectory(
            FreeCADGui.getMainWindow(),
            "Select Working Directory",
            start_dir
        )

        if folder:
            # Normalize path
            folder = os.path.normpath(folder)

            # Save to user parameters (persists across sessions)
            params.SetString("WorkingDirectory", folder)

            # Change current working directory
            try:
                os.chdir(folder)
            except Exception as e:
                FreeCAD.Console.PrintError(f"Failed to change directory: {str(e)}\n")
                return

            # Update window title with working directory
            mw = FreeCADGui.getMainWindow()

            def update_title():
                """Update window title to show working directory"""
                current_title = mw.windowTitle()

                # Remove old WD suffix if present
                if " — WD: " in current_title:
                    base_title = current_title.split(" — WD: ")[0]
                else:
                    base_title = current_title

                # Add new WD suffix
                new_title = f"{base_title} — WD: {folder}"
                mw.setWindowTitle(new_title)

            # Delay title update so FreeCAD doesn't overwrite it
            QtCore.QTimer.singleShot(200, update_title)

            # Print confirmation message
            FreeCAD.Console.PrintMessage(f"Working Directory set to:\n{folder}\n")


# Instantiate command object
FreeCADGui.addCommand('Std_SetWorkingDirectory', Std_SetWorkingDirectory())

FreeCAD.Console.PrintLog("Std_SetWorkingDirectory command registered\n")
