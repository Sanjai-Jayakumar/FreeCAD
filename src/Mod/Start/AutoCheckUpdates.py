# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Calls the update API on launch then repeats every _CHECK_INTERVAL_MS.
Uses only QTimer.singleShot (static) in a self-rescheduling pattern so no
QTimer instance is stored in Python — avoiding FreeCAD's GC-kills-QObject bug.

When the user dismisses the banner, polling is stopped permanently for the
session (call stop_update_polling() from UpdateUI).
"""
import queue
import FreeCAD

try:
    from PySide2 import QtCore
except ImportError:
    from PySide import QtCore

_CHECK_INTERVAL_MS = 2 * 60 * 1000   # <-- adjust polling interval here

_result_queue    = queue.Queue()
_polling_started = False
_polling_stopped = False   # set to True when user dismisses banner


# ── result handling (always in main thread via queue drain) ─────────────────

def _handle_result(result):
    try:
        import UpdateUI
        if result.get("update_available"):
            ver = result.get("latest_version", "")
            msg = (f"BNC CAD {ver} is available — please update."
                   if ver else "A new version of BNC CAD is available.")
            url = result.get("download_url", "")
            FreeCAD.Console.PrintMessage(f"BNC: Update available — {msg}\n")
            UpdateUI.show_update_banner(msg, url)
        else:
            UpdateUI.hide_update_banner()
            if result.get("error"):
                FreeCAD.Console.PrintMessage(
                    f"BNC: Update check error: {result['error']}\n")
            else:
                FreeCAD.Console.PrintMessage("BNC: Software is up to date\n")
    except Exception as exc:
        FreeCAD.Console.PrintError(f"BNC: Update handler error: {exc}\n")


def _on_result(result):
    """Background thread callback — only touches the Python queue, never Qt."""
    _result_queue.put(result)


# ── self-rescheduling drain (1 s tick) ──────────────────────────────────────

def _drain_and_reschedule():
    if _polling_stopped:
        return
    try:
        while True:
            result = _result_queue.get_nowait()
            _handle_result(result)
    except queue.Empty:
        pass
    QtCore.QTimer.singleShot(1000, _drain_and_reschedule)


# ── self-rescheduling API check ─────────────────────────────────────────────

def _check_and_reschedule():
    if _polling_stopped:
        return
    run_check()
    QtCore.QTimer.singleShot(_CHECK_INTERVAL_MS, _check_and_reschedule)


# ── public API ───────────────────────────────────────────────────────────────

def run_check():
    """Run a single update check now (used by both the timer and the menu button)."""
    FreeCAD.Console.PrintMessage("BNC: Checking for updates...\n")
    try:
        import UpdateChecker
        UpdateChecker.check_for_updates_async(_on_result)
    except Exception as exc:
        FreeCAD.Console.PrintError(f"BNC: Update check error: {exc}\n")


def stop_update_polling():
    """Stop all future auto-checks (called when user dismisses the banner)."""
    global _polling_stopped
    _polling_stopped = True
    FreeCAD.Console.PrintMessage("BNC: Update polling stopped by user\n")


def start_update_polling():
    """Call once from InitGui.py. Fires on launch then repeats."""
    global _polling_started, _polling_stopped
    if _polling_started:
        return
    _polling_started = True
    _polling_stopped = False

    QtCore.QTimer.singleShot(1000, _drain_and_reschedule)
    QtCore.QTimer.singleShot(5000, _check_and_reschedule)
    FreeCAD.Console.PrintMessage("BNC: Update polling started\n")
