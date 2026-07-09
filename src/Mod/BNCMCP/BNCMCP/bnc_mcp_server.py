#!/usr/bin/env python3
"""
ANVIL CAD MCP Server
==================
External MCP server that bridges Claude Desktop / AI clients
to ANVIL CAD via XML-RPC. Based on freecad-mcp by neka-nat.

Usage:
    python bnc_mcp_server.py
    python bnc_mcp_server.py --only-text-feedback

Requires: pip install "mcp[cli]>=1.12.2"
"""

import json
import logging
import xmlrpc.client
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Literal

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent, ImageContent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("BNCCADMCPserver")


_only_text_feedback = False


class BNCCADConnection:
    def __init__(self, host="localhost", port=9875):
        self.server = xmlrpc.client.ServerProxy(
            "http://{}:{}".format(host, port), allow_none=True
        )

    def ping(self):
        return self.server.ping()

    def create_document(self, name):
        return self.server.create_document(name)

    def create_object(self, doc_name, obj_data):
        return self.server.create_object(doc_name, obj_data)

    def edit_object(self, doc_name, obj_name, obj_data):
        return self.server.edit_object(doc_name, obj_name, obj_data)

    def delete_object(self, doc_name, obj_name):
        return self.server.delete_object(doc_name, obj_name)

    def insert_part_from_library(self, relative_path):
        return self.server.insert_part_from_library(relative_path)

    def execute_code(self, code):
        return self.server.execute_code(code)

    def get_active_screenshot(self, view_name="Isometric", width=None, height=None, focus_object=None):
        try:
            result = self.server.execute_code("""
import FreeCAD
import FreeCADGui

if FreeCAD.Gui.ActiveDocument and FreeCAD.Gui.ActiveDocument.ActiveView:
    view_type = type(FreeCAD.Gui.ActiveDocument.ActiveView).__name__
    unsupported_views = ['SpreadsheetGui::SheetView', 'DrawingGui::DrawingView', 'TechDrawGui::MDIViewPage']
    if view_type in unsupported_views or not hasattr(FreeCAD.Gui.ActiveDocument.ActiveView, 'saveImage'):
        print("Current view does not support screenshots")
        False
    else:
        print("Current view supports screenshots: " + view_type)
        True
else:
    print("No active view")
    False
""")
            if not result.get("success", False) or "Current view does not support screenshots" in result.get("message", ""):
                logger.info("Screenshot unavailable in current view")
                return None

            return self.server.get_active_screenshot(view_name, width, height, focus_object)
        except Exception as e:
            logger.error("Error getting screenshot: {}".format(e))
            return None

    def get_objects(self, doc_name):
        return self.server.get_objects(doc_name)

    def get_object(self, doc_name, obj_name):
        return self.server.get_object(doc_name, obj_name)

    def get_parts_list(self):
        return self.server.get_parts_list()

    def list_documents(self):
        return self.server.list_documents()


@asynccontextmanager
async def server_lifespan(server):
    try:
        logger.info("ANVIL CAD MCP server starting up")
        try:
            _ = get_bnccad_connection()
            logger.info("Successfully connected to ANVIL CAD on startup")
        except Exception as e:
            logger.warning("Could not connect to ANVIL CAD on startup: {}".format(str(e)))
            logger.warning(
                "Make sure ANVIL CAD is running with the MCP addon enabled before using tools"
            )
        yield {}
    finally:
        global _bnccad_connection
        if _bnccad_connection:
            logger.info("Disconnecting from ANVIL CAD on shutdown")
            _bnccad_connection = None
        logger.info("ANVIL CAD MCP server shut down")


mcp = FastMCP(
    "BNCMCP",
    instructions="ANVIL CAD integration through the Model Context Protocol",
    lifespan=server_lifespan,
)


_bnccad_connection = None


def get_bnccad_connection():
    """Get or create a persistent ANVIL CAD connection"""
    global _bnccad_connection
    if _bnccad_connection is None:
        _bnccad_connection = BNCCADConnection(host="localhost", port=9875)
        if not _bnccad_connection.ping():
            logger.error("Failed to ping ANVIL CAD")
            _bnccad_connection = None
            raise Exception(
                "Failed to connect to ANVIL CAD. Make sure ANVIL CAD is running with the MCP Server started."
            )
    return _bnccad_connection


