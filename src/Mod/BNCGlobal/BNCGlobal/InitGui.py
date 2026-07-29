# -*- coding: utf-8 -*-
import FreeCAD
import FreeCADGui
import os
import sys
from PySide import QtCore, QtGui, QtWidgets

# Force Tab workbench selector on every launch
try:
    FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General").SetInt("WorkbenchSelector", 1)
except Exception as e:
    FreeCAD.Console.PrintError("Error setting workbench selector: " + str(e) + "\n")

_BNC_GLOBAL_DIR = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCGlobal", "BNCGlobal")


def remove_help_menu():
    try:
        mw = FreeCADGui.getMainWindow()
        menubar = mw.menuBar()
        for menu_action in menubar.actions():
            menu = menu_action.menu()
            if menu and "Help" in menu.title():
                menubar.removeAction(menu_action)
                break
    except Exception as e:
        FreeCAD.Console.PrintError("Error removing Help menu: " + str(e) + "\n")


def set_workbench_selector_style():
    try:
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General").SetInt("WorkbenchSelector", 1)
        mw = FreeCADGui.getMainWindow()
        for toolbar in mw.findChildren(QtGui.QToolBar):
            if "workbench" in toolbar.objectName().lower() or "Workbenches" in toolbar.windowTitle():
                toolbar.setVisible(True)
                toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
                break
    except Exception as e:
        FreeCAD.Console.PrintError("Error refreshing workbench selector: " + str(e) + "\n")


# The toolbar Save button (Std_Save override) must run the SAME save as Ctrl+S
# (Save.FCMacro) — the single-file save that exports each part as .prt, exports
# subassemblies as .asm, and uses clean (non-compounding) version names. The old
# Version_Save.FCMacro compounded filenames ('432.001.001') and did NOT export
# parts, so pointing here fixes both when the user clicks the Save button.
_macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "Save.FCMacro")
_open_macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "OPEN_File.FCMacro")


def _force_clear_modified():
    # FreeCADGui.updateGui() calls qApp->processEvents(), which can fire pending
    # Qt events that re-call setModified(true). So drain all events FIRST, then
    # set Modified=False as the very last operation so nothing undoes it.
    try:
        FreeCADGui.updateGui()  # drain all pending Qt events (may set Modified=True)
        for name in list(FreeCAD.listDocuments().keys()):
            try:
                gui_doc = FreeCADGui.getDocument(name)
                if gui_doc:
                    gui_doc.Modified = False
            except Exception:
                pass
    except Exception as e:
        FreeCAD.Console.PrintError("BNC clear modified: " + str(e) + "\n")


def _run_version_save():
    if os.path.exists(_macro_path):
        try:
            exec(open(_macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
        except Exception as e:
            FreeCAD.Console.PrintError("BNC Version Save error: " + str(e) + "\n")
        QtCore.QTimer.singleShot(500, _force_clear_modified)
    else:
        FreeCAD.Console.PrintError("BNC Version Save: macro not found at " + _macro_path + "\n")


def _run_open_file():
    if os.path.exists(_open_macro_path):
        try:
            exec(open(_open_macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
        except Exception as e:
            FreeCAD.Console.PrintError("BNC Open File error: " + str(e) + "\n")
    else:
        FreeCAD.Console.PrintError("BNC Open File: macro not found at " + _open_macro_path + "\n")


def _apply_std_open_override():
    try:
        mw = FreeCADGui.getMainWindow()
        for old_action in mw.findChildren(QtGui.QAction):
            if old_action.objectName() != "Std_Open":
                continue
            try:
                containers = [w for w in old_action.associatedObjects()
                              if isinstance(w, QtWidgets.QWidget)]
            except AttributeError:
                containers = old_action.associatedWidgets()
            for widget in list(containers):
                already = [a for a in widget.actions()
                           if a.objectName() == "BNC_Std_Open_Override"]
                if already:
                    continue
                new_action = QtGui.QAction(old_action.icon(), old_action.text(), widget)
                new_action.setObjectName("BNC_Std_Open_Override")
                new_action.setToolTip(old_action.toolTip())
                new_action.setShortcut(old_action.shortcut())
                new_action.setShortcutContext(QtCore.Qt.ApplicationShortcut)
                new_action.triggered.connect(_run_open_file)
                widget.insertAction(old_action, new_action)
                widget.removeAction(old_action)
            old_action.setEnabled(False)
            old_action.setShortcut(QtGui.QKeySequence())
    except Exception as e:
        FreeCAD.Console.PrintError("BNC override_std_open error: " + str(e) + "\n")


def _apply_std_save_override():
    try:
        mw = FreeCADGui.getMainWindow()
        for old_action in mw.findChildren(QtGui.QAction):
            if old_action.objectName() != "Std_Save":
                continue
            # Replace this action inside each widget that contains it
            # PySide6 removed associatedWidgets() — use associatedObjects() instead
            try:
                containers = [w for w in old_action.associatedObjects()
                              if isinstance(w, QtWidgets.QWidget)]
            except AttributeError:
                containers = old_action.associatedWidgets()
            for widget in list(containers):
                # Skip if we already replaced it in this widget
                already = [a for a in widget.actions()
                           if a.objectName() == "BNC_Std_Save_Override"]
                if already:
                    continue
                new_action = QtGui.QAction(old_action.icon(), old_action.text(), widget)
                new_action.setObjectName("BNC_Std_Save_Override")
                new_action.setToolTip(old_action.toolTip())
                new_action.setShortcut(old_action.shortcut())
                new_action.setShortcutContext(QtCore.Qt.ApplicationShortcut)
                new_action.triggered.connect(_run_version_save)
                widget.insertAction(old_action, new_action)
                widget.removeAction(old_action)
            old_action.setEnabled(False)
            old_action.setShortcut(QtGui.QKeySequence())
    except Exception as e:
        FreeCAD.Console.PrintError("BNC override_std_save error: " + str(e) + "\n")


def override_std_actions():
    _apply_std_save_override()
    _apply_std_open_override()
    # Re-apply after every workbench switch — FreeCAD rebuilds toolbars on each switch
    try:
        mw = FreeCADGui.getMainWindow()
        def _on_wb_change(wb_name=None):
            QtCore.QTimer.singleShot(400, _apply_std_save_override)
            QtCore.QTimer.singleShot(400, _apply_std_open_override)
        mw.workbenchActivated.connect(_on_wb_change)
    except Exception as e:
        FreeCAD.Console.PrintError("BNC wb-hook error: " + str(e) + "\n")


QtCore.QTimer.singleShot(3000, remove_help_menu)
QtCore.QTimer.singleShot(3500, set_workbench_selector_style)
QtCore.QTimer.singleShot(4000, override_std_actions)
