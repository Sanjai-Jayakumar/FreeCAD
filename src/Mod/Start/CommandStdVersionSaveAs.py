# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 ANVIL CAD                                            *
# *                                                                         *
# *   This file is part of ANVIL CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Version Save As command for ANVIL CAD - Save As with automatic version numbering"""

import FreeCAD
import FreeCADGui
from PySide import QtGui, QtCore
import os

__title__ = "ANVIL CAD - Version Save As Command"
__author__ = "ANVIL CAD"
__url__ = ""


class Std_VersionSaveAs:
    """
    Version Save As - Standard FreeCAD Command

    Save As dialog with automatic version numbering.
    Creates version-controlled files: FileName.001.FCStd, FileName.002.FCStd, etc.
    Updates working directory if user saves to a different location.
    """

    def GetResources(self):
        """Return command resources (icon, menu text, tooltip)"""
        return {
            'Pixmap': 'save_as',  # Icon name (will look for save_as.svg)
            'MenuText': 'Version Save As',
            'Accel': 'Ctrl+Shift+S',
            'ToolTip': 'Save As with automatic version numbering.\nCreates version-controlled files (.001, .002, .003).\nUpdates working directory if changed.',
            'CmdType': 'ForEdit'
        }

    def IsActive(self):
        """Command is active only when there's an active document"""
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        """Execute the Version Save As command"""

        # Get working directory
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        working_dir = params.GetString("WorkingDirectory", os.path.expanduser("~"))

        # Check for active document
        doc = FreeCAD.ActiveDocument
        if not doc:
            FreeCAD.Console.PrintError("No active document!\n")
            QtGui.QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "No Document",
                "There is no active document to save."
            )
            return

        def clean_name(name):
            """Clean document name for use as filename"""
            return name.replace(" ", "_")

        # Get default name from document label
        default_name = clean_name(doc.Label)

        # Create Save As dialog
        dialog = QtGui.QFileDialog(
            FreeCADGui.getMainWindow(),
            "Save As (Version Controlled)",
            working_dir,
            "ANVIL CAD Files (*.FCStd)"
        )

        dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        dialog.selectFile(default_name)

        # Execute dialog
        if not dialog.exec_():
            return  # User cancelled

        file_path = dialog.selectedFiles()[0]

        # Update working directory if changed
        new_dir = os.path.dirname(file_path)
        if new_dir != working_dir:
            params.SetString("WorkingDirectory", new_dir)
            try:
                os.chdir(new_dir)
                FreeCAD.Console.PrintMessage(f"✓ Working Directory updated to:\n{new_dir}\n")
            except Exception as e:
                FreeCAD.Console.PrintError(f"Warning: Could not change directory: {str(e)}\n")

        # Extract base name (without .FCStd extension)
        base_name = os.path.basename(file_path).replace(".FCStd", "")
        base_path = os.path.join(new_dir, base_name)

        def latest_version(base):
            """Find the latest version number for a given base filename"""
            v = 1
            while os.path.exists(f"{base}.{v:03d}.FCStd"):
                v += 1
            return v - 1  # Return last existing version (0 if none exist)

        # Find latest version
        last_v = latest_version(base_path)

        # Get undo count tracking for this document
        save_params = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/VersionSave"
        )
        undo_key = f"{base_name}_Undo"

        # Current undo count
        undo_now = doc.UndoCount
        last_undo = save_params.GetInt(undo_key, -1)

        # Determine version to save
        try:
            if last_v == 0:
                # No existing versions - create .001
                path = f"{base_path}.001.FCStd"
                doc.saveAs(path)
                save_params.SetInt(undo_key, undo_now)
                FreeCAD.Console.PrintMessage(
                    f"✓ {base_name} → Saved as .001\n"
                )
            else:
                # Existing versions found
                if undo_now != last_undo:
                    # Document has changed - create new version
                    new_v = last_v + 1
                    path = f"{base_path}.{new_v:03d}.FCStd"
                    doc.saveAs(path)
                    save_params.SetInt(undo_key, undo_now)
                    FreeCAD.Console.PrintMessage(
                        f"✓ {base_name} → Modified → Saved as .{new_v:03d}\n"
                    )
                else:
                    # No changes - overwrite same version
                    path = f"{base_path}.{last_v:03d}.FCStd"
                    doc.saveAs(path)
                    FreeCAD.Console.PrintMessage(
                        f"✓ {base_name} → No changes → Saved same version (.{last_v:03d})\n"
                    )

            FreeCAD.Console.PrintMessage(
                f"✔ Saved in directory:\n{new_dir}\n"
            )

        except Exception as e:
            FreeCAD.Console.PrintError(f"Error saving file: {str(e)}\n")
            QtGui.QMessageBox.critical(
                FreeCADGui.getMainWindow(),
                "Save Error",
                f"Failed to save file:\n{str(e)}"
            )


# Register command
FreeCADGui.addCommand('Std_VersionSaveAs', Std_VersionSaveAs())

FreeCAD.Console.PrintLog("Std_VersionSaveAs command registered\n")
