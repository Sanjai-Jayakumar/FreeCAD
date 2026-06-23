# SPDX-License-Identifier: LGPL-2.1-or-later
# /**************************************************************************
#                                                                           *
#    Copyright (c) 2024 Ondsel <development@ondsel.com>                     *
#                                                                           *
#    This file is part of FreeCAD.                                          *
#                                                                           *
#    FreeCAD is free software: you can redistribute it and/or modify it     *
#    under the terms of the GNU Lesser General Public License as            *
#    published by the Free Software Foundation, either version 2.1 of the   *
#    License, or (at your option) any later version.                        *
#                                                                           *
#    FreeCAD is distributed in the hope that it will be useful, but         *
#    WITHOUT ANY WARRANTY; without even the implied warranty of             *
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
#    Lesser General Public License for more details.                        *
#                                                                           *
#    You should have received a copy of the GNU Lesser General Public       *
#    License along with FreeCAD. If not, see                                *
#    <https://www.gnu.org/licenses/>.                                       *
#                                                                           *
# **************************************************************************/

import re
import os
import FreeCAD as App

from PySide.QtCore import QT_TRANSLATE_NOOP

if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtCore, QtGui, QtWidgets
    from PySide.QtGui import QIcon
    from PySide.QtCore import QTimer

import UtilsAssembly
import Preferences
import JointObject

translate = App.Qt.translate

__title__ = "Assembly Command Insert New Part"
__author__ = "Ondsel"
__url__ = "https://www.freecad.org"


class _BNCPartViewProxy:
    """ViewObject proxy that overrides the tree icon for BNC-created App::Part objects.
    Attached after part creation so the App::Link in the assembly tree mirrors this icon."""
    def getIcon(self):
        import os as _os
        return _os.path.normpath(_os.path.join(
            _os.path.dirname(__file__), "..", "PartDesign", "Gui", "Resources", "icons", "PartDesignWorkbench.svg"
        ))
    def attach(self, vobj): pass
    def onChanged(self, vobj, prop): pass
    def __getstate__(self): return None
    def __setstate__(self, state): pass


def _save_asm_doc_to_work_dir(doc):
    """Save *doc* to the configured Working Directory without showing a file-path dialog.

    If the document already has a filename it is saved in place (no dialog).
    Otherwise a versioned filename is built from the document label and saved
    directly into the Working Directory.  Falls back to the native saveAs dialog
    only when the Working Directory is not configured or does not exist.

    Returns True on success, False if the user cancelled or an error occurred.
    """
    import os as _os
    import re as _re

    if doc.FileName:
        try:
            doc.save()
            return True
        except Exception:
            return bool(Gui.getDocument(doc).saveAs())

    params = App.ParamGet("User parameter:BaseApp/Preferences/General")
    work_dir = params.GetString("WorkingDirectory", "").strip()

    if not work_dir or not _os.path.isdir(work_dir):
        return bool(Gui.getDocument(doc).saveAs())

    base_name = (doc.Label or "Assembly").strip()
    _name_pat = _re.compile(
        rf"^{_re.escape(base_name)}\.(\d{{3}})\.asm(?:\.FCStd)?$",
        _re.IGNORECASE,
    )
    existing = [
        int(m.group(1))
        for f in _os.listdir(work_dir)
        for m in [_name_pat.match(f)]
        if m
    ]
    next_ver = max(existing) + 1 if existing else 1
    versioned = f"{base_name}.{next_ver:03d}.asm.FCStd"
    full_path = _os.path.join(work_dir, versioned)

    try:
        doc.saveAs(full_path)
        return True
    except Exception as exc:
        QtWidgets.QMessageBox.critical(
            Gui.getMainWindow(),
            translate("Assembly", "Save Assembly"),
            translate("Assembly", "Failed to save document:\n{}").format(str(exc)),
        )
        return False


