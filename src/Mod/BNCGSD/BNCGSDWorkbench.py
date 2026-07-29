"""
BNCGSDWorkbench.py — BNC Generative Surface Design Workbench.

Combines tools from four sources into one unified workbench:
  • Surface   — FreeCAD built-in surface creation tools (C++)
  • Curves    — NURBS curves & surfaces (community workbench)
  • Curved Shapes — 3D shapes from 2D curves (community workbench)
  • Analysis  — GSD surface quality analysis (BNC internal)

A dockable tab panel at the bottom lets the user switch between
the four modes without leaving the workbench.
"""

from __future__ import annotations
import os
import sys

import FreeCAD as App
import FreeCADGui as Gui

_WB_ROOT  = os.path.dirname(os.path.abspath(__file__))
_ICON_DIR = os.path.join(_WB_ROOT, "icons")

# ---------------------------------------------------------------------------
# Command lists — ordered for toolbar display.
# Commands that are not registered (optional workbenches missing) are silently
# skipped when building toolbars and menus.
# ---------------------------------------------------------------------------

SURFACE_CMDS = [
    "Surface_Filling",
    "Surface_GeomFillSurface",
    "Surface_Sections",
    "Surface_Extend",
    "Surface_CurveOnMesh",
    "Surface_BlendCurve",
]

CURVES_CMDS = [
    # Curve tools
    "Curves_line",
    "mixed_curve",
    "extend",
    "join",
    "split",
    "Discretize",
    "Approximate",
    "Interpolate",
    "ParametricBlendCurve",
    "ParametricComb",
    # Surface tools
    "sw2r",
    "gordon",
    "MultiLoft",
    "Curves_BlendSurf2",
    "Curves_BlendSolid",
    "IsoCurve",
    "Trim",
    "ReflectLines",
    "Curves_FlattenFace",
    "Curves_RotationSweep",
]
# NOTE: the analysis tools (Surface Analysis, Zebra, Waterline) live in the
# Analysis tab — see ANALYSIS_CMDS — not in the Curves tab.

CURVED_SHAPES_CMDS = [
    "CurvedArray",
    "CurvedPathArray",
    "CurvedSegment",
    "CurvedPathSegment",
    "InterpolatedMiddle",
    "SurfaceCut",
    "NotchConnector",
]

# Analysis tab: surface-quality tools drawn from the Curves workbench plus the
# BNC Mold Tools draft analysis (BNCMold_DraftAnalysis — registered by
# _load_mold_draft so it works without first visiting the Mold Tools WB).
ANALYSIS_CMDS = [
    "Curves_SurfaceAnalysis",
    "ZebraTool",
    "Curves_WaterlineCurves",
    "BNCMold_DraftAnalysis",
]

# Map mode name → command list (order defines tab order)
MODES: dict[str, list[str]] = {
    "Surface":       SURFACE_CMDS,
    "Curves":        CURVES_CMDS,
    "Curved Shapes": CURVED_SHAPES_CMDS,
    "Analysis":      ANALYSIS_CMDS,
}


# ---------------------------------------------------------------------------
# Workbench
# ---------------------------------------------------------------------------

