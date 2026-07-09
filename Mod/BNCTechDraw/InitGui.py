# -*- coding: utf-8 -*-
# BNC TechDraw module - command registration only.
# The toolbar is declared via self.appendToolbar() inside TechDraw's
# own InitGui.py so FreeCAD's workbench system handles show/hide natively.

import FreeCAD
import FreeCADGui
import os

ICON_PATH = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCTechDraw", "icons")
try:
    FreeCADGui.addIconPath(ICON_PATH)
except Exception as _e:
    FreeCAD.Console.PrintWarning("BNCTechDraw: addIconPath failed: " + str(_e) + "\n")


class BNC_GenerateDrawing_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_GenerateDrawing",
                "MenuText": "Generate Drawing",
                "ToolTip": "Generate TechDraw drawing from 3D model"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "GenerateDrawing.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return True


class BNC_InsertToleranceTable_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_InsertToleranceTable",
                "MenuText": "Insert Tolerance Table",
                "ToolTip": "Insert tolerance table into TechDraw sheet"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "InsertToleranceTable.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return True


class BNC_InsertTitleBlock_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_InsertTitleBlock",
                "MenuText": "Insert Title Block",
                "ToolTip": "Insert BNC title block into TechDraw sheet"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "FillTitleBlock.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return True


class BNC_AssemblyTable_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_AssemblyTable",
                "MenuText": "Assembly Table",
                "ToolTip": "Insert assembly parts list (BOM) into TechDraw sheet"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "AssemblyTable.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


class BNC_BalloonAssembly_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_BalloonAssembly",
                "MenuText": "Balloon Assembly",
                "ToolTip": "Auto-create balloons on selected view numbered to match Assembly Table"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "BalloonAssembly.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


class BNC_ExportPDF_Cmd(object):
    def GetResources(self):
        return {"Pixmap": "BNC_ExportPDF",
                "MenuText": "Export PDF",
                "ToolTip": "Recompute all views then export drawing as PDF (fixes missing views and Acrobat errors)"}

    def Activated(self):
        import os as _os, FreeCAD as _FC, traceback as _tb
        macro_name = "ExportPDF.FCMacro"
        try:
            for p in [_os.path.join(_FC.getHomePath(), "Macro", macro_name),
                      _os.path.join(_FC.getUserMacroDir(True), macro_name),
                      _os.path.join(_FC.getResourceDir(), "Macro", macro_name)]:
                if _os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="replace") as f:
                        exec(compile(f.read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
                    return
            _FC.Console.PrintError("BNCTechDraw: Macro not found: " + macro_name + "\n")
        except Exception as e:
            _FC.Console.PrintError("BNCTechDraw: " + str(e) + "\n")
            _FC.Console.PrintError(_tb.format_exc())

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


try:
    FreeCADGui.addCommand("BNC_GenerateDrawing", BNC_GenerateDrawing_Cmd())
    FreeCADGui.addCommand("BNC_InsertToleranceTable", BNC_InsertToleranceTable_Cmd())
    FreeCADGui.addCommand("BNC_InsertTitleBlock", BNC_InsertTitleBlock_Cmd())
    FreeCADGui.addCommand("BNC_AssemblyTable", BNC_AssemblyTable_Cmd())
    FreeCADGui.addCommand("BNC_BalloonAssembly", BNC_BalloonAssembly_Cmd())
    FreeCADGui.addCommand("BNC_ExportPDF", BNC_ExportPDF_Cmd())
except Exception as _e:
    FreeCAD.Console.PrintError("BNCTechDraw: Command registration failed: " + str(_e) + "\n")