def add_screenshot_if_available(response, screenshot):
    """Safely add screenshot to response only if available"""
    if screenshot is not None and not _only_text_feedback:
        response.append(ImageContent(type="image", data=screenshot, mimeType="image/png"))
    elif not _only_text_feedback:
        response.append(TextContent(
            type="text",
            text="Note: Visual preview is unavailable in the current view type. "
                 "Switch to a 3D view to see visual feedback."
        ))
    return response


@mcp.tool()
def create_document(ctx: Context, name: str):
    """Create a new document in ANVIL CAD.

    Args:
        name: The name of the document to create.
    """
    freecad = get_bnccad_connection()
    try:
        res = freecad.create_document(name)
        if res["success"]:
            return [TextContent(type="text", text="Document '{}' created successfully".format(res['document_name']))]
        else:
            return [TextContent(type="text", text="Failed to create document: {}".format(res['error']))]
    except Exception as e:
        logger.error("Failed to create document: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to create document: {}".format(str(e)))]


@mcp.tool()
def create_object(ctx: Context, doc_name: str, obj_type: str, obj_name: str,
                  analysis_name: str = None, obj_properties: dict = None):
    """Create a new object in ANVIL CAD.
    Object type starts with "Part::" or "Draft::" or "PartDesign::" or "Fem::".

    Args:
        doc_name: The name of the document.
        obj_type: The type of object (e.g. 'Part::Box', 'Part::Cylinder', 'Draft::Circle').
        obj_name: The name of the object.
        analysis_name: Optional FEM analysis name.
        obj_properties: The properties of the object.
    """
    freecad = get_bnccad_connection()
    try:
        obj_data = {"Name": obj_name, "Type": obj_type, "Properties": obj_properties or {}, "Analysis": analysis_name}
        res = freecad.create_object(doc_name, obj_data)
        screenshot = freecad.get_active_screenshot()
        if res["success"]:
            response = [TextContent(type="text", text="Object '{}' created successfully".format(res['object_name']))]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [TextContent(type="text", text="Failed to create object: {}".format(res['error']))]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to create object: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to create object: {}".format(str(e)))]


@mcp.tool()
def edit_object(ctx: Context, doc_name: str, obj_name: str, obj_properties: dict):
    """Edit an object in ANVIL CAD.

    Args:
        doc_name: The name of the document.
        obj_name: The name of the object to edit.
        obj_properties: The properties to update.
    """
    freecad = get_bnccad_connection()
    try:
        res = freecad.edit_object(doc_name, obj_name, {"Properties": obj_properties})
        screenshot = freecad.get_active_screenshot()
        if res["success"]:
            response = [TextContent(type="text", text="Object '{}' edited successfully".format(res['object_name']))]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [TextContent(type="text", text="Failed to edit object: {}".format(res['error']))]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to edit object: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to edit object: {}".format(str(e)))]


@mcp.tool()
def delete_object(ctx: Context, doc_name: str, obj_name: str):
    """Delete an object in ANVIL CAD.

    Args:
        doc_name: The name of the document.
        obj_name: The name of the object to delete.
    """
    freecad = get_bnccad_connection()
    try:
        res = freecad.delete_object(doc_name, obj_name)
        screenshot = freecad.get_active_screenshot()
        if res["success"]:
            response = [TextContent(type="text", text="Object '{}' deleted successfully".format(res['object_name']))]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [TextContent(type="text", text="Failed to delete object: {}".format(res['error']))]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to delete object: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to delete object: {}".format(str(e)))]


@mcp.tool()
def execute_code(ctx: Context, code: str):
    """Execute arbitrary Python code in ANVIL CAD.

    Args:
        code: The Python code to execute.
    """
    freecad = get_bnccad_connection()
    try:
        res = freecad.execute_code(code)
        screenshot = freecad.get_active_screenshot()
        if res["success"]:
            response = [TextContent(type="text", text="Code executed successfully: {}".format(res['message']))]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [TextContent(type="text", text="Failed to execute code: {}".format(res['error']))]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to execute code: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to execute code: {}".format(str(e)))]


