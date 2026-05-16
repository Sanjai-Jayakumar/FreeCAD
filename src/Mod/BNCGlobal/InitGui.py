import sys
import os
import FreeCAD

_mod_dir = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCGlobal")
if _mod_dir not in sys.path:
    sys.path.insert(0, _mod_dir)

from BNCGlobal import InitGui
