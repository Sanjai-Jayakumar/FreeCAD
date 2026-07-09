# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 ANVIL CAD                                            *
# *                                                                         *
# *   This file is part of ANVIL CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Hide Help menu and enforce ANVIL CAD branding in menubar text"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

_help_hidden = False
_runtime_timer = None


def _normalize(text):
    if not text:
        return ""
    return text.replace("&", "").strip().lower()


def _is_help_menu_action(action):
    try:
        menu = action.menu() if action else None
        title = _normalize(menu.title() if menu else "")
        text = _normalize(action.text() if action else "")
        obj = _normalize(action.objectName() if action else "")

        if title in ("help", "?") or text in ("help", "?"):
            return True
        if "help" in title or "help" in text or "help" in obj:
            return True

        if menu:
            for sub_action in menu.actions():
                sub_text = _normalize(sub_action.text())
                sub_obj = _normalize(sub_action.objectName())
                if "about" in sub_text and "freecad" in sub_text:
                    return True
                if "std_about" in sub_obj or "std_help" in sub_obj:
                    return True
    except Exception:
        return False

    return False


def _replace_freecad_text(action):
    try:
        if not action:
            return
        current = action.text()
        if current and "FreeCAD" in current:
            action.setText(current.replace("FreeCAD", "ANVIL CAD"))

        menu = action.menu()
        if menu:
            menu_title = menu.title()
            if menu_title and "FreeCAD" in menu_title:
                menu.setTitle(menu_title.replace("FreeCAD", "ANVIL CAD"))

            for sub_action in menu.actions():
                sub_text = sub_action.text()
                if sub_text and "FreeCAD" in sub_text:
                    sub_action.setText(sub_text.replace("FreeCAD", "ANVIL CAD"))
    except Exception:
        pass

def hide_help_menu():
    """Hide the Help menu from the menubar and enforce visible BNC branding"""
    global _help_hidden

    try:
        # Wait for GUI to be ready
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, hide_help_menu)
            return

        # Get the menubar
        menubar = mw.menuBar()
        if not menubar:
            FreeCAD.Console.PrintWarning("ANVIL CAD: Could not access menubar\n")
            return

        help_found = False
        actions = list(menubar.actions())

        for action in actions:
            _replace_freecad_text(action)

            if _is_help_menu_action(action):
                try:
                    menu = action.menu()
                    if menu:
                        menu.clear()
                        menu.setVisible(False)
                    action.setVisible(False)
                    menubar.removeAction(action)
                    help_found = True
                except Exception:
                    pass

        # Also check all child menus in case action removal is delayed by Qt
        for menu in mw.findChildren(QtGui.QMenu):
            title = _normalize(menu.title())
            if title in ("help", "?") or "help" in title:
                menu.setVisible(False)
                menu.menuAction().setVisible(False)
                help_found = True

        if help_found:
            _help_hidden = True
            # Message removed to reduce console noise
        else:
            _help_hidden = False

        # Keep application/window title branded
        if "FreeCAD" in mw.windowTitle():
            mw.setWindowTitle(mw.windowTitle().replace("FreeCAD", "ANVIL CAD"))

        app = QtGui.QApplication.instance()
        if app and app.applicationName() and "FreeCAD" in app.applicationName():
            app.setApplicationName(app.applicationName().replace("FreeCAD", "ANVIL CAD"))

    except Exception as e:
        FreeCAD.Console.PrintError(f"ANVIL CAD: Error hiding Help menu: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())

# Hide Help menu after GUI is fully loaded - keep enforcing at runtime
QtCore.QTimer.singleShot(1000, hide_help_menu)
QtCore.QTimer.singleShot(2500, hide_help_menu)
QtCore.QTimer.singleShot(5000, hide_help_menu)

_runtime_timer = QtCore.QTimer()
_runtime_timer.setInterval(1500)
_runtime_timer.timeout.connect(hide_help_menu)
_runtime_timer.start()

FreeCAD.Console.PrintLog("ANVIL CAD: Help menu hide module loaded\n")
