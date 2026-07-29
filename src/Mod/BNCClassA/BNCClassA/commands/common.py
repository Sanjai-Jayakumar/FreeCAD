# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared command boilerplate."""
import FreeCAD
import FreeCADGui as Gui

from BNCClassA import icon


class CommandBase(object):
    """Minimal FreeCAD command: subclasses set NAME/ICON/MENU/TIP and
    implement Activated (or set PANEL to a task-panel class)."""
    NAME = None
    ICON = None
    MENU = ""
    TIP = ""
    PANEL = None

    def GetResources(self):
        return {
            "Pixmap": icon(self.ICON or self.NAME),
            "MenuText": self.MENU,
            "ToolTip": self.TIP,
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        if self.PANEL is not None:
            from BNCClassA.ui.panels import show_panel
            show_panel(self.PANEL())


def register(cls):
    """Class decorator: Gui.addCommand under cls.NAME (guarded)."""
    if cls.NAME not in Gui.listCommands():
        Gui.addCommand(cls.NAME, cls())
    return cls
