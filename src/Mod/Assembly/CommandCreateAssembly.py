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

        # Create assembly object directly via Python API (avoids Gui.doCommand exec-context
        # issues where Assembly::AssemblyObject type is not visible)
        try:
            if activeAssembly:
                assembly = activeAssembly.newObject("Assembly::AssemblyObject", "Assembly")
            else:
                assembly = App.ActiveDocument.addObject("Assembly::AssemblyObject", "Assembly")

            assembly.Label = App.ActiveDocument.Label
            assembly.Type = "Assembly"
            assembly.newObject("Assembly::JointGroup", "Joints")
        except Exception as e:
            App.closeActiveTransaction(True)
            App.Console.PrintError(f"Assembly_CreateAssembly failed: {e}\n")
            return

        if not activeAssembly:
            Gui.doCommandGui(f"Gui.ActiveDocument.setEdit('{assembly.Name}')")

        App.closeActiveTransaction()

        # Apply description and save
        if not activeAssembly and description:
            doc = App.ActiveDocument
            if not hasattr(assembly, "Description"):
                assembly.addProperty("App::PropertyString", "Description", "Base", "")
            assembly.Description = description
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
                    # Clear then re-set with subname so FreeCAD navigates the full
                    # path from token to the target link (not just token's level).
                    # The Insert panel reads activeAssembly() from the cache so it
                    # always shows the correct depth regardless of the visual token.
                    try:
                        view.setActiveObject("assembly", None)
                    except Exception:
                        pass
                    try:
                        if subname:
                            view.setActiveObject("assembly", token, subname)
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
        App.Console.PrintMessage("[Asm] ActivateMainAssembly: invoked\n")

        def _find_root_in(d):
            for obj in d.Objects:
                if obj.TypeId == "Assembly::AssemblyObject":
                    if not any(p.TypeId == "Assembly::AssemblyObject" for p in obj.InList):
                        return obj
            return None

        # The user may be looking at the assembly tab while App.ActiveDocument
        # is still the previously-edited part doc. Try several sources:
        # 1. Gui.ActiveDocument's underlying App doc (the visible MDI tab)
        # 2. App.ActiveDocument
        # 3. Any open document
        root = None
        candidates = []
        try:
            gd = Gui.ActiveDocument
            if gd is not None and getattr(gd, "Document", None) is not None:
                candidates.append(gd.Document)
        except Exception:
            pass
        if App.ActiveDocument is not None:
            candidates.append(App.ActiveDocument)
        for d in App.listDocuments().values():
            if d not in candidates:
                candidates.append(d)

        chosen_doc = None
        for d in candidates:
            r = _find_root_in(d)
            if r is not None:
                # If found, also make sure that doc is the active one
                root = r
                chosen_doc = d
                break

        if root is None:
            App.Console.PrintMessage("[Asm] ActivateMainAssembly: no root assembly found in any open doc\n")
            return

        # Make sure we're operating on the doc that contains the root
        if App.ActiveDocument is not chosen_doc:
            try:
                App.setActiveDocument(chosen_doc.Name)
                Gui.ActiveDocument = Gui.getDocument(chosen_doc.Name)
                App.Console.PrintMessage(
                    "[Asm] ActivateMainAssembly: switched active doc to '{}'\n".format(chosen_doc.Name))
            except Exception as e:
                App.Console.PrintMessage(
                    "[Asm] ActivateMainAssembly: doc switch failed: {}\n".format(e))
        App.Console.PrintMessage("[Asm] ActivateMainAssembly: found root '{}'\n".format(root.Label))

        # Clear subassembly cache + selection
        UtilsAssembly.clearActiveAsmLinkTarget()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass

        # Clear ALL view-level active objects (pdbody, assembly) so the main
        # assembly becomes the only active context
        try:
            gv = Gui.ActiveDocument.ActiveView
            if gv is not None:
                try:
                    gv.setActiveObject("pdbody", None)
                    App.Console.PrintMessage("[Asm] ActivateMainAssembly: cleared pdbody\n")
                except Exception:
                    pass
                try:
                    gv.setActiveObject("part", None)
                except Exception:
                    pass
        except Exception:
            pass

        # Exit any current edit mode (e.g. body) so the root setEdit takes hold
        try:
            gui_doc = Gui.ActiveDocument
            if gui_doc is not None:
                try:
                    gui_doc.resetEdit()
                    App.Console.PrintMessage("[Asm] ActivateMainAssembly: resetEdit done\n")
                except Exception:
                    pass
                if gui_doc.setEdit(root, 0):
                    App.Console.PrintMessage("[Asm] ActivateMainAssembly: setEdit OK\n")
                else:
                    App.Console.PrintMessage("[Asm] ActivateMainAssembly: setEdit returned False\n")
        except Exception as e:
            App.Console.PrintMessage("[Asm] ActivateMainAssembly: setEdit failed: {}\n".format(e))

        # Set the active assembly object on the view
        try:
            gv = Gui.ActiveDocument.ActiveView
            if gv is not None:
                gv.setActiveObject("assembly", root)
                App.Console.PrintMessage("[Asm] ActivateMainAssembly: setActiveObject(assembly) OK\n")
        except Exception as e:
            App.Console.PrintMessage("[Asm] ActivateMainAssembly: setActiveObject failed: {}\n".format(e))


