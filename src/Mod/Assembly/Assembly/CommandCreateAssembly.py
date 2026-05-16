# SPDX-License-Identifier: LGPL-2.1-or-later
# /**************************************************************************
#                                                                           *
#    Copyright (c) 2023 Ondsel <development@ondsel.com>                     *
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

import FreeCAD as App

from PySide.QtCore import QT_TRANSLATE_NOOP

if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtCore, QtGui, QtWidgets

import UtilsAssembly
import Preferences

translate = App.Qt.translate

__title__ = "Assembly Command Create Assembly"
__author__ = "Ondsel"
__url__ = "https://www.freecad.org"


class CommandCreateAssembly:
    def __init__(self):
        pass

    def GetResources(self):
        return {
            "Pixmap": "Geoassembly",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_CreateAssembly", "New Assembly"),
            "Accel": "A",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_CreateAssembly",
                "Creates an assembly object in the current document, or in the current active assembly (if any). Limit of one root assembly per file.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        if Gui.Control.activeDialog():
            return False

        if Preferences.preferences().GetBool("EnforceOneAssemblyRule", True):
            activeAssembly = UtilsAssembly.activeAssembly()

            if UtilsAssembly.isThereOneRootAssembly() and not activeAssembly:
                return False

        return App.ActiveDocument is not None

    def Activated(self):
        from PySide import QtWidgets

        activeAssembly = UtilsAssembly.activeAssembly()
        asm_name = None
        description = None

        if not activeAssembly:
            # Root assembly creation — prompt for name and description,
            # then save the document to the Working Directory before continuing.
            from CommandInsertNewPart import NewBodyDialog, _save_asm_doc_to_work_dir

            dlg = NewBodyDialog(Gui.getMainWindow())
            dlg.setWindowTitle(translate("Assembly", "New Assembly"))
            dlg.setNameLabel(translate("Assembly", "Assembly name:"))
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                return

            asm_name = dlg.getName()
            description = dlg.getDescription()

            doc = App.ActiveDocument
            if not doc.FileName:
                old_label = doc.Label
                doc.Label = asm_name
                if not _save_asm_doc_to_work_dir(doc):
                    doc.Label = old_label
                    return

        App.setActiveTransaction("New Assembly")
        Gui.addModule("UtilsAssembly")

        if activeAssembly:
            commands = (
                "activeAssembly = UtilsAssembly.activeAssembly()\n"
                'assembly = activeAssembly.newObject("Assembly::AssemblyObject", "Assembly")\n'
                'assembly.Label = App.ActiveDocument.Label\n'
            )
        else:
            commands = (
                'assembly = App.ActiveDocument.addObject("Assembly::AssemblyObject", "Assembly")\n'
                'assembly.Label = App.ActiveDocument.Label\n'
            )

        commands = commands + 'assembly.Type = "Assembly"\n'
        commands = commands + 'assembly.newObject("Assembly::JointGroup", "Joints")'

        Gui.doCommand(commands)
        if not activeAssembly:
            Gui.doCommandGui("Gui.ActiveDocument.setEdit(assembly)")

        App.closeActiveTransaction()

        # Apply description and save
        if not activeAssembly and description:
            doc = App.ActiveDocument
            for obj in doc.Objects:
                if obj.isDerivedFrom("Assembly::AssemblyObject"):
                    if not hasattr(obj, "Description"):
                        obj.addProperty("App::PropertyString", "Description", "Base", "")
                    obj.Description = description
                    break
            try:
                doc.save()
            except Exception:
                pass


class ActivateAssemblyTaskPanel:
    """A basic TaskPanel to select an assembly to activate."""

    def __init__(self, entries):
        # entries is a list of (label, doc_name, obj_name) tuples
        self.entries = entries
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(translate("Assembly_ActivateAssembly", "Activate Assembly"))

        layout = QtWidgets.QVBoxLayout(self.form)
        label = QtWidgets.QLabel(
            translate("Assembly_ActivateAssembly", "Select an assembly to activate:")
        )
        self.combo = QtWidgets.QComboBox()

        for display_label, doc_name, obj_name in self.entries:
            self.combo.addItem(display_label, (doc_name, obj_name))

        layout.addWidget(label)
        layout.addWidget(self.combo)

    def accept(self):
        """Called when the user clicks OK."""
        data = self.combo.currentData()
        if data:
            doc_name, obj_name = data
            _activate_assembly(doc_name, obj_name)
        return True

    def reject(self):
        """Called when the user clicks Cancel or closes the panel."""
        return True


def _is_assembly_link(obj):
    """Return True for both App::Link and Assembly::AssemblyLink."""
    if obj.isDerivedFrom("App::Link"):
        return True
    if obj.isDerivedFrom("Assembly::AssemblyLink"):
        return True
    # TypeId fallback — isDerivedFrom can miss module-specific types in some builds
    return getattr(obj, "TypeId", "") == "Assembly::AssemblyLink"


def _is_asm_link_type(obj):
    """Return True specifically for Assembly::AssemblyLink (not plain App::Link)."""
    if getattr(obj, "TypeId", "") == "Assembly::AssemblyLink":
        return True
    return obj.isDerivedFrom("Assembly::AssemblyLink") and not obj.isDerivedFrom("App::Link")


def _selected_assembly_activation_target():
    def _is_asm_link(o):
        """Return True only for link objects pointing to an Assembly::AssemblyObject."""
        try:
            linked = getattr(o, "LinkedObject", None)
            if linked is None:
                return False
            return (linked.isDerivedFrom("Assembly::AssemblyObject")
                    or getattr(linked, "TypeId", "") == "Assembly::AssemblyObject")
        except Exception:
            return False

    # Strategy 1 (PRIMARY): Qt tree widget selected item label.
    # This is the most reliable source: it directly reflects what the user
    # right-clicked, unaffected by FreeCAD's path-based selection model which
    # returns the PARENT link (e.g. dgdg) instead of the clicked child (sgfdgd).
    try:
        selected_labels = set()
        mw = Gui.getMainWindow()
        from PySide import QtGui as _QtGui
        for tree in mw.findChildren(_QtGui.QTreeWidget):
            for item in tree.selectedItems():
                lbl = item.text(0)
                if lbl:
                    selected_labels.add(lbl)

        App.Console.PrintMessage("[Asm] S1 selected_labels={}\n".format(selected_labels))

        if selected_labels:
            # Active assembly's group first — tightest scope
            try:
                active_asm = UtilsAssembly.activeAssembly()
                App.Console.PrintMessage("[Asm] S1 active_asm={}\n".format(
                    getattr(active_asm, "Label", None) if active_asm else None))
                if active_asm is not None and hasattr(active_asm, "Group"):
                    for obj in active_asm.Group:
                        if obj.Label in selected_labels and _is_asm_link(obj):
                            App.Console.PrintMessage(
                                "[Asm] S1 found in active_asm.Group: {}/{}\n".format(
                                    obj.Document.Name, obj.Name))
                            return obj.Document.Name, obj.Name
            except Exception as _e:
                App.Console.PrintMessage("[Asm] S1 active_asm.Group error: {}\n".format(_e))
            # All open documents — only link-type objects (never bare AssemblyObjects)
            for doc in App.listDocuments().values():
                for obj in doc.Objects:
                    try:
                        if obj.Label in selected_labels and _is_asm_link(obj):
                            App.Console.PrintMessage(
                                "[Asm] S1 found in doc {}: {}/{}\n".format(
                                    doc.Name, obj.Document.Name, obj.Name))
                            return obj.Document.Name, obj.Name
                    except Exception:
                        pass
    except Exception as _e:
        App.Console.PrintMessage("[Asm] S1 outer error: {}\n".format(_e))

    # Strategy 2: getSelectionEx with subname path walking (fallback)
    def _is_activatable(obj):
        try:
            if obj.isDerivedFrom("Assembly::AssemblyObject"):
                return True
            if getattr(obj, "TypeId", "") == "Assembly::AssemblyObject":
                return True
            linked = getattr(obj, "LinkedObject", None)
            if linked is None:
                return False
            if linked.isDerivedFrom("Assembly::AssemblyObject"):
                return True
            if getattr(linked, "TypeId", "") == "Assembly::AssemblyObject":
                return True
        except Exception:
            pass
        return False

    def _walk_to_deepest(start, subname):
        parts = [p for p in subname.split(".") if p]
        cur = start
        for part in parts:
            try:
                linked = getattr(cur, "LinkedObject", None)
                if linked is not None:
                    child = linked.Document.getObject(part)
                    if child is not None:
                        cur = child
                        continue
                child = cur.Document.getObject(part)
                if child is not None:
                    cur = child
            except Exception:
                break
        return cur

    for _get in (
        lambda: Gui.Selection.getSelectionEx(),
        lambda: Gui.Selection.getSelectionEx(""),
    ):
        try:
            for s in _get():
                try:
                    obj = s.Object
                    if obj is None:
                        continue
                    best = None
                    for subname in (getattr(s, "SubElementNames", None) or []):
                        candidate = _walk_to_deepest(obj, subname)
                        if candidate is not obj and _is_activatable(candidate):
                            best = candidate
                    if best is not None:
                        return best.Document.Name, best.Name
                    if _is_asm_link(obj):
                        return obj.Document.Name, obj.Name
                except Exception:
                    pass
        except Exception:
            pass

    # Strategy 3: per-document getSelection (last fallback)
    for doc_name in App.listDocuments():
        try:
            for obj in Gui.Selection.getSelection(doc_name):
                if _is_asm_link(obj):
                    return obj.Document.Name, obj.Name
        except Exception:
            pass

    return None


def _activate_assembly(doc_name, obj_name):
    """Activate a sub-assembly in-context (no tab switch for AssemblyLink types)."""
    UtilsAssembly.clearActiveAsmLinkTarget()

    obj_doc = App.getDocument(doc_name)
    if obj_doc is None:
        return
    obj = obj_doc.getObject(obj_name)
    if obj is None:
        return

    linked = getattr(obj, "LinkedObject", None)

    App.Console.PrintMessage(
        "[Asm] _activate_assembly: doc={} obj={} TypeId={} is_asm_link_type={}\n".format(
            doc_name, obj_name,
            getattr(obj, "TypeId", "?") if obj else "None",
            _is_asm_link_type(obj) if obj else False,
        )
    )

    if _is_asm_link_type(obj) and linked and linked.isDerivedFrom("Assembly::AssemblyObject"):
        # Assembly::AssemblyLink — activate in-context, no tab switch.
        # The cache (_active_asm_link_target) is the authoritative source.
        # setActiveObject is called with the nearest ancestor token so FreeCAD fires
        # its "active object changed" signal and the Insert panel refreshes.
        # The 200ms timer early-returns when the cache is live, so it won't override.
        UtilsAssembly.setActiveAsmLinkTarget(doc_name, obj_name, linked)
        try:
            gui_doc = Gui.ActiveDocument
            current_app_doc = App.ActiveDocument
            if gui_doc and gui_doc.ActiveView and current_app_doc:
                token = None
                subname = None
                if current_app_doc.Name == doc_name:
                    # Level-1: obj is in the current doc — set it directly
                    token = obj
                else:
                    # Level-2+: BFS from current doc through the linked-document graph
                    # to find doc_name at any depth, building the subname path along
                    # the way.  Handles assemblies nested up to any depth (20+).
                    from collections import deque as _deque
                    _visited = {current_app_doc.Name}
                    _queue = _deque()
                    for _root in current_app_doc.Objects:
                        try:
                            _lo = getattr(_root, "LinkedObject", None)
                            if _lo is None:
                                continue
                            _lo_doc = getattr(_lo, "Document", None)
                            if _lo_doc is None:
                                continue
                            if _lo_doc.Name == doc_name:
                                token = _root
                                subname = obj.Name + "."
                                break
                            if _lo_doc.Name not in _visited:
                                _visited.add(_lo_doc.Name)
                                _queue.append((_root, _lo_doc, ""))
                        except Exception:
                            pass
                    if token is None:
                        while _queue and token is None:
                            _root_tok, _cur_doc, _path = _queue.popleft()
                            try:
                                for _mid in _cur_doc.Objects:
                                    try:
                                        _mid_lo = getattr(_mid, "LinkedObject", None)
                                        if _mid_lo is None:
                                            continue
                                        _mid_doc = getattr(_mid_lo, "Document", None)
                                        if _mid_doc is None:
                                            continue
                                        _new_path = _path + _mid.Name + "."
                                        if _mid_doc.Name == doc_name:
                                            token = _root_tok
                                            subname = _new_path + obj.Name + "."
                                            break
                                        if _mid_doc.Name not in _visited:
                                            _visited.add(_mid_doc.Name)
                                            _queue.append((_root_tok, _mid_doc, _new_path))
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                App.Console.PrintMessage(
                    "[Asm] token={} subname={}\n".format(
                        getattr(token, "Name", None) if token else None, subname)
                )
                if token is not None:
                    view = gui_doc.ActiveView
                    try:
                        view.setActiveObject("assembly", None)
                    except Exception:
                        pass
                    try:
                        if subname:
                            # Level-2+: setActiveObject("assembly", token, subname)
                            # highlights the entire parent-to-child path, making the
                            # intermediate token (e.g. '55') appear active alongside
                            # the real target (e.g. '66'). Skip the re-set here.
                            # The cache + _refresh_active_subassembly_bold() provide
                            # correct single-item visual feedback for the leaf only.
                            pass
                        else:
                            view.setActiveObject("assembly", token)
                    except Exception:
                        pass
        except Exception:
            pass

        # Status-bar AND console confirmation so the user has a clear, visible signal.
        # Status bar message is PERSISTENT (timeout 0) so it stays until the next activation.
        try:
            msg = "Active subassembly: {} (in {})".format(
                linked.Label, linked.Document.Label
            )
            Gui.getMainWindow().statusBar().showMessage(msg, 0)
            App.Console.PrintMessage(msg + "\n")
        except Exception:
            pass
        return

    # App::Link or inline AssemblyObject: must switch to the owning document tab.
    App.setActiveDocument(doc_name)
    gui_doc = Gui.getDocument(doc_name)
    Gui.ActiveDocument = gui_doc
    gui_doc.setEdit(obj_name)
    if linked and linked.isDerivedFrom("Assembly::AssemblyObject"):
        try:
            if gui_doc and gui_doc.ActiveView:
                gui_doc.ActiveView.setActiveObject("assembly", obj)
        except Exception:
            pass


def _find_activatable_assemblies(doc):
    """Return list of (display_label, doc_name, obj_name) for all activatable assemblies
    in doc — including nested inline assemblies and those in separate documents via App::Link.
    Excludes the currently active assembly so it is not offered as an option.

    For inline Assembly::AssemblyObject items, stores (current_doc, obj.Name) so that
    activation calls setEdit in the same document (in-context, same tab).
    For App::Link items pointing to an external assembly, stores (linked_doc, linked.Name)
    so that activation switches to that document tab.
    """
    entries = []
    seen = set()
    current = UtilsAssembly.activeAssembly()

    def _collect(obj_list, parent_label=""):
        for obj in obj_list:
            if obj.isDerivedFrom("Assembly::AssemblyObject"):
                key = (doc.Name, obj.Name)
                if key not in seen and obj is not current:
                    seen.add(key)
                    label = (parent_label + " > " + obj.Label) if parent_label else obj.Label
                    entries.append((label, doc.Name, obj.Name))
                # Recurse into nested inline assemblies
                if hasattr(obj, "Group"):
                    _collect(obj.Group, obj.Label)
            elif _is_assembly_link(obj) and hasattr(obj, "LinkedObject") and obj.LinkedObject:
                try:
                    linked = obj.LinkedObject
                    if linked.isDerivedFrom("Assembly::AssemblyObject"):
                        key = (doc.Name, obj.Name)
                        if key not in seen:
                            seen.add(key)
                            label = (parent_label + " > " + obj.Label) if parent_label else obj.Label
                            entries.append((label, doc.Name, obj.Name))
                except Exception:
                    pass

    _collect(doc.Objects)
    return entries


class CommandActivateAssembly:
    def __init__(self):
        self.task_panel = None

    def GetResources(self):
        return {
            "Pixmap": "Assembly_ActivateAssembly",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_ActivateAssembly", "Activate Assembly"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_ActivateAssembly", "Sets an assembly as the active one for editing."
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        if Gui.Control.activeDialog() or App.ActiveDocument is None:
            return False

        # Active if there is at least one assembly (direct, nested, or linked) to activate
        return len(_find_activatable_assemblies(App.ActiveDocument)) > 0

    def Activated(self):
        target = _selected_assembly_activation_target()
        if target is not None:
            _activate_assembly(target[0], target[1])
            return

        entries = _find_activatable_assemblies(App.ActiveDocument)

        if len(entries) == 1:
            _activate_assembly(entries[0][1], entries[0][2])
        elif len(entries) > 1:
            self.task_panel = ActivateAssemblyTaskPanel(entries)
            Gui.Control.showDialog(self.task_panel)


class CommandActivateObject:
    def GetResources(self):
        return {
            "Pixmap": "Assembly_ActivateAssembly",
            "MenuText": QT_TRANSLATE_NOOP(
                "Assembly_ActivateObject", "Activate Subassembly"
            ),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_ActivateObject",
                "Activates the selected subassembly in the current assembly tab.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        # Always active when a document is open — ContextMenu controls when this
        # item is shown, and Activated() validates the selection before acting.
        return App.ActiveDocument is not None

    def Activated(self):
        target = _selected_assembly_activation_target()
        App.Console.PrintMessage("[Asm] target={}\n".format(target))
        if target is None:
            App.Console.PrintMessage("[Asm] no target found — selection not recognised\n")
            return
        # Toggle: if the selected subassembly is already the active one, deactivate it.
        cache = getattr(UtilsAssembly, "_active_asm_link_target", None)
        if cache is not None:
            try:
                cached_doc, cached_obj, _ = cache
                if cached_doc == target[0] and cached_obj == target[1]:
                    UtilsAssembly.clearActiveAsmLinkTarget()
                    try:
                        gui_doc = Gui.ActiveDocument
                        if gui_doc and gui_doc.ActiveView:
                            gui_doc.ActiveView.setActiveObject("assembly", None)
                    except Exception:
                        pass
                    return
            except Exception:
                pass
        _activate_assembly(target[0], target[1])


class CommandActivateMainAssembly:
    """Activate the root AssemblyObject of the active document.
    Clears any active subassembly cache so the main assembly becomes the active one."""

    def GetResources(self):
        return {
            "Pixmap": "Assembly_ActivateAssembly",
            "MenuText": QT_TRANSLATE_NOOP(
                "Assembly_ActivateMainAssembly", "Activate Main Assembly"
            ),
            "Accel": "Ctrl+A",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_ActivateMainAssembly",
                "Activate the root assembly of the current document, deactivating any active subassembly. (Ctrl+A)",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        doc = App.ActiveDocument
        if doc is None:
            return
        # Find the root AssemblyObject (no parent AssemblyObject in InList)
        root = None
        for obj in doc.Objects:
            if obj.TypeId == "Assembly::AssemblyObject":
                if not any(p.TypeId == "Assembly::AssemblyObject" for p in obj.InList):
                    root = obj
                    break
        if root is None:
            App.Console.PrintMessage("[Asm] ActivateMainAssembly: no root assembly found\n")
            return
        # Clear any active subassembly cache so the root becomes the only active one
        UtilsAssembly.clearActiveAsmLinkTarget()
        # Put root in edit mode (FreeCAD's standard "Active object" behaviour)
        try:
            gui_doc = Gui.ActiveDocument
            if gui_doc is not None:
                gui_doc.setEdit(root, 0)
        except Exception as e:
            App.Console.PrintMessage("[Asm] ActivateMainAssembly: setEdit failed: {}\n".format(e))


if App.GuiUp:
    Gui.addCommand("Assembly_CreateAssembly", CommandCreateAssembly())
    Gui.addCommand("Assembly_ActivateAssembly", CommandActivateAssembly())
    Gui.addCommand("Assembly_ActivateObject", CommandActivateObject())
    Gui.addCommand("Assembly_ActivateMainAssembly", CommandActivateMainAssembly())