class BNCGSDWorkbench(Gui.Workbench):

    MenuText = "GSD"
    ToolTip  = "Generative Surface Design — Combined Surface Modeling"
    Icon     = os.path.join(_ICON_DIR, "GSD.svg")

    # ------------------------------------------------------------------ init

    def Initialize(self):
        """Called once the first time this workbench is activated."""
        self._mode_panel = None

        self._load_surface()
        self._load_curves()
        self._load_curved_shapes()
        self._load_gsd_analysis()
        self._load_mold_draft()

        available = set(Gui.listCommands())

        def avail(cmds):
            return [c for c in cmds if c in available]

        # No bulk toolbars — the dockable tab panel (bottom) is the primary UI.
        # We expose only the menu so keyboard users can still reach every command.
        self.appendMenu(["&GSD", "Surface"],        avail(SURFACE_CMDS))
        self.appendMenu(["&GSD", "Curves"],         avail(CURVES_CMDS))
        self.appendMenu(["&GSD", "Curved Shapes"],  avail(CURVED_SHAPES_CMDS))
        self.appendMenu(["&GSD", "Analysis"],       avail(ANALYSIS_CMDS))

        App.Console.PrintLog("BNC GSD Workbench: initialized.\n")

    def Activated(self):
        self._show_mode_panel()
        App.Console.PrintLog("BNC GSD Workbench activated.\n")

    def Deactivated(self):
        self._hide_mode_panel()
        App.Console.PrintLog("BNC GSD Workbench deactivated.\n")

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    # ------------------------------------------------------------------ deps

    def _load_surface(self):
        """Import FreeCAD's built-in C++ Surface module to register its commands."""
        try:
            import Surface       # noqa: F401  — side-effect: registers C++ feature types
            import SurfaceGui    # noqa: F401  — side-effect: registers C++ commands
        except Exception as exc:
            App.Console.PrintWarning(f"BNC GSD: Surface workbench unavailable — {exc}\n")

    def _load_curves(self):
        """Import Curves workbench modules to register their commands."""
        try:
            # The Curves addon sits under the user Mod dir as a 'freecad.Curves' namespace pkg.
            _user_mod = os.path.join(App.getUserAppDataDir(), "Mod", "Curves")
            if os.path.isdir(_user_mod) and _user_mod not in sys.path:
                sys.path.insert(0, _user_mod)

            # Each module import calls Gui.addCommand() as a side effect.
            from freecad.Curves import (      # noqa: F401
                lineFP,
                gordon_profile_FP,
                curveExtendFP,
                JoinCurves,
                splitCurves_2,
                Discretize,
                approximate,
                ParametricBlendCurve,
                ParametricComb,
                ZebraTool,
                TrimFace,
                IsoCurve,
                Sweep2Rails,
                gordonFP,
                blendSurfaceFP_new,
                blendSolidFP,
                FlattenFP,
                RotationSweepFP,
                SurfaceAnalysisFP,
                DraftAnalysisFP,
                Truncate_Extend_FP,
                WaterLineFP,
                MapOnFaceFP,
                multiLoftFP,
                ReflectLinesFP,
                mixed_curve,
                interpolate,
            )
        except Exception as exc:
            App.Console.PrintWarning(f"BNC GSD: Curves workbench unavailable — {exc}\n")

    def _load_curved_shapes(self):
        """Import CurvedShapes workbench modules to register their commands."""
        try:
            _user_mod = os.path.join(App.getUserAppDataDir(), "Mod", "CurvedShapes")
            if os.path.isdir(_user_mod) and _user_mod not in sys.path:
                sys.path.insert(0, _user_mod)

            import CurvedShapes       # noqa: F401
            import CurvedSegment      # noqa: F401
            import CurvedArray        # noqa: F401
            import CurvedPathArray    # noqa: F401
            import InterpolatedMiddle # noqa: F401
            import SurfaceCut         # noqa: F401
            import NotchConnector     # noqa: F401
        except Exception as exc:
            App.Console.PrintWarning(f"BNC GSD: CurvedShapes workbench unavailable — {exc}\n")

    def _load_gsd_analysis(self):
        """Register GSD analysis commands if not already present."""
        already = set(Gui.listCommands())
        if all(c in already for c in ANALYSIS_CMDS):
            return  # GSD workbench already initialised them

        try:
            _gsd_root = None
            for _candidate in [
                os.path.join(App.getResourceDir(), "..", "Mod", "GSD"),
                os.path.join(App.getUserAppDataDir(), "Mod", "GSD"),
                r"d:\Freecad 1.1 installed\Mod\GSD",
            ]:
                if os.path.isfile(os.path.join(_candidate, "GSDWorkbench.py")):
                    _gsd_root = os.path.normpath(_candidate)
                    break

            if _gsd_root is None:
                App.Console.PrintLog("BNC GSD: optional GSD workbench not found — skipping extra analysis commands.\n")
                return

            if _gsd_root not in sys.path:
                sys.path.insert(0, _gsd_root)

            # Use GSD's own namespace guard to avoid package conflicts.
            from GSDWorkbench import _ensure_gsd_imports
            _ensure_gsd_imports()

            from commands.CmdCurvatureComb       import CurvatureCombCommand
            from commands.CmdZebraAnalysis       import ZebraAnalysisCommand
            from commands.CmdContinuityInspector import ContinuityInspectorCommand
            from commands.CmdValidation          import ValidationCommand

            _reg = {
                "GSD_CurvatureComb":       CurvatureCombCommand,
                "GSD_ZebraAnalysis":       ZebraAnalysisCommand,
                "GSD_ContinuityInspector": ContinuityInspectorCommand,
                "GSD_Validation":          ValidationCommand,
            }
            for name, cls in _reg.items():
                if name not in already:
                    Gui.addCommand(name, cls())

        except Exception as exc:
            App.Console.PrintWarning(f"BNC GSD: GSD analysis commands unavailable — {exc}\n")

    def _load_mold_draft(self):
        """Register BNC Mold Tools' Draft Analysis (BNCMold_DraftAnalysis) so the
        Analysis tab can use it without first activating the Mold Tools WB."""
        if "BNCMold_DraftAnalysis" in set(Gui.listCommands()):
            return
        try:
            inner = None
            for _base in (App.getHomePath(), os.path.join(App.getResourceDir(), "..")):
                _cand = os.path.normpath(
                    os.path.join(_base, "Mod", "BNCMoldTools", "BNCMoldTools"))
                if os.path.isfile(os.path.join(_cand, "CommandDraftAnalysis.py")):
                    inner = _cand
                    break
            if inner is None:
                _cand = os.path.join(App.getUserAppDataDir(),
                                     "Mod", "BNCMoldTools", "BNCMoldTools")
                if os.path.isfile(os.path.join(_cand, "CommandDraftAnalysis.py")):
                    inner = _cand
            if inner is None:
                App.Console.PrintWarning(
                    "BNC GSD: Mold Tools draft analysis not found.\n")
                return
            if inner not in sys.path:
                sys.path.insert(0, inner)
            import CommandDraftAnalysis  # noqa: F401 — registers BNCMold_DraftAnalysis
        except Exception as exc:
            App.Console.PrintWarning(
                f"BNC GSD: Mold draft analysis unavailable — {exc}\n")

    # ------------------------------------------------------------------ panel

    def _show_mode_panel(self):
        try:
            if self._mode_panel is None:
                _panels_dir = os.path.join(_WB_ROOT, "panels")
                if _panels_dir not in sys.path:
                    sys.path.insert(0, _panels_dir)
                from ModeSwitchPanel import ModeSwitchPanel
                mw = Gui.getMainWindow()
                self._mode_panel = ModeSwitchPanel(MODES)
                # Dock on the RIGHT side of the main window.
                if mw is not None:
                    try:
                        from PySide2.QtCore import Qt as _Qt2
                        _right = _Qt2.RightDockWidgetArea
                    except ImportError:
                        from PySide6.QtCore import Qt as _Qt6
                        _right = _Qt6.DockWidgetArea.RightDockWidgetArea
                    mw.addDockWidget(_right, self._mode_panel)

            self._mode_panel.setFloating(False)
            self._mode_panel.show()
            self._mode_panel.raise_()
        except Exception as exc:
            App.Console.PrintWarning(f"BNC GSD: mode panel error — {exc}\n")

    def _hide_mode_panel(self):
        try:
            if self._mode_panel is not None:
                self._mode_panel.hide()
        except Exception:
            pass