def _get_active_body_in_view():
    """Return the active Part Design body from the current GUI view, or None."""
    try:
        gd = Gui.ActiveDocument
        if gd is None or gd.ActiveView is None:
            return None
        return gd.ActiveView.getActiveObject("pdbody")
    except Exception:
        return None


def _pick_sketch_plane(body):
    """Modal plane picker for top-down sketch creation. Lists the body's base
    planes (XY/XZ/YZ) and any datum planes. Returns the chosen plane object
    or None if cancelled."""
    try:
        from PySide import QtWidgets, QtCore
    except Exception:
        return None

    # Collect available planes from the body's Origin and any datum planes
    options = []  # list of (label, plane_obj)
    try:
        origin = body.Origin
        for ref in origin.OutList:
            name = ref.Name
            if "XY" in name:
                options.append(("XY-plane (Base plane)", ref))
            elif "XZ" in name:
                options.append(("XZ-plane (Base plane)", ref))
            elif "YZ" in name:
                options.append(("YZ-plane (Base plane)", ref))
    except Exception:
        pass
    try:
        for child in body.Group:
            if getattr(child, "TypeId", "") == "PartDesign::Plane":
                options.append((child.Label + " (Datum)", child))
    except Exception:
        pass

    if not options:
        QtWidgets.QMessageBox.warning(
            Gui.getMainWindow(),
            "New Sketch",
            "No attachment planes found on the active body.",
        )
        return None

    dlg = QtWidgets.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle("Select Sketch Plane")
    dlg.setModal(True)
    dlg.setMinimumWidth(420)
    dlg.setMinimumHeight(300)
    dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

    lay = QtWidgets.QVBoxLayout(dlg)
    header = QtWidgets.QLabel(
        "<b>Choose the attachment plane</b><br>"
        "<span style='color:gray'>Select a base plane to sketch on. "
        "The sketch will be added to the active body.</span>"
    )
    header.setWordWrap(True)
    lay.addWidget(header)

    lst = QtWidgets.QListWidget()
    for label, _ in options:
        item = QtWidgets.QListWidgetItem(label)
        item.setSizeHint(QtCore.QSize(0, 30))
        lst.addItem(item)
    lst.setCurrentRow(0)
    # Double-click selects and accepts
    lst.itemDoubleClicked.connect(lambda _it: dlg.accept())
    lay.addWidget(lst, 1)

    btns = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
    )
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    lay.addWidget(btns)

    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return None
    idx = lst.currentRow()
    if idx < 0 or idx >= len(options):
        return None
    return options[idx][1]


def _find_link_to_body_doc(asm_doc, body_doc):
    """Walk asm_doc looking for an App::Link whose LinkedObject lives in
    body_doc. Returns (link_obj, body_in_link_subname) or (None, None)."""
    for obj in asm_doc.Objects:
        if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
            continue
        linked = getattr(obj, "LinkedObject", None)
        if linked is None:
            continue
        if linked.Document is body_doc:
            return obj, ""
    # Recursive: walk through asm-level links
    for obj in asm_doc.Objects:
        if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
            continue
        linked = getattr(obj, "LinkedObject", None)
        if linked is None:
            continue
        sub_doc = linked.Document
        if sub_doc is asm_doc:
            continue
        # Try to find body_doc inside sub_doc's links (one level deeper)
        for sub_obj in sub_doc.Objects:
            if not (sub_obj.isDerivedFrom("App::Link") or sub_obj.isDerivedFrom("Assembly::AssemblyLink")):
                continue
            sl = getattr(sub_obj, "LinkedObject", None)
            if sl is not None and sl.Document is body_doc:
                return obj, sub_obj.Name + "."
    return None, None


