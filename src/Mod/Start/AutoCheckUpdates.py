# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Calls the update API ONCE on launch, then stops (no repeated polling).
Uses only QTimer.singleShot (static) so no QTimer instance is stored in Python
— avoiding FreeCAD's GC-kills-QObject bug.

The update check runs on a background thread and posts its result to a queue;
a short, self-terminating drain reads that result on the main thread and then
stops. The menu "Check for Updates" command can still call run_check() any time.
"""
import queue
import FreeCAD

try:
    from PySide2 import QtCore
except ImportError:
    from PySide import QtCore

_result_queue    = queue.Queue()
_polling_started = False
_polling_stopped = False   # set to True when user dismisses banner
_drain_active    = False
_drain_ticks     = 0
_MAX_DRAIN_TICKS = 60      # safety stop (~60 s) if no result ever arrives


# ── result handling (always in main thread via queue drain) ─────────────────

def _handle_result(result):
    try:
        import UpdateUI
        if result.get("update_available"):
            ver = result.get("latest_version", "")
            msg = (f"ANVIL CAD {ver} is available — please update."
                   if ver else "A new version of ANVIL CAD is available.")
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


# ── self-terminating drain (1 s tick, stops once the result is handled) ──────

def _drain_once():
    global _drain_ticks, _drain_active
    handled = False
    try:
        while True:
            _handle_result(_result_queue.get_nowait())
            handled = True
    except queue.Empty:
        pass
    _drain_ticks += 1
    # one check yields one result → stop as soon as it is handled (or time out)
    if handled or _drain_ticks >= _MAX_DRAIN_TICKS:
        _drain_active = False
        return
    QtCore.QTimer.singleShot(1000, _drain_once)


def _start_drain():
    """Begin (or restart) the bounded drain that handles the next result."""
    global _drain_active, _drain_ticks
    _drain_ticks = 0
    if _drain_active:
        return
    _drain_active = True
    QtCore.QTimer.singleShot(500, _drain_once)


# ── public API ───────────────────────────────────────────────────────────────

def run_check():
    """Run a single update check now (used by both launch and the menu button)."""
    FreeCAD.Console.PrintMessage("BNC: Checking for updates...\n")
    try:
        import UpdateChecker
        UpdateChecker.check_for_updates_async(_on_result)
        _start_drain()
    except Exception as exc:
        FreeCAD.Console.PrintError(f"BNC: Update check error: {exc}\n")


def stop_update_polling():
    """Kept for UpdateUI compatibility (called when user dismisses the banner)."""
    global _polling_stopped
    _polling_stopped = True


def start_update_polling():
    """Call once from InitGui.py. Runs a SINGLE update check on launch — no repeat."""
    global _polling_started
    if _polling_started:
        return
    _polling_started = True
    QtCore.QTimer.singleShot(5000, run_check)
    FreeCAD.Console.PrintMessage("BNC: Update check scheduled (one-time)\n")
