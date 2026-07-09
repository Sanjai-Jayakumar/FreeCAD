"""
ANVIL CAD Macro Setup

Binds the BNC file-operation keyboard shortcuts and auto-runs the Selection
Filter widget on startup.

IMPORTANT: the BNC macros live ONLY in the application macro directory
(<FreeCAD home>/Macro), NOT in the user macro directory. That keeps the user's
"Execute Macro" list clean — only macros the USER creates show up there. The
toolbar buttons and the shortcuts below run the BNC macros straight from the
app macro dir by file path, so they work without polluting the user list.
"""

import os
import FreeCAD
import FreeCADGui

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:                       # PySide2 fallback
    from PySide2 import QtCore, QtGui, QtWidgets

# QAction moved from QtWidgets (PySide2/Qt5) to QtGui (PySide6/Qt6).
QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction

_MACRO_DIR = os.path.join(FreeCAD.getHomePath(), "Macro")

# macro file -> (accelerator, label, native commands whose shortcut to release
# so the BNC macro owns the key — prevents a Qt "ambiguous shortcut" clash).
_SHORTCUTS = [
    ("SetWorkingDirectory.FCMacro", "Ctrl+Shift+W", "BNC Set Working Directory", []),
    ("New_File.FCMacro",            "Ctrl+N",       "BNC New File",   ["Std_New"]),
    ("Save.FCMacro",                "Ctrl+S",       "BNC Save",       ["Std_Save"]),
    ("Save_As.FCMacro",             "Ctrl+Shift+S", "BNC Save As",    ["Std_SaveAs"]),
    ("OPEN_File.FCMacro",           "Ctrl+O",       "BNC Open File",  ["Std_Open"]),
]

# keep references so the QActions are not garbage-collected
_bnc_actions = []


def _run_macro_file(path):
    """Execute a macro file in a fresh __main__ namespace (like the toolbar buttons)."""
    try:
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), path, "exec"), {"__name__": "__main__"})
    except Exception as exc:
        import traceback
        FreeCAD.Console.PrintError(
            "BNC macro error (%s): %s\n" % (os.path.basename(path), exc))
        FreeCAD.Console.PrintError(traceback.format_exc())


def _clear_native_shortcut(mw, accel):
    """Release `accel` from any existing QAction so the BNC action owns it
    (avoids Qt ambiguous-shortcut, which would disable the key entirely)."""
    try:
        seq = QtGui.QKeySequence(accel)
        for act in mw.findChildren(QAction):
            try:
                if act in _bnc_actions:
                    continue
                for sc in act.shortcuts():
                    if sc == seq:
                        act.setShortcuts([])
                        break
            except Exception:
                pass
    except Exception:
        pass


def setup_bnc_shortcuts():
    mw = FreeCADGui.getMainWindow()
    if mw is None or not os.path.isdir(_MACRO_DIR):
        return
    sc_param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Shortcut")
    for macro, accel, label, clear_cmds in _SHORTCUTS:
        path = os.path.join(_MACRO_DIR, macro)
        if not os.path.isfile(path):
            continue
        # release the key from native commands (persistent param)
        for cmd in clear_cmds:
            try:
                sc_param.SetString(cmd, "")
            except Exception:
                pass
        # drop the stale MacroPath-based execute shortcut (the macro is no
        # longer in the user macro dir, so that command no longer exists)
        try:
            sc_param.RemString("Std_DlgMacroExecute_" + macro)
        except Exception:
            pass
        # release the key from any live native action this session
        _clear_native_shortcut(mw, accel)

        act = QAction(label, mw)
        act.setShortcut(QtGui.QKeySequence(accel))
        act.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        act.triggered.connect(lambda checked=False, p=path: _run_macro_file(p))
        mw.addAction(act)
        _bnc_actions.append(act)


def auto_run_selection_filter():
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            return
        setattr(mw, '_sel_filter_auto_run', True)
        macro_path = os.path.join(_MACRO_DIR, "SelectionFilter.FCMacro")
        if os.path.exists(macro_path):
            with open(macro_path, encoding="utf-8") as f:
                exec(f.read(), {"__name__": "__main__"})
        setattr(mw, '_sel_filter_auto_run', False)
    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError("Failed to load Selection Filter: " + str(e) + "\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


try:
    # Delay until the main window + native command actions exist, so clearing
    # the native shortcuts and registering ours takes effect this session.
    QtCore.QTimer.singleShot(1500, setup_bnc_shortcuts)
    QtCore.QTimer.singleShot(2000, auto_run_selection_filter)
except Exception as e:
    import traceback
    FreeCAD.Console.PrintError("BNC Macro setup failed: " + str(e) + "\n")
    FreeCAD.Console.PrintError(traceback.format_exc())
