# SPDX-License-Identifier: LGPL-2.1-or-later
# /**************************************************************************
#                                                                           *
#    Copyright (c) 2024 The FreeCAD Project Association AISBL               *
#                                                                           *
#    This file is part of ANVIL CAD.                                          *
#                                                                           *
#    ANVIL CAD is free software: you can redistribute it and/or modify it     *
#    under the terms of the GNU Lesser General Public License as            *
#    published by the Free Software Foundation, either version 2.1 of the   *
#    License, or (at your option) any later version.                        *
#                                                                           *
#    ANVIL CAD is distributed in the hope that it will be useful, but         *
#    WITHOUT ANY WARRANTY; without even the implied warranty of             *
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
#    Lesser General Public License for more details.                        *
#                                                                           *
#    You should have received a copy of the GNU Lesser General Public       *
#    License along with ANVIL CAD. If not, see                                *
#    <https://www.gnu.org/licenses/>.                                       *
#                                                                           *
# **************************************************************************/

import StartMigrator
import FreeCAD

migrator = StartMigrator.StartMigrator2024()
migrator.run_migration()

# StartGui intentionally not imported so the Start page is never created at launch


# ANVIL CAD: Rename Origin sub-features to BNC naming (X-axis, XY-TOP, etc.)
try:
    import BNCOriginLabels
    FreeCAD.Console.PrintLog("ANVIL CAD: Origin labels module loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Origin labels: {str(e)}\n")

# ANVIL CAD: Register Set Working Directory command
try:
    import CommandStdSetWorkingDirectory
    FreeCAD.Console.PrintLog("ANVIL CAD: Set Working Directory command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Set Working Directory command: {str(e)}\n")

# ANVIL CAD: Add BNC Tools toolbar with 4 buttons
try:
    import AddSetWDButton
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to add BNC toolbar: {str(e)}\n")

# ANVIL CAD: Register Version Save command
try:
    import CommandStdVersionSave
    FreeCAD.Console.PrintLog("ANVIL CAD: Version Save command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Version Save command: {str(e)}\n")

# ANVIL CAD: Register Version Open command
try:
    import CommandStdVersionOpen
    FreeCAD.Console.PrintLog("ANVIL CAD: Version Open command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Version Open command: {str(e)}\n")

# ANVIL CAD: Register Version Save As command
try:
    import CommandStdVersionSaveAs
    FreeCAD.Console.PrintLog("ANVIL CAD: Version Save As command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Version Save As command: {str(e)}\n")

# ANVIL CAD: Apply default light gray theme
try:
    import BNCThemeConfig
    FreeCAD.Console.PrintLog("ANVIL CAD: Theme configuration loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load theme configuration: {str(e)}\n")

# ANVIL CAD: Hide Help menu
try:
    import HideHelpMenu
    FreeCAD.Console.PrintLog("ANVIL CAD: Help menu hide module loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Help hide module: {str(e)}\n")


# ANVIL CAD: Force workbench toolbar to always show
try:
    import ForceWorkbenchToolbar
    FreeCAD.Console.PrintLog("ANVIL CAD: Force workbench toolbar module loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load force workbench toolbar module: {str(e)}\n")

# ANVIL CAD: Pipe Bending toolbar — visible ONLY in Part Design workbench
try:
    import BNCPipeBendingToolbar
    from PySide import QtCore as _pb_qtc
    _pb_qtc.QTimer.singleShot(2500, BNCPipeBendingToolbar.init)
    FreeCAD.Console.PrintLog("ANVIL CAD: Pipe Bending toolbar scheduled\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to setup Pipe Bending toolbar: {str(e)}\n")

# ANVIL CAD: Check for Updates menu item
try:
    import CommandCheckForUpdates
    FreeCAD.Console.PrintLog("ANVIL CAD: Check for Updates command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load Check for Updates command: {str(e)}\n")

# ANVIL CAD: Poll update API every 5 minutes — shows banner when update_available
try:
    import AutoCheckUpdates
    AutoCheckUpdates.start_update_polling()
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to start update polling: {str(e)}\n")

# ANVIL CAD: Set default workbench tab order on first launch
try:
    import BNCWorkbenchOrder  # noqa: F401 — side-effect import
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load workbench order module: {str(e)}\n")

# ANVIL CAD: Bounce workbench to force PartDesign toolbars to appear on startup
# activateWorkbench() is a no-op when the target is already active, so we must
# switch away first, then back, to trigger C++ setupToolBars().
try:
    def _bnc_refresh_partdesign_toolbars():
        try:
            import FreeCADGui
            active = FreeCADGui.activeWorkbench()
            if active and active.__class__.__name__ == "PartDesignWorkbench":
                FreeCADGui.activateWorkbench("NoneWorkbench")
                FreeCADGui.activateWorkbench("PartDesignWorkbench")
                FreeCAD.Console.PrintLog("ANVIL CAD: PartDesign toolbars refreshed via bounce\n")
        except Exception as exc:
            FreeCAD.Console.PrintError(f"ANVIL CAD: Toolbar refresh error: {exc}\n")

    from PySide import QtCore
    QtCore.QTimer.singleShot(2000, _bnc_refresh_partdesign_toolbars)
    FreeCAD.Console.PrintLog("ANVIL CAD: PartDesign toolbar refresh scheduled\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to schedule toolbar refresh: {str(e)}\n")

# ANVIL CAD: Apply auth from web launcher URL before showing login dialog.
# Must run before BNCLoginScheduler so is_logged_in() already returns True
# when the scheduler fires 2 seconds later.
try:
    import BNCAuthFromUrl  # noqa: F401 — side-effect import, runs _apply() on load
except Exception as e:
    FreeCAD.Console.PrintWarning(f"ANVIL CAD: BNCAuthFromUrl skipped: {str(e)}\n")

# ANVIL CAD: Show Google Sign-In dialog on launch
# NOTE: Must use QTimer.singleShot (static) — the same approach that works for
# the toolbar bounce above.  FreeCAD loads InitGui.py via exec(), so any Python
# QTimer *instance* created here is garbage-collected before it can fire.
# IMPORTANT: Do NOT define helper functions here — exec() scope cleanup will
# garbage-collect them before the timer fires, causing NameError.
# All login logic lives in BNCLoginScheduler.py to avoid this.
try:
    import BNCLoginScheduler
    BNCLoginScheduler.schedule()
except Exception as e:
    FreeCAD.Console.PrintError(f"ANVIL CAD: Failed to load login dialog: {str(e)}\n")
