# -*- coding: utf-8 -*-
"""
Fix ALL Toolbars - Prevent Grouping Globally
This module ensures ALL toolbars in BNC CAD appear ungrouped
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui


def fix_all_toolbars():
    """Fix all toolbars to prevent grouping and ensure proper display"""
    try:
        FreeCAD.Console.PrintMessage("\n=== Fixing All Toolbars ===\n")

        # Step 1: Disable PersistentToolbarsGui entirely
        try:
            pTux = FreeCAD.ParamGet("User parameter:Tux")
            pTux.GetGroup("PersistentToolbars").SetBool("Enabled", False)
            FreeCAD.Console.PrintMessage("✓ Disabled PersistentToolbarsGui module\n")
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not disable PersistentToolbarsGui: {e}\n")

        # Step 2: Clear all cached toolbar positions
        try:
            pUser = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/User")
            pSystem = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/System")

            user_count = len(pUser.GetGroups())
            system_count = len(pSystem.GetGroups())

            for group in pUser.GetGroups():
                pUser.RemGroup(group)
            for group in pSystem.GetGroups():
                pSystem.RemGroup(group)

            FreeCAD.Console.PrintMessage(f"✓ Cleared {user_count} user + {system_count} system cached configs\n")
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not clear toolbar cache: {e}\n")

        # Step 3: Clear main window toolbar state
        try:
            mainWindow = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
            mainWindow.SetString("ToolBarState", "")
            mainWindow.SetString("WindowState", "")
            FreeCAD.Console.PrintMessage("✓ Cleared main window toolbar state\n")
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not clear main window state: {e}\n")

        # Step 4: Fix all existing toolbars
        mw = FreeCADGui.getMainWindow()
        all_toolbars = mw.findChildren(QtGui.QToolBar)

        fixed_count = 0
        for toolbar in all_toolbars:
            try:
                # Skip if toolbar is not docked or has no parent
                if not toolbar.objectName() or toolbar.parentWidget() != mw:
                    continue

                # Find and disable extension button
                extension = toolbar.findChild(QtGui.QToolButton, "qt_toolbar_ext_button")
                if extension:
                    extension.setVisible(False)
                    extension.setEnabled(False)
                    fixed_count += 1

                # Ensure toolbar is visible and properly configured
                toolbar.setVisible(True)
                toolbar.show()

            except Exception as e:
                FreeCAD.Console.PrintWarning(f"Could not fix toolbar {toolbar.objectName()}: {e}\n")

        FreeCAD.Console.PrintMessage(f"✓ Fixed {fixed_count} toolbars (disabled extension buttons)\n")

        # Step 5: Force toolbar refresh
        try:
            # Reorganize all toolbars to top area with breaks between major groups
            file_toolbars = []
            workbench_toolbars = []
            other_toolbars = []

            for toolbar in all_toolbars:
                if not toolbar.objectName() or toolbar.parentWidget() != mw:
                    continue

                name = toolbar.objectName().lower()
                if "file" in name or "bnc" in name:
                    file_toolbars.append(toolbar)
                elif "part" in name or "sketch" in name or "design" in name:
                    workbench_toolbars.append(toolbar)
                else:
                    other_toolbars.append(toolbar)

            # Remove all toolbars
            for tb in all_toolbars:
                if tb.objectName() and tb.parentWidget() == mw:
                    mw.removeToolBar(tb)

            # Re-add in organized order with breaks
            for tb in file_toolbars:
                mw.addToolBar(QtCore.Qt.TopToolBarArea, tb)

            if workbench_toolbars:
                mw.addToolBarBreak(QtCore.Qt.TopToolBarArea)
                for tb in workbench_toolbars:
                    mw.addToolBar(QtCore.Qt.TopToolBarArea, tb)

            if other_toolbars:
                mw.addToolBarBreak(QtCore.Qt.TopToolBarArea)
                for tb in other_toolbars:
                    mw.addToolBar(QtCore.Qt.TopToolBarArea, tb)

            FreeCAD.Console.PrintMessage("✓ Reorganized all toolbars with proper breaks\n")

        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Could not reorganize toolbars: {e}\n")

        FreeCAD.Console.PrintMessage("=== All Toolbars Fixed ===\n\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error fixing toolbars: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


def maintain_all_toolbars():
    """Continuously maintain all toolbars to prevent grouping"""
    try:
        mw = FreeCADGui.getMainWindow()
        all_toolbars = mw.findChildren(QtGui.QToolBar)

        for toolbar in all_toolbars:
            if not toolbar.objectName() or toolbar.parentWidget() != mw:
                continue

            # Check and fix extension button if it becomes visible
            extension = toolbar.findChild(QtGui.QToolButton, "qt_toolbar_ext_button")
            if extension and (extension.isVisible() or extension.isEnabled()):
                extension.setVisible(False)
                extension.setEnabled(False)

    except:
        pass  # Silently fail to avoid spam


# CRITICAL: Disable PersistentToolbarsGui IMMEDIATELY before it can load
try:
    pTux = FreeCAD.ParamGet("User parameter:Tux")
    pTux.GetGroup("PersistentToolbars").SetBool("Enabled", False)

    # Clear cache immediately
    pUser = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/User")
    pSystem = FreeCAD.ParamGet("User parameter:Tux/PersistentToolbars/System")

    for group in pUser.GetGroups():
        pUser.RemGroup(group)
    for group in pSystem.GetGroups():
        pSystem.RemGroup(group)

    FreeCAD.Console.PrintMessage("✓ Pre-emptively disabled PersistentToolbarsGui\n")
except:
    pass

# Run initial fix after GUI is ready
QtCore.QTimer.singleShot(3500, fix_all_toolbars)

# Run additional fixes at multiple intervals to catch all toolbars
QtCore.QTimer.singleShot(5000, fix_all_toolbars)
QtCore.QTimer.singleShot(7000, fix_all_toolbars)

# Set up continuous monitoring
_global_toolbar_timer = QtCore.QTimer()
_global_toolbar_timer.timeout.connect(maintain_all_toolbars)
_global_toolbar_timer.start(10000)  # Check every 10 seconds

FreeCAD.Console.PrintMessage("Global toolbar fix module loaded\n")
