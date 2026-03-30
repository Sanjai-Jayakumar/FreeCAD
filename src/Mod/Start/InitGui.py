# SPDX-License-Identifier: LGPL-2.1-or-later
# /**************************************************************************
#                                                                           *
#    Copyright (c) 2024 The FreeCAD Project Association AISBL               *
#                                                                           *
#    This file is part of BNC CAD.                                          *
#                                                                           *
#    BNC CAD is free software: you can redistribute it and/or modify it     *
#    under the terms of the GNU Lesser General Public License as            *
#    published by the Free Software Foundation, either version 2.1 of the   *
#    License, or (at your option) any later version.                        *
#                                                                           *
#    BNC CAD is distributed in the hope that it will be useful, but         *
#    WITHOUT ANY WARRANTY; without even the implied warranty of             *
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
#    Lesser General Public License for more details.                        *
#                                                                           *
#    You should have received a copy of the GNU Lesser General Public       *
#    License along with BNC CAD. If not, see                                *
#    <https://www.gnu.org/licenses/>.                                       *
#                                                                           *
# **************************************************************************/

import StartMigrator
import FreeCAD

migrator = StartMigrator.StartMigrator2024()
migrator.run_migration()

# StartGui intentionally not imported so the Start page is never created at launch


# BNC CAD: Register Set Working Directory command
try:
    import CommandStdSetWorkingDirectory
    FreeCAD.Console.PrintLog("BNC CAD: Set Working Directory command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load Set Working Directory command: {str(e)}\n")

# BNC CAD: Add BNC Tools toolbar with 4 buttons
try:
    import AddSetWDButton
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to add BNC toolbar: {str(e)}\n")

# BNC CAD: Register Version Save command
try:
    import CommandStdVersionSave
    FreeCAD.Console.PrintLog("BNC CAD: Version Save command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load Version Save command: {str(e)}\n")

# BNC CAD: Register Version Open command
try:
    import CommandStdVersionOpen
    FreeCAD.Console.PrintLog("BNC CAD: Version Open command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load Version Open command: {str(e)}\n")

# BNC CAD: Register Version Save As command
try:
    import CommandStdVersionSaveAs
    FreeCAD.Console.PrintLog("BNC CAD: Version Save As command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load Version Save As command: {str(e)}\n")

# BNC CAD: Apply default light gray theme
try:
    import BNCThemeConfig
    FreeCAD.Console.PrintLog("BNC CAD: Theme configuration loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load theme configuration: {str(e)}\n")

# BNC CAD: Hide Help menu
try:
    import HideHelpMenu
    FreeCAD.Console.PrintLog("BNC CAD: Help menu hide module loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load Help hide module: {str(e)}\n")


# BNC CAD: Force workbench toolbar to always show
try:
    import ForceWorkbenchToolbar
    FreeCAD.Console.PrintLog("BNC CAD: Force workbench toolbar module loaded\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to load force workbench toolbar module: {str(e)}\n")
