# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""BNC CAD Default Theme Configuration - Light Gray Theme"""

import FreeCAD
import FreeCADGui
from PySide import QtCore

# ============================================================================
# EARLY INITIALIZATION: Set workbench selector default BEFORE GUI is created
# This must execute early to ensure the Tab selector is used by default
# ============================================================================
def set_workbench_selector_default():
    """Set workbench selector to TabBar mode if not already configured by user."""
    try:
        # Correct path: User parameter:BaseApp/Preferences/Workbenches
        # WorkbenchSelectorType: 0 = ComboBox (FreeCAD default), 1 = TabBar
        wb_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Workbenches")
        if not wb_prefs.HasParameter("WorkbenchSelectorType"):
            wb_prefs.SetInt("WorkbenchSelectorType", 1)
            FreeCAD.Console.PrintLog("BNC: Workbench selector type defaulted to TabBar\n")
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not set workbench selector default: {e}\n")

# Execute immediately when module loads (before GUI initialization)
set_workbench_selector_default()

def set_bnc_default_theme():
    """Set BNC CAD solid gray background - ALWAYS apply"""
    try:
        # Wait for GUI to be ready
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, set_bnc_default_theme)
            return

        # Get preferences
        view_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        main_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
        general_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        bnc_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/BNC")

        # FORCE CLEAR ALL OLD BACKGROUND COLORS - Remove any previous settings
        FreeCAD.Console.PrintLog("BNC: Clearing all old background color settings...\n")
        try:
            # Get all parameter names and remove background-related ones
            for param_name in ["BackgroundColor", "BackgroundColor2", "BackgroundColor3", "BackgroundColor4", "Simple"]:
                if view_prefs.HasParameter(param_name):
                    view_prefs.RemUnsigned(param_name)
        except:
            pass

        # SOLID LIGHT GRAY BACKGROUND - Simple and consistent
        # Pure gray #e3e3e3 (227, 227, 227) - neutral light gray
        # Color format: RGBA as unsigned int (R << 24 | G << 16 | B << 8 | A)
        # Calculation: (227 << 24) | (227 << 16) | (227 << 8) | 255
        gray_color = 3823363327  # e3e3e3FF = pure gray

        # ALWAYS set gray background - override everything
        view_prefs.SetUnsigned("BackgroundColor", gray_color)
        view_prefs.SetUnsigned("BackgroundColor2", gray_color)
        view_prefs.SetUnsigned("BackgroundColor3", gray_color)
        view_prefs.SetUnsigned("BackgroundColor4", gray_color)

        # Force disable gradient - use solid color
        view_prefs.SetBool("Gradient", False)
        view_prefs.SetBool("Simple", True)  # Use simple solid color
        view_prefs.SetBool("UseBackgroundColorMid", False)
        view_prefs.SetBool("RadialGradient", False)

        # Check if theme has already been set by user (for other settings)
        theme_initialized = bnc_prefs.GetBool("ThemeInitialized", False)

        if not theme_initialized:
            # Selection and highlighting colors
            view_prefs.SetUnsigned("SelectionColor", 210082303)  # Selection highlight
            view_prefs.SetUnsigned("HighlightColor", 192054783)  # Mouse hover highlight

            # Default shape colors (for created objects)
            view_prefs.SetUnsigned("DefaultShapeColor", 2914369023)  # Default part color
            view_prefs.SetUnsigned("DefaultShapeLineColor", 421075455)  # Edge colors

            # Sketcher colors - yellow sketch lines for visibility on gray background
            sketcher_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher/General")
            sketcher_prefs.SetUnsigned("EdgeColor", 4294902015)  # Yellow (255,255,0) RGBA

            # Set BNC Theme Light as the active theme
            main_prefs.SetString("StyleSheet", "BNC Theme Light.qss")
            main_prefs.SetString("OverlayActiveStyleSheet", "BNC Theme Light Overlay.qss")
            main_prefs.SetString("Theme", "BNC Theme Light")

            # Set workbench selector type to TabBar (correct path)
            FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Workbenches").SetInt("WorkbenchSelectorType", 1)

            # Set mode preference
            bnc_prefs.SetString("Mode", "light")

            # Mark theme as initialized
            bnc_prefs.SetBool("ThemeInitialized", True)


        # Apply preferences immediately
        try:
            FreeCADGui.runCommand("Std_ApplyCurrentPreferences", 0)
        except Exception:
            pass

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error setting BNC theme: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())

# Apply theme after GUI is ready (delayed to ensure everything is loaded)
QtCore.QTimer.singleShot(1000, set_bnc_default_theme)

# ============================================================================
# DOCUMENT OBSERVER: Apply gray background to new documents automatically
# ============================================================================
class BNCDocumentObserver:
    """Observer to apply BNC viewport settings to newly created documents"""

    def slotCreatedDocument(self, doc):
        """Called when a new document is created"""
        try:
            # Apply gray background to the new document's viewport
            QtCore.QTimer.singleShot(100, self.apply_viewport_colors)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"BNC: Error in document observer: {e}\n")

    def apply_viewport_colors(self):
        """Apply BNC solid gray background to active view"""
        try:
            view = FreeCADGui.ActiveDocument.ActiveView
            if view:
                # Pure gray #e3e3e3 = RGB(227, 227, 227) = normalized (0.890, 0.890, 0.890)
                view.setBackgroundColor(0.890, 0.890, 0.890)
                view.setGradientBackground(False)  # Disable gradient - solid color only
                FreeCAD.Console.PrintLog("✓ Applied solid gray background to new document\n")
        except Exception as e:
            FreeCAD.Console.PrintLog(f"BNC: Could not apply viewport colors: {e}\n")

# Register document observer
try:
    observer = BNCDocumentObserver()
    FreeCAD.addDocumentObserver(observer)
    FreeCAD.Console.PrintLog("✓ BNC document observer registered\n")
except Exception as e:
    FreeCAD.Console.PrintWarning(f"Could not register BNC document observer: {e}\n")

FreeCAD.Console.PrintLog("BNC CAD: Theme configuration module loaded\n")
