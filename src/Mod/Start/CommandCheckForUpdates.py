# BNC CAD Check for Updates Command
# Creates BNC menu with "Check for Updates" option

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui
import os


class CheckForUpdatesCommand:
    """Command to check for BNC CAD updates"""
    
    def GetResources(self):
        icon_path = os.path.join(
            os.path.dirname(__file__),
            "Resources", "icons", "update-icon.svg"
        )
        
        return {
            'Pixmap': icon_path,
            'MenuText': 'Check for Updates...',
            'ToolTip': 'Check if a new version of BNC CAD is available',
            'Accel': 'Ctrl+U'
        }
    
    def Activated(self):
        """Called when the command is executed"""
        try:
            import UpdateUI
            UpdateUI.check_for_updates_menu()
        except Exception as e:
            QtGui.QMessageBox.critical(
                FreeCADGui.getMainWindow(),
                "Update Check Error",
                f"Failed to check for updates:\n{str(e)}"
            )
    
    def IsActive(self):
        """Always active"""
        return True


def register_command():
    """Register the Check for Updates command"""
    FreeCADGui.addCommand('BNC_CheckForUpdates', CheckForUpdatesCommand())


def add_to_help_menu():
    """Create BNC menu with Check for Updates option"""
    
    def _add_menu_item():
        try:
            main_window = FreeCADGui.getMainWindow()
            if not main_window:
                # GUI not ready, try again later
                QtCore.QTimer.singleShot(1000, _add_menu_item)
                return
                
            menu_bar = main_window.menuBar()
            if not menu_bar:
                # Menu bar not ready, try again later
                QtCore.QTimer.singleShot(1000, _add_menu_item)
                return
            
            # Check if BNC menu already exists
            bnc_menu = None
            for action in menu_bar.actions():
                try:
                    if action and action.text() == "&BNC":
                        bnc_menu = action.menu()
                        break
                except RuntimeError:
                    continue
            
            # If BNC menu doesn't exist, create it next to Windows menu
            if not bnc_menu:
                # Find Windows menu to insert before it
                windows_action = None
                for action in menu_bar.actions():
                    try:
                        if action and action.text() and ("Window" in action.text()):
                            windows_action = action
                            break
                    except RuntimeError:
                        continue
                
                # Create BNC menu
                bnc_menu = QtGui.QMenu("&BNC", main_window)
                
                # Insert before Windows menu, or add at end if not found
                if windows_action:
                    menu_bar.insertMenu(windows_action, bnc_menu)
                else:
                    menu_bar.addMenu(bnc_menu)
            
            # Check if Check for Updates action already exists
            try:
                for action in bnc_menu.actions():
                    if action and action.text() == "Check for Updates...":
                        return  # Already added
            except RuntimeError:
                return
            
            # Create the Check for Updates action
            update_action = QtGui.QAction("Check for Updates...", main_window)
            
            # Set icon
            icon_path = os.path.join(
                os.path.dirname(__file__),
                "Resources", "icons", "update-icon.svg"
            )
            if os.path.exists(icon_path):
                update_action.setIcon(QtGui.QIcon(icon_path))
            
            # Set keyboard shortcut
            update_action.setShortcut(QtGui.QKeySequence("Ctrl+U"))
            
            # Connect to command
            update_action.triggered.connect(
                lambda: FreeCADGui.runCommand('BNC_CheckForUpdates')
            )
            
            # Add to BNC menu
            try:
                bnc_menu.addAction(update_action)
                FreeCAD.Console.PrintLog("BNC CAD: BNC menu created with Check for Updates option\n")
            except RuntimeError:
                pass
            
        except Exception as e:
            FreeCAD.Console.PrintError(f"BNC CAD: Failed to create BNC menu: {str(e)}\n")
    
    # Delay execution to ensure GUI and menus are fully ready
    QtCore.QTimer.singleShot(3000, _add_menu_item)


# Initialize when module is loaded
try:
    register_command()
    add_to_help_menu()
    FreeCAD.Console.PrintLog("BNC CAD: Check for Updates command registered\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to register Check for Updates: {str(e)}\n")
