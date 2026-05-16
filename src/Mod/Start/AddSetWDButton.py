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
from PySide import QtGui, QtCore, QtWidgets
import os

# Global reference to keep toolbar alive
_persistent_toolbar = None


def _create_plane_display_icon():
    """Create Plane Display icon - loads SVG/PNG file or uses embedded PNG data."""
    try:
        # Strategy 1: Load SVG or PNG file from icon directories
        icon_dirs = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "BNCCustomTools", "Resources", "icons"),
        ]
        for d in icon_dirs:
            for fname in ("Plane_Display.svg", "Plane_Display.png"):
                path = os.path.join(d, fname)
                if os.path.exists(path):
                    icon = QtGui.QIcon(path)
                    if not icon.isNull():
                        return icon

        # Strategy 2: Embedded PNG as base64 (works even if files missing)
        import base64
        b64 = (
            "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"
            "yEnq0oAAAAASUVORK5CYII=")
        png_data = base64.b64decode(b64)
        pixmap = QtGui.QPixmap()
        if pixmap.loadFromData(png_data, "PNG") and not pixmap.isNull():
            return QtGui.QIcon(pixmap)

        return None
    except Exception:
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
            FreeCAD.Console.PrintMessage("BNC Tools: GUI not ready, retrying in 500ms...\n")
            QtCore.QTimer.singleShot(500, create_persistent_toolbar)
            return

        mw = FreeCADGui.getMainWindow()

        # Check if toolbar already exists
        if _persistent_toolbar is not None:
            return

        # Remove stale toolbar from previous session so it gets recreated with all buttons
        for old_tb in mw.findChildren(QtGui.QToolBar):
            if old_tb.objectName() == "BNC_Custom_Toolbar":
                mw.removeToolBar(old_tb)
                old_tb.deleteLater()
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
                break

        # Connect directly to rename function (avoids command registration timing issues)
        def run_rename():
            import sys
            rename_mod_path = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCGlobal", "BNCGlobal", "Gui")
            if rename_mod_path not in sys.path:
                sys.path.insert(0, rename_mod_path)
            try:
                from CommandStdVersionRename import main as rename_main
                rename_main()
            except Exception as e:
                FreeCAD.Console.PrintError("BNC Rename error: " + str(e) + "\n")

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

                break

        # Connect to Apply Material macro
        def run_apply_material():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "Apply_Material.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError("BNC Apply Material error: " + str(e) + "\n")
            else:
                FreeCAD.Console.PrintError("BNC Apply Material: macro not found at " + macro_path + "\n")

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
                break

        # Connect to MeasureMass macro
        def run_measure_mass():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "MeasureMass.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception:
                    pass

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

                break

        # Connect to ModelParameters macro
        def run_model_parameters():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "ModelParameters.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception:
                    pass

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


        def run_plane_display(checked):
            """Toggle XY, XZ, YZ datum plane visibility on all bodies."""
            doc = FreeCAD.ActiveDocument
            if not doc:
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
                except Exception:
                    pass

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
                except Exception:
                    pass

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
                    break
        if axis_icon and not axis_icon.isNull():
            action_axis_display.setIcon(axis_icon)
        else:
            action_axis_display.setText("AXS")

        def run_axis_display(checked):
            """Toggle center-axis lines for cylindrical/conical features (Creo-style Axis Display)."""
            import Part as _Part

            doc = FreeCAD.ActiveDocument
            if not doc:
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
                return

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

        action_axis_display.triggered.connect(run_axis_display)
        toolbar.addAction(action_axis_display)

        # =========================================
        # Button 11: Datum Point Display (Toggle Datum Points)
        # =========================================
        action_point_display = QtGui.QAction(mw)
        action_point_display.setToolTip('Toggle visibility of datum points on all bodies and assemblies\nShows/hides reference points')
        action_point_display.setObjectName("BNC_PointDisplay_Action")
        action_point_display.setCheckable(True)

        # Load Datum Point Display icon (SVG)
        point_icon = None
        point_icon_dirs = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "BNCCustomTools", "Resources", "icons"),
        ]
        for d in point_icon_dirs:
            svg_path = os.path.join(d, "Datum_Point_Display.svg")
            if os.path.exists(svg_path):
                point_icon = QtGui.QIcon(svg_path)
                if not point_icon.isNull():
                    break
        if point_icon and not point_icon.isNull():
            action_point_display.setIcon(point_icon)
        else:
            action_point_display.setText("PT")

        def run_point_display(checked):
            """Toggle datum point visibility on all bodies and assemblies."""
            doc = FreeCAD.ActiveDocument
            if not doc:

                return

            # Recursively find all PartDesign::Body objects across ALL open documents
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

            # Search all open documents
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
                return

            show = checked  # True = show points, False = hide points

            # Toggle ONLY user-created datum points on PartDesign::Body
            # (NOT origin points - those stay as-is)
            for body in bodies:
                try:
                    # Check what attributes the body has
                    body_objects = []
                    if hasattr(body, 'Group'):
                        body_objects = body.Group
                    elif hasattr(body, 'Model'):
                        body_objects = body.Model
                    else:
                        body_objects = [obj for obj in body.OutList if hasattr(obj, 'TypeId')]
                    
                    for obj in body_objects:
                        # Check for datum points (both Part::DatumPoint and PartDesign::Point)
                        is_datum_point = False
                        if hasattr(obj, 'isDerivedFrom'):
                            is_datum_point = obj.isDerivedFrom("Part::DatumPoint") or obj.isDerivedFrom("PartDesign::Point")
                        elif hasattr(obj, 'TypeId'):
                            is_datum_point = obj.TypeId in ["Part::DatumPoint", "PartDesign::Point"]
                        
                        if is_datum_point:
                            obj.ViewObject.Visibility = show
                            
                except Exception:
                    pass  # Silently handle errors

        action_point_display.triggered.connect(run_point_display)
        toolbar.addAction(action_point_display)

        # =========================================
        # Button 12: Family Table (Creo-style variant generator)
        # =========================================
        action_family_table = QtGui.QAction(mw)
        action_family_table.setToolTip('Open Family Table editor\nCreate part/assembly variants with different features and dimensions (Creo-style)')
        action_family_table.setObjectName("BNC_FamilyTable_Action")

        # Load Family Table icon
        family_icon = None
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "FamilyTable.svg")
            if os.path.exists(icon_path):
                family_icon = QtGui.QIcon(icon_path)
                if not family_icon.isNull():
                    break
        
        if family_icon and not family_icon.isNull():
            action_family_table.setIcon(family_icon)
        else:
            action_family_table.setText("FAM")

        # Connect to FamilyTable macro
        def run_family_table():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "FamilyTable.FCMacro")
            if os.path.exists(macro_path):
                try:
                    exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
                except Exception as e:
                    FreeCAD.Console.PrintError(f"FamilyTable error: {e}\n")

        action_family_table.triggered.connect(run_family_table)
        toolbar.addAction(action_family_table)

        # Store action reference for workbench hiding
        toolbar._action_family_table = action_family_table

        # =========================================
        # Button 13: Sketch Show/Hide Toggle
        # =========================================
        action_sketch_toggle = QtGui.QAction(mw)
        action_sketch_toggle.setToolTip('Toggle Sketch Visibility\nShow or hide all sketches in the active document')
        action_sketch_toggle.setObjectName("BNC_SketchToggle_Action")

        # Load Sketch Show/Hide icon
        sketch_icon = None
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "Sketch_ShowHide.svg")
            if os.path.exists(icon_path):
                sketch_icon = QtGui.QIcon(icon_path)
                if not sketch_icon.isNull():
                    break
        
        if sketch_icon and not sketch_icon.isNull():
            action_sketch_toggle.setIcon(sketch_icon)
        else:
            action_sketch_toggle.setText("SKE")

        # Toggle sketch visibility function
        def toggle_sketch_visibility():
            try:
                doc = FreeCAD.ActiveDocument
                if not doc:
                    FreeCAD.Console.PrintWarning("No active document\n")
                    return
                
                # Find all Sketcher::SketchObject objects
                sketches = [obj for obj in doc.Objects if obj.TypeId == 'Sketcher::SketchObject']
                
                if not sketches:
                    FreeCAD.Console.PrintMessage("No sketches found in active document\n")
                    return
                
                # Check current visibility state (if any sketch is visible, hide all; otherwise show all)
                any_visible = False
                for sketch in sketches:
                    if hasattr(sketch, 'ViewObject') and sketch.ViewObject:
                        if sketch.ViewObject.Visibility:
                            any_visible = True
                            break
                
                # Toggle: if any visible, hide all; if all hidden, show all
                new_state = not any_visible
                
                count = 0
                for sketch in sketches:
                    if hasattr(sketch, 'ViewObject') and sketch.ViewObject:
                        sketch.ViewObject.Visibility = new_state
                        count += 1
                
                state_msg = "shown" if new_state else "hidden"
                FreeCAD.Console.PrintMessage(f"✓ {count} sketch(es) {state_msg}\n")
                
                # Refresh view
                if FreeCADGui.ActiveDocument:
                    FreeCADGui.ActiveDocument.ActiveView.fitAll()
                    
            except Exception as e:
                FreeCAD.Console.PrintError(f"Sketch toggle error: {e}\n")
                import traceback
                FreeCAD.Console.PrintError(traceback.format_exc())

        action_sketch_toggle.triggered.connect(toggle_sketch_visibility)
        toolbar.addAction(action_sketch_toggle)

        # =========================================
        # Workbench Change Detection (hide Family Table in TechDraw)
        # =========================================
        def on_workbench_activated():
            """Hide Family Table button only in TechDraw workbench."""
            try:
                wb = FreeCADGui.activeWorkbench()
                wb_name = wb.name() if hasattr(wb, 'name') else str(wb.__class__.__name__)
                
                # Hide Family Table in TechDraw workbench only
                if hasattr(toolbar, '_action_family_table'):
                    is_techdraw = 'TechDraw' in wb_name
                    toolbar._action_family_table.setVisible(not is_techdraw)
            except Exception:
                pass

        # Connect to workbench activation signal
        mw.workbenchActivated.connect(on_workbench_activated)
        
        # Initial state (hide if starting in TechDraw)
        on_workbench_activated()

        # =========================================
        # View Manager Button
        # =========================================
        action_vm = QtGui.QAction(mw)
        action_vm.setToolTip("View Manager - Apply or insert named views (like Creo)")
        vm_icon = os.path.join(FreeCAD.getHomePath(), "Mod", "BNCTechDraw", "icons", "BNC_ViewManager.svg")
        if os.path.exists(vm_icon):
            action_vm.setIcon(QtGui.QIcon(vm_icon))
        else:
            action_vm.setText("Views")
        def _run_view_manager():
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "ViewManager.FCMacro")
            if os.path.exists(macro_path):
                with open(macro_path, encoding="utf-8") as _f:
                    exec(_f.read(), {"__file__": macro_path, "__name__": "__main__"})
        action_vm.triggered.connect(_run_view_manager)
        toolbar.addAction(action_vm)
        toolbar.addSeparator()

        # =========================================
        # Finalize Toolbar
        # =========================================

        # Keep global reference to prevent garbage collection
        _persistent_toolbar = toolbar

        # Make sure toolbar is visible
        toolbar.setVisible(True)
        toolbar.show()

        # =========================================
        # Selection Filter Widget (Status Bar)
        # =========================================
        try:
            # Run SelectionFilter macro to add widget to status bar
            macro_path = os.path.join(FreeCAD.getHomePath(), "Macro", "SelectionFilter.FCMacro")
            if os.path.exists(macro_path):
                # Set marker to prevent popup on auto-run
                setattr(mw, '_sel_filter_auto_run', True)
                with open(macro_path, encoding="utf-8") as f:
                    exec(f.read(), {"__name__": "__main__"})
                setattr(mw, '_sel_filter_auto_run', False)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"Selection Filter init failed: {e}\n")

    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC Tools toolbar creation failed: {str(e)}\n")
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())


