"""
panels/ModeSwitchPanel.py — BNC GSD left-side tool palette (thumbnail grid).

Four tabs: Surface | Curves | Shapes | Analysis
Each tab: 2-column thumbnail grid — large icon on top, dark label below.
"""

from __future__ import annotations
import os
import FreeCAD    as App
import FreeCADGui as Gui

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    _Qt        = QtCore.Qt
    _TextUnder = _Qt.ToolButtonTextUnderIcon
    _ScrollOn  = _Qt.ScrollBarAsNeeded
    _ScrollOff = _Qt.ScrollBarAlwaysOff
    _NoFrame   = QtWidgets.QFrame.NoFrame
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    _Qt        = QtCore.Qt
    _TextUnder = _Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    _ScrollOn  = _Qt.ScrollBarPolicy.ScrollBarAsNeeded
    _ScrollOff = _Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    _NoFrame   = QtWidgets.QFrame.Shape.NoFrame

# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------
_LABEL: dict[str, str] = {
    "Surface_Filling":         "Filling",
    "Surface_GeomFillSurface": "GeomFill",
    "Surface_Sections":        "Sections",
    "Surface_Extend":          "Extend",
    "Surface_CurveOnMesh":     "Curve on\nMesh",
    "Surface_BlendCurve":      "Blend\nCurve",
    "Curves_line":             "Line",
    "mixed_curve":             "Mixed\nCurve",
    "extend":                  "Extend\nCurve",
    "join":                    "Join\nCurves",
    "split":                   "Split\nCurve",
    "Discretize":              "Discretize",
    "Approximate":             "Approx.",
    "Interpolate":             "Interpolate",
    "ParametricBlendCurve":    "Blend\nCurve",
    "ParametricComb":          "Param.\nComb",
    "sw2r":                    "Sweep\n2 Rails",
    "gordon":                  "Gordon\nSurface",
    "MultiLoft":               "Multi\nLoft",
    "Curves_BlendSurf2":       "Blend\nSurface",
    "Curves_BlendSolid":       "Blend\nSolid",
    "IsoCurve":                "Iso\nCurve",
    "Trim":                    "Trim\nFace",
    "ReflectLines":            "Reflect\nLines",
    "Curves_FlattenFace":      "Flatten\nFace",
    "Curves_RotationSweep":    "Rotation\nSweep",
    "Curves_SurfaceAnalysis":  "Surface\nAnalysis",
    "Curves_DraftAnalysis":    "Draft\nAnalysis",
    "ZebraTool":               "Zebra\nTool",
    "Curves_WaterlineCurves":  "Waterline\nCurves",
    "BNCMold_DraftAnalysis":   "Draft\nAnalysis",
    "CurvedArray":             "Curved\nArray",
    "CurvedPathArray":         "Path\nArray",
    "CurvedSegment":           "Curved\nSegment",
    "CurvedPathSegment":       "Path\nSegment",
    "InterpolatedMiddle":      "Interp.\nMiddle",
    "SurfaceCut":              "Surface\nCut",
    "NotchConnector":          "Notch\nConnect.",
    "GSD_CurvatureComb":       "Curvature\nComb",
    "GSD_ZebraAnalysis":       "Zebra\nAnalysis",
    "GSD_ContinuityInspector": "Continuity\nInspect.",
    "GSD_Validation":          "Validation",
}

_ACCENT: dict[str, str] = {
    "Surface":       "#0077b6",
    "Curves":        "#1b6b3a",
    "Curved Shapes": "#6a0572",
    "Analysis":      "#b05a00",
}
_TILE: dict[str, str] = {
    "Surface":       "#caf0f8",
    "Curves":        "#d8f3dc",
    "Curved Shapes": "#ead7f7",
    "Analysis":      "#ffe8cc",
}

_TAB_LABEL: dict[str, str] = {
    "Surface":       "Surface",
    "Curves":        "Curves",
    "Curved Shapes": "Shapes",
    "Analysis":      "Analysis",
}

# BNC theme blue — used for ALL tab headings (uniform) and the selected-tab
# underline. Matches branding AccentColor: light "#1565c0", dark "#89b4fa".
_BNC_BLUE_LIGHT = "#1565c0"
_BNC_BLUE_DARK  = "#89b4fa"


def _bnc_blue() -> str:
    """Theme-aware BNC accent blue (picks the dark-theme tint on dark UIs)."""
    try:
        mw = Gui.getMainWindow()
        if mw is not None and mw.palette().color(QtGui.QPalette.Window).lightness() < 128:
            return _BNC_BLUE_DARK
    except Exception:
        pass
    return _BNC_BLUE_LIGHT

_ICON_PX  = 32    # thumbnail icon size
_BTN_W    = 75    # button width
_BTN_H    = 68    # button height
_COLS     = 4     # columns in the grid
_PANEL_W  = 320   # dock width  (_COLS * _BTN_W + margins)