_inplace_overlays = []  # keep references so SoSeparators don't get garbage-collected


def _add_sketch_overlay(view, sketch, link, body):
    """Add a Coin3D scene-graph overlay drawing reference axes (red X, green Y)
    and an origin marker at the sketch plane. This compensates for FreeCAD
    not rendering the native sketch axes when entered via subname."""
    try:
        from pivy import coin

        # Compose world-space placement
        base_pl = App.Placement()
        if link is not None:
            try:
                base_pl = (link.getGlobalPlacement()
                           if hasattr(link, 'getGlobalPlacement')
                           else link.Placement)
            except Exception:
                pass
        global_pl = base_pl.multiply(body.Placement).multiply(sketch.Placement)
        origin = global_pl.Base
        x_dir = global_pl.Rotation.multVec(App.Vector(1, 0, 0))
        y_dir = global_pl.Rotation.multVec(App.Vector(0, 1, 0))

        L = 200.0  # axis line length
        sg = view.getSceneGraph()
        sep = coin.SoSeparator()
        sep.setName("AsmInplaceSketchOverlay")

        # Draw an axis line as a separator: SoBaseColor + SoLineSet on coords
        def _axis(start, end, color):
            grp = coin.SoSeparator()
            col = coin.SoBaseColor()
            col.rgb.setValue(*color)
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, 2, [(start.x, start.y, start.z),
                                          (end.x, end.y, end.z)])
            ds = coin.SoDrawStyle()
            ds.lineWidth.setValue(2.0)
            ls = coin.SoLineSet()
            ls.numVertices.setValue(2)
            grp.addChild(ds)
            grp.addChild(col)
            grp.addChild(coords)
            grp.addChild(ls)
            return grp

        # X axis (red), Y axis (green)
        sep.addChild(_axis(origin - x_dir * L, origin + x_dir * L, (1.0, 0.0, 0.0)))
        sep.addChild(_axis(origin - y_dir * L, origin + y_dir * L, (0.0, 0.7, 0.0)))

        # Origin marker (small green sphere)
        marker = coin.SoSeparator()
        m_col = coin.SoBaseColor()
        m_col.rgb.setValue(0.0, 0.6, 0.0)
        m_trans = coin.SoTranslation()
        m_trans.translation.setValue(origin.x, origin.y, origin.z)
        m_sphere = coin.SoSphere()
        m_sphere.radius.setValue(1.5)
        marker.addChild(m_col)
        marker.addChild(m_trans)
        marker.addChild(m_sphere)
        sep.addChild(marker)

        sg.addChild(sep)
        # Track for later removal
        _inplace_overlays.append((view, sep, sketch.Document.Name, sketch.Name))
        App.Console.PrintMessage("[Asm] inplace: overlay added\n")
    except Exception as e:
        App.Console.PrintMessage("[Asm] inplace: overlay failed: {}\n".format(e))


def _remove_sketch_overlays_for(doc_name, obj_name):
    """Remove any overlays we added for the given sketch when it exits edit."""
    global _inplace_overlays
    keep = []
    for view, sep, dn, on in _inplace_overlays:
        if dn == doc_name and on == obj_name:
            try:
                view.getSceneGraph().removeChild(sep)
            except Exception:
                pass
        else:
            keep.append((view, sep, dn, on))
    _inplace_overlays = keep


class _InplaceCleanupObserver:
    """Removes the overlay when the sketch exits edit mode."""
    def __init__(self, doc_name, obj_name):
        self.doc_name = doc_name
        self.obj_name = obj_name

    def slotResetEdit(self, viewObj):
        try:
            _remove_sketch_overlays_for(self.doc_name, self.obj_name)
        except Exception:
            pass
        try:
            Gui.removeDocumentObserver(self)
        except Exception:
            pass


