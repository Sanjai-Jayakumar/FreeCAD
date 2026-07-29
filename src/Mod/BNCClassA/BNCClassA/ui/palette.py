# SPDX-License-Identifier: LGPL-2.1-or-later
"""Class-A tool palette — dockable thumbnail grid (adapted from the BNCGSD
ModeSwitchPanel pattern, vendored so BNCClassA stays standalone)."""
import FreeCADGui as Gui

from BNCClassA import icon
from .qtcompat import (QtWidgets, QtCore, QtGui, Qt, TEXT_UNDER_ICON,
                       SCROLL_AS_NEEDED, SCROLL_OFF, NO_FRAME)

_GROUPS = [
    ("Curves", "#1b6b3a", [
        ("BNCClassA_CVCurve", "CV\nCurve"),
        ("BNCClassA_EditCurve", "Edit\nCurve"),
        ("BNCClassA_RebuildCurve", "Rebuild\nCurve"),
        ("BNCClassA_BlendCurve", "Blend\nCurve"),
        ("BNCClassA_ProjectCurve", "Project\nCurve"),
        ("BNCClassA_ExtractIso", "Extract\nIsoparm"),
    ]),
    ("Surfaces", "#0077b6", [
        ("BNCClassA_Extrude", "Extrude"),
        ("BNCClassA_Revolve", "Revolve"),
        ("BNCClassA_Loft", "Loft"),
        ("BNCClassA_Birail", "Birail"),
        ("BNCClassA_SquarePatch", "Square\nPatch"),
        ("BNCClassA_FreeformBlend", "Freeform\nBlend"),
        ("BNCClassA_Fillet", "Class-A\nFillet"),
    ]),
    ("Edit", "#b05a00", [
        ("BNCClassA_EditSurface", "Edit\nSurface"),
        ("BNCClassA_MatchSurface", "Match\nSurface"),
        ("BNCClassA_Extend", "Extend"),
        ("BNCClassA_Trim", "Trim"),
        ("BNCClassA_Untrim", "Untrim"),
        ("BNCClassA_RebuildSurface", "Rebuild\nSurface"),
        ("BNCClassA_Mirror", "Mirror"),
        ("BNCClassA_Bake", "Bake to\nCV Surf"),
    ]),
    ("Evaluate", "#6a0572", [
        ("BNCClassA_Comb", "Curvature\nComb"),
        ("BNCClassA_Zebra", "Zebra"),
        ("BNCClassA_Highlight", "Highlight\nLines"),
        ("BNCClassA_CurvatureMap", "Curvature\nMap"),
        ("BNCClassA_EnvMap", "Env\nMap"),
        ("BNCClassA_ContinuityCheck", "Continuity\nCheck"),
        ("BNCClassA_Deviation", "Deviation"),
        ("BNCMold_DraftAnalysis", "Draft\nAnalysis"),
    ]),
]

_ICON_PX = 32
_BTN_W = 75
_BTN_H = 68
_COLS = 4
_PANEL_W = 320

_panel = None


def _command_icon(cmd_name):
    """Icon for a command: our own SVG set first, then the live QAction."""
    guess = "ClassA" + cmd_name.split("_", 1)[-1]
    path = icon(guess)
    ic = QtGui.QIcon(path)
    if not ic.isNull() and ic.availableSizes():
        return ic
    try:
        action = Gui.Command.get(cmd_name).getAction()[0]
        if action and not action.icon().isNull():
            return action.icon()
    except Exception:
        pass
    return QtGui.QIcon(icon("BNCClassA"))


class ClassAPalette(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super(ClassAPalette, self).__init__("Class-A Tools", parent)
        self.setObjectName("BNCClassAPalette")
        self.setFixedWidth(_PANEL_W)
        tabs = QtWidgets.QTabWidget()
        known = set(Gui.listCommands())
        for title, accent, cmds in _GROUPS:
            page = QtWidgets.QScrollArea()
            page.setFrameShape(NO_FRAME)
            page.setWidgetResizable(True)
            page.setHorizontalScrollBarPolicy(SCROLL_OFF)
            page.setVerticalScrollBarPolicy(SCROLL_AS_NEEDED)
            inner = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(inner)
            grid.setSpacing(4)
            grid.setContentsMargins(6, 8, 6, 8)
            row = col = 0
            for cmd, label in cmds:
                if cmd not in known:
                    continue
                btn = QtWidgets.QToolButton()
                btn.setText(label)
                btn.setIcon(_command_icon(cmd))
                btn.setIconSize(QtCore.QSize(_ICON_PX, _ICON_PX))
                btn.setToolButtonStyle(TEXT_UNDER_ICON)
                btn.setFixedSize(_BTN_W, _BTN_H)
                btn.setStyleSheet(
                    "QToolButton { border: 1px solid transparent; border-radius: 6px; }"
                    "QToolButton:hover { border-color: %s; }" % accent)
                btn.clicked.connect(lambda _c=False, name=cmd: Gui.runCommand(name, 0))
                grid.addWidget(btn, row, col)
                col += 1
                if col >= _COLS:
                    col, row = 0, row + 1
            grid.setRowStretch(row + 1, 1)
            page.setWidget(inner)
            tabs.addTab(page, title)
        self.setWidget(tabs)


def show():
    global _panel
    mw = Gui.getMainWindow()
    if mw is None:
        return
    if _panel is None:
        _panel = ClassAPalette(mw)
        mw.addDockWidget(Qt.RightDockWidgetArea
                         if hasattr(Qt, "RightDockWidgetArea")
                         else Qt.DockWidgetArea.RightDockWidgetArea, _panel)
    _panel.show()


def hide():
    if _panel is not None:
        _panel.hide()