def _find_file_toolbar(mw):
    """Return the File toolbar, trying multiple names/titles."""
    # Try by object name first
    for tb in mw.findChildren(QtGui.QToolBar):
        if tb.objectName().lower() in ("file operations", "file", "filetoolbar"):
            return tb
    # Try by window title
    for tb in mw.findChildren(QtGui.QToolBar):
        if tb.windowTitle().lower() in ("file", "file operations"):
            return tb
    # Fallback: find toolbar that contains Std_New action (reliable marker for File toolbar)
    for tb in mw.findChildren(QtGui.QToolBar):
        for act in tb.actions():
            if act.objectName() in ("Std_New", "Std_Open"):
                return tb
    return None


def _add_setwd_to_file_toolbar():
    """Inject Set Working Directory button into FreeCAD's built-in File toolbar."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _add_setwd_to_file_toolbar)
            return

        file_toolbar = _find_file_toolbar(mw)

        if file_toolbar is None:
            FreeCAD.Console.PrintWarning("BNC CAD: File toolbar not found — will retry after next workbench switch\n")
            return

        # Don't add twice
        for act in file_toolbar.actions():
            if act.objectName() == "BNC_SetWD_Action":
                return

        action_setwd = QtGui.QAction(mw)
        action_setwd.setToolTip('Set the working directory for file operations\nKeyboard: Ctrl+Shift+W')
        action_setwd.setObjectName("BNC_SetWD_Action")

        icon_base_paths = [
            os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "Resources", "icons"),
            os.path.join(FreeCAD.getHomePath(), "Mod", "BNCCustomTools", "Resources", "icons"),
        ]
        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "SET_WD.svg")
            if os.path.exists(icon_path):
                action_setwd.setIcon(QtGui.QIcon(icon_path))
                break

        action_setwd.triggered.connect(lambda: FreeCADGui.runCommand('Std_SetWorkingDirectory'))

        # Insert as 2nd item (right after the New file button)
        actions = file_toolbar.actions()
        if len(actions) >= 2:
            file_toolbar.insertAction(actions[1], action_setwd)
        else:
            file_toolbar.addAction(action_setwd)
        FreeCAD.Console.PrintLog("BNC CAD: Set Working Directory added to File toolbar\n")

        # --- Save As button ---
        # Don't add twice
        for act in file_toolbar.actions():
            if act.objectName() == "BNC_SaveAs_Action":
                return

        action_saveas = QtGui.QAction(mw)
        action_saveas.setToolTip('Save As with automatic version numbering\nKeyboard: Ctrl+Shift+S')
        action_saveas.setObjectName("BNC_SaveAs_Action")

        for base_path in icon_base_paths:
            icon_path = os.path.join(base_path, "save_as.svg")
            if os.path.exists(icon_path):
                action_saveas.setIcon(QtGui.QIcon(icon_path))
                break

        action_saveas.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSaveAs'))

        # Insert right after the Save button (Std_Save)
        actions = file_toolbar.actions()
        save_idx = next((i for i, a in enumerate(actions) if a.objectName() in ("Std_Save", "Std_SaveAs")), None)
        if save_idx is not None and save_idx + 1 < len(actions):
            file_toolbar.insertAction(actions[save_idx + 1], action_saveas)
        elif save_idx is not None:
            file_toolbar.addAction(action_saveas)
        else:
            file_toolbar.addAction(action_saveas)
        FreeCAD.Console.PrintLog("BNC CAD: Save As added to File toolbar next to Save\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: Failed to add SetWD to File toolbar: {e}\n")


def _connect_setwd_on_workbench():
    """Re-inject SetWD button after every workbench switch (toolbar gets recreated)."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _connect_setwd_on_workbench)
            return
        mw.workbenchActivated.connect(
            lambda: QtCore.QTimer.singleShot(400, _add_setwd_to_file_toolbar)
        )
        FreeCAD.Console.PrintLog("BNC CAD: SetWD workbench hook installed\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: _connect_setwd_on_workbench error: {e}\n")


