# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of BNC CAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Add BNC Tools buttons - PERSISTENT STANDALONE TOOLBAR"""

import FreeCAD
import FreeCADGui
from PySide import QtGui, QtCore
import os

# Global reference to keep toolbar alive
_persistent_toolbar = None


def _create_plane_display_icon():
    """Create Plane Display icon - loads PNG file or uses embedded PNG data."""
    try:
        # Strategy 1: Load PNG file from icon directories
        icon_dirs = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
        ]
        for d in icon_dirs:
            png_path = os.path.join(d, "Plane_Display.png")
            if os.path.exists(png_path):
                pix = QtGui.QPixmap(png_path)
                if not pix.isNull():
                    FreeCAD.Console.PrintMessage(f"BNC CAD: Plane_Display.png loaded from {png_path}\n")
                    return QtGui.QIcon(pix)

        # Strategy 2: Embedded PNG as base64 (works even if files missing)
        import base64
        b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAA7E"
            "AAAOxAGVKw4bAAAGDklEQVR4nO2Zy28b1xlHz53h8E3KpORYIqlYqdsAhYG0"
            "ieOgmywC1IVVoFkE8qNBWhdOUSTRIoui6Lp/QJe2k0VdoEVrJ+kDKOLaQRYF"
            "CnQRO+qmiRdJhBimJFquKL7JIcczXxcKJQKmaVIakkEzZ3nn9c1v7pyZey94"
            "eHh4eHh4eHh4fCVR47jozA8fn9KN1sutxlM/M6vHECfyJobvYuXdFzdGXcso"
            "A1CZH809I/AailNAoLz+q87tTVBvKeRc+b0z10dW1LAvkDmRCTlh32klLAJH"
            "2leNJKPkbv4CAGNyCivf8fAVHyJyvhIPX+adk41h1je0AGbPzB5y8L2KyFkg"
            "AaD7dCZScRLpfRghP9cvvQhA4rnv4jQaNNdWaObWEMtqn6YAclHTuFC6+pPl"
            "YdTpbgAn0NOhr82LOItKcbzdHIwHSKQTxB+JoXRte/fOANqI42DdXcdczWKX"
            "y9vNwDWE85WJ0FXeOWm7VbIrAbSlJvAKMAeglCI+HSORSRCMBbse1y2ATuxy"
            "GXMti7W+jjhOu/kWqAtuSXMvAdwnNQB/yGAivY990xPofr3nCR4WQBuxLJq"
            "5NZqrKzjmthJckebAAfSSWiIzQSQZQan+TttvANuIYG3maa6uuCbNvgPoR2q"
            "DMnAAHbglzd4BDCi1QdlLAG32Kk1fr5OnQwcvg7OgVH9SGwdK0/BPz+Cfnum"
            "UphLHmUcxH6s0/lSBEw86vmcAoBYA9n99f19SGzd6PE4kfhg59DjN3BqN5U9"
            "BWOh1TF/9d/LR5Jf+5jtRhkHw0YN97bv7F/j/BC+AcRcwbr7yATzkKzBcIq"
            "1b47w8MKYeYJdsSm/mSVWukCpfYeqvp9Bq6+MoZTwBVC8VkZagxEZho+41S"
            "L7/+jhKGX0A1q0W4sj9G2wL/52lUZczwgAEzJJJIVvoGoA4Ds3s7c7/+ZEw"
            "dAmK7VC+W6GwUsSsmAAcUMmt4UonSqdYjcHSdfR4nGAqg3FgGqUN9xkNLQC"
            "r0aKwWqKYK+FYW4OxiAXfy+sc89n82jJoiSCAH/i5Mni38gFXwk9QLUOtfB"
            "P12ScEZlIE0rNoodBQ6nQ1ABGhlq9TWClQ26xttz9WhRc2AzzfjBL64q27ZM"
            "CSo0DBEQXQ4Kjc4Je1f/MXmeNy8Ft8Rgozextz5TZGcopAKoMxOQl9Trj0gy"
            "sB2C2bUq5EYbWIZW5NTvgceHZT41Q5wlN29+HzkS69O4zNS2qZl5rL3GhM8"
            "nvjMP8IH8bKb2DlN9CCIQLpDIGZFMow9lz77gMQMMsmhdUC5fUKIlsv9X4Tf"
            "pD3s9CIMiV7G0Ee1fIctf/Jfysf8Ee+wZ9D3+Yu0Fj+FPPzZYxHDhBMz6LH"
            "47u+xsABdJOaAp4sKhaKQZ5rhfEpd8W1nyav8xGL9Y94X1L8wf8ES+FDtO7"
            "kaN3J7UmafQfQS2qna1Eec76YExziWpNPwbxaY/7eGsulKL/TvrlnafYsN/3"
            "jOQGIJCMPldq4qKPvSDOQ2mpUYCR3ltsq75154H32FQD0J7Vxc8PpkKba8U+"
            "vAHpa6oVEfNrWePpYVvjpTYdj5QAHtQCG/uWcHktYZZ4sfsyzd/9FzK5T84X"
            "5Tuk/b3y8tnTlQcf07AFvgx5Pp4+j1KLA8fb+Yb/BZDTCRDiI5uI3eTc4IpT"
            "qJhuVGo2d9QEBriqR8+XV1Wsn4YHT4n1X//fZ2UNK5BXgLJAE0DWNRCTEVD"
            "SC3zfaXtG6Z7NRrVGoNbB31g03gYui1Bvfz2ZdWBjpwtuZTCim1ClEFoGn2+"
            "3xYIDJaJhoMND30tigiAhVs8lGtU7FbHZu+hClzlVE3jq5sjKcpbFuXMtknh"
            "GlXkPkNO3FUV1nMhYmEQnjc2kgc89x2KzW2azWadnbvbmJUpeBc/PZ7I3dnt"
            "uVR/W3mZkpv66fFZFXUWoOtn7X94XDTEXDhPy7+2Wttyzy1TrFeh3ZGT1+D"
            "lywbPu3z+dyY10evw83pLlXqQ3K0BQ+qDTdktqgDP0b1kuayVgEgHyl5prUB"
            "mWkH/Fu0uzAFakNylj+YralCS+z9X7/xi2peXh4eHh4eHh4eHj0xf8AiszvU"
            "yEnq0oAAAAASUVORK5CYII=")
        png_data = base64.b64decode(b64)
        pixmap = QtGui.QPixmap()
        if pixmap.loadFromData(png_data, "PNG") and not pixmap.isNull():
            FreeCAD.Console.PrintMessage("BNC CAD: Plane_Display icon from embedded PNG\n")
            return QtGui.QIcon(pixmap)

        FreeCAD.Console.PrintError("BNC CAD: All Plane_Display icon methods failed\n")
        return None
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: Plane_Display icon error: {e}\n")
        return None


