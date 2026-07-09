# -*- coding: utf-8 -*-
# ANVIL CAD Custom Commands

import FreeCAD
import FreeCADGui
from PySide import QtGui, QtCore
import os
import re
import Part
import math

# =============================================================================
# NEW FILE COMMAND
# =============================================================================
class NewFileCommand:
    """Command to create a new file with options"""

    def GetResources(self):
        return {
            'Pixmap': 'NEW_FILE',
            'MenuText': 'New File',
            'ToolTip': 'Create a new file with type selection'
        }

    def Activated(self):
        """Execute when command is activated"""
        from .NewFileDialog import NewFileDialog

        dlg = NewFileDialog()
        if dlg.exec_():
            part_name = dlg.partName.text().strip()
            part_desc = dlg.partDesc.text().strip()
            file_type = dlg.get_selected_type()

            if not part_name:
                QtGui.QMessageBox.warning(None, "Error", "Part Name is required")
            else:
                # Create new document
                doc = FreeCAD.newDocument(part_name)
                doc.Label = part_name
                doc.Comment = part_desc

                # Switch workbench based on selection
                if file_type == "Sketch":
                    FreeCADGui.activateWorkbench("SketcherWorkbench")
                elif file_type == "Part Design":
                    FreeCADGui.activateWorkbench("PartDesignWorkbench")
                elif file_type == "Assembly":
                    try:
                        FreeCADGui.activateWorkbench("AssemblyWorkbench")
                    except:
                        QtGui.QMessageBox.information(None, "Assembly", "Assembly workbench not installed")
                elif file_type == "Drawing":
                    FreeCADGui.activateWorkbench("TechDrawWorkbench")

                FreeCADGui.ActiveDocument = doc

    def IsActive(self):
        """Command is always active"""
        return True


# =============================================================================
# OPEN FILE COMMAND
# =============================================================================
class OpenFileCommand:
    """Command to open a file with version control"""

    def GetResources(self):
        return {
            'Pixmap': 'Open',
            'MenuText': 'Open File',
            'ToolTip': 'Open file with version control support'
        }

    def Activated(self):
        """Execute when command is activated"""
        # Get working directory
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        wd = params.GetString("WorkingDirectory", "")

        if not wd or not os.path.isdir(wd):
            FreeCAD.Console.PrintError("Working Directory not set\n")
            QtGui.QMessageBox.warning(None, "Error", "Please set Working Directory first")
            return

        # Version regex
        version_re = re.compile(r"(.+)\.(\d{3})\.FCStd$", re.IGNORECASE)

        def scan_versions(directory):
            latest = {}
            all_files = []

            for f in os.listdir(directory):
                m = version_re.match(f)
                if not m:
                    continue

                base, v = m.group(1), int(m.group(2))
                full = os.path.join(directory, f)
                all_files.append(full)

                if base not in latest or v > latest[base][0]:
                    latest[base] = (v, full)

            latest_files = [v[1] for v in latest.values()]
            return latest_files, all_files

        # Custom file dialog
        dlg = QtGui.QFileDialog(None, "Open File (Version Controlled)", wd, "FreeCAD Files (*.FCStd)")
        dlg.setOption(QtGui.QFileDialog.DontUseNativeDialog, True)
        dlg.setFileMode(QtGui.QFileDialog.ExistingFile)
        dlg.setViewMode(QtGui.QFileDialog.Detail)

        # Checkbox
        chk = QtGui.QCheckBox("Show all versions")
        dlg.layout().addWidget(chk)

        # Update view
        def update_view():
            dlg.setDirectory(dlg.directory())
            current_dir = dlg.directory().absolutePath()
            latest, all_files = scan_versions(current_dir)

            if chk.isChecked():
                dlg.setNameFilter("FreeCAD Files (*.FCStd)")
            else:
                if latest:
                    patterns = " ".join([os.path.basename(f) for f in latest])
                    dlg.setNameFilter(f"Latest Versions ({patterns})")
                else:
                    dlg.setNameFilter("FreeCAD Files (*.FCStd)")

        chk.stateChanged.connect(update_view)
        dlg.directoryEntered.connect(lambda _: update_view())
        update_view()

        # Execute
        if dlg.exec_():
            file_path = dlg.selectedFiles()[0]
            FreeCAD.openDocument(file_path)
            FreeCAD.Console.PrintMessage(f"Opened: {os.path.basename(file_path)}\n")

    def IsActive(self):
        """Command is always active"""
        return True