def _new_sketch_in_active_body_inplace():
    """Top-down sketch creation: ask for a plane, create the Sketch on the
    active body (in its document), and try to enter edit mode in the
    CURRENT (assembly) view via setEdit-with-subname (in-place through link).
    Adds a Coin3D overlay with reference axes since FreeCAD won't render them
    through the link itself."""
    try:
        gd_asm = Gui.ActiveDocument
        if gd_asm is None or gd_asm.ActiveView is None:
            App.Console.PrintMessage("[Asm] inplace: no gui_doc/view\n")
            return
        asm_view = gd_asm.ActiveView  # capture eagerly — used in QTimer callback
        body = _get_active_body_in_view()
        if body is None:
            App.Console.PrintMessage("[Asm] inplace: no active body\n")
            return
        body_doc = body.Document
        asm_doc = App.ActiveDocument

        # Ask the user which plane to attach to
        App.Console.PrintMessage("[Asm] inplace: showing plane picker dialog\n")
        plane = _pick_sketch_plane(body)
        if plane is None:
            App.Console.PrintMessage("[Asm] inplace: plane picker cancelled\n")
            return

        App.setActiveTransaction("Create sketch")
        sketch = body_doc.addObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(plane, "")]
        sketch.MapMode = "FlatFace"
        body.addObject(sketch)
        body_doc.recompute()
        App.closeActiveTransaction()
        App.Console.PrintMessage("[Asm] inplace: sketch '{}' created in '{}'\n".format(
            sketch.Name, body_doc.Name))

        # Will be set by Strategy 1 if a link is found
        link = None

        def _fit_view_to_sketch():
            """Directly position the camera to look perpendicular at the sketch
            plane using Coin3D, then fit the view."""
            try:
                from PySide.QtCore import QTimer
                def _do_orient_and_fit():
                    try:
                        from pivy import coin
                        import math

                        view = Gui.ActiveDocument.ActiveView
                        if view is None:
                            App.Console.PrintMessage("[Asm] orient: no active view\n")
                            return

                        # Compute sketch plane in world coordinates.
                        # The sketch lives in the body's doc; the assembly view
                        # shows the body via a link, so we need the link's global
                        # placement composed with the sketch's local placement.
                        base_pl = App.Placement()
                        if link is not None:
                            try:
                                base_pl = (link.getGlobalPlacement()
                                           if hasattr(link, 'getGlobalPlacement')
                                           else link.Placement)
                            except Exception:
                                pass
                        try:
                            body_pl = body.Placement
                        except Exception:
                            body_pl = App.Placement()
                        sketch_pl = sketch.Placement
                        global_pl = base_pl.multiply(body_pl).multiply(sketch_pl)

                        normal = global_pl.Rotation.multVec(App.Vector(0, 0, 1))
                        origin = global_pl.Base

                        # The placement's rotation already maps from canonical
                        # (X, Y, Z) frame to the sketch plane's frame — that's
                        # exactly the camera orientation we need.
                        q = global_pl.Rotation.Q  # (x, y, z, w)

                        cam = view.getCameraNode()
                        cam.orientation.setValue(q[0], q[1], q[2], q[3])
                        # Position the camera back along the normal so we look at the plane
                        dist = 100.0
                        cam_pos = origin + normal * dist
                        cam.position.setValue(cam_pos.x, cam_pos.y, cam_pos.z)

                        # Fit the view
                        try:
                            view.fitAll()
                        except Exception:
                            try:
                                Gui.SendMsgToActiveView("ViewFit")
                            except Exception:
                                pass
                        App.Console.PrintMessage(
                            "[Asm] orient: camera set normal=({:.2f},{:.2f},{:.2f}) origin=({:.2f},{:.2f},{:.2f})\n".format(
                                normal.x, normal.y, normal.z, origin.x, origin.y, origin.z))
                    except Exception as e:
                        App.Console.PrintMessage("[Asm] orient: failed: {}\n".format(e))

                # Run after FreeCAD finishes its own view setup
                QTimer.singleShot(100, _do_orient_and_fit)
                QTimer.singleShot(400, _do_orient_and_fit)
            except Exception:
                pass

        # Strategy 1: edit the sketch through a link in the assembly doc.
        # This is how FreeCAD edits objects in linked documents in-place.
        if asm_doc is not body_doc:
            link, sub_prefix = _find_link_to_body_doc(asm_doc, body_doc)
            if link is not None:
                subname = sub_prefix + body.Name + "." + sketch.Name + "."
                App.Console.PrintMessage(
                    "[Asm] inplace: attempting setEdit via link '{}' subname '{}'\n".format(
                        link.Name, subname))
                try:
                    if gd_asm.setEdit(link, 0, subname):
                        App.Console.PrintMessage("[Asm] inplace: setEdit via link OK\n")
                        # Add reference-axes overlay since FreeCAD won't render
                        # the native ones through link/subname editing
                        _add_sketch_overlay(asm_view, sketch, link, body)
                        # Install observer to clean up the overlay on close
                        try:
                            Gui.addDocumentObserver(
                                _InplaceCleanupObserver(body_doc.Name, sketch.Name))
                        except Exception:
                            pass
                        _fit_view_to_sketch()
                        return
                    else:
                        App.Console.PrintMessage("[Asm] inplace: setEdit via link returned False\n")
                except Exception as e:
                    App.Console.PrintMessage("[Asm] inplace: setEdit via link raised: {}\n".format(e))

        # Strategy 2: direct setEdit on the sketch (only works if asm_doc is body_doc)
        try:
            if gd_asm.setEdit(sketch):
                App.Console.PrintMessage("[Asm] inplace: direct setEdit OK\n")
                _fit_view_to_sketch()
                return
        except Exception as e:
            App.Console.PrintMessage("[Asm] inplace: direct setEdit raised: {}\n".format(e))

        # Strategy 3 (fallback): switch to body's doc tab and open sketcher there
        App.Console.PrintMessage("[Asm] inplace: falling back to tab switch\n")
        try:
            App.setActiveDocument(body_doc.Name)
            Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
            Gui.getDocument(body_doc.Name).setEdit(sketch)
            _fit_view_to_sketch()
        except Exception as e2:
            App.Console.PrintMessage("[Asm] inplace: fallback also failed: {}\n".format(e2))
    except Exception as e:
        App.Console.PrintMessage("[Asm] _new_sketch_in_active_body_inplace failed: {}\n".format(e))


