# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure geometry math for BNCClassA.

This package must stay importable under FreeCADCmd (headless): it may import
FreeCAD, Part and numpy — never FreeCADGui, pivy or Qt.
"""
import FreeCAD

try:
    import numpy  # noqa: F401 — required by the match solver and fitters
except ImportError:
    FreeCAD.Console.PrintError(
        "BNCClassA: numpy is required but not available in this FreeCAD build. "
        "Class-A geometry tools will not work.\n")
    raise
