import FreeCAD
import FreeCADGui as Gui
import os as _os


class TechDrawWorkbench(Gui.Workbench):
    "Technical Drawing workbench object"

    def __init__(self):
        self.__class__.Icon = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Resources/icons/preferences-techdraw.svg"
        )
        self.__class__.MenuText = "TechDraw"
        self.__class__.ToolTip = "Technical Drawing workbench"

    def Initialize(self):
        import TechDrawGui
        from PySide.QtCore import QT_TRANSLATE_NOOP
        import FreeCAD as _FC
        import FreeCADGui as _Gui
        import os as _o
        import traceback as _tb

        try:
            import TechDrawTools
        except ImportError as err:
            _FC.Console.PrintError(
                "Features from TechDrawTools package cannot be loaded. {err}\n".format(
                    err=str(err)))

        # ---- macro runner (fully self-contained, no external references) ----
        def run_macro(macro_name):
            home = _FC.getHomePath().rstrip('/\\')
            candidates = [
                _o.path.join(home, "Macro", macro_name),
                _o.path.join(_FC.getUserMacroDir(True), macro_name),
            ]
            _FC.Console.PrintMessage("BNC TechDraw: running " + macro_name + "\n")
            for p in candidates:
                if _o.path.exists(p):
                    _FC.Console.PrintMessage("BNC TechDraw: found at " + p + "\n")
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as fh:
                            exec(compile(fh.read(), p, "exec"),
                                 {"__file__": p, "__name__": "__main__"})
                    except Exception as e:
                        _FC.Console.PrintError("BNC TechDraw: " + macro_name + " error: " + str(e) + "\n")
                        _FC.Console.PrintError(_tb.format_exc())
                    return
            _FC.Console.PrintError("BNC TechDraw: " + macro_name + " not found. Searched:\n")
            for p in candidates:
                _FC.Console.PrintError("  " + p + "\n")

        # ---- icon helper ----
        def icon(name):
            return _o.path.join(
                _FC.getHomePath().rstrip('/\\'),
                "Mod", "BNCTechDraw", "icons", name)

        # ---- command classes (defined locally so they close over run_macro) ----
        class CmdGenerateDrawing(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_GenerateDrawing.svg"),
                        "MenuText": "Generate Drawing",
                        "ToolTip": "Automatically generate 2D drawing from 3D model"}
            def IsActive(self):
                return _FC.ActiveDocument is not None
            def Activated(self):
                run_macro("GenerateDrawing.FCMacro")

        class CmdFillTitleBlock(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_InsertTitleBlock.svg"),
                        "MenuText": "Fill Title Block",
                        "ToolTip": "Auto-fill title block from model parameters"}
            def IsActive(self):
                if _FC.ActiveDocument is None:
                    return False
                for obj in _FC.ActiveDocument.Objects:
                    if obj.TypeId == "TechDraw::DrawPage":
                        return True
                return False
            def Activated(self):
                run_macro("FillTitleBlock.FCMacro")

        class CmdInsertToleranceTable(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_InsertToleranceTable.svg"),
                        "MenuText": "Insert Tolerance Table",
                        "ToolTip": "Insert tolerance table into drawing sheet"}
            def IsActive(self):
                if _FC.ActiveDocument is None:
                    return False
                for obj in _FC.ActiveDocument.Objects:
                    if obj.TypeId == "TechDraw::DrawPage":
                        return True
                return False
            def Activated(self):
                run_macro("InsertToleranceTable.FCMacro")

        _Gui.addCommand("TechDraw_GenerateDrawing",     CmdGenerateDrawing())
        _Gui.addCommand("TechDraw_FillTitleBlock",       CmdFillTitleBlock())
        _Gui.addCommand("TechDraw_InsertToleranceTable", CmdInsertToleranceTable())

        # store run_macro on self so _bnc_toolbar can use it after Initialize returns
        self._run_macro = run_macro

    def _bnc_toolbar(self, show):
        try:
            try:
                from PySide2 import QtCore, QtGui, QtWidgets
            except ImportError:
                from PySide import QtCore, QtGui
                QtWidgets = QtGui

            mw = Gui.getMainWindow()
            if mw is None:
                return

            tb = mw.findChild(QtWidgets.QToolBar, "BNC_TechDraw_Tools")

            if not show:
                if tb is not None:
                    tb.hide()
                return

            if tb is not None:
                tb.show()
                return

            import os as _o2
            icon_dir = _o2.path.join(
                FreeCAD.getHomePath().rstrip('/\\'),
                "Mod", "BNCTechDraw", "icons")

            tb = QtWidgets.QToolBar("BNC TechDraw Tools", mw)
            tb.setObjectName("BNC_TechDraw_Tools")
            tb.setWindowTitle("BNC TechDraw Tools")
            tb.setMovable(True)
            tb.setIconSize(QtCore.QSize(24, 24))
            tb.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

            run = getattr(self, "_run_macro", None)

            for icon_file, tip, macro in [
                ("BNC_GenerateDrawing.svg",     "Generate Drawing",       "GenerateDrawing.FCMacro"),
                ("BNC_InsertTitleBlock.svg",     "Fill Title Block",       "FillTitleBlock.FCMacro"),
                ("BNC_InsertToleranceTable.svg", "Insert Tolerance Table", "InsertToleranceTable.FCMacro"),
            ]:
                icon_path = _o2.path.join(icon_dir, icon_file)
                if _o2.path.exists(icon_path):
                    action = QtWidgets.QAction(QtGui.QIcon(icon_path), tip, mw)
                else:
                    action = QtWidgets.QAction(tip, mw)
                action.setToolTip(tip)
                if run is not None:
                    action.triggered.connect(
                        lambda checked=False, m=macro: run(m))
                tb.addAction(action)

            mw.addToolBar(QtCore.Qt.TopToolBarArea, tb)

        except Exception as e:
            import traceback
            FreeCAD.Console.PrintError("BNC TechDraw toolbar error: " + str(e) + "\n")
            FreeCAD.Console.PrintError(traceback.format_exc())

    def Activated(self):
        self._bnc_toolbar(True)

    def Deactivated(self):
        self._bnc_toolbar(False)

    def GetClassName(self):
        return "TechDrawGui::Workbench"


Gui.addWorkbench(TechDrawWorkbench())

FreeCAD.addExportType("Technical Drawing (*.svg *.dxf *.pdf)", "TechDrawGui")

FreeCAD.__unit_test__ += ["TestTechDrawGui"]