def _ensure_toolbar_separate_row(mw, toolbar):
    """Force the BNC toolbar onto its own row in the top area."""
    # Restore default: do not force a separate row, let FreeCAD handle toolbar placement
    pass


def create_persistent_toolbar():
    """Create a persistent toolbar that won't be removed by workbench changes"""
    global _persistent_toolbar

    try:
        # Check if GUI is ready
        if not FreeCADGui.getMainWindow():
            QtCore.QTimer.singleShot(500, create_persistent_toolbar)
            return

        mw = FreeCADGui.getMainWindow()

        # Check if toolbar already exists
        if _persistent_toolbar is not None:
            FreeCAD.Console.PrintLog("BNC toolbar already exists\n")
            return

        # Remove stale toolbar from previous session so it gets recreated with all buttons
        for old_tb in mw.findChildren(QtGui.QToolBar):
            if old_tb.objectName() == "BNC_Custom_Toolbar":
                mw.removeToolBar(old_tb)
                old_tb.deleteLater()
                FreeCAD.Console.PrintLog("BNC CAD: Removed stale toolbar, recreating\n")
                break

        # Create new persistent toolbar
        toolbar = mw.addToolBar("BNC Tools")
        toolbar.setObjectName("BNC_Custom_Toolbar")

        # Make toolbar persistent - set it as a top-level toolbar
        toolbar.setAllowedAreas(QtCore.Qt.TopToolBarArea | QtCore.Qt.BottomToolBarArea)
        mw.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        # Do not force toolbar row, use FreeCAD default

        # Icon base paths
        icon_base_paths = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "PartDesign", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "Assembly", "Resources", "icons")
        ]

        # =========================================
        # Button 1: Set Working Directory
        # =========================================
        action_setwd = QtGui.QAction(mw)
        # action_setwd.setText('Set Working Directory')  # Removed to show icon only
        action_setwd.setToolTip('Set the working directory for file operations\nKeyboard: Ctrl+Shift+W')
        action_setwd.setObjectName("BNC_SetWD_Action")

        # Load SET_WD icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "SET_WD.svg")
            if os.path.exists(icon_path):
                action_setwd.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ SET_WD icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_setwd.triggered.connect(lambda: FreeCADGui.runCommand('Std_SetWorkingDirectory'))

        # Add to toolbar
        toolbar.addAction(action_setwd)

        # =========================================
        # Button 2: Version Save
        # =========================================
        action_save = QtGui.QAction(mw)
        # action_save.setText('Version Save')  # Removed to show icon only
        action_save.setToolTip('Save all open documents with automatic version numbering\nKeyboard: Ctrl+S')
        action_save.setObjectName("BNC_VersionSave_Action")
        action_save.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        action_save.setShortcutContext(QtCore.Qt.ApplicationShortcut)

        # Load save icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "save.svg")
            if os.path.exists(icon_path):
                action_save.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ save icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_save.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSave'))

        # Add to toolbar
        toolbar.addAction(action_save)

        # =========================================
        # Button 3: Version Open
        # =========================================
        action_open = QtGui.QAction(mw)
        # action_open.setText('Version Open')  # Removed to show icon only
        action_open.setToolTip('Open version-controlled documents from working directory\\nKeyboard: Ctrl+O')
        action_open.setObjectName("BNC_VersionOpen_Action")

        # Load Open icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Open.svg")
            if os.path.exists(icon_path):
                action_open.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Open icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_open.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionOpen'))

        # Add to toolbar
        toolbar.addAction(action_open)

        # =========================================
        # Button 4: Version Save As
        # =========================================
        action_saveas = QtGui.QAction(mw)
        # action_saveas.setText('Version Save As')  # Removed to show icon only
        action_saveas.setToolTip('Save As with automatic version numbering\nKeyboard: Ctrl+Shift+S')
        action_saveas.setObjectName("BNC_VersionSaveAs_Action")

        # Load save_as icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "save_as.svg")
            if os.path.exists(icon_path):
                action_saveas.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ save_as icon loaded: {icon_path}\n")
                break

        # Connect to command
        action_saveas.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSaveAs'))

        # Add to toolbar
        toolbar.addAction(action_saveas)

        # =========================================
        # Button 5: Rename
        # =========================================
        action_rename = QtGui.QAction(mw)
        action_rename.setToolTip('Rename model and update all versions\nKeyboard: F2')
        action_rename.setObjectName("BNC_Rename_Action")

        # Load Rename icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Rename.svg")
            if os.path.exists(icon_path):
                action_rename.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Rename icon loaded: {icon_path}\n")
                break

        # Connect directly to rename function (avoids command registration timing issues)
        def run_rename():
            import sys
            rename_mod_path = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCGlobal", "Gui")
            if rename_mod_path not in sys.path:
                sys.path.insert(0, rename_mod_path)
            try:
                from CommandStdVersionRename import main as rename_main
                rename_main()
            except Exception as e:
                FreeCAD.Console.PrintError(f"Rename error: {str(e)}\n")

        action_rename.triggered.connect(run_rename)

        # Add to toolbar
        toolbar.addAction(action_rename)

        # =========================================
        # Button 6: Apply Material
        # =========================================
        action_applymat = QtGui.QAction(mw)
        action_applymat.setToolTip('Apply Indian Standard Material to the active body')
        action_applymat.setObjectName("BNC_ApplyMaterial_Action")

        # Load Apply_Material icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Apply_Material.svg")
            if os.path.exists(icon_path):
                action_applymat.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Apply_Material icon loaded: {icon_path}\n")
                break

        # Connect to Apply Material macro
        def run_apply_material():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "Apply_Material.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Apply Material error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"Apply Material macro not found: {macro_path}\n")

        action_applymat.triggered.connect(run_apply_material)

        # Add to toolbar
        toolbar.addAction(action_applymat)

        # =========================================
        # Button 7: Measure Mass
        # =========================================
        action_mass = QtGui.QAction(mw)
        action_mass.setToolTip('Measure mass of selected component(s) based on applied material density')
        action_mass.setObjectName("BNC_MeasureMass_Action")

        # Load Mass_Properties icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Mass_Properties.svg")
            if os.path.exists(icon_path):
                action_mass.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Mass_Properties icon loaded: {icon_path}\n")
                break

        # Connect to MeasureMass macro
        def run_measure_mass():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "MeasureMass.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Measure Mass error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"MeasureMass macro not found: {macro_path}\n")

        action_mass.triggered.connect(run_measure_mass)

        # Add to toolbar
        toolbar.addAction(action_mass)

        # =========================================
        # Button 8: Model Parameters
        # =========================================
        action_model_params = QtGui.QAction(mw)
        action_model_params.setToolTip('View and edit model parameters (Part Number, Description, Revision, etc.)')
        action_model_params.setObjectName("BNC_ModelParameters_Action")

        # Load Model_Parameters icon
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Model_Parameters.svg")
            if os.path.exists(icon_path):
                action_model_params.setIcon(QtGui.QIcon(icon_path))
                FreeCAD.Console.PrintLog(f"✓ Model_Parameters icon loaded: {icon_path}\n")
                break

        # Connect to ModelParameters macro
        def run_model_parameters():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "ModelParameters.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Model Parameters error: {str(e)}\n")
            else:
                FreeCAD.Console.PrintError(f"ModelParameters macro not found: {macro_path}\n")

        action_model_params.triggered.connect(run_model_parameters)

        # Add to toolbar
        toolbar.addAction(action_model_params)

        # =========================================
        # Button 9: Plane Display (Toggle Datum Planes)
        # =========================================
        action_plane_display = QtGui.QAction(mw)
        action_plane_display.setToolTip('Toggle visibility of datum planes (XY, XZ, YZ) on all bodies\nLike Creo Plane Display')
        action_plane_display.setObjectName("BNC_PlaneDisplay_Action")
        action_plane_display.setCheckable(True)

        # Load Plane Display icon (PNG file or embedded PNG)
        plane_icon = _create_plane_display_icon()
        if plane_icon and not plane_icon.isNull():
            action_plane_display.setIcon(plane_icon)
        else:
            action_plane_display.setText("XYZ")
            FreeCAD.Console.PrintWarning("BNC CAD: Plane_Display icon failed, using text\n")

        def run_plane_display(checked):
            """Toggle XY, XZ, YZ datum plane visibility on all bodies."""
            doc = FreeCAD.ActiveDocument
            if not doc:
                FreeCAD.Console.PrintWarning("BNC CAD: No active document — open a model first\n")
                return

            # Recursively find all PartDesign::Body objects across ALL open documents
            # Also follows App::Link objects to find linked bodies
            def _find_bodies_in(objs, visited=None):
                if visited is None:
                    visited = set()
                result = []
                for obj in objs:
                    oid = id(obj)
                    if oid in visited:
                        continue
                    visited.add(oid)
                    if obj.isDerivedFrom("PartDesign::Body"):
                        result.append(obj)
                    # Follow App::Link to its linked object
                    if obj.isDerivedFrom("App::Link"):
                        linked = getattr(obj, "LinkedObject", None)
                        if linked is not None:
                            result.extend(_find_bodies_in([linked], visited))
                    # Recurse into Group containers (Assembly, Part, etc.)
                    if hasattr(obj, "Group"):
                        result.extend(_find_bodies_in(obj.Group, visited))
                return result

            # Search all open documents, not just the active one
            all_bodies = []
            seen_names = set()
            for doc_name in FreeCAD.listDocuments():
                d = FreeCAD.getDocument(doc_name)
                for b in _find_bodies_in(d.Objects):
                    key = (d.Name, b.Name)
                    if key not in seen_names:
                        seen_names.add(key)
                        all_bodies.append(b)
            bodies = all_bodies

            # Also find Assembly (or any container) origins in all open docs
            assembly_origins = []
            for doc_name in FreeCAD.listDocuments():
                d = FreeCAD.getDocument(doc_name)
                for obj in d.Objects:
                    # Skip PartDesign::Body — those are handled separately
                    if obj.isDerivedFrom("PartDesign::Body"):
                        continue
                    # Look for containers with an Origin (Assembly, Part, etc.)
                    origin = getattr(obj, "Origin", None)
                    if origin is not None and hasattr(origin, "OriginFeatures"):
                        assembly_origins.append((obj, origin))

            if not bodies and not assembly_origins:
                FreeCAD.Console.PrintWarning("BNC CAD: No Part Design bodies or assemblies found in this document\n")
                return

            show = checked  # True = show planes, False = hide planes
            count = 0

            # Toggle planes on PartDesign::Body origins
            for body in bodies:
                try:
                    origin = body.Origin
                    if show:
                        origin.ViewObject.Visibility = True
                    for feat in origin.OriginFeatures:
                        if hasattr(feat, 'Role') and '_Plane' in feat.Role:
                            feat.ViewObject.Visibility = show
                            count += 1
                    if not show:
                        origin.ViewObject.Visibility = False
                except Exception as exc:
                    FreeCAD.Console.PrintError(f"BNC CAD: Plane toggle error on {body.Label}: {exc}\n")

            # Toggle planes on Assembly / container origins
            for container, origin in assembly_origins:
                try:
                    if show:
                        origin.ViewObject.Visibility = True
                    for feat in origin.OriginFeatures:
                        if hasattr(feat, 'Role') and '_Plane' in feat.Role:
                            feat.ViewObject.Visibility = show
                            count += 1
                    if not show:
                        origin.ViewObject.Visibility = False
                except Exception as exc:
                    FreeCAD.Console.PrintError(f"BNC CAD: Plane toggle error on {container.Label} origin: {exc}\n")

            n_total = len(bodies) + len(assembly_origins)
            state = "shown" if show else "hidden"
            FreeCAD.Console.PrintMessage(f"BNC CAD: {count} datum planes {state} across {n_total} object(s)\n")

        action_plane_display.triggered.connect(run_plane_display)
        toolbar.addAction(action_plane_display)

        # =========================================
        # Button 10: Axis Display (Toggle Origin Axes)
        # =========================================
        action_axis_display = QtGui.QAction(mw)
        action_axis_display.setToolTip('Toggle visibility of origin axes (X, Y, Z) on all bodies and assemblies\nShows center axis lines for all circular parts')
        action_axis_display.setObjectName("BNC_AxisDisplay_Action")
        action_axis_display.setCheckable(True)

        # Load Axis Display icon (SVG)
        axis_icon = None
        axis_icon_dirs = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
        ]
        for d in axis_icon_dirs:
            svg_path = os.path.join(d, "Axis_Display.svg")
            if os.path.exists(svg_path):
                axis_icon = QtGui.QIcon(svg_path)
                if not axis_icon.isNull():
                    FreeCAD.Console.PrintMessage(f"BNC CAD: Axis_Display.svg loaded from {svg_path}\n")
                    break
        if axis_icon and not axis_icon.isNull():
            action_axis_display.setIcon(axis_icon)
        else:
            action_axis_display.setText("AXS")
            FreeCAD.Console.PrintWarning("BNC CAD: Axis_Display icon failed, using text\n")

        def run_axis_display(checked):
            """Toggle center-axis lines for cylindrical/conical features (Creo-style Axis Display)."""
            import Part as _Part

            doc = FreeCAD.ActiveDocument
            if not doc:
                FreeCAD.Console.PrintWarning("BNC CAD: No active document — open a model first\n")
                return

            # ---- 1. Remove any previously created center-axis objects ----
            for dname in FreeCAD.listDocuments():
                d = FreeCAD.getDocument(dname)
                to_del = [o.Name for o in d.Objects if o.Name.startswith("BNC_CAxis")]
                for n in to_del:
                    d.removeObject(n)

            if not checked:
                doc.recompute()
                FreeCADGui.updateGui()
                FreeCAD.Console.PrintMessage("BNC CAD: Center axes hidden\n")
                return

            # ---- 2. Collect shapes to scan ----
            #  In Part Design: PartDesign::Body gives the final shape.
            #  In Assembly: App::Link gives the transformed linked shape.
            shapes = []
            for obj in doc.Objects:
                if obj.Name.startswith("BNC_CAxis"):
                    continue
                if obj.isDerivedFrom("PartDesign::Body") or obj.isDerivedFrom("App::Link"):
                    sh = getattr(obj, "Shape", None)
                    if sh and not sh.isNull():
                        shapes.append(sh)

            # ---- 3. Find center axes of full-circle cylindrical / conical faces ----
            import math as _math
            raw_axes = []  # [(p1, p2, direction_unit_vector), ...]
            for sh in shapes:
                try:
                    for face in sh.Faces:
                        surf = face.Surface
                        stype = type(surf).__name__
                        if stype not in ("Cylinder", "Cone"):
                            continue
                        # u-parameter range gives angular span; full circle ≈ 2π
                        u0, u1, vmin, vmax = face.ParameterRange
                        angular_span = abs(u1 - u0)
                        if angular_span < _math.pi * 1.5:
                            # Skip partial cylinders (fillets, chamfers, etc.)
                            continue
                        center = surf.Center
                        axis_dir = FreeCAD.Vector(surf.Axis).normalize()
                        p1 = center + axis_dir * vmin
                        p2 = center + axis_dir * vmax
                        if (p2 - p1).Length > 1e-6:
                            raw_axes.append((p1, p2, axis_dir))
                except Exception:
                    pass

            if not raw_axes:
                FreeCAD.Console.PrintWarning("BNC CAD: No cylindrical or conical features found\n")
                return

            # ---- 4. Merge colinear axes (e.g. inner + outer cylinder of same hole) ----
            used = [False] * len(raw_axes)
            unique = []
            for i in range(len(raw_axes)):
                if used[i]:
                    continue
                p1, p2, d = raw_axes[i]
                t_vals = [0.0, (p2 - p1).dot(d)]
                for j in range(i + 1, len(raw_axes)):
                    if used[j]:
                        continue
                    p1j, p2j, dj = raw_axes[j]
                    # Check parallel (same or opposite direction)
                    if d.cross(dj).Length > 0.01:
                        continue
                    # Check colinear: (p1j - p1) must be parallel to d
                    diff = p1j - p1
                    if diff.Length > 1e-6 and diff.cross(d).Length > 0.01:
                        continue
                    # Same axis line — merge extents
                    used[j] = True
                    t_vals.append(diff.dot(d))
                    t_vals.append((p2j - p1).dot(d))
                tmin = min(t_vals)
                tmax = max(t_vals)
                unique.append((p1 + d * tmin, p1 + d * tmax, d))

            # ---- 5. Create visual center-line objects ----
            count = 0
            for p1, p2, axis_dir in unique:
                length = (p2 - p1).Length
                extend = max(length * 0.15, 1.0)  # extend at least 1 mm
                ep1 = p1 - axis_dir * extend
                ep2 = p2 + axis_dir * extend
                line = _Part.makeLine(tuple(ep1), tuple(ep2))
                obj = doc.addObject("Part::Feature", f"BNC_CAxis{count:03d}")
                obj.Shape = line
                obj.ViewObject.LineColor = (1.0, 0.0, 0.0)   # red center-line
                obj.ViewObject.LineWidth = 1.0
                obj.ViewObject.DrawStyle = "Dashdot"          # long-short dash
                obj.ViewObject.Selectable = False
                count += 1

            doc.recompute()
            FreeCADGui.updateGui()
            FreeCAD.Console.PrintMessage(f"BNC CAD: {count} center axis line(s) shown\n")

        action_axis_display.triggered.connect(run_axis_display)
        toolbar.addAction(action_axis_display)

        # =========================================
        # Finalize Toolbar
        # =========================================

        # Keep global reference to prevent garbage collection
        _persistent_toolbar = toolbar

        # Make sure toolbar is visible
        toolbar.setVisible(True)
        toolbar.show()

        FreeCAD.Console.PrintMessage("✓ BNC Custom toolbar created with 10 buttons\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error creating BNC toolbar: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


# Create toolbar with delay to ensure GUI is ready
QtCore.QTimer.singleShot(2000, create_persistent_toolbar)

FreeCAD.Console.PrintLog("BNC CAD: Persistent toolbar module loaded\n")