class CommandInsertNewPart:
    def __init__(self):
        pass

    def GetResources(self):
        return {
            "Pixmap": "Geofeaturegroup",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_InsertNewPart", "New Subassembly"),
            "Accel": "P",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_InsertNewPart",
                "Insert a new subassembly into the active assembly. The new subassembly's origin can be positioned in the assembly.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()

    def Activated(self):
        # Check if document is saved before proceeding
        doc = App.ActiveDocument
        if not doc.FileName:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText(
                translate(
                    "Assembly",
                    "The assembly document must be saved before inserting a new subassembly.",
                )
            )
            msgBox.setWindowTitle(translate("Assembly", "Save Document"))
            saveButton = msgBox.addButton(
                translate("Assembly", "Save"), QtWidgets.QMessageBox.AcceptRole
            )
            msgBox.addButton(QtWidgets.QMessageBox.Cancel)
            msgBox.exec_()
            if msgBox.clickedButton() == saveButton:
                if not _save_asm_doc_to_work_dir(doc):
                    return
            else:
                return

        panel = TaskAssemblyNewPart()
        dialog = Gui.Control.showDialog(panel)
        if dialog is not None:
            dialog.setAutoCloseOnDeletedDocument(True)
            dialog.setDocumentName(App.ActiveDocument.Name)


class TaskAssemblyNewPart(JointObject.TaskAssemblyCreateJoint):
    def __init__(self):
        super().__init__(0, None, True)

        self.assembly = UtilsAssembly.activeAssembly()

        # Retrieve the existing layout of `self.form`
        mainLayout = self.form.layout()

        # Add a name input
        nameLayout = QtWidgets.QHBoxLayout()
        nameLabel = QtWidgets.QLabel(translate("Assembly", "Subassembly name"))
        self.nameEdit = QtWidgets.QLineEdit()
        nameLayout.addWidget(nameLabel)
        nameLayout.addWidget(self.nameEdit)
        mainLayout.addLayout(nameLayout)
        self.nameEdit.setText(translate("Assembly", "Subassembly"))

        # Add a checkbox
        self.createInNewFileCheck = QtWidgets.QCheckBox(
            translate("Assembly", "Create subassembly in new file")
        )
        mainLayout.addWidget(self.createInNewFileCheck)
        self.createInNewFileCheck.setChecked(
            Preferences.preferences().GetBool("PartInNewFile", True)
        )

        # Wrap the joint creation UI in a groupbox
        jointGroupBox = QtWidgets.QGroupBox(translate("Assembly", "Joint new subassembly origin"))
        jointLayout = QtWidgets.QVBoxLayout(jointGroupBox)
        jointLayout.addWidget(self.jForm)
        jointLayout.setContentsMargins(0, 0, 0, 0)
        jointLayout.setSpacing(0)
        mainLayout.addWidget(jointGroupBox)

        self.link = self.assembly.newObject("App::Link", "Link")
        # add the link as the first object of the joint
        Gui.Selection.addSelection(
            self.assembly.Document.Name, self.assembly.Name, self.link.Name + "."
        )

    def createPart(self):
        partName = self.nameEdit.text()
        newFile = self.createInNewFileCheck.isChecked()

        doc = self.assembly.Document
        if newFile:
            doc = App.newDocument(partName)

        part, body = UtilsAssembly.createPart(partName, doc)

        App.setActiveDocument(self.assembly.Document.Name)

        # Then we need to link the part.
        if newFile:
            # --- Versioned save into Working Directory ---
            import os as _os
            import re as _re

            params = App.ParamGet("User parameter:BaseApp/Preferences/General")
            work_dir = params.GetString("WorkingDirectory", "").strip()

            if not work_dir or not _os.path.isdir(work_dir):
                QtWidgets.QMessageBox.warning(
                    Gui.getMainWindow(),
                    translate("Assembly", "New Subassembly"),
                    translate(
                        "Assembly",
                        "Working Directory is not set or does not exist.\n"
                        "Please set it via the Set Working Directory macro first.",
                    ),
                )
                App.closeDocument(doc.Name)
                return

            _name_pattern = _re.compile(
                rf"^{_re.escape(partName)}\.(\d{{3}})\.prt(?:\.FCStd)?$",
                _re.IGNORECASE,
            )
            existing_versions = [
                int(m.group(1))
                for f in _os.listdir(work_dir)
                for m in [_name_pattern.match(f)]
                if m
            ]

            if existing_versions:
                QtWidgets.QMessageBox.critical(
                    Gui.getMainWindow(),
                    translate("Assembly", "New Subassembly"),
                    translate(
                        "Assembly",
                        "A file named '{}' already exists in the Working Directory.\n"
                        "Please choose a different name."
                    ).format(partName),
                )
                App.closeDocument(doc.Name)
                return

            versioned_filename = f"{partName}.001.prt.FCStd"
            full_save_path = _os.path.join(work_dir, versioned_filename)

            try:
                doc.saveAs(full_save_path)
                App.setActiveDocument(self.assembly.Document.Name)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    Gui.getMainWindow(),
                    translate("Assembly", "New Subassembly"),
                    translate("Assembly", "Failed to save document:\n{}").format(str(e)),
                )
                App.closeDocument(doc.Name)
                return

        self.link.LinkedObject = part
        self.link.touch()

        self.link.Label = part.Label

        # Set the body as active in the assembly doc
        self.expandLinkManually(self.link)
        doc = self.assembly.Document
        Gui.getDocument(doc).ActiveView.setActiveObject("pdbody", body)
        doc.recompute()

    def expandLinkManually(self, link):
        # Should not be necessary
        # This is a workaround of https://github.com/FreeCAD/FreeCAD/issues/17904
        mw = Gui.getMainWindow()
        trees = mw.findChildren(QtGui.QTreeWidget)

        Gui.Selection.addSelection(link)
        for tree in trees:
            for item in tree.selectedItems():
                tree.expandItem(item)

    def accept(self):
        if len(self.refs) != 2:
            # if the joint is not complete we cancel the joint but not the new part!
            self.joint.Document.removeObject(self.joint.Name)
        else:
            JointObject.solveIfAllowed(self.assembly)
            self.joint.Visibility = False
            cmds = UtilsAssembly.generatePropertySettings(self.joint)
            Gui.doCommand(cmds)

        self.deactivate()

        self.createPart()

        App.closeActiveTransaction()

        return True

    def deactivate(self):
        Preferences.preferences().SetBool("PartInNewFile", self.createInNewFileCheck.isChecked())
        super().deactivate()