def _feature_in_active_body_inplace(type_id, name_hint):
    """Generic in-place feature creation (Pad/Pocket/Revolution).
    Creates the feature object via Python API in the body's doc with the
    selected sketch as Profile, then opens edit mode through the link in
    the assembly view (no tab switch)."""
    try:
        gd_asm = Gui.ActiveDocument
        if gd_asm is None or gd_asm.ActiveView is None:
            App.Console.PrintMessage("[Asm] feature: no view\n")
            return
        body = _get_active_body_in_view()
        if body is None:
            App.Console.PrintMessage("[Asm] feature: no active body\n")
            return
        body_doc = body.Document
        asm_doc = App.ActiveDocument

        # Find the underlying selected sketch (resolve through any link chain)
        selected_sketch = None
        for sel in Gui.Selection.getSelectionEx():
            obj = sel.Object
            seen = 0
            while obj is not None and seen < 10:
                if obj.isDerivedFrom("Sketcher::SketchObject"):
                    selected_sketch = obj
                    break
                if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
                    obj = obj.LinkedObject
                    seen += 1
                else:
                    break
            if selected_sketch is not None:
                break

        if selected_sketch is None:
            App.Console.PrintMessage("[Asm] feature: no sketch selected — falling back to native\n")
            _run_pd_cmd_in_body_doc("PartDesign_" + name_hint)
            return

        # Create the feature in the body's document
        App.setActiveTransaction("Create " + name_hint)
        feature = body_doc.addObject(type_id, name_hint)
        try:
            feature.Profile = selected_sketch
        except Exception:
            try:
                feature.Profile = (selected_sketch, [""])
            except Exception:
                pass
        # Default length / angle for common features
        try:
            if hasattr(feature, "Length"):
                feature.Length = 10.0
            if hasattr(feature, "Angle"):
                feature.Angle = 360.0
        except Exception:
            pass
        body.addObject(feature)
        body_doc.recompute()
        App.closeActiveTransaction()
        App.Console.PrintMessage("[Asm] feature: created '{}' in '{}'\n".format(
            feature.Name, body_doc.Name))

        # Try in-place edit through link
        if asm_doc is not body_doc:
            link, sub_prefix = _find_link_to_body_doc(asm_doc, body_doc)
            if link is not None:
                subname = sub_prefix + body.Name + "." + feature.Name + "."
                App.Console.PrintMessage(
                    "[Asm] feature: setEdit via link '{}' subname '{}'\n".format(
                        link.Name, subname))
                try:
                    if gd_asm.setEdit(link, 0, subname):
                        App.Console.PrintMessage("[Asm] feature: setEdit via link OK\n")
                        return
                    else:
                        App.Console.PrintMessage("[Asm] feature: setEdit via link returned False\n")
                except Exception as e:
                    App.Console.PrintMessage("[Asm] feature: setEdit via link raised: {}\n".format(e))

        # Fallback: switch tabs and edit
        App.Console.PrintMessage("[Asm] feature: falling back to tab switch\n")
        try:
            App.setActiveDocument(body_doc.Name)
            Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
            Gui.getDocument(body_doc.Name).setEdit(feature)
            # Auto-return when feature panel closes
            try:
                Gui.addDocumentObserver(_AutoReturnObserver(asm_doc.Name))
            except Exception:
                pass
        except Exception as e:
            App.Console.PrintMessage("[Asm] feature: fallback failed: {}\n".format(e))
    except Exception as e:
        App.Console.PrintMessage("[Asm] _feature_in_active_body_inplace failed: {}\n".format(e))