@mcp.tool()
def get_view(ctx: Context, view_name: str, width: int = None, height: int = None, focus_object: str = None):
    """Get a screenshot of the active view.

    Args:
        view_name: One of: Isometric, Front, Top, Right, Back, Left, Bottom, Dimetric, Trimetric.
        width: Optional screenshot width in pixels.
        height: Optional screenshot height in pixels.
        focus_object: Optional object name to focus on.
    """
    freecad = get_bnccad_connection()
    screenshot = freecad.get_active_screenshot(view_name, width, height, focus_object)
    if screenshot is not None:
        return [ImageContent(type="image", data=screenshot, mimeType="image/png")]
    else:
        return [TextContent(type="text", text="Cannot get screenshot in the current view type")]


@mcp.tool()
def insert_part_from_library(ctx: Context, relative_path: str):
    """Insert a part from the parts library addon.

    Args:
        relative_path: The relative path of the part to insert.
    """
    freecad = get_bnccad_connection()
    try:
        res = freecad.insert_part_from_library(relative_path)
        screenshot = freecad.get_active_screenshot()
        if res["success"]:
            response = [TextContent(type="text", text="Part inserted from library: {}".format(res['message']))]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [TextContent(type="text", text="Failed to insert part: {}".format(res['error']))]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to insert part: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to insert part: {}".format(str(e)))]


@mcp.tool()
def get_objects(ctx: Context, doc_name: str):
    """Get all objects in a document.

    Args:
        doc_name: The name of the document.
    """
    freecad = get_bnccad_connection()
    try:
        screenshot = freecad.get_active_screenshot()
        response = [TextContent(type="text", text=json.dumps(freecad.get_objects(doc_name)))]
        return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to get objects: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to get objects: {}".format(str(e)))]


@mcp.tool()
def get_object(ctx: Context, doc_name: str, obj_name: str):
    """Get an object from a document.

    Args:
        doc_name: The name of the document.
        obj_name: The name of the object.
    """
    freecad = get_bnccad_connection()
    try:
        screenshot = freecad.get_active_screenshot()
        response = [TextContent(type="text", text=json.dumps(freecad.get_object(doc_name, obj_name)))]
        return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error("Failed to get object: {}".format(str(e)))
        return [TextContent(type="text", text="Failed to get object: {}".format(str(e)))]


@mcp.tool()
def get_parts_list(ctx: Context):
    """Get the list of parts in the parts library addon."""
    freecad = get_bnccad_connection()
    parts = freecad.get_parts_list()
    if parts:
        return [TextContent(type="text", text=json.dumps(parts))]
    else:
        return [TextContent(type="text", text="No parts found in the parts library.")]


@mcp.tool()
def list_documents(ctx: Context):
    """Get the list of open documents in ANVIL CAD."""
    freecad = get_bnccad_connection()
    docs = freecad.list_documents()
    return [TextContent(type="text", text=json.dumps(docs))]


@mcp.prompt()
def asset_creation_strategy():
    return """
Asset Creation Strategy for ANVIL CAD MCP

When creating content in ANVIL CAD, always follow these steps:

0. Before starting any task, always use get_objects() to confirm the current state of the document.

1. Utilize the parts library:
   - Check available parts using get_parts_list().
   - If the required part exists in the library, use insert_part_from_library().

2. If the appropriate asset is not available in the parts library:
   - Create basic shapes (e.g., cubes, cylinders, spheres) using create_object().
   - Adjust properties using edit_object().

3. Always assign clear and descriptive names to objects.

4. Explicitly set position, scale, and rotation properties using edit_object().

5. After editing an object, verify properties with get_object().

6. For detailed customization, use execute_code() to run custom Python scripts.

Only revert to basic creation methods when:
- The required asset is not available in the parts library.
- A basic shape is explicitly requested.
- Complex shapes require custom scripting.
"""


def main():
    """Run the ANVIL CAD MCP server"""
    global _only_text_feedback
    import argparse
    parser = argparse.ArgumentParser(description="ANVIL CAD MCP Server")
    parser.add_argument("--only-text-feedback", action="store_true", help="Only return text feedback (no screenshots)")
    args = parser.parse_args()
    _only_text_feedback = args.only_text_feedback
    logger.info("Only text feedback: {}".format(_only_text_feedback))
    mcp.run()


if __name__ == "__main__":
    main()
