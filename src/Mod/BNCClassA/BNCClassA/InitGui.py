# SPDX-License-Identifier: LGPL-2.1-or-later
"""BNCClassA workbench definition — Alias-style Class-A surfacing."""
import os
import FreeCAD
import FreeCADGui as Gui

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

# Command modules (BNCClassA.commands.<module>) and the command ids they register.
# Modules are imported one by one with per-module error reporting so the
# workbench stays usable while individual tools are under development.
_COMMAND_MODULES = [
    # Curves
    "CommandCVCurve",
    "CommandEditCurve",
    "CommandRebuildCurve",
    "CommandBlendCurve",
    "CommandProjectCurve",
    "CommandExtractIso",
    # Surfaces
    "CommandExtrude",
    "CommandRevolve",
    "CommandLoft",
    "CommandBirail",
    "CommandSquarePatch",
    "CommandFreeformBlend",
    "CommandFillet",
    # Edit
    "CommandEditSurface",
    "CommandMatchSurface",
    "CommandExtend",
    "CommandTrim",
    "CommandRebuildSurface",
    "CommandMirror",
    "CommandBake",
    # Evaluate
    "CommandComb",
    "CommandZebra",
    "CommandHighlight",
    "CommandCurvatureMap",
    "CommandEnvMap",
    "CommandContinuityCheck",
    "CommandDeviation",
]

CURVE_CMDS = [
    "BNCClassA_CVCurve",
    "BNCClassA_EditCurve",
    "BNCClassA_RebuildCurve",
    "BNCClassA_BlendCurve",
    "BNCClassA_ProjectCurve",
    "BNCClassA_ExtractIso",
]
SURFACE_CMDS = [
    "BNCClassA_Extrude",
    "BNCClassA_Revolve",
    "BNCClassA_Loft",
    "BNCClassA_Birail",
    "BNCClassA_SquarePatch",
    "BNCClassA_FreeformBlend",
    "BNCClassA_Fillet",
]
EDIT_CMDS = [
    "BNCClassA_EditSurface",
    "BNCClassA_MatchSurface",
    "BNCClassA_Extend",
    "BNCClassA_Trim",
    "BNCClassA_Untrim",
    "BNCClassA_RebuildSurface",
    "BNCClassA_Mirror",
    "BNCClassA_Bake",
]
EVALUATE_CMDS = [
    "BNCClassA_Comb",
    "BNCClassA_Zebra",
    "BNCClassA_Highlight",
    "BNCClassA_CurvatureMap",
    "BNCClassA_EnvMap",
    "BNCClassA_ContinuityCheck",
    "BNCClassA_Deviation",
    "BNCMold_DraftAnalysis",   # reused from BNCMoldTools when installed
]


class ClassAWorkbench(Gui.Workbench):
    MenuText = "Class-A Surface"
    ToolTip = "BNC Class-A Surfacing — Alias-style CV modeling, matching and optical analysis"
    Icon = os.path.join(_iconsDir, "BNCClassA.svg")

    def Initialize(self):
        import sys
        _mod_dir = os.path.dirname(os.path.dirname(__file__))
        if _mod_dir not in sys.path:
            sys.path.insert(0, _mod_dir)

        import importlib
        for name in _COMMAND_MODULES:
            try:
                importlib.import_module("BNCClassA.commands." + name)
            except Exception as e:
                FreeCAD.Console.PrintWarning(
                    "BNCClassA: command module %s not loaded — %s\n" % (name, e))

        # BNCMold_DraftAnalysis registers itself when BNCMoldTools loads; make
        # sure it is available even if the Mold workbench was never activated.
        if "BNCMold_DraftAnalysis" not in Gui.listCommands():
            try:
                _mold_dir = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCMoldTools")
                pkg_dir = os.path.join(_mold_dir, "BNCMoldTools")
                for p in (_mold_dir, pkg_dir):
                    if os.path.isdir(p) and p not in sys.path:
                        sys.path.insert(0, p)
                importlib.import_module("CommandDraftAnalysis")
            except Exception:
                pass

        def avail(cmds):
            known = set(Gui.listCommands())
            return [c for c in cmds if c in known]

        curve_cmds = avail(CURVE_CMDS)
        surface_cmds = avail(SURFACE_CMDS)
        edit_cmds = avail(EDIT_CMDS)
        evaluate_cmds = avail(EVALUATE_CMDS)

        if curve_cmds:
            self.appendToolbar("Class-A Curves", curve_cmds)
        if surface_cmds:
            self.appendToolbar("Class-A Surfaces", surface_cmds)
        if edit_cmds:
            self.appendToolbar("Class-A Edit", edit_cmds)
        if evaluate_cmds:
            self.appendToolbar("Class-A Evaluate", evaluate_cmds)

        menu = []
        for group in (curve_cmds, surface_cmds, edit_cmds, evaluate_cmds):
            if group:
                if menu:
                    menu.append("Separator")
                menu.extend(group)
        if menu:
            self.appendMenu(["Class-A"], menu)

    def Activated(self):
        try:
            from BNCClassA.ui import palette
            palette.show()
        except Exception:
            pass

    def Deactivated(self):
        try:
            from BNCClassA.ui import palette
            palette.hide()
        except Exception:
            pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(ClassAWorkbench())
