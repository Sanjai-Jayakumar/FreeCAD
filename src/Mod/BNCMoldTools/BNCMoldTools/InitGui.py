# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import FreeCAD
import FreeCADGui as Gui

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")


class BNCMoldToolsWorkbench(Gui.Workbench):
    MenuText = "Mold Tools"
    ToolTip  = "BNC Mold Design Tools — parting line, core/cavity split, draft analysis"
    Icon     = os.path.join(_iconsDir, "BNCMoldTools.svg")

    def Initialize(self):
        import sys
        _pkg_dir = os.path.dirname(__file__)
        if _pkg_dir not in sys.path:
            sys.path.insert(0, _pkg_dir)

        import CommandScale
        import CommandDraftAnalysis
        import CommandDraft
        import CommandSplitLine
        import CommandPartingLine
        import CommandShutOffSurface
        import CommandPartingSurface
        import CommandToolingSplit
        import CommandCore
        import CommandUndercutAnalysis

        analysisTools = [
            "BNCMold_DraftAnalysis",
            "BNCMold_UndercutAnalysis",
        ]
        prepTools = [
            "BNCMold_Scale",
            "BNCMold_Draft",
            "BNCMold_SplitLine",
        ]
        moldTools = [
            "BNCMold_PartingLine",
            "BNCMold_ShutOffSurface",
            "BNCMold_PartingSurface",
            "BNCMold_ToolingSplit",
        ]
        coreTools = [
            "BNCMold_Core",
        ]

        self.appendToolbar("Mold Analysis",    analysisTools)
        self.appendToolbar("Mold Preparation", prepTools)
        self.appendToolbar("Mold Definition",  moldTools)
        self.appendToolbar("Mold Core",        coreTools)

        allCmds = analysisTools + prepTools + moldTools + coreTools
        self.appendMenu(["Mold Tools"], allCmds)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BNCMoldToolsWorkbench())
