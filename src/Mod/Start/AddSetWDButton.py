# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Add BNC Tools buttons - PERSISTENT STANDALONE TOOLBAR"""

import FreeCAD
import FreeCADGui
from PySide import QtGui, QtCore
import os

# Global reference to keep toolbar alive
_persistent_toolbar = None


def _ensure_toolbar_separate_row(mw, toolbar):
    """Force the BNC toolbar onto its own row in the top area."""
    # Restore default: do not force a separate row, let FreeCAD handle toolbar placement
    pass


def create_persistent_toolbar():
    """Create a persistent toolbar that won't be removed by workbench changes"""
    global _persistent_toolbar

    try:
        # Check if GUI is ready
        if not FreeCADGui.getMainWindow():
            QtCore.QTimer.singleShot(500, create_persistent_toolbar)
            return

        mw = FreeCADGui.getMainWindow()

        # Check if toolbar already exists
        if _persistent_toolbar is not None:
            FreeCAD.Console.PrintLog("BNC toolbar already exists\n")
            return

        # Check if toolbar exists by name
        for toolbar in mw.findChildren(QtGui.QToolBar):
            if toolbar.objectName() == "BNC_Custom_Toolbar":
                _persistent_toolbar = toolbar
                # Do not force toolbar row, use FreeCAD default
                toolbar.setVisible(True)
                toolbar.show()
                FreeCAD.Console.PrintLog("Found existing BNC toolbar\n")
                return

        # Create new persistent toolbar
        toolbar = mw.addToolBar("BNC Tools")
        toolbar.setObjectName("BNC_Custom_Toolbar")

        # Make toolbar persistent - set it as a top-level toolbar
        toolbar.setAllowedAreas(QtCore.Qt.TopToolBarArea | QtCore.Qt.BottomToolBarArea)
        mw.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        # Do not force toolbar row, use FreeCAD default

        # Icon base paths
        icon_base_paths = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "PartDesign", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "Assembly", "Resources", "icons")
        ]

        # =========================================
        # Button 1: Set Working Directory
        # =========================================
        action_setwd = QtGui.QAction(mw)
        # action_setwd.setText('Set Working Directory')  # Removed to show icon only
        action_setwd.setToolTip('Set the working directory for file operations\nKeyboard: Ctrl+Shift+W')
        action_setwd.setObjectName("BNC_SetWD_Action")

        # Load SET_WD icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "SET_WD.svg")
            if os.path.exists(icon_path):
                action_setwd.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ SET_WD icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_setwd.triggered.connect(lambda: FreeCADGui.runCommand('Std_SetWorkingDirectory'))

        # Add to toolbar
        toolbar.addAction(action_setwd)

        # =========================================
        # Button 2: Version Save
        # =========================================
        action_save = QtGui.QAction(mw)
        # action_save.setText('Version Save')  # Removed to show icon only
        action_save.setToolTip('Save all open documents with automatic version numbering\nKeyboard: Ctrl+S')
        action_save.setObjectName("BNC_VersionSave_Action")
        action_save.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        action_save.setShortcutContext(QtCore.Qt.ApplicationShortcut)

        # Load save icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "save.svg")
            if os.path.exists(icon_path):
                action_save.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ save icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_save.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSave'))

        # Add to toolbar
        toolbar.addAction(action_save)

        # =========================================
        # Button 3: Version Open
        # =========================================
        action_open = QtGui.QAction(mw)
        # action_open.setText('Version Open')  # Removed to show icon only
        action_open.setToolTip('Open version-controlled documents from working directory\\nKeyboard: Ctrl+O')
        action_open.setObjectName("BNC_VersionOpen_Action")

        # Load Open icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Open.svg")
            if os.path.exists(icon_path):
                action_open.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Open icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_open.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionOpen'))

        # Add to toolbar
        toolbar.addAction(action_open)

        # =========================================
        # Button 4: Version Save As
        # =========================================
        action_saveas = QtGui.QAction(mw)
        # action_saveas.setText('Version Save As')  # Removed to show icon only
        action_saveas.setToolTip('Save As with automatic version numbering\nKeyboard: Ctrl+Shift+S')
        action_saveas.setObjectName("BNC_VersionSaveAs_Action")

        # Load save_as icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "save_as.svg")
            if os.path.exists(icon_path):
                action_saveas.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ save_as icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_saveas.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSaveAs'))

        # Add to toolbar
        toolbar.addAction(action_saveas)

        # =========================================
        # Button 5: Rename
        # =========================================
        action_rename = QtGui.QAction(mw)
        action_rename.setToolTip('Rename model and update all versions\nKeyboard: F2')
        action_rename.setObjectName("BNC_Rename_Action")

        # Load Rename icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Rename.svg")
            if os.path.exists(icon_path):
                action_rename.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Rename icon loaded: {icon_path}\n")
                break

        # Connect directly to rename function (avoids command registration timing issues)
        def run_rename():
            import sys
            rename_mod_path = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCGlobal", "Gui")
            if rename_mod_path not in sys.path:
                sys.path.insert(0, rename_mod_path)
            try:
                from CommandStdVersionRename import main as rename_main
                rename_main()
            except Exception as e:
                FreeCAD.Console.PrintError(f"Rename error: {str(e)}\n")

        action_rename.triggered.connect(run_rename)

        # Add to toolbar
        toolbar.addAction(action_rename)

        # =========================================
        # Button 6: Apply Material
        # =========================================
        action_applymat = QtGui.QAction(mw)
        action_applymat.setToolTip('Apply Indian Standard Material to the active body')
        action_applymat.setObjectName("BNC_ApplyMaterial_Action")

        # Load Apply_Material icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Apply_Material.svg")
            if os.path.exists(icon_path):
                action_applymat.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Apply_Material icon loaded: {icon_path}\n")
                break

        # Connect to Apply Material macro
        def run_apply_material():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "Apply_Material.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Apply Material error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"Apply Material macro not found: {macro_path}\n")

        action_applymat.triggered.connect(run_apply_material)

        # Add to toolbar
        toolbar.addAction(action_applymat)

        # =========================================
        # Button 7: Measure Mass
        # =========================================
        action_mass = QtGui.QAction(mw)
        action_mass.setToolTip('Measure mass of selected component(s) based on applied material density')
        action_mass.setObjectName("BNC_MeasureMass_Action")

        # Load Mass_Properties icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Mass_Properties.svg")
            if os.path.exists(icon_path):
                action_mass.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Mass_Properties icon loaded: {icon_path}\n")
                break

        # Connect to MeasureMass macro
        def run_measure_mass():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "MeasureMass.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Measure Mass error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"MeasureMass macro not found: {macro_path}\n")

        action_mass.triggered.connect(run_measure_mass)

        # Add to toolbar
        toolbar.addAction(action_mass)

        # =========================================
        # Button 8: Model Parameters
        # =========================================
        action_model_params = QtGui.QAction(mw)
        action_model_params.setToolTip('View and edit model parameters (Part Number, Description, Revision, etc.)')
        action_model_params.setObjectName("BNC_ModelParameters_Action")

        # Load Model_Parameters icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Model_Parameters.svg")
            if os.path.exists(icon_path):
                action_model_params.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Model_Parameters icon loaded: {icon_path}\n")
                break

        # Connect to ModelParameters macro
        def run_model_parameters():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "ModelParameters.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Model Parameters error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"ModelParameters macro not found: {macro_path}\n")

        action_model_params.triggered.connect(run_model_parameters)

        # Add to toolbar
        toolbar.addAction(action_model_params)

        # =========================================
        # Finalize Toolbar
        # =========================================

        # Keep global reference to prevent garbage collection
        _persistent_toolbar = toolbar

        # Make sure toolbar is visible
        toolbar.setVisible(True)
        toolbar.show()

        FreeCAD.Console.PrintMessage("✓ BNC Custom toolbar created with 8 buttons\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error creating BNC toolbar: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


# Create toolbar with delay to ensure GUI is ready
QtCore.QTimer.singleShot(2000, create_persistent_toolbar)

FreeCAD.Console.PrintLog("BNC CAD: Persistent toolbar module loaded\n")