class _AutoReturnObserver:
    """One-shot document observer: when the watched object exits edit mode,
    switch the active document back to the recorded assembly doc and remove
    self from the observer list."""

    def __init__(self, asm_doc_name):
        self.asm_doc_name = asm_doc_name
        self._fired = False

    def slotResetEdit(self, viewObj):
        if self._fired:
            return
        self._fired = True
        try:
            App.setActiveDocument(self.asm_doc_name)
            try:
                Gui.ActiveDocument = Gui.getDocument(self.asm_doc_name)
            except Exception:
                pass
            # Find the MDI sub-window for the assembly doc and bring it forward
            try:
                from PySide import QtWidgets
                mw = Gui.getMainWindow()
                mdi = mw.findChild(QtWidgets.QMdiArea)
                if mdi is not None:
                    for sub in mdi.subWindowList():
                        try:
                            w = sub.widget()
                            if w and hasattr(w, "windowTitle"):
                                if self.asm_doc_name in w.windowTitle():
                                    mdi.setActiveSubWindow(sub)
                                    break
                        except Exception:
                            pass
            except Exception:
                pass
            App.Console.PrintMessage(
                "[Asm] auto-return: switched back to '{}'\n".format(self.asm_doc_name))
        except Exception as e:
            App.Console.PrintMessage("[Asm] auto-return failed: {}\n".format(e))
        finally:
            # Remove self from FreeCAD observer list
            try:
                Gui.removeDocumentObserver(self)
            except Exception:
                pass


def _new_sketch_with_auto_return():
    """Switch to the body's document, run native PartDesign_NewSketch (full UX),
    and install a one-shot observer that returns to the assembly tab when the
    sketch is closed."""
    try:
        gd = Gui.ActiveDocument
        if gd is None or gd.ActiveView is None:
            return
        body = _get_active_body_in_view()
        if body is None:
            App.Console.PrintMessage("[Asm] auto-return: no active body\n")
            return
        body_doc = body.Document
        asm_doc_name = App.ActiveDocument.Name

        # If we're already in the body's doc, no need for auto-return
        if body_doc.Name == asm_doc_name:
            Gui.runCommand("PartDesign_NewSketch")
            return

        # Install the observer BEFORE switching docs and starting edit
        observer = _AutoReturnObserver(asm_doc_name)
        try:
            Gui.addDocumentObserver(observer)
        except Exception as e:
            App.Console.PrintMessage("[Asm] addDocumentObserver failed: {}\n".format(e))

        # Switch to body doc and re-assert active body
        App.setActiveDocument(body_doc.Name)
        try:
            Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
        except Exception:
            pass
        try:
            bd_gui = Gui.getDocument(body_doc.Name)
            if bd_gui and bd_gui.ActiveView:
                bd_gui.ActiveView.setActiveObject("pdbody", body)
        except Exception:
            pass

        # Run the native PartDesign_NewSketch — full UX (plane picker, axes, etc.)
        Gui.runCommand("PartDesign_NewSketch")
    except Exception as e:
        App.Console.PrintMessage("[Asm] _new_sketch_with_auto_return failed: {}\n".format(e))


