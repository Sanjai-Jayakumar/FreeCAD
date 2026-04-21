"""
BNC CAD Macro Setup
Automatically configures keyboard shortcuts for BNC macros
"""

import FreeCAD
import FreeCADGui
import os

def setup_bnc_macros():
    """Setup keyboard shortcuts for BNC macros"""

    # Get the Macro folder path
    app_path = FreeCAD.getHomePath()
    macro_folder = os.path.join(app_path, "Macro")

    if not os.path.exists(macro_folder):
        FreeCAD.Console.PrintWarning("BNC Macro folder not found\n")
        return

    # Define macro shortcuts
    macros = {
        "SetWorkingDirectory.FCMacro": "Ctrl+Shift+W",
        "New_File.FCMacro": "Ctrl+N",
        "Version_Save.FCMacro": "Ctrl+S",
        "Save_As.FCMacro": "Ctrl+Shift+S",
        "OPEN_File.FCMacro": "Ctrl+O"
    }

    # Parameter group for keyboard shortcuts
    params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Shortcut")

    for macro, shortcut in macros.items():
        macro_path = os.path.join(macro_folder, macro)
        if os.path.exists(macro_path):
            # Register shortcut
            command_name = f"Std_DlgMacroExecute_{macro}"
            params.SetString(command_name, shortcut)

    FreeCAD.Console.PrintMessage("✓ BNC Macros configured with keyboard shortcuts\n")
    FreeCAD.Console.PrintMessage("  Ctrl+Shift+W - Set Working Directory\n")
    FreeCAD.Console.PrintMessage("  Ctrl+N       - New File\n")
    FreeCAD.Console.PrintMessage("  Ctrl+S       - Version Save\n")
    FreeCAD.Console.PrintMessage("  Ctrl+Shift+S - Save As\n")
    FreeCAD.Console.PrintMessage("  Ctrl+O       - Open File\n")


def auto_run_selection_filter():
    """Auto-run SelectionFilter.FCMacro to show status bar widget"""
    try:
        # Ensure GUI is available
        if not FreeCADGui:
            FreeCAD.Console.PrintWarning("GUI not ready for Selection Filter\n")
            return
            
        # Check if main window is available
        mw = FreeCADGui.getMainWindow()
        if not mw:
            FreeCAD.Console.PrintWarning("Main window not ready for Selection Filter\n")
            return
        
        # Set marker to indicate this is an auto-run (prevents popup from showing)
        setattr(mw, '_sel_filter_auto_run', True)
        
        # Get the Macro folder path
        app_path = FreeCAD.getHomePath()
        macro_path = os.path.join(app_path, "Macro", "SelectionFilter.FCMacro")
        
        if os.path.exists(macro_path):
            # Execute the macro to create the status bar widget
            with open(macro_path, encoding="utf-8") as f:
                macro_code = f.read()
            exec(macro_code, {"__name__": "__main__"})
            FreeCAD.Console.PrintMessage("✓ Selection Filter enabled in status bar\n")
        else:
            FreeCAD.Console.PrintWarning(f"SelectionFilter.FCMacro not found at: {macro_path}\n")
        
        # Clear the auto-run marker
        setattr(mw, '_sel_filter_auto_run', False)
    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError(f"Failed to load Selection Filter: {e}\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


# Run setup on FreeCAD startup
try:
    setup_bnc_macros()
    
    # Auto-run selection filter after main window is ready
    # Use a longer delay (2000ms) to ensure GUI is fully initialized
    try:
        from PySide2.QtCore import QTimer
    except ImportError:
        try:
            from PySide6.QtCore import QTimer
        except ImportError:
            FreeCAD.Console.PrintError("PySide not available for Selection Filter\n")
            QTimer = None
    
    if QTimer:
        QTimer.singleShot(2000, auto_run_selection_filter)
    else:
        FreeCAD.Console.PrintWarning("Could not schedule Selection Filter auto-run\n")
except Exception as e:
    import traceback
    FreeCAD.Console.PrintError(f"BNC Macro setup failed: {e}\n")
    FreeCAD.Console.PrintError(traceback.format_exc())
