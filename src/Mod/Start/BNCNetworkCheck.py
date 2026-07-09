# -*- coding: utf-8 -*-
"""ANVIL CAD: Network connectivity checker — non-blocking.

Checks internet on startup and every 5 minutes.
If offline, logs a warning to the console only (does NOT block the UI).
"""

import os
import FreeCAD

from PySide import QtCore, QtGui
try:
    from PySide import QtWidgets
except ImportError:
    QtWidgets = QtGui

# ─── Configuration ────────────────────────────────────────────────────────────
_CHECK_URL          = "https://bnc-ai.com"
_CHECK_INTERVAL_MS  = 5 * 60 * 1000   # 5 minutes
_CONNECT_TIMEOUT    = 5               # seconds — short so startup isn't delayed

_timer = None   # QTimer kept alive at module level


def _has_internet():
    """Return True if we can reach the BNC server within the timeout."""
    try:
        import urllib.request
        req = urllib.request.Request(_CHECK_URL, method="HEAD")
        urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT)
        return True
    except Exception:
        return False


def check_startup():
    """Called once at startup — non-blocking.
    Logs a warning if offline but does NOT show a blocking dialog."""
    FreeCAD.Console.PrintLog("ANVIL CAD: Checking internet connection...\n")
    if _has_internet():
        FreeCAD.Console.PrintLog("ANVIL CAD: Internet connection OK\n")
        return True
    FreeCAD.Console.PrintWarning(
        "ANVIL CAD: No internet connection detected. "
        "Some online features may be unavailable.\n")
    return False   # non-blocking — ANVIL CAD continues normally


def _periodic_check():
    """Called every 5 minutes — logs warning only, never blocks."""
    if _has_internet():
        return
    FreeCAD.Console.PrintWarning(
        "ANVIL CAD: Internet connection lost. "
        "Some online features may be unavailable.\n")


def init():
    """Start the periodic connectivity timer. Called from InitGui.py."""
    check_startup()
    start_periodic_check()


def start_periodic_check():
    """Start the recurring 5-minute connectivity timer."""
    global _timer
    if _timer is not None:
        return
    _timer = QtCore.QTimer()
    _timer.timeout.connect(_periodic_check)
    _timer.start(_CHECK_INTERVAL_MS)
    FreeCAD.Console.PrintLog("ANVIL CAD: Network check timer started (every 5 min)\n")
