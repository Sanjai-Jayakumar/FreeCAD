# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui

try:
    from PySide2 import QtCore, QtWidgets, QtGui
except ImportError:
    from PySide import QtCore, QtGui
    QtWidgets = QtGui


class CheckForUpdatesCommand:
    def GetResources(self):
        icon_path = os.path.join(os.path.dirname(__file__),
                                 "Resources", "icons", "update-icon.svg")
        return {
            "Pixmap":   icon_path,
            "MenuText": "Check for Updates...",
            "ToolTip":  "Check if a new version of ANVIL CAD is available",
            "Accel":    "Ctrl+U",
        }

    def Activated(self):
        """Direct API call — shows banner or 'up to date' message. No auto-check."""
        mw = FreeCADGui.getMainWindow()

        # Show checking status
        if mw:
            mw.statusBar().showMessage("ANVIL CAD: Checking for updates…", 10000)

        # Shared result holder between background thread and main thread
        _holder = [None]

        def _callback(result):
            _holder[0] = result   # background thread just stores — never touches Qt

        try:
            import UpdateChecker
            UpdateChecker.check_for_updates_async(_callback)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"BNC: Check for Updates error: {exc}\n")
            if mw:
                mw.statusBar().clearMessage()
            return

        # Poll from main thread every 500 ms until result arrives (max 15 s = 30 ticks)
        _ticks = [0]

        def _poll():
            _ticks[0] += 1
            result = _holder[0]

            if result is None:
                if _ticks[0] < 30:
                    QtCore.QTimer.singleShot(500, _poll)
                else:
                    # Timeout
                    if mw:
                        mw.statusBar().clearMessage()
                    try:
                        QtWidgets.QMessageBox.warning(
                            mw, "Check for Updates",
                            "Could not reach the update server.\nPlease check your internet connection."
                        )
                    except Exception:
                        pass
                return

            # Got result — clear status bar
            if mw:
                mw.statusBar().clearMessage()

            if result.get("error"):
                FreeCAD.Console.PrintMessage(f"BNC: Update check error: {result['error']}\n")
                try:
                    QtWidgets.QMessageBox.warning(
                        mw, "Check for Updates",
                        f"Could not reach the update server.\n\n{result['error']}"
                    )
                except Exception:
                    pass
                return

            if result.get("update_available"):
                ver = result.get("latest_version", "")
                msg = (f"ANVIL CAD {ver} is available — please update."
                       if ver else "A new version of ANVIL CAD is available.")
                url = result.get("download_url", "")
                FreeCAD.Console.PrintMessage(f"BNC: {msg}\n")
                try:
                    import UpdateUI
                    UpdateUI.show_update_banner(msg, url)
                except Exception as exc:
                    FreeCAD.Console.PrintError(f"BNC: Banner error: {exc}\n")
            else:
                FreeCAD.Console.PrintMessage("BNC: Software is up to date\n")
                try:
                    QtWidgets.QMessageBox.information(
                        mw, "Check for Updates",
                        "ANVIL CAD is up to date.\nYou have the latest version installed."
                    )
                except Exception:
                    pass

        QtCore.QTimer.singleShot(500, _poll)

    def IsActive(self):
        return True


def register_command():
    FreeCADGui.addCommand("BNC_CheckForUpdates", CheckForUpdatesCommand())


def add_to_bnc_menu():
    def _add():
        try:
            mw = FreeCADGui.getMainWindow()
            if not mw:
                QtCore.QTimer.singleShot(1000, _add)
                return

            menu_bar = mw.menuBar()
            bnc_menu = None
            for action in menu_bar.actions():
                try:
                    if action.text() == "&BNC":
                        bnc_menu = action.menu()
                        break
                except RuntimeError:
                    continue

            if not bnc_menu:
                windows_action = None
                for action in menu_bar.actions():
                    try:
                        if action.text() and "Window" in action.text():
                            windows_action = action
                            break
                    except RuntimeError:
                        continue
                bnc_menu = QtGui.QMenu("&BNC", mw)
                if windows_action:
                    menu_bar.insertMenu(windows_action, bnc_menu)
                else:
                    menu_bar.addMenu(bnc_menu)

            for action in bnc_menu.actions():
                try:
                    if action.text() == "Check for Updates...":
                        return
                except RuntimeError:
                    return

            update_action = QtGui.QAction("Check for Updates...", mw)
            icon_path = os.path.join(os.path.dirname(__file__),
                                     "Resources", "icons", "update-icon.svg")
            if os.path.exists(icon_path):
                update_action.setIcon(QtGui.QIcon(icon_path))
            update_action.setShortcut(QtGui.QKeySequence("Ctrl+U"))
            update_action.triggered.connect(
                lambda: FreeCADGui.runCommand("BNC_CheckForUpdates"))
            bnc_menu.addAction(update_action)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"BNC: Failed to create BNC menu: {exc}\n")

    QtCore.QTimer.singleShot(3000, _add)


try:
    register_command()
    add_to_bnc_menu()
except Exception as e:
    FreeCAD.Console.PrintError(f"BNC: Failed to register Check for Updates: {e}\n")