class ModeSwitchPanel(QtWidgets.QDockWidget):
    """Left-side BNC GSD tool palette — thumbnail grid, one tab per mode."""

    def __init__(self, modes: dict[str, list[str]], parent=None):
        super().__init__("BNC GSD Tools", parent)
        self.setObjectName("BNCGSDToolPalette")
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable   |
            QtWidgets.QDockWidget.DockWidgetFloatable |
            QtWidgets.QDockWidget.DockWidgetClosable
        )

        self._available = set(Gui.listCommands())

        blue = _bnc_blue()
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setTabPosition(QtWidgets.QTabWidget.North)
        tabs.setUsesScrollButtons(False)
        tabs.setStyleSheet(
            "QTabWidget::pane { border: none; }"
            "QTabBar::tab {"
            "  padding: 6px 12px;"
            "  font-size: 11px;"
            "  font-weight: bold;"
            f"  color: {blue};"
            "  margin-right: 2px;"
            "}"
            "QTabBar::tab:selected {"
            f"  color: {blue};"
            f"  border-bottom: 3px solid {blue};"
            "}"
        )

        for idx, (name, cmds) in enumerate(modes.items()):
            scroll     = self._build_grid(cmds, name)
            short_name = _TAB_LABEL.get(name, name)
            tabs.addTab(scroll, short_name)
            # Uniform BNC theme blue for every tab heading.
            tabs.tabBar().setTabTextColor(idx, QtGui.QColor(blue))

        self.setWidget(tabs)
        self.setMinimumWidth(_PANEL_W)
        self.setMaximumWidth(_PANEL_W + 60)

    # ----------------------------------------------------------------- grid

    def _build_grid(self, cmds: list[str], mode: str) -> QtWidgets.QScrollArea:
        tile = _TILE.get(mode, "#ddd")

        inner  = QtWidgets.QWidget()
        grid   = QtWidgets.QGridLayout(inner)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(4)
        grid.setAlignment(_Qt.AlignTop | _Qt.AlignLeft)

        col = 0
        row = 0
        added = 0

        for cmd in cmds:
            btn = self._make_btn(cmd, tile, mode)
            if btn:
                grid.addWidget(btn, row, col)
                col += 1
                if col >= _COLS:
                    col = 0
                    row += 1
                added += 1

        if added == 0:
            lbl = QtWidgets.QLabel(
                "Workbench not installed.\n"
                "Use Add-on Manager to install it."
            )
            lbl.setStyleSheet("color:#555; font-style:italic; padding:10px; font-size:10px;")
            lbl.setWordWrap(True)
            grid.addWidget(lbl, 0, 0, 1, _COLS)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(_ScrollOff)
        scroll.setVerticalScrollBarPolicy(_ScrollOn)
        scroll.setFrameShape(_NoFrame)
        return scroll

    # ----------------------------------------------------------------- button

    def _make_btn(self, cmd: str, tile_color: str, mode: str) -> QtWidgets.QToolButton | None:
        if cmd not in self._available:
            return None

        info: dict = {}
        try:
            c = Gui.Command.get(cmd)
            if c:
                info = c.getInfo()
        except Exception:
            pass

        label   = _LABEL.get(cmd) or info.get("MenuText", cmd) or cmd
        tooltip = info.get("ToolTip", "") or label
        accent  = _ACCENT.get(mode, "#0077b6")

        btn = QtWidgets.QToolButton()
        btn.setToolButtonStyle(_TextUnder)
        btn.setIconSize(QtCore.QSize(_ICON_PX, _ICON_PX))
        btn.setFixedSize(_BTN_W, _BTN_H)
        btn.setText(label)
        btn.setToolTip(f"<b>{info.get('MenuText', label)}</b><hr><small>{tooltip}</small>")

        # Explicit dark text — never inherit white from dark themes
        btn.setStyleSheet(
            "QToolButton {"
            "  color: #222222;"
            "  font-size: 9px;"
            "  text-align: center;"
            "  border: 1px solid transparent;"
            "  border-radius: 5px;"
            "  background: transparent;"
            "  padding: 2px;"
            "}"
            f"QToolButton:hover  {{ border: 1px solid {accent}; background: rgba(0,119,182,0.08); }}"
            "QToolButton:pressed { background: rgba(0,119,182,0.18); }"
        )

        btn.setIcon(_load_icon(cmd, info.get("Pixmap", ""), tile_color))
        btn.clicked.connect(lambda _=False, c=cmd: _run(c))
        return btn


# ---------------------------------------------------------------------------
# Icon loading — 5 strategies
# ---------------------------------------------------------------------------

def _load_icon(cmd_name: str, pixmap_src: str, fallback_color: str) -> QtGui.QIcon:
    # 1) Live QAction icon — already resolved by FreeCAD
    try:
        cmd_obj = Gui.Command.get(cmd_name)
        if cmd_obj:
            actions = cmd_obj.getAction()
            if actions:
                icon = actions[0].icon()
                if icon and not icon.isNull():
                    return icon
    except Exception:
        pass

    if pixmap_src:
        # 2) BitmapFactory — full source
        try:
            pm = Gui.BitmapFactory.pixmap(pixmap_src)
            if pm and not pm.isNull():
                return QtGui.QIcon(pm)
        except Exception:
            pass

        # 3) BitmapFactory — bare name (no path, no extension)
        try:
            bare = os.path.splitext(os.path.basename(pixmap_src))[0]
            if bare and bare != pixmap_src:
                pm = Gui.BitmapFactory.pixmap(bare)
                if pm and not pm.isNull():
                    return QtGui.QIcon(pm)
        except Exception:
            pass

        # 4) Direct file path
        if os.path.isfile(pixmap_src):
            icon = QtGui.QIcon(pixmap_src)
            if not icon.isNull():
                return icon

        # 5) Qt resource string
        icon = QtGui.QIcon(pixmap_src)
        if not icon.isNull():
            return icon

    # Fallback — mode-coloured tile
    pm = QtGui.QPixmap(_ICON_PX, _ICON_PX)
    pm.fill(QtGui.QColor(fallback_color))
    return QtGui.QIcon(pm)


# ---------------------------------------------------------------------------

def _run(cmd: str) -> None:
    try:
        Gui.runCommand(cmd, 0)
    except Exception as exc:
        App.Console.PrintError(f"BNC GSD: error running '{cmd}': {exc}\n")