def _run_pd_cmd_in_body_doc(part_design_cmd):
    """Run a Part Design feature command (Pad/Pocket/etc.) in-place.
    Stays in the current (assembly) tab whenever possible.

    Strategy:
      1. Try running the PartDesign command directly in the current context.
         If a sketch is selected via the link path and the body is properly
         set as active in the view, the command may succeed without switching.
      2. If that approach fails, find the selected sketch and the body, and
         resolve the underlying objects in the body's document. Pre-select
         the original sketch object then run the command.
    """
    try:
        gui_doc = Gui.ActiveDocument
        if gui_doc is None or gui_doc.ActiveView is None:
            return
        body = _get_active_body_in_view()
        if body is None:
            App.Console.PrintMessage("[Asm] No active body found\n")
            return

        # Find the underlying selected sketch (resolve through any link)
        underlying_sketch = None
        for sel in Gui.Selection.getSelectionEx():
            obj = sel.Object
            # Resolve link chain to find the actual SketchObject
            seen = 0
            while obj is not None and seen < 10:
                if obj.isDerivedFrom("Sketcher::SketchObject"):
                    underlying_sketch = obj
                    break
                if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
                    obj = obj.LinkedObject
                    seen += 1
                else:
                    break
            if underlying_sketch is not None:
                break

        body_doc = body.Document
        asm_doc_name = App.ActiveDocument.Name if App.ActiveDocument else None

        # Switch to body's doc, run command, then switch back
        if body_doc.Name != asm_doc_name:
            App.setActiveDocument(body_doc.Name)
            try:
                Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
            except Exception:
                pass
            try:
                bd_gui = Gui.getDocument(body_doc.Name)
                if bd_gui and bd_gui.ActiveView:
                    bd_gui.ActiveView.setActiveObject("pdbody", body)
            except Exception:
                pass
            # Re-select the underlying sketch in the body's doc context
            if underlying_sketch is not None:
                try:
                    Gui.Selection.clearSelection()
                    Gui.Selection.addSelection(underlying_sketch)
                except Exception:
                    pass

        # Run the command (now active doc = body doc)
        Gui.runCommand(part_design_cmd)

        # After the user closes the feature panel, return to the assembly tab.
        # We install a one-shot observer that fires on resetEdit.
        if asm_doc_name and body_doc.Name != asm_doc_name:
            try:
                Gui.addDocumentObserver(_AutoReturnObserver(asm_doc_name))
                App.Console.PrintMessage(
                    "[Asm] {}: auto-return observer installed\n".format(part_design_cmd))
            except Exception as e:
                App.Console.PrintMessage(
                    "[Asm] auto-return install failed: {}\n".format(e))
    except Exception as e:
        App.Console.PrintMessage("[Asm] _run_pd_cmd_in_body_doc({}) failed: {}\n".format(
            part_design_cmd, e))


class _BaseBodyCmd:
    """Base for body-context wrapper commands."""
    _PD_CMD = ""
    _MENU = ""
    _PIXMAP = ""
    _TOOLTIP = ""

    def GetResources(self):
        return {
            "Pixmap": self._PIXMAP,
            "MenuText": self._MENU,
            "ToolTip": self._TOOLTIP,
        }

    def IsActive(self):
        try:
            gd = Gui.ActiveDocument
            if gd and gd.ActiveView:
                return gd.ActiveView.getActiveObject("pdbody") is not None
        except Exception:
            pass
        return False

    def Activated(self):
        _run_pd_cmd_in_body_doc(self._PD_CMD)


class CommandBodyNewSketch(_BaseBodyCmd):
    _PD_CMD = "PartDesign_NewSketch"
    _MENU = "New Sketch"
    _PIXMAP = "Sketcher_NewSketch"
    _TOOLTIP = "Create a new sketch on the active body (top-down, stays in assembly tab)."

    def Activated(self):
        _new_sketch_in_active_body_inplace()