# =============================================================================
# SAVE COMMAND (Version Save)
# =============================================================================
class SaveCommand:
    """Command to save with version control"""

    def GetResources(self):
        return {
            'Pixmap': 'save',
            'MenuText': 'Save',
            'ToolTip': 'Save document with version control'
        }

    def Activated(self):
        """Execute when command is activated"""
        # Get working directory
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        working_dir = params.GetString("WorkingDirectory", "")

        if not working_dir or not os.path.isdir(working_dir):
            FreeCAD.Console.PrintError("Working Directory not set or invalid!\n")
            QtGui.QMessageBox.warning(None, "Error", "Please set Working Directory first")
            return

        save_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/VersionSave")

        def latest_version(base):
            v = 1
            while os.path.exists(f"{base}.{v:03d}.FCStd"):
                v += 1
            return v - 1

        def get_valid_name(doc):
            label = (doc.Label or "").strip()
            if (not label) or label.lower().startswith("unnamed"):
                name, ok = QtGui.QInputDialog.getText(None, "Enter File Name", "File name is not defined.\nPlease enter a file name:")
                if not ok or not name.strip():
                    return None
                label = name.strip().replace(" ", "_")
                doc.Label = label
            return label.replace(" ", "_")

        def base_name(doc):
            if doc.FileName:
                name = os.path.basename(doc.FileName).replace(".FCStd", "")
                if "." in name:
                    name = name.rsplit(".", 1)[0]
                return name
            return get_valid_name(doc)

        def save_doc(doc):
            name = base_name(doc)
            if not name:
                return

            base = os.path.join(working_dir, name)
            last_v = latest_version(base)
            undo_now = int(getattr(doc, "UndoCount", 0))
            undo_key = f"{name}_Undo"
            last_undo = save_params.GetInt(undo_key, -1)

            # First version ever
            if last_v < 1:
                path = f"{base}.001.FCStd"
                doc.saveAs(path)
                save_params.SetInt(undo_key, undo_now)
                FreeCAD.Console.PrintMessage(f"{name} → Saved as .001\n")
                return

            changed = bool(getattr(doc, "Modified", False)) or (undo_now != last_undo)

            if changed:
                new_v = last_v + 1
                path = f"{base}.{new_v:03d}.FCStd"
                doc.saveAs(path)
                save_params.SetInt(undo_key, undo_now)
                FreeCAD.Console.PrintMessage(f"{name} → Modified → Saved as .{new_v:03d}\n")
            else:
                FreeCAD.Console.PrintMessage(f"{name} → No changes → skipped save\n")

        # Save all open documents
        for doc in FreeCAD.listDocuments().values():
            try:
                save_doc(doc)
            except Exception as e:
                FreeCAD.Console.PrintError(str(e) + "\n")

        FreeCAD.Console.PrintMessage(f"\n✔ Version save done in WD:\n{working_dir}\n")

    def IsActive(self):
        """Command is active when there's an active document"""
        return FreeCAD.ActiveDocument is not None