class _TaskPanelRenamer(QtCore.QObject):
    """Event filter that renames 'New Body' to 'New Part' in PartDesign task panel."""

    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.ChildAdded, QtCore.QEvent.Show):
            QtCore.QTimer.singleShot(50, self._rename)
        return False

    def _rename(self):
        try:
            mw = FreeCADGui.getMainWindow()
            if not mw:
                return
            for widget in mw.findChildren(QtWidgets.QWidget):
                if not widget.isVisible():
                    continue
                if isinstance(widget, (QtWidgets.QPushButton, QtWidgets.QCommandLinkButton,
                                       QtWidgets.QAbstractButton, QtWidgets.QLabel)):
                    if widget.text() == "New Body":
                        widget.setText("New Part")
        except Exception:
            pass


_task_panel_renamer = None


def _fix_std_part_name():
    """Rename Std_Part action from 'New Part' to 'Std Part' and fix its tooltip."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _fix_std_part_name)
            return
        fixed = False
        for tb in mw.findChildren(QtGui.QToolBar):
            for action in tb.actions():
                # Match by object name OR by text being "New Part" with Std_Part tooltip context
                is_std_part = (
                    action.objectName() in ("Std_Part", "Std Part")
                    or (action.text() == "New Part" and "general-purpose" in action.toolTip())
                    or (action.text() == "New Part" and "TopoShape" in action.toolTip())
                    or (action.text() == "New Part" and "Std_Part" in action.toolTip())
                )
                if is_std_part:
                    action.setText("Std Part")
                    # Rebuild tooltip to match desired style
                    action.setToolTip(
                        "<b>Std Part</b><br/><br/>"
                        "Creates a part, which is a general-purpose container to group objects "
                        "so they act as a unit in the 3D view. It is intended to arrange objects "
                        "that have a part TopoShape, like part primitives, Part Design bodies, "
                        "and other parts.<br/><br/>"
                        "<i>Std_Part</i>"
                    )
                    fixed = True
                    FreeCAD.Console.PrintLog("BNC CAD: Fixed Std_Part name and tooltip\n")
        if not fixed:
            # Retry once more after a short delay if toolbars not ready yet
            QtCore.QTimer.singleShot(1000, _fix_std_part_name)
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: _fix_std_part_name error: {e}\n")


def _install_task_panel_renamer():
    global _task_panel_renamer
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _install_task_panel_renamer)
            return
        _task_panel_renamer = _TaskPanelRenamer()
        # Watch the Tasks dock widget for child/show events
        for dock in mw.findChildren(QtWidgets.QDockWidget):
            if dock.windowTitle() in ("Tasks", "Task"):
                dock.installEventFilter(_task_panel_renamer)
                break
        # Also watch the main window itself as fallback
        mw.installEventFilter(_task_panel_renamer)
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: Task panel renamer error: {e}\n")


def _apply_partdesign_icons():
    """Force-replace PartDesign toolbar icons by directly setting QIcon on each action."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _apply_partdesign_icons)
            return

        icons_dir = os.path.join(FreeCAD.getHomePath(), "data", "Mod", "PartDesign", "Resources", "icons")
        if not os.path.isdir(icons_dir):
            return

        # Build a map: stem -> full path  (e.g. "PartDesign_Pad" -> "/path/PartDesign_Pad.svg")
        icon_map = {}
        for fname in os.listdir(icons_dir):
            if fname.lower().endswith(".svg"):
                stem = os.path.splitext(fname)[0]
                icon_map[stem] = os.path.join(icons_dir, fname)

        # Add group command mappings (dropdown buttons use first child icon)
        group_map = {
            "PartDesign_CompPrimitiveAdditive":    "PartDesign_AdditiveBox",
            "PartDesign_CompPrimitiveSubtractive": "PartDesign_SubtractiveBox",
            "PartDesign_CompSketcher":             "PartDesign_NewSketch",
        }
        for gname, icon_stem in group_map.items():
            if gname not in icon_map and icon_stem in icon_map:
                icon_map[gname] = icon_map[icon_stem]

        replaced = 0
        for tb in mw.findChildren(QtGui.QToolBar):
            for action in tb.actions():
                name = action.objectName()
                if name in icon_map:
                    action.setIcon(QtGui.QIcon(icon_map[name]))
                    replaced += 1

        # Also replace icons on QToolButton widgets (group/dropdown buttons)
        for btn in mw.findChildren(QtWidgets.QToolButton):
            action = btn.defaultAction()
            if action:
                name = action.objectName()
                if name in icon_map:
                    btn.setIcon(QtGui.QIcon(icon_map[name]))
                    replaced += 1

            # Traverse dropdown menu items inside group buttons
            menu = btn.menu()
            if menu:
                for menu_action in menu.actions():
                    mname = menu_action.objectName()
                    if mname in icon_map:
                        menu_action.setIcon(QtGui.QIcon(icon_map[mname]))
                        replaced += 1

        FreeCAD.Console.PrintLog(f"BNC CAD: Force-replaced {replaced} PartDesign icons\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: _apply_partdesign_icons error: {e}\n")