class CommandBodyPad(_BaseBodyCmd):
    _PD_CMD = "PartDesign_Pad"
    _MENU = "Pad"
    _PIXMAP = "PartDesign_Pad"
    _TOOLTIP = "Pad the selected sketch on the active body (top-down, stays in assembly tab)."

    def Activated(self):
        _feature_in_active_body_inplace("PartDesign::Pad", "Pad")


class CommandBodyPocket(_BaseBodyCmd):
    _PD_CMD = "PartDesign_Pocket"
    _MENU = "Pocket"
    _PIXMAP = "PartDesign_Pocket"
    _TOOLTIP = "Pocket the selected sketch on the active body (top-down, stays in assembly tab)."

    def Activated(self):
        _feature_in_active_body_inplace("PartDesign::Pocket", "Pocket")


class CommandBodyRevolution(_BaseBodyCmd):
    _PD_CMD = "PartDesign_Revolution"
    _MENU = "Revolve"
    _PIXMAP = "PartDesign_Revolution"
    _TOOLTIP = "Revolve the selected sketch on the active body (top-down, stays in assembly tab)."

    def Activated(self):
        _feature_in_active_body_inplace("PartDesign::Revolution", "Revolution")


class CommandBodyHole(_BaseBodyCmd):
    _PD_CMD = "PartDesign_Hole"
    _MENU = "Hole"
    _PIXMAP = "PartDesign_Hole"
    _TOOLTIP = "Add a hole feature to the active body."

    def Activated(self):
        # Hole has its own attachment workflow; fallback to switching docs
        _run_pd_cmd_in_body_doc("PartDesign_Hole")


class CommandActivatePart:
    """Activate the selected Part Design body as the active pdbody on the
    current view, WITHOUT triggering an auto-switch to Part Design workbench."""

    def GetResources(self):
        return {
            "Pixmap": "Assembly_ActivateAssembly",
            "MenuText": "Activate Part",
            "ToolTip": "Make the selected body the active Part Design body. "
                       "Stays in Assembly workbench.",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        App.Console.PrintMessage("[Asm] ActivatePart: invoked\n")
        # Find a Part Design body in the current selection (resolve through links)
        body = None
        for sel in Gui.Selection.getSelectionEx():
            obj = sel.Object
            seen = 0
            while obj is not None and seen < 10:
                if obj.TypeId == "PartDesign::Body":
                    body = obj
                    break
                if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
                    obj = obj.LinkedObject
                    seen += 1
                else:
                    break
            if body is not None:
                break
        if body is None:
            App.Console.PrintMessage("[Asm] ActivatePart: no Body in selection\n")
            return
        try:
            gv = Gui.ActiveDocument.ActiveView
            if gv is not None:
                gv.setActiveObject("pdbody", body)
                App.Console.PrintMessage(
                    "[Asm] ActivatePart: pdbody set to '{}'\n".format(body.Label))
        except Exception as e:
            App.Console.PrintMessage("[Asm] ActivatePart: setActiveObject failed: {}\n".format(e))
        # Make sure we stay in Assembly workbench (in case anything tried to switch)
        try:
            from PySide.QtCore import QTimer
            def _stay_in_asm():
                try:
                    if Gui.activeWorkbench().__class__.__name__ != "AssemblyWorkbench":
                        Gui.activateWorkbench("AssemblyWorkbench")
                except Exception:
                    pass
            QTimer.singleShot(0, _stay_in_asm)
            QTimer.singleShot(50, _stay_in_asm)
        except Exception:
            pass


if App.GuiUp:
    Gui.addCommand("Assembly_CreateAssembly", CommandCreateAssembly())
    Gui.addCommand("Assembly_ActivateAssembly", CommandActivateAssembly())
    Gui.addCommand("Assembly_ActivateObject", CommandActivateObject())
    Gui.addCommand("Assembly_ActivateMainAssembly", CommandActivateMainAssembly())
    Gui.addCommand("Assembly_ActivatePart", CommandActivatePart())
    Gui.addCommand("Assembly_BodyNewSketch",  CommandBodyNewSketch())
    Gui.addCommand("Assembly_BodyPad",        CommandBodyPad())
    Gui.addCommand("Assembly_BodyPocket",     CommandBodyPocket())
    Gui.addCommand("Assembly_BodyRevolution", CommandBodyRevolution())
    Gui.addCommand("Assembly_BodyHole",       CommandBodyHole())
