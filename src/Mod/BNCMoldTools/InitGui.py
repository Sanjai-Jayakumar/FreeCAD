# SPDX-License-Identifier: LGPL-2.1-or-later
import sys
import os
import FreeCAD

_mod_dir = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCMoldTools")
if _mod_dir not in sys.path:
    sys.path.insert(0, _mod_dir)

try:
    from BNCMoldTools import InitGui
except Exception as e:
    FreeCAD.Console.PrintError("BNCMoldTools: failed to load — " + str(e) + "\n")