def _apply_partdesign_icons_on_wb():
    """Re-apply icons whenever workbench changes (toolbars reload)."""
    try:
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.workbenchActivated.connect(
                lambda: QtCore.QTimer.singleShot(400, _apply_partdesign_icons)
            )
    except Exception:
        pass

def _remap_file_menu_saveas():
    """Remap File > Save As... to call the BNC version save-as macro instead of Std_SaveAs."""
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            QtCore.QTimer.singleShot(500, _remap_file_menu_saveas)
            return

        # Find the File menu in the menu bar
        file_menu = None
        for action in mw.menuBar().actions():
            if action.text().replace("&", "").strip().lower() == "file":
                file_menu = action.menu()
                break

        if file_menu is None:
            FreeCAD.Console.PrintWarning("BNC CAD: File menu not found\n")
            return

        # Find the Save As action by object name or text
        saveas_action = None
        for act in file_menu.actions():
            name = act.objectName()
            text = act.text().replace("&", "").strip().lower()
            if name == "Std_SaveAs" or text in ("save as...", "save as"):
                saveas_action = act
                break

        if saveas_action is None:
            FreeCAD.Console.PrintWarning("BNC CAD: Save As menu action not found\n")
            return

        # Disconnect original trigger and connect to BNC version save-as
        try:
            saveas_action.triggered.disconnect()
        except Exception:
            pass
        saveas_action.triggered.connect(lambda: FreeCADGui.runCommand('Std_VersionSaveAs'))
        FreeCAD.Console.PrintLog("BNC CAD: File > Save As... remapped to Std_VersionSaveAs\n")
    except Exception as e:
        FreeCAD.Console.PrintError(f"BNC CAD: _remap_file_menu_saveas error: {e}\n")


# Create toolbar with delay to ensure GUI is ready
QtCore.QTimer.singleShot(2000, create_persistent_toolbar)
QtCore.QTimer.singleShot(2500, _add_setwd_to_file_toolbar)
QtCore.QTimer.singleShot(3000, _install_task_panel_renamer)
QtCore.QTimer.singleShot(3000, _fix_std_part_name)
QtCore.QTimer.singleShot(3500, _apply_partdesign_icons)
QtCore.QTimer.singleShot(4000, _apply_partdesign_icons_on_wb)
QtCore.QTimer.singleShot(3000, _connect_setwd_on_workbench)
QtCore.QTimer.singleShot(3500, _remap_file_menu_saveas)

def _connect_workbench_fix():
    try:
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.workbenchActivated.connect(lambda: QtCore.QTimer.singleShot(300, _fix_std_part_name))
    except Exception:
        pass

QtCore.QTimer.singleShot(3500, _connect_workbench_fix)
