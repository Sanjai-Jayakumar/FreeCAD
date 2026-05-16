import FreeCAD
import sys
import os

# Add Mod directory to path so BNC_MacroSetup is importable
_mod_dir = os.path.join(FreeCAD.getHomePath(), "Mod")
if _mod_dir not in sys.path:
    sys.path.append(_mod_dir)

try:
    import BNC_MacroSetup
except Exception as e:
    FreeCAD.Console.PrintError("BNC CAD initialization error: " + str(e) + "\n")
