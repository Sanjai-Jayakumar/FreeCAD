class BNCMCPAddonWorkbench(Workbench):
    MenuText = "BNC MCP"
    ToolTip = "BNC CAD MCP Server - AI Integration via Model Context Protocol"

    def Initialize(self):
        from rpc_server import rpc_server

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
