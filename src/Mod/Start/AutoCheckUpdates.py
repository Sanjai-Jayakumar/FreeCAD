# BNC CAD Auto Update Checker
# Automatically checks for updates on startup and shows banner if available

import FreeCAD
import FreeCADGui
from PySide import QtCore


def auto_check_for_updates():
    """Automatically check for updates on startup"""
    try:
        # Import update modules
        import UpdateChecker
        import UpdateUI
        
        # Get update checker instance
        checker = UpdateChecker.get_update_checker()
        
        # Check if we should check now (respects check interval)
        if not checker.should_check_now():
            FreeCAD.Console.PrintLog("BNC CAD: Update check skipped (checked recently)\n")
            return
        
        # Check for updates
        FreeCAD.Console.PrintLog("BNC CAD: Checking for updates...\n")
        update_info = checker.check_for_updates()
        
        # If update available, show banner automatically
        if update_info.get('update_available', False):
            new_version = update_info.get('new_version', 'unknown')
            FreeCAD.Console.PrintMessage(f"BNC CAD: Update available - version {new_version}\n")
            
            # Show the update banner
            UpdateUI.show_update_banner()
        else:
            FreeCAD.Console.PrintLog("BNC CAD: No updates available\n")
            
    except Exception as e:
        # Silently fail - don't spam console on startup
        FreeCAD.Console.PrintLog(f"BNC CAD: Update check error: {str(e)}\n")


def schedule_auto_check():
    """Schedule automatic update check after GUI is ready"""
    def _check():
        try:
            # Make sure GUI is ready
            if FreeCADGui.getMainWindow():
                auto_check_for_updates()
            else:
                # GUI not ready, try again
                QtCore.QTimer.singleShot(2000, _check)
        except:
            pass
    
    # Wait 5 seconds after startup to check for updates
    # This ensures FreeCAD is fully loaded
    QtCore.QTimer.singleShot(5000, _check)
    FreeCAD.Console.PrintLog("BNC CAD: Auto update check scheduled\n")


# Schedule the auto-check when module loads
try:
    schedule_auto_check()
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC CAD: Failed to schedule auto update check: {str(e)}\n")
