import FreeCAD
import FreeCADGui as Gui
import sys
import os

Workbench = Gui.Workbench

# rpc_server package lives inside the BNCMCP package directory
_pkg_dir = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCMCP", "BNCMCP")
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)


class BNCMCPAddonWorkbench(Workbench):
    MenuText = "BNC MCP"
    ToolTip = "BNC CAD MCP Server - AI Integration via Model Context Protocol"

    def Initialize(self):
        try:
            from rpc_server import rpc_server  # registers Start_RPC_Server / Stop_RPC_Server
        except Exception as e:
            FreeCAD.Console.PrintWarning("BNC MCP: rpc_server not loaded: " + str(e) + "\n")

        commands = ["Start_RPC_Server", "Stop_RPC_Server"]
        self.appendToolbar("BNC MCP", commands)
        self.appendMenu("BNC MCP", commands)

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(BNCMCPAddonWorkbench())
