"""
BNC CAD Macro Setup
Configures keyboard shortcuts and selection filter widget on startup.
"""

import FreeCAD
import FreeCADGui
import os


def setup_bnc_macros():
    app_path = FreeCAD.getHomePath()
    macro_folder = os.path.join(app_path, "Macro")
    if not os.path.exists(macro_folder):
        return

    macros = {
        "SetWorkingDirectory.FCMacro": "Ctrl+Shift+W",
        "New_File.FCMacro":            "Ctrl+N",
        "Version_Save.FCMacro":        "Ctrl+S",
        "Save_As.FCMacro":             "Ctrl+Shift+S",
        "OPEN_File.FCMacro":           "Ctrl+O",
    }

    params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Shortcut")
    for macro, shortcut in macros.items():
        if os.path.exists(os.path.join(macro_folder, macro)):
            params.SetString("Std_DlgMacroExecute_" + macro, shortcut)


def auto_run_selection_filter():
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            return
        setattr(mw, '_sel_filter_auto_run', True)
        macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "SelectionFilter.FCMacro")
        if os.path.exists(macro_path):
            with open(macro_path, encoding="utf-8") as f:
                exec(f.read(), {"__name__": "__main__"})
        setattr(mw, '_sel_filter_auto_run', False)
    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError("Failed to load Selection Filter: " + str(e) + "\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


try:
    setup_bnc_macros()
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    QtCore.QTimer.singleShot(2000, auto_run_selection_filter)
except Exception as e:
    import traceback
    FreeCAD.Console.PrintError("BNC Macro setup failed: " + str(e) + "\n")
    FreeCAD.Console.PrintError(traceback.format_exc())
