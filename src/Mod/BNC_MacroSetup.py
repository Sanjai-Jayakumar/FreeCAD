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

# Run setup on FreeCAD startup
try:
    setup_bnc_macros()
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC Macro setup failed: {e}\n")
