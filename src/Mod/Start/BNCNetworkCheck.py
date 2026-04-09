# -*- coding: utf-8 -*-
"""BNC CAD: Network connectivity checker.

- On startup: blocks until internet is available (shows retry dialog).
- Every 5 minutes: rechecks; if offline, shows a blocking dialog.

Imported from InitGui.py.  Lives in its own module so that all objects
survive FreeCAD's exec() scope cleanup.
"""

import os
import FreeCAD

from PySide import QtCore, QtGui
try:
    from PySide import QtWidgets
except ImportError:
    QtWidgets = QtGui

# ─── Configuration ────────────────────────────────────────────────────────────
_CHECK_URL = "https://bnc-ai.com"
_CHECK_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes
_CONNECT_TIMEOUT = 10  # seconds

_timer = None  # QTimer reference kept alive at module level


def _has_internet():
    """Return True if we can reach the BNC server."""
    try:
        import urllib.request
        req = urllib.request.Request(_CHECK_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT)
        return True
    except Exception:
        return False


def _show_no_internet_dialog():
    """Show a blocking dialog until the user clicks Retry and internet is back."""
    mw = None
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
    except Exception:
        pass

    while True:
        dlg = QtWidgets.QMessageBox(mw)
        dlg.setWindowTitle("BNC CAD")
        dlg.setIcon(QtWidgets.QMessageBox.Warning)
        dlg.setText("No internet connection detected.\n\n"
                    "BNC CAD requires an active internet connection.\n"
                    "Please check your network and try again.")
        retry_btn = dlg.addButton("Retry", QtWidgets.QMessageBox.AcceptRole)
        exit_btn = dlg.addButton("Exit", QtWidgets.QMessageBox.RejectRole)
        dlg.setDefaultButton(retry_btn)
        if mw:
            dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        dlg.exec_()

        if dlg.clickedButton() == retry_btn:
            if _has_internet():
                FreeCAD.Console.PrintMessage("BNC CAD: Internet connection restored\n")
                return True
            # Still no internet — loop again
        else:
            # User chose Exit
            FreeCAD.Console.PrintMessage("BNC CAD: No internet — user chose to exit\n")
            QtWidgets.QApplication.instance().quit()
            return False


def check_startup():
    """Called once at startup. Blocks until internet is available or user exits."""
    FreeCAD.Console.PrintLog("BNC CAD: Checking internet connection...\n")
    if _has_internet():
        FreeCAD.Console.PrintLog("BNC CAD: Internet connection OK\n")
        return True
    FreeCAD.Console.PrintWarning("BNC CAD: No internet connection detected\n")
    return _show_no_internet_dialog()


def _periodic_check():
    """Called every 5 minutes by the timer."""
    if _has_internet():
        return
    FreeCAD.Console.PrintWarning("BNC CAD: Internet connection lost\n")
    _show_no_internet_dialog()


def init():
    """Start the periodic connectivity timer. Called from InitGui.py via QTimer."""
    # Initial startup check
    if not check_startup():
        return
    start_periodic_check()


def start_periodic_check():
    """Start the recurring 5-minute connectivity timer."""
    global _timer
    if _timer is not None:
        return  # already running
    _timer = QtCore.QTimer()
    _timer.timeout.connect(_periodic_check)
    _timer.start(_CHECK_INTERVAL_MS)
    FreeCAD.Console.PrintLog("BNC CAD: Network check timer started (every 5 min)\n")