class NewBodyDialog(QtWidgets.QDialog):
    """Dialog that collects file name and description for a new part/assembly document."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("Assembly", "New Part"))
        self.setMinimumWidth(380)

        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._nameLabel = QtWidgets.QLabel(translate("Assembly", "File / Part name:"))
        self.nameEdit = QtWidgets.QLineEdit()
        self.nameEdit.setPlaceholderText(translate("Assembly", "e.g. Bracket_001"))
        layout.addRow(self._nameLabel, self.nameEdit)

        self.descEdit = QtWidgets.QLineEdit()
        self.descEdit.setPlaceholderText(translate("Assembly", "Short description"))
        layout.addRow(translate("Assembly", "Description:"), self.descEdit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.nameEdit.setFocus()

    def setNameLabel(self, text):
        """Change the name field label (e.g. for sub-assembly dialogs)."""
        self._nameLabel.setText(text)

    def _on_accept(self):
        if not self.nameEdit.text().strip():
            QtWidgets.QMessageBox.warning(
                self,
                translate("Assembly", "New Part"),
                translate("Assembly", "Please enter a file / body name."),
            )
            return
        self.accept()

    def getName(self):
        return self.nameEdit.text().strip()

    def getDescription(self):
        return self.descEdit.text().strip()


def _ensure_mp_properties(obj):
    """Add MP_ model-parameter properties to *obj* if not already present."""
    props = {
        "MP_PartNumber": "App::PropertyString",
        "MP_Description": "App::PropertyString",
        "MP_Revision": "App::PropertyString",
        "MP_Weight": "App::PropertyFloat",
        "MP_BOMType": "App::PropertyString",
        "MP_Type": "App::PropertyString",
        "MP_Material": "App::PropertyString",
    }
    for pname, ptype in props.items():
        if not hasattr(obj, pname):
            obj.addProperty(ptype, pname, "Model Parameters")


class CommandInsertNewBody:
    """Create a new FreeCAD document containing one PartDesign Body and link it into the assembly."""

    def __init__(self):
        pass

    def GetResources(self):
        return {
            "Pixmap": "PartDesign_Body",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_InsertNewBody", "New Part"),
            "Accel": "",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_InsertNewBody",
                "Create a new document with a PartDesign Body and link it into the active assembly.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()

    def Activated(self):
        assembly = UtilsAssembly.activeAssembly()
        if not assembly:
            return

        # FreeCAD requires the assembly document to be saved before cross-document
        # links can be created. Prompt the user to save first.
        asm_doc = assembly.Document
        if not asm_doc.FileName:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText(
                translate(
                    "Assembly",
                    "The assembly document must be saved before inserting a new part.",
                )
            )
            msgBox.setWindowTitle(translate("Assembly", "Save Document"))
            saveButton = msgBox.addButton(
                translate("Assembly", "Save"), QtWidgets.QMessageBox.AcceptRole
            )
            msgBox.addButton(QtWidgets.QMessageBox.Cancel)
            msgBox.exec_()
            if msgBox.clickedButton() == saveButton:
                if not _save_asm_doc_to_work_dir(asm_doc):
                    return
            else:
                return

        # --- Show dialog ---
        dlg = NewBodyDialog(Gui.getMainWindow())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        body_name = dlg.getName()
        description = dlg.getDescription()

        # --- Versioned save path check first (before creating any documents) ---
        import os as _os
        import re as _re

        params = App.ParamGet("User parameter:BaseApp/Preferences/General")
        work_dir = params.GetString("WorkingDirectory", "").strip()

        if not work_dir or not _os.path.isdir(work_dir):
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                translate("Assembly", "New Part"),
                translate(
                    "Assembly",
                    "Working Directory is not set or does not exist.\n"
                    "Please set it via the Set Working Directory macro first.",
                ),
            )
            return

        _name_pattern = _re.compile(
            rf"^{_re.escape(body_name)}\.(\d{{3}})\.prt(?:\.FCStd)?$",
            _re.IGNORECASE,
        )
        existing_versions = [
            int(m.group(1))
            for f in _os.listdir(work_dir)
            for m in [_name_pattern.match(f)]
            if m
        ]
        if existing_versions:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Part"),
                translate(
                    "Assembly",
                    "A file named '{}' already exists in the Working Directory.\n"
                    "Please choose a different name."
                ).format(body_name),
            )
            return

        versioned_filename = f"{body_name}.001.prt.FCStd"
        full_save_path = _os.path.join(work_dir, versioned_filename)

        # --- Create new document ---
        new_doc = App.newDocument(body_name)
        new_doc.Label = body_name

        # --- Create App::Part > PartDesign::Body (same structure as rest of codebase) ---
        part, body = UtilsAssembly.createPart(body_name, new_doc)
        part.Label = body_name

        # Override the tree icon to show PartDesign workbench icon
        if App.GuiUp:
            try:
                part.ViewObject.Proxy = _BNCPartViewProxy()
            except Exception:
                pass

        # --- Add model parameters to document and part ---
        for target in (new_doc, part):
            _ensure_mp_properties(target)
            target.MP_PartNumber = body_name
            target.MP_Description = description

        new_doc.recompute()

        try:
            new_doc.saveAs(full_save_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Part"),
                translate("Assembly", "Failed to save document:\n{}").format(str(e)),
            )
            App.closeDocument(new_doc.Name)
            return

        # --- Switch back to assembly document and create link ---
        App.setActiveDocument(asm_doc.Name)
        App.setActiveTransaction("Insert New Part")

        link = assembly.newObject("App::Link", "Link")
        link.Label = body_name  # set before LinkedObject so name is correct even on error
        try:
            link.LinkedObject = part  # link to App::Part, not PartDesign::Body
        except Exception as e:
            assembly.Document.removeObject(link.Name)
            App.closeActiveTransaction()
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Part"),
                translate("Assembly", "Failed to link part into assembly:\n{}").format(str(e)),
            )
            return

        link.touch()
        assembly.Document.recompute()
        App.closeActiveTransaction()

        # Stay in the current tab — no document switch needed.


class CommandInsertNewAssembly:
    """Create a new FreeCAD document with an Assembly and link it into the active assembly."""

    def __init__(self):
        pass

    def GetResources(self):
        import os as _os
        _icon = _os.path.normpath(_os.path.join(
            _os.path.dirname(__file__), "Gui", "Resources", "icons", "Subassembly.svg"
        ))
        return {
            "Pixmap": _icon,
            "MenuText": QT_TRANSLATE_NOOP("Assembly_InsertNewAssembly", "Create Subassembly"),
            "Accel": "",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_InsertNewAssembly",
                "Create a new document with an Assembly and link it into the active assembly.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()

    def Activated(self):
        assembly = UtilsAssembly.activeAssembly()
        App.Console.PrintMessage(
            "[Asm] InsertNewAssembly: assembly={} doc={}\n".format(
                getattr(assembly, "Label", None) if assembly else None,
                getattr(getattr(assembly, "Document", None), "Label", None) if assembly else None,
            )
        )
        if not assembly:
            return

        # Remember the original tab so we can stay on it after creating new docs.
        # App.newDocument() switches tabs; we always restore to the caller's tab.
        original_active_doc_name = App.ActiveDocument.Name if App.ActiveDocument else None

        # Assembly document must be saved before cross-document links can be created
        asm_doc = assembly.Document
        if not asm_doc.FileName:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText(
                translate(
                    "Assembly",
                    "The assembly document must be saved before creating a subassembly.",
                )
            )
            msgBox.setWindowTitle(translate("Assembly", "Save Document"))
            saveButton = msgBox.addButton(
                translate("Assembly", "Save"), QtWidgets.QMessageBox.AcceptRole
            )
            msgBox.addButton(QtWidgets.QMessageBox.Cancel)
            msgBox.exec_()
            if msgBox.clickedButton() == saveButton:
                if not _save_asm_doc_to_work_dir(asm_doc):
                    return
            else:
                return

        # --- Show dialog ---
        dlg = NewBodyDialog(Gui.getMainWindow())
        dlg.setWindowTitle(translate("Assembly", "New Assembly"))
        dlg.setNameLabel(translate("Assembly", "File / Subassembly name:"))
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        asm_name = dlg.getName()
        description = dlg.getDescription()

        # --- Versioned save path check before creating any documents ---
        import os as _os
        import re as _re

        params = App.ParamGet("User parameter:BaseApp/Preferences/General")
        work_dir = params.GetString("WorkingDirectory", "").strip()

        if not work_dir or not _os.path.isdir(work_dir):
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                translate("Assembly", "New Assembly"),
                translate(
                    "Assembly",
                    "Working Directory is not set or does not exist.\n"
                    "Please set it via the Set Working Directory macro first.",
                ),
            )
            return

        _name_pattern = _re.compile(
            rf"^{_re.escape(asm_name)}\.(\d{{3}})\.asm(?:\.FCStd)?$",
            _re.IGNORECASE,
        )
        existing_versions = [
            int(m.group(1))
            for f in _os.listdir(work_dir)
            for m in [_name_pattern.match(f)]
            if m
        ]
        if existing_versions:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Assembly"),
                translate(
                    "Assembly",
                    "A file named '{}' already exists in the Working Directory.\n"
                    "Please choose a different name."
                ).format(asm_name),
            )
            return

        versioned_filename = f"{asm_name}.001.asm.FCStd"
        full_save_path = _os.path.join(work_dir, versioned_filename)

        # --- Create new document with Assembly object ---
        new_doc = App.newDocument(asm_name)
        new_doc.Label = asm_name

        sub_asm = new_doc.addObject("Assembly::AssemblyObject", asm_name)
        sub_asm.Label = asm_name
        sub_asm.Type = "Assembly"
        sub_asm.newObject("Assembly::JointGroup", "Joints")

        for target in (new_doc, sub_asm):
            _ensure_mp_properties(target)
            target.MP_PartNumber = asm_name
            target.MP_Description = description

        new_doc.recompute()

        try:
            new_doc.saveAs(full_save_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Assembly"),
                translate("Assembly", "Failed to save document:\n{}").format(str(e)),
            )
            App.closeDocument(new_doc.Name)
            return

        # --- Switch back to parent assembly document and create link ---
        App.Console.PrintMessage(
            "[Asm] InsertNewAssembly: switching to asm_doc.Name={} asm_doc.Label={}\n".format(
                asm_doc.Name, asm_doc.Label)
        )
        try:
            App.setActiveDocument(asm_doc.Name)
        except Exception as _e:
            App.Console.PrintMessage("[Asm] InsertNewAssembly: setActiveDocument failed: {}\n".format(_e))
        App.setActiveTransaction("Insert New Assembly")

        try:
            link = assembly.newObject("Assembly::AssemblyLink", "Link")
            App.Console.PrintMessage(
                "[Asm] InsertNewAssembly: link created={} in doc={}\n".format(
                    link.Name, link.Document.Name if link else "?")
            )
        except Exception as _e:
            App.Console.PrintMessage("[Asm] InsertNewAssembly: newObject failed: {}\n".format(_e))
            App.closeActiveTransaction()
            return

        link.Label = asm_name  # set label before LinkedObject so name is correct even on error
        try:
            link.LinkedObject = sub_asm
            App.Console.PrintMessage(
                "[Asm] InsertNewAssembly: LinkedObject set OK sub_asm={}\n".format(
                    getattr(sub_asm, "Label", "?"))
            )
        except Exception as e:
            App.Console.PrintMessage("[Asm] InsertNewAssembly: LinkedObject failed: {}\n".format(e))
            assembly.Document.removeObject(link.Name)
            App.closeActiveTransaction()
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Assembly"),
                translate("Assembly", "Failed to link subassembly:\n{}").format(str(e)),
            )
            return

        link.touch()
        assembly.Document.recompute()
        App.closeActiveTransaction()

        # Save the modified subassembly doc so the link persists on disk.
        try:
            if assembly.Document.FileName:
                assembly.Document.purgeTouched()
                assembly.Document.save()
        except Exception as _e:
            App.Console.PrintMessage("[Asm] InsertNewAssembly: save asm_doc failed: {}\n".format(_e))

        # --- Multi-level ancestor propagation ---
        # BFS upward through the linked-document graph so every ancestor doc
        # (not just the direct parent) gets its links touched and recomputed.
        # This ensures the model tree refreshes all the way to the root.
        _modified_set = {assembly.Document.Name}
        _visited = {assembly.Document.Name}
        while _modified_set:
            _next_set = set()
            for _doc in list(App.listDocuments().values()):
                if _doc.Name in _visited:
                    continue
                _needs = False
                for _obj in _doc.Objects:
                    try:
                        _lo = getattr(_obj, "LinkedObject", None)
                        if _lo is not None and _lo.Document.Name in _modified_set:
                            _obj.touch()
                            _needs = True
                    except Exception:
                        pass
                if _needs:
                    try:
                        _doc.recompute()
                        if _doc.FileName:
                            _doc.purgeTouched()
                            _doc.save()
                    except Exception:
                        pass
                    _next_set.add(_doc.Name)
            _visited |= _next_set
            _modified_set = _next_set

        # Restore the original active document tab so the user stays on the same view.
        if original_active_doc_name:
            try:
                App.setActiveDocument(original_active_doc_name)
                _orig = App.getDocument(original_active_doc_name)
                if _orig:
                    _orig.recompute()
            except Exception:
                pass
        try:
            Gui.updateGui()
        except Exception:
            pass


class CommandInsertNewBodyInline:
    """Create a new document with a PartDesign Body (no App::Part wrapper) and link it into the assembly."""

    def __init__(self):
        pass

    def GetResources(self):
        import os as _os
        _icon = _os.path.normpath(_os.path.join(
            _os.path.dirname(__file__), "..", "PartDesign", "Gui", "Resources", "icons", "PartDesignWorkbench.svg"
        ))
        return {
            "Pixmap": _icon,
            "MenuText": QT_TRANSLATE_NOOP("Assembly_InsertNewBodyInline", "Create New Part"),
            "Accel": "",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_InsertNewBodyInline",
                "Create a new document with a PartDesign Body and link it into the active assembly.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()

    def Activated(self):
        assembly = UtilsAssembly.activeAssembly()
        if not assembly:
            return

        # Remember the current GUI tab so we can restore it after creating the
        # new body — App.newDocument() and Gui.getDocument().setActiveObject()
        # would otherwise switch the tab.
        original_active_doc_name = App.ActiveDocument.Name if App.ActiveDocument else None

        # Assembly document must be saved before cross-document links can be created
        asm_doc = assembly.Document
        if not asm_doc.FileName:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText(
                translate(
                    "Assembly",
                    "The assembly document must be saved before inserting a new body.",
                )
            )
            msgBox.setWindowTitle(translate("Assembly", "Save Document"))
            saveButton = msgBox.addButton(
                translate("Assembly", "Save"), QtWidgets.QMessageBox.AcceptRole
            )
            msgBox.addButton(QtWidgets.QMessageBox.Cancel)
            msgBox.exec_()
            if msgBox.clickedButton() == saveButton:
                if not _save_asm_doc_to_work_dir(asm_doc):
                    return
            else:
                return

        dlg = NewBodyDialog(Gui.getMainWindow())
        dlg.setWindowTitle(translate("Assembly", "New Body"))
        dlg.setNameLabel(translate("Assembly", "Body name:"))
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        body_name = dlg.getName()
        description = dlg.getDescription()

        # --- Versioned save path check before creating any documents ---
        import os as _os
        import re as _re

        params = App.ParamGet("User parameter:BaseApp/Preferences/General")
        work_dir = params.GetString("WorkingDirectory", "").strip()

        if not work_dir or not _os.path.isdir(work_dir):
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                translate("Assembly", "New Body"),
                translate(
                    "Assembly",
                    "Working Directory is not set or does not exist.\n"
                    "Please set it via the Set Working Directory macro first.",
                ),
            )
            return

        _name_pattern = _re.compile(
            rf"^{_re.escape(body_name)}\.(\d{{3}})\.prt(?:\.FCStd)?$",
            _re.IGNORECASE,
        )
        existing_versions = [
            int(m.group(1))
            for f in _os.listdir(work_dir)
            for m in [_name_pattern.match(f)]
            if m
        ]
        if existing_versions:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Body"),
                translate(
                    "Assembly",
                    "A file named '{}' already exists in the Working Directory.\n"
                    "Please choose a different name."
                ).format(body_name),
            )
            return

        versioned_filename = f"{body_name}.001.prt.FCStd"
        full_save_path = _os.path.join(work_dir, versioned_filename)

        # --- Create new document with a bare PartDesign::Body (no App::Part wrapper) ---
        new_doc = App.newDocument(body_name)
        new_doc.Label = body_name

        body = new_doc.addObject("PartDesign::Body", body_name)
        body.Label = body_name

        _ensure_mp_properties(body)
        body.MP_PartNumber = body_name
        body.MP_Description = description

        new_doc.recompute()

        try:
            new_doc.saveAs(full_save_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Body"),
                translate("Assembly", "Failed to save document:\n{}").format(str(e)),
            )
            App.closeDocument(new_doc.Name)
            return

        # --- Switch back to assembly and link the body ---
        App.setActiveDocument(asm_doc.Name)
        App.setActiveTransaction("Insert New Body")

        link = assembly.newObject("App::Link", "Link")
        link.Label = body_name  # set label first so tree name is correct even on error
        try:
            link.LinkedObject = body
        except Exception as e:
            assembly.Document.removeObject(link.Name)
            App.closeActiveTransaction()
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(),
                translate("Assembly", "New Body"),
                translate("Assembly", "Failed to link body into assembly:\n{}").format(str(e)),
            )
            return

        link.touch()
        assembly.Document.recompute()
        App.closeActiveTransaction()

        # Propagate recompute to ancestor docs so the new body shows up under
        # this assembly in the parent assembly's tree (works at any nesting depth).
        modified_doc_name = assembly.Document.Name
        for doc in App.listDocuments().values():
            if doc.Name == modified_doc_name:
                continue
            needs_recompute = False
            for obj in doc.Objects:
                try:
                    lo = getattr(obj, "LinkedObject", None)
                    if lo is not None and lo.Document.Name == modified_doc_name:
                        obj.touch()
                        needs_recompute = True
                except Exception:
                    pass
            if needs_recompute:
                doc.recompute()

        # Restore the original active tab so the user stays where they were.
        # (Skip the "activate body for modelling" call — it switches tabs and
        # the user can do this manually if they want to model the body.)
        if original_active_doc_name:
            try:
                App.setActiveDocument(original_active_doc_name)
            except Exception:
                pass


if App.GuiUp:
    Gui.addCommand("Assembly_InsertNewBody", CommandInsertNewBody())
    Gui.addCommand("Assembly_InsertNewAssembly", CommandInsertNewAssembly())
    Gui.addCommand("Assembly_InsertNewBodyInline", CommandInsertNewBodyInline())