# =============================================================================
# SAVE AS COMMAND
# =============================================================================
class SaveAsCommand:
    """Command to save as with version control"""

    def GetResources(self):
        return {
            'Pixmap': 'save_as',
            'MenuText': 'Save As',
            'ToolTip': 'Save document as with version control'
        }

    def Activated(self):
        """Execute when command is activated"""
        doc = FreeCAD.ActiveDocument
        if not doc:
            return

        # Get working directory
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        working_dir = params.GetString("WorkingDirectory", os.path.expanduser("~"))

        # Get base name
        def clean_name(name):
            return name.replace(" ", "_")

        default_name = clean_name(doc.Label)

        # Save As Dialog
        dialog = QtGui.QFileDialog(None, "Save As (Version Controlled)", working_dir, "FreeCAD Files (*.FCStd)")
        dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        dialog.selectFile(default_name)

        if not dialog.exec_():
            return

        file_path = dialog.selectedFiles()[0]

        # Update working directory if changed
        new_dir = os.path.dirname(file_path)
        if new_dir != working_dir:
            params.SetString("WorkingDirectory", new_dir)
            os.chdir(new_dir)

        # Version logic
        base_name = os.path.basename(file_path).replace(".FCStd", "")
        base_path = os.path.join(new_dir, base_name)

        def latest_version(base):
            v = 1
            while os.path.exists(f"{base}.{v:03d}.FCStd"):
                v += 1
            return v - 1

        last_v = latest_version(base_path)

        save_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/VersionSave")
        undo_key = f"{base_name}_Undo"
        undo_now = doc.UndoCount
        last_undo = save_params.GetInt(undo_key, -1)

        # Save as with versioning
        if last_v == 0:
            path = f"{base_path}.001.FCStd"
            doc.saveAs(path)
            save_params.SetInt(undo_key, undo_now)
            FreeCAD.Console.PrintMessage(f"{base_name} → Saved as .001\n")
        else:
            if undo_now != last_undo:
                new_v = last_v + 1
                path = f"{base_path}.{new_v:03d}.FCStd"
                doc.saveAs(path)
                save_params.SetInt(undo_key, undo_now)
                FreeCAD.Console.PrintMessage(f"{base_name} → Modified → Saved as .{new_v:03d}\n")
            else:
                path = f"{base_path}.{last_v:03d}.FCStd"
                doc.saveAs(path)
                FreeCAD.Console.PrintMessage(f"{base_name} → No changes → Saved same version\n")

        FreeCAD.Console.PrintMessage(f"✔ Saved in directory:\n{new_dir}\n")

    def IsActive(self):
        """Command is active when there's an active document"""
        return FreeCAD.ActiveDocument is not None


# =============================================================================
# SET WORKING DIRECTORY COMMAND
# =============================================================================
class SetWorkingDirectoryCommand:
    """Command to set working directory"""

    def GetResources(self):
        return {
            'Pixmap': 'SET_WD',
            'MenuText': 'Set Working Directory',
            'ToolTip': 'Set the working directory for file operations'
        }

    def Activated(self):
        """Execute when command is activated"""
        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        start_dir = params.GetString("WorkingDirectory", os.path.expanduser("~"))

        folder = QtGui.QFileDialog.getExistingDirectory(None, "Select Working Directory", start_dir)

        if folder:
            params.SetString("WorkingDirectory", folder)
            os.chdir(folder)

            mw = FreeCADGui.getMainWindow()

            def update_title():
                base_title = mw.windowTitle().split(" — ")[0]
                mw.setWindowTitle(f"{base_title} — WD: {folder}")

            # Delay title update so FreeCAD cannot overwrite it
            QtCore.QTimer.singleShot(200, update_title)

            FreeCAD.Console.PrintMessage(f"Working Directory set to:\n{folder}\n")

    def IsActive(self):
        """Command is always active"""
        return True


# =============================================================================
# PIPE BENDING COMMAND
# =============================================================================
class PipeBendingCommand:
    """Command to create bent pipes"""

    def GetResources(self):
        return {
            'Pixmap': 'pipe_bending',
            'MenuText': 'Pipe Bending',
            'ToolTip': 'Create bent pipe designs'
        }

    def Activated(self):
        """Execute when command is activated"""
        from .PipeBendingDialog import PipeBendingDialog, create_bent_pipe

        dialog = PipeBendingDialog()

        if dialog.exec_():
            # Get parameters from dialog
            outer_radius = dialog.outer_radius.value()
            wall_thickness = dialog.wall_thickness.value()
            bend_radius = dialog.bend_radius.value()
            bend_angle = dialog.bend_angle.value()
            length1 = dialog.length1.value()
            length2 = dialog.length2.value()

            # Validate parameters
            if wall_thickness >= outer_radius:
                QtGui.QMessageBox.warning(None, "Invalid Parameters", "Wall thickness must be less than outer radius!")
            else:
                create_bent_pipe(outer_radius, wall_thickness, bend_radius, bend_angle, length1, length2)

    def IsActive(self):
        """Command is always active"""
        return True
