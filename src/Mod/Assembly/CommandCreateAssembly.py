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

        # Clean label (strip any '.NNN'/'.asm' version the save added to the doc
        # label) so the assembly object shows '555', not '555.001'.
        try:
            from CommandInsertNewPart import _strip_version as _sv
            _clean_label = _sv(asm_name if asm_name else App.ActiveDocument.Label)
        except Exception:
            _clean_label = asm_name if asm_name else App.ActiveDocument.Label
        if activeAssembly:
            commands = (
                "activeAssembly = UtilsAssembly.activeAssembly()\n"
                'assembly = activeAssembly.newObject("Assembly::AssemblyObject", "Assembly")\n'
                'assembly.Label = {!r}\n'.format(_clean_label)
            )
        else:
            commands = (
                'assembly = App.ActiveDocument.addObject("Assembly::AssemblyObject", "Assembly")\n'
                'assembly.Label = {!r}\n'.format(_clean_label)
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

    def _is_activatable_asm(o):
        """True for an INLINE Assembly::AssemblyObject (single-file subassembly)
        OR a link whose target is an assembly. Inline assemblies have no
        LinkedObject, so `_is_asm_link` alone misses them."""
        try:
            if o.isDerivedFrom("Assembly::AssemblyObject"):
                return True
            if getattr(o, "TypeId", "") == "Assembly::AssemblyObject":
                return True
        except Exception:
            pass
        return _is_asm_link(o)

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
            # Active assembly's group first — tightest scope. Match inline
            # subassemblies (AssemblyObject) as well as links.
            try:
                active_asm = UtilsAssembly.activeAssembly()
                App.Console.PrintMessage("[Asm] S1 active_asm={}\n".format(
                    getattr(active_asm, "Label", None) if active_asm else None))
                if active_asm is not None and hasattr(active_asm, "Group"):
                    for obj in active_asm.Group:
                        if obj.Label in selected_labels and _is_activatable_asm(obj):
                            App.Console.PrintMessage(
                                "[Asm] S1 found in active_asm.Group: {}/{}\n".format(
                                    obj.Document.Name, obj.Name))
                            return obj.Document.Name, obj.Name
            except Exception as _e:
                App.Console.PrintMessage("[Asm] S1 active_asm.Group error: {}\n".format(_e))
            # Search documents (CURRENT doc first) for an activatable object —
            # inline AssemblyObject OR link — whose label matches. Current-doc-
            # first keeps single-file activation unambiguous.
            _docs = []
            try:
                if App.ActiveDocument is not None:
                    _docs.append(App.ActiveDocument)
            except Exception:
                pass
            for _d in App.listDocuments().values():
                if _d not in _docs:
                    _docs.append(_d)
            for doc in _docs:
                for obj in doc.Objects:
                    try:
                        if obj.Label in selected_labels and _is_activatable_asm(obj):
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

    # Exit any in-progress edit (a body/sketch/part being edited) and clear the
    # active part BEFORE switching activation. FreeCAD allows only ONE object in
    # edit mode at a time, so when a PART is active/being edited, setEdit() on the
    # target subassembly is silently blocked and the subassembly never becomes
    # active. Resetting first makes "Activate Subassembly" work regardless of
    # whether a part, the main assembly, or another subassembly was active.
    try:
        _cur_gd = Gui.ActiveDocument
        if _cur_gd is not None:
            try:
                _cur_gd.resetEdit()
            except Exception:
                pass
            try:
                if _cur_gd.ActiveView is not None:
                    _cur_gd.ActiveView.setActiveObject("pdbody", None)
                    # Also release an active App::Part (e.g. a sheet-metal part)
                    # so activating an assembly leaves ONLY the assembly active
                    # (mirror of the pdbody release; skip assembly-type objects).
                    _ap = _cur_gd.ActiveView.getActiveObject("part")
                    if _ap is not None and not _ap.isDerivedFrom("Assembly::AssemblyObject"):
                        _cur_gd.ActiveView.setActiveObject("part", None)
            except Exception:
                pass
    except Exception:
        pass

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

    # App::Link or inline AssemblyObject: activate in the owning document.
    App.setActiveDocument(doc_name)
    gui_doc = Gui.getDocument(doc_name)
    Gui.ActiveDocument = gui_doc
    # setEdit MUST succeed for an inline AssemblyObject: activeAssembly() only
    # returns it when its ViewObject.isInEditMode() is True (UtilsAssembly ~116).
    try:
        gui_doc.setEdit(obj_name)
    except Exception as _e:
        App.Console.PrintMessage(
            "[Asm] _activate_assembly: setEdit('{}') failed: {}\n".format(obj_name, _e))
    # Mark it the active assembly so activeAssembly() (and every Insert command)
    # resolves it. For an INLINE nested AssemblyObject there is NO LinkedObject —
    # obj itself IS the assembly, so the old `linked and ...` guard skipped it and
    # activation silently failed. Handle both: inline AssemblyObject OR a link
    # whose target is an assembly.
    is_inline_asm = False
    try:
        is_inline_asm = obj.isDerivedFrom("Assembly::AssemblyObject")
    except Exception:
        is_inline_asm = getattr(obj, "TypeId", "") == "Assembly::AssemblyObject"
    if is_inline_asm or (linked and linked.isDerivedFrom("Assembly::AssemblyObject")):
        try:
            if gui_doc and gui_doc.ActiveView:
                gui_doc.ActiveView.setActiveObject("assembly", obj)
        except Exception:
            pass
    try:
        _ime = obj.ViewObject.isInEditMode()
        App.Console.PrintMessage(
            "[Asm] _activate_assembly: '{}' active set, isInEditMode={}\n".format(
                getattr(obj, "Label", obj_name), _ime))
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


def _doc_is_assembly(doc):
    """True if the document itself hosts an Assembly (top assembly OR a
    subassembly — each subassembly is its own document/file)."""
    try:
        return any(getattr(o, "TypeId", "") == "Assembly::AssemblyObject"
                   for o in doc.Objects)
    except Exception:
        return False


def _frame_origin_planes(body, delay_ms=0):
    """Make the body's origin planes visible and frame them (isometric + fitAll)
    so the native sketch attachment dialog shows them clearly — like Part Design
    — instead of tiny and edge-on (the default TOP view shows XZ/YZ as a thin
    line). Optionally deferred so it runs after the attachment dialog opens."""
    try:
        from PySide import QtCore
    except Exception:
        QtCore = None

    def _do():
        try:
            origin = getattr(body, "Origin", None)
            if origin is not None:
                try:
                    origin.Visibility = True
                except Exception:
                    pass
                for ref in getattr(origin, "OutList", []):
                    try:
                        ref.Visibility = True
                    except Exception:
                        pass
            v = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
            if v is not None:
                try:
                    v.viewIsometric()
                except Exception:
                    pass
                try:
                    v.fitAll()
                except Exception:
                    pass
        except Exception:
            pass

    if QtCore is not None and delay_ms > 0:
        QtCore.QTimer.singleShot(delay_ms, _do)
    else:
        _do()


def _pick_sketch_plane(body):
    """Interactive, NON-MODAL plane/face picker for top-down sketch creation.

    Unlike a modal dialog, this keeps the 3D view live so the user can click a
    base plane or a flat face directly in the workspace (Part Design style),
    then press OK. A list of base/datum planes is offered as a fallback.

    Returns (object, subelement) suitable for Sketch.AttachmentSupport, or None
    if cancelled."""
    try:
        from PySide import QtWidgets, QtCore
    except Exception:
        return None

    # Collect base/datum planes for the fallback list
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

    # Make the body's base planes visible so they can be clicked in the 3D view.
    _restore_vis = []
    try:
        origin = body.Origin
        try:
            _restore_vis.append((origin, origin.Visibility))
            origin.Visibility = True
        except Exception:
            pass
        for ref in origin.OutList:
            try:
                _restore_vis.append((ref, ref.Visibility))
                ref.Visibility = True
            except Exception:
                pass
    except Exception:
        pass

    dlg = QtWidgets.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle("Select Sketch Plane")
    dlg.setModal(False)   # NON-modal so the 3D view stays interactive
    dlg.setMinimumWidth(430)
    dlg.setWindowFlags(
        dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)

    lay = QtWidgets.QVBoxLayout(dlg)
    header = QtWidgets.QLabel(
        "<b>Choose the attachment plane</b><br>"
        "<span style='color:gray'>Click a base plane or a flat face in the 3D "
        "view, then press OK — or pick a base plane from the list below.</span>"
    )
    header.setWordWrap(True)
    lay.addWidget(header)

    lst = QtWidgets.QListWidget()
    for label, _ in options:
        item = QtWidgets.QListWidgetItem(label)
        item.setSizeHint(QtCore.QSize(0, 28))
        lst.addItem(item)
    if options:
        lst.setCurrentRow(0)
    lst.itemDoubleClicked.connect(lambda _it: dlg.accept())
    lay.addWidget(lst, 1)

    status = QtWidgets.QLabel("")
    status.setStyleSheet("color:#22aa77;")
    status.setWordWrap(True)
    lay.addWidget(status)

    btns = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
    )
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    lay.addWidget(btns)

    # Poll the 3D selection so the status reflects what the user clicked. When
    # something valid is picked in the view it takes priority over the list.
    def _refresh_status():
        try:
            ref = _selected_sketch_ref(body)
            if ref is not None:
                obj, sub = ref
                status.setText("Picked in view: {}{}".format(
                    getattr(obj, "Label", getattr(obj, "Name", "?")),
                    (" · " + sub) if sub else ""))
            else:
                status.setText("")
        except Exception:
            status.setText("")

    timer = QtCore.QTimer(dlg)
    timer.setInterval(200)
    timer.timeout.connect(_refresh_status)
    timer.start()

    # Frame the base planes so they read large and centred (like Part Design)
    # instead of tiny in a corner. Clear any stale selection first so the
    # picker starts empty and the view fit isn't biased.
    try:
        Gui.Selection.clearSelection()
    except Exception:
        pass

    def _frame_planes():
        try:
            v = Gui.ActiveDocument.ActiveView
            if v is None:
                return
            try:
                v.viewIsometric()
            except Exception:
                pass
            v.fitAll()
        except Exception:
            pass

    QtCore.QTimer.singleShot(80, _frame_planes)

    # Local event loop: blocks this function until the dialog closes, but the
    # main window (and 3D view) keep processing events because the dialog is
    # non-modal — that is what lets the user click a plane/face in the view.
    dlg.show()
    dlg.raise_()
    loop = QtCore.QEventLoop()
    dlg.finished.connect(lambda _r: loop.quit())
    loop.exec_()
    timer.stop()
    accepted = dlg.result() == QtWidgets.QDialog.Accepted

    # Restore original base-plane visibility
    for obj, vis in _restore_vis:
        try:
            obj.Visibility = vis
        except Exception:
            pass

    if not accepted:
        return None

    # Prefer whatever the user clicked in the 3D view; else the highlighted row.
    ref = _selected_sketch_ref(body)
    if ref is not None:
        return ref
    idx = lst.currentRow()
    if 0 <= idx < len(options):
        return (options[idx][1], "")
    return None


def _selected_sketch_ref(body):
    """If the user pre-selected a base/datum plane or a planar face belonging
    to the active body, return (object, subelement) suitable for
    Sketch.AttachmentSupport — so New Sketch behaves like Part Design and skips
    the plane-picker dialog. Returns None when nothing usable is selected.

    Resolves through the assembly's link chain down to the real object in the
    body's OWN document (the sketch must attach to objects in that document)."""
    try:
        body_doc = body.Document
    except Exception:
        return None

    _PLANE_TYPES = ("App::Plane", "PartDesign::Plane")

    try:
        sels = Gui.Selection.getSelectionEx("", 0)   # resolve=0 → keep link subnames
    except Exception:
        try:
            sels = Gui.Selection.getSelectionEx()
        except Exception:
            return None

    for sel in sels or []:
        top = getattr(sel, "Object", None)
        if top is None:
            continue
        for sub in (list(getattr(sel, "SubElementNames", None) or []) or [""]):
            # Resolve the dotted link path to the tail object in body_doc.
            tail = top
            try:
                chain = top.getSubObjectList(sub) if sub else [top]
                if chain:
                    tail = chain[-1]
            except Exception:
                tail = top
            # Follow any remaining LinkedObject indirection into body_doc.
            seen = 0
            while (tail is not None
                   and getattr(tail, "Document", None) is not body_doc
                   and seen < 10):
                lo = getattr(tail, "LinkedObject", None)
                if lo is None or lo is tail:
                    break
                tail = lo
                seen += 1
            if tail is None or getattr(tail, "Document", None) is not body_doc:
                continue

            # Case 1: a base plane (XY/XZ/YZ) or a datum plane, picked directly.
            if getattr(tail, "TypeId", "") in _PLANE_TYPES:
                return (tail, "")

            # Case 2: a planar face on a solid feature of the body.
            elem = sub.split(".")[-1] if sub else ""
            if elem.startswith("Face"):
                try:
                    face = tail.Shape.getElement(elem)
                    if face.Surface.__class__.__name__ == "Plane":
                        return (tail, elem)
                except Exception:
                    pass
    return None


def _find_doc_with_direct_link_to(body_doc, asm_doc):
    """Find any open document that has an App::Link/AssemblyLink directly
    pointing to body_doc, preferring documents that are reachable from asm_doc
    via the link chain. Returns the document, or None."""
    candidates = []
    for d in App.listDocuments().values():
        if d is body_doc:
            continue
        for obj in d.Objects:
            try:
                if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
                    continue
                linked = getattr(obj, "LinkedObject", None)
                if linked is None:
                    continue
                if linked.Document is body_doc:
                    candidates.append(d)
                    break
            except Exception:
                pass
    if not candidates:
        return None
    # Prefer a candidate that's NOT asm_doc (i.e., a subasm doc), since we
    # want to use the deepest direct-link doc
    for d in candidates:
        if d is not asm_doc:
            return d
    return candidates[0]


def _find_link_to_body_doc(asm_doc, body_doc):
    """Walk asm_doc looking for a link chain that reaches body_doc.
    Returns (top_link_obj, sub_prefix) where sub_prefix is the dotted
    subname path INSIDE the top link, NOT including the body name/sketch name
    (callers append those).

    FreeCAD subname convention for traversing links:
        "LinkName.LinkedObjectName.{children…}"

    So for a single-level link directly to body_doc:
        sub_prefix = ""  (the body.Name is appended by the caller)

    For a nested chain (asm → AssemblyLink → SubAsm → InnerLink → body):
        sub_prefix = "<SubAsmName>.<InnerLinkName>."
        Then caller appends "<BodyName>.<SketchName>." giving the full
        path like "Link002.22.Link._5.Sketch."
    """
    # Level 1 — direct link to body_doc
    for obj in asm_doc.Objects:
        if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
            continue
        linked = getattr(obj, "LinkedObject", None)
        if linked is None:
            continue
        if linked.Document is body_doc:
            return obj, ""
    # Level 2 — through a subassembly link
    # sub_prefix is just sub_obj.Name + "." because setEdit subnames are
    # relative to the linked document's root, not to the linked object itself.
    for obj in asm_doc.Objects:
        if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
            continue
        linked = getattr(obj, "LinkedObject", None)
        if linked is None:
            continue
        sub_doc = linked.Document
        if sub_doc is asm_doc:
            continue
        for sub_obj in sub_doc.Objects:
            if not (sub_obj.isDerivedFrom("App::Link") or sub_obj.isDerivedFrom("Assembly::AssemblyLink")):
                continue
            sl = getattr(sub_obj, "LinkedObject", None)
            if sl is not None and sl.Document is body_doc:
                return obj, sub_obj.Name + "."
    # Level 3 — through two nested subassembly links (deep nesting)
    for obj in asm_doc.Objects:
        if not (obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("Assembly::AssemblyLink")):
            continue
        linked = getattr(obj, "LinkedObject", None)
        if linked is None:
            continue
        sub_doc = linked.Document
        if sub_doc is asm_doc:
            continue
        for sub_obj in sub_doc.Objects:
            if not (sub_obj.isDerivedFrom("App::Link") or sub_obj.isDerivedFrom("Assembly::AssemblyLink")):
                continue
            sl = getattr(sub_obj, "LinkedObject", None)
            if sl is None:
                continue
            sub_sub_doc = sl.Document
            if sub_sub_doc is sub_doc or sub_sub_doc is asm_doc:
                continue
            for sss_obj in sub_sub_doc.Objects:
                if not (sss_obj.isDerivedFrom("App::Link") or sss_obj.isDerivedFrom("Assembly::AssemblyLink")):
                    continue
                ssl = getattr(sss_obj, "LinkedObject", None)
                if ssl is not None and ssl.Document is body_doc:
                    return obj, (linked.Name + "." + sub_obj.Name + "." +
                                 sl.Name + "." + sss_obj.Name + ".")
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

        # CRITICAL: make the whole overlay UNPICKABLE. These reference lines are
        # drawn on top of the sketch's REAL (snappable) X/Y axes + origin. If the
        # overlay stayed pickable, Coin would intercept the click/hover on the
        # visible line and the Sketcher could not snap/constrain to the real axis
        # behind it — which is exactly the "unable to take reference" problem.
        # An UNPICKABLE overlay is purely visual and lets picks pass through to
        # the real axes.
        _pick = coin.SoPickStyle()
        _pick.style.setValue(coin.SoPickStyle.UNPICKABLE)
        sep.addChild(_pick)

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


def _discover_link_subname(link, target, tails=None, max_depth=12):
    """Discover the EXACT subname (relative to `link`) whose resolution is
    `target`, validated with link.getSubObject(...) — the SAME resolver setEdit
    uses — so a returned subname is guaranteed accepted by setEdit (no guessing).

    Two mechanisms, because App::Link/AssemblyLink hides the deep hierarchy:
      1. Walk getSubObjects() where available.
      2. At EVERY node also probe explicit `tails` (e.g. '<body>.Sketch.',
         'Sketch.'). This is essential: through a link, getSubObjects() often
         returns [] for the nested part, yet an explicit path still resolves.
    This is what lets us open a sketch nested several links deep (main asm →
    subasm → part) while STAYING in the root tab. Returns the subname, or None."""
    tgt_name = getattr(target, "Name", None)
    tgt_doc = getattr(target, "Document", None)
    tails = tails or []

    def _same(o):
        if o is target:
            return True
        try:
            return (getattr(o, "Name", None) == tgt_name
                    and getattr(o, "Document", None) is tgt_doc)
        except Exception:
            return False

    def _resolve(subname):
        try:
            return link.getSubObject(subname, 1) if subname else link
        except Exception:
            return None

    seen = set()

    def rec(prefix, depth):
        if depth > max_depth:
            return None
        cur = _resolve(prefix)
        if cur is None:
            return None
        # (1) Probe explicit tails at this node — handles links whose
        #     getSubObjects() is empty but explicit deep paths still resolve.
        for t in tails:
            full = prefix + t
            obj = _resolve(full)
            if obj is not None and _same(obj):
                return full
        # (2) Walk enumerated children.
        try:
            kids = cur.getSubObjects()
        except Exception:
            kids = None
        for c in (kids or []):
            full = prefix + c
            if full in seen:
                continue
            seen.add(full)
            obj = _resolve(full)
            if obj is None:
                continue
            if _same(obj):
                return full
            r = rec(full, depth + 1)
            if r:
                return r
        return None

    return rec("", 0)


def _dump_link_subtree(link, max_items=40):
    """Log the immediate sub-object graph under `link` (2 levels) — diagnostic
    used when subname discovery fails, so we can see the real child names."""
    try:
        kids = link.getSubObjects() or []
        App.Console.PrintMessage("[Asm] subtree: '{}' children={}\n".format(
            getattr(link, "Name", "?"), list(kids)[:max_items]))
        for c in list(kids)[:max_items]:
            try:
                obj = link.getSubObject(c, 1)
                gkids = obj.getSubObjects() if obj is not None else []
                App.Console.PrintMessage("[Asm] subtree:   {} -> {} :: {}\n".format(
                    c, getattr(obj, "Name", "?"), list(gkids or [])[:max_items]))
            except Exception as _e:
                App.Console.PrintMessage("[Asm] subtree:   {} -> <err {}>\n".format(c, _e))
    except Exception as e:
        App.Console.PrintMessage("[Asm] subtree: dump failed: {}\n".format(e))


def _add_reference_axes(sketch, doc, length=50.0):
    """Add two construction lines lying on the sketch's local X and Y axes,
    anchored symmetric about the origin. Because they are ordinary sketch
    geometry (unlike the native axes) they remain SELECTABLE when the sketch is
    edited through a link — enabling symmetry/reference against the axes while
    staying in the assembly tab. Returns (gx, gy) GeoIds or None."""
    try:
        import Sketcher
        import Part
    except Exception as e:
        App.Console.PrintMessage("[Asm] ref-axes: import failed: {}\n".format(e))
        return None
    try:
        L = float(length)
        gx = sketch.addGeometry(
            Part.LineSegment(App.Vector(-L, 0, 0), App.Vector(L, 0, 0)), True)
        gy = sketch.addGeometry(
            Part.LineSegment(App.Vector(0, -L, 0), App.Vector(0, L, 0)), True)
        # Lie on the axes: horizontal / vertical, and centred on the origin
        # (RootPoint = GeoId -1, PointPos 1) so each line passes through it.
        sketch.addConstraint(Sketcher.Constraint('Horizontal', gx))
        sketch.addConstraint(Sketcher.Constraint('Vertical', gy))
        sketch.addConstraint(Sketcher.Constraint('Symmetric', gx, 1, gx, 2, -1, 1))
        sketch.addConstraint(Sketcher.Constraint('Symmetric', gy, 1, gy, 2, -1, 1))
        doc.recompute()
        App.Console.PrintMessage(
            "[Asm] ref-axes: added pickable X/Y construction axes (gx={}, gy={})\n".format(
                gx, gy))
        return (gx, gy)
    except Exception as e:
        App.Console.PrintMessage("[Asm] ref-axes: add failed: {}\n".format(e))
        return None


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

        # Prefer a plane / planar face the user pre-selected (Part Design
        # behaviour). Only fall back to the modal picker when nothing usable
        # is selected.
        ref = _selected_sketch_ref(body)
        if ref is not None:
            plane, plane_sub = ref
            App.Console.PrintMessage(
                "[Asm] inplace: using pre-selected attachment '{}.{}'\n".format(
                    getattr(plane, "Name", "?"), plane_sub))
        else:
            App.Console.PrintMessage("[Asm] inplace: showing interactive plane picker\n")
            picked = _pick_sketch_plane(body)
            if picked is None:
                App.Console.PrintMessage("[Asm] inplace: plane picker cancelled\n")
                return
            plane, plane_sub = picked

        App.setActiveTransaction("Create sketch")
        sketch = body_doc.addObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(plane, plane_sub)]
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

        # NOTE: an earlier revision made the PRIMARY path switch to the part's
        # OWN document for a native Sketcher edit (real snappable axes). That
        # broke the top-down workflow — the user must stay in the MAIN ASSEMBLY
        # tab to model a part in assembly context. So we keep the in-place
        # through-link strategies below (Strategy 0/1) as the primary path and
        # never switch tabs for a direct part.

        # Subassembly-level FALLBACK — defined here but CALLED ONLY AFTER the
        # stay-in-tab root strategy (Strategy 1) below fails. The user's rule is
        # to stay in the CURRENT (root) tab, so a tab switch is a last resort.
        # For a multi-level chain (main asm → subasm → body), if FreeCAD's root
        # setEdit can't traverse the chain, this switches to the subasm doc (with
        # auto-return) so at least the sketch opens.
        def _subasm_switch_fallback():
            direct_link_doc = _find_doc_with_direct_link_to(body_doc, asm_doc)
            if direct_link_doc is None or direct_link_doc is asm_doc:
                return False
            App.Console.PrintMessage(
                "[Asm] inplace: FALLBACK subasm-level in-place edit (doc='{}')\n".format(
                    direct_link_doc.Name))
            try:
                inner_link, _ = _find_link_to_body_doc(direct_link_doc, body_doc)
                if inner_link is not None:
                    asm_doc_name = asm_doc.Name
                    # Switch to subasm tab
                    App.setActiveDocument(direct_link_doc.Name)
                    try:
                        Gui.ActiveDocument = Gui.getDocument(direct_link_doc.Name)
                    except Exception:
                        pass
                    sub_gd = Gui.getDocument(direct_link_doc.Name)
                    # Do setEdit with the simple (direct-case) subname format
                    subname = body.Name + "." + sketch.Name + "."
                    App.Console.PrintMessage(
                        "[Asm] inplace: subasm-level setEdit link='{}' subname='{}'\n".format(
                            inner_link.Name, subname))
                    if sub_gd and sub_gd.setEdit(inner_link, 0, subname):
                        App.Console.PrintMessage("[Asm] inplace: subasm-level OK\n")
                        # Add overlay (in subasm view this time)
                        if sub_gd.ActiveView is not None:
                            _add_sketch_overlay(sub_gd.ActiveView, sketch, inner_link, body)
                        # Auto-return to main asm tab when sketch closes
                        try:
                            Gui.addDocumentObserver(_AutoReturnObserver(asm_doc_name))
                            App.Console.PrintMessage(
                                "[Asm] inplace: auto-return to '{}' installed\n".format(asm_doc_name))
                        except Exception:
                            pass
                        try:
                            Gui.addDocumentObserver(
                                _InplaceCleanupObserver(body_doc.Name, sketch.Name))
                        except Exception:
                            pass
                        _fit_view_to_sketch()
                        return True
                    else:
                        App.Console.PrintMessage("[Asm] inplace: subasm-level returned False\n")
            except Exception as e:
                App.Console.PrintMessage("[Asm] inplace: subasm-level raised: {}\n".format(e))
            return False

        # Strategy 1 (PRIMARY, stay-in-tab): edit the sketch through a link in
        # the CURRENT assembly doc — this keeps the user in the root tab.
        # This is how FreeCAD edits objects in linked documents in-place.
        if asm_doc is not body_doc:
            link, sub_prefix = _find_link_to_body_doc(asm_doc, body_doc)
            if link is not None:
                # Try multiple subname variations — exact format depends on
                # FreeCAD's internal naming for links and bodies
                # sub_prefix for nested case is like "_123.Link."
                # body.Name is like "_12", sketch.Name is like "Sketch"
                bn = body.Name
                sn = sketch.Name
                # Also try with labels (without underscore prefixes)
                lbl_body = (body.Label or bn).replace(" ", "_")
                lbl_sketch = (sketch.Label or sn).replace(" ", "_")
                candidates = [
                    sub_prefix + bn + "." + sn + ".",                       # standard
                    sub_prefix + sn + ".",                                   # skip body
                    sub_prefix.replace("_", "") + bn + "." + sn + ".",      # no underscores
                    sub_prefix + lbl_body + "." + lbl_sketch + ".",         # labels
                    bn + "." + sn + ".",                                     # just body+sketch
                    sn + ".",                                                 # just sketch
                ]
                # For 2-level chains: also try with the inner link name only (last segment of sub_prefix)
                if sub_prefix and "." in sub_prefix.rstrip("."):
                    parts = sub_prefix.rstrip(".").split(".")
                    inner = parts[-1] + "."
                    candidates.insert(1, inner + bn + "." + sn + ".")
                    candidates.insert(2, inner + sn + ".")
                # Also try fully qualified path through all prefix segments individually
                if sub_prefix:
                    pfx_no_trail = sub_prefix.rstrip(".")
                    # Try with leading underscore stripped from each segment
                    cleaned = ".".join(p.lstrip("_") for p in pfx_no_trail.split(".")) + "."
                    if cleaned != sub_prefix:
                        candidates.append(cleaned + bn + "." + sn + ".")
                # The tail of the subname (path from the deepest link down to the
                # sketch). Through a link, the body appears under its own Name,
                # so '<bodyName>.Sketch.' is the shape that resolves (proven by
                # the subasm-level case using '_443.Sketch.').
                tails = [
                    bn + "." + sn + ".",
                    sn + ".",
                    bn.lstrip("_") + "." + sn + ".",
                    lbl_body + "." + lbl_sketch + ".",
                ]
                # CRITICAL: from the root, the inner link is exposed under a
                # DIFFERENT name than in its own doc (the subtree dump showed
                # 'Link001', not 'Link'). So build candidates from the OUTER
                # link's ACTUAL enumerated child names + each tail — this is the
                # segment every earlier guess got wrong.
                try:
                    real_children = list(link.getSubObjects() or [])
                except Exception:
                    real_children = []
                graph_cands = []
                for ch in real_children:
                    for t in tails:
                        graph_cands.append(ch + t)
                # Prepend real-child candidates (most likely correct).
                for gc in reversed(graph_cands):
                    candidates.insert(0, gc)
                # BEST: ask FreeCAD's own resolver for the exact subname (no
                # guessing), probing explicit tails at every node. Try it FIRST —
                # it is guaranteed valid.
                discovered = None
                try:
                    discovered = _discover_link_subname(link, sketch, tails=tails)
                except Exception as _e:
                    App.Console.PrintMessage(
                        "[Asm] inplace: subname discovery raised: {}\n".format(_e))
                if discovered:
                    App.Console.PrintMessage(
                        "[Asm] inplace: DISCOVERED exact subname '{}'\n".format(discovered))
                    candidates.insert(0, discovered)
                else:
                    App.Console.PrintMessage(
                        "[Asm] inplace: subname discovery found no path to sketch; "
                        "dumping subtree for diagnosis\n")
                    _dump_link_subtree(link)
                App.Console.PrintMessage(
                    "[Asm] inplace: body.Name='{}' sketch.Name='{}' sub_prefix='{}'\n".format(
                        body.Name, sketch.Name, sub_prefix))
                edited = False
                for candidate in candidates:
                    App.Console.PrintMessage(
                        "[Asm] inplace: trying setEdit via link '{}' subname '{}'\n".format(
                            link.Name, candidate))
                    try:
                        if gd_asm.setEdit(link, 0, candidate):
                            App.Console.PrintMessage("[Asm] inplace: setEdit via link OK\n")
                            edited = True
                            break
                        else:
                            App.Console.PrintMessage("[Asm] inplace: returned False\n")
                    except Exception as e:
                        App.Console.PrintMessage("[Asm] inplace: raised: {}\n".format(e))
                if edited:
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

        # Strategy 2: direct setEdit on the sketch (only works if asm_doc is body_doc)
        try:
            if gd_asm.setEdit(sketch):
                App.Console.PrintMessage("[Asm] inplace: direct setEdit OK\n")
                _fit_view_to_sketch()
                return
        except Exception as e:
            App.Console.PrintMessage("[Asm] inplace: direct setEdit raised: {}\n".format(e))

        # Root strategies couldn't open the sketch in this tab. Only NOW do we
        # allow the subassembly-level tab switch (last-resort fallback).
        if _subasm_switch_fallback():
            return

        # Strategy 3 (fallback): switch to body's doc tab and open sketcher there.
        # Install auto-return observer so we come back to the assembly tab on close.
        App.Console.PrintMessage("[Asm] inplace: falling back to tab switch (with auto-return)\n")
        try:
            asm_doc_name = asm_doc.Name
            App.setActiveDocument(body_doc.Name)
            Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
            Gui.getDocument(body_doc.Name).setEdit(sketch)
            try:
                Gui.addDocumentObserver(_AutoReturnObserver(asm_doc_name))
                App.Console.PrintMessage(
                    "[Asm] inplace: auto-return observer installed (returns to '{}')\n".format(
                        asm_doc_name))
            except Exception:
                pass
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
            # No explicit selection — auto-find the most recent SketchObject in
            # the active body's tree. This handles the common case where the
            # user just closed New Sketch and immediately clicks Pad/Pocket.
            try:
                # Prefer the body's Tip if it's a sketch
                tip = getattr(body, "Tip", None)
                if tip is not None and tip.isDerivedFrom("Sketcher::SketchObject"):
                    selected_sketch = tip
            except Exception:
                pass
            if selected_sketch is None:
                # Walk the body's Group in reverse to find the newest sketch
                try:
                    for child in reversed(body.Group):
                        if child.isDerivedFrom("Sketcher::SketchObject"):
                            selected_sketch = child
                            break
                except Exception:
                    pass
        if selected_sketch is None:
            App.Console.PrintMessage("[Asm] feature: no sketch found in body\n")
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(),
                name_hint,
                "Select a sketch first (or create one with New Sketch), then click " + name_hint + ".",
            )
            return
        App.Console.PrintMessage("[Asm] feature: using sketch '{}'\n".format(selected_sketch.Name))

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

        # Strategy 0: subasm-level direct edit (same trick as new sketch)
        direct_link_doc = _find_doc_with_direct_link_to(body_doc, asm_doc)
        if direct_link_doc is not None and direct_link_doc is not asm_doc:
            App.Console.PrintMessage(
                "[Asm] feature: using subasm-level edit (doc='{}')\n".format(
                    direct_link_doc.Name))
            try:
                inner_link, _ = _find_link_to_body_doc(direct_link_doc, body_doc)
                if inner_link is not None:
                    asm_doc_name = asm_doc.Name
                    App.setActiveDocument(direct_link_doc.Name)
                    try:
                        Gui.ActiveDocument = Gui.getDocument(direct_link_doc.Name)
                    except Exception:
                        pass
                    sub_gd = Gui.getDocument(direct_link_doc.Name)
                    subname = body.Name + "." + feature.Name + "."
                    App.Console.PrintMessage(
                        "[Asm] feature: subasm-level setEdit link='{}' subname='{}'\n".format(
                            inner_link.Name, subname))
                    if sub_gd and sub_gd.setEdit(inner_link, 0, subname):
                        App.Console.PrintMessage("[Asm] feature: subasm-level OK\n")
                        try:
                            Gui.addDocumentObserver(_AutoReturnObserver(asm_doc_name))
                            App.Console.PrintMessage(
                                "[Asm] feature: auto-return to '{}' installed\n".format(asm_doc_name))
                        except Exception:
                            pass
                        return
                    else:
                        App.Console.PrintMessage("[Asm] feature: subasm-level returned False\n")
            except Exception as e:
                App.Console.PrintMessage("[Asm] feature: subasm-level raised: {}\n".format(e))

        # Strategy 1: try in-place edit through link from main asm
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

        # Fallback: switch tabs and edit (last resort) with auto-return
        App.Console.PrintMessage("[Asm] feature: falling back to tab switch\n")
        try:
            asm_doc_name = asm_doc.Name
            App.setActiveDocument(body_doc.Name)
            Gui.ActiveDocument = Gui.getDocument(body_doc.Name)
            Gui.getDocument(body_doc.Name).setEdit(feature)
            try:
                Gui.addDocumentObserver(_AutoReturnObserver(asm_doc_name))
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
        cur_doc_name = App.ActiveDocument.Name

        # A top-down part lives INSIDE an assembly document — the top assembly
        # OR a subassembly (each subassembly is its own file). In that case we
        # edit natively in that document's tab and STAY there: no auto-return.
        # A linked separate-.prt body (Create New Part) is NOT an assembly doc,
        # so it keeps the switch-and-return behaviour.
        body_doc_is_assembly = _doc_is_assembly(body_doc)

        # If the body lives in the VISIBLE tab's document, edit it natively in
        # place — full snappable axes/origin/symmetry, staying in this tab.
        # (With top-down parts now born in the visible tab, this is the path.)
        if body_doc.Name == cur_doc_name:
            _frame_origin_planes(body)
            Gui.runCommand("PartDesign_NewSketch")
            _frame_origin_planes(body, delay_ms=150)
            return

        # The active body lives in a DIFFERENT file than the visible tab (e.g. a
        # linked separate-.prt part activated from the assembly). The user's rule
        # is: NEVER auto-switch tabs. So we do NOT jump to the body's document.
        # Instead we edit the sketch THROUGH THE LINK, staying in the current
        # tab. (Note: a sketch edited through a link cannot natively snap its own
        # X/Y axes — that's a hard FreeCAD limit — so for axis-referenced
        # symmetry the part must be created top-down in this tab, or opened in
        # its own tab. But we honour the stay-in-tab rule as asked.)
        _ = body_doc_is_assembly  # (kept for clarity; no longer drives a switch)
        App.Console.PrintMessage(
            "[Asm] New Sketch: body '{}' is in another file ('{}'); editing "
            "through the link, staying in tab '{}'\n".format(
                body.Name, body_doc.Name, cur_doc_name))
        _new_sketch_in_active_body_inplace()
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


_BNC_PD_ICON_STEMS = (
    "PartDesign_Pad", "PartDesign_Pocket", "PartDesign_Revolution",
    "PartDesign_Hole", "PartDesign_SubShapeBinder",
)
_bnc_registered_icons = {}


def _register_bnc_pd_icons():
    """Register the custom 3D PartDesign icons under NEW cache names ("BNC_<x>")
    so the Part Tools panel can request them and get the same icons the Part
    Design toolbar shows. Uses BitmapFactory's cache (checked first), avoiding
    the standard registered icon. Safe to call repeatedly."""
    # Wrapped whole-body so this can NEVER break the Assembly module import.
    try:
        import FreeCADGui as _Gui
        try:
            from PySide import QtGui, QtCore, QtSvg
        except Exception:
            from PySide2 import QtGui, QtCore, QtSvg
        icons_dir = os.path.join(App.getHomePath(), "data", "Mod", "PartDesign",
                                 "Resources", "icons")
        for stem in _BNC_PD_ICON_STEMS:
            reg_name = "BNC_" + stem
            path = os.path.join(icons_dir, stem + ".svg")
            if not os.path.exists(path):
                continue
            try:
                cached = False
                try:
                    cached = bool(_Gui.isIconCached(reg_name))
                except Exception:
                    cached = False
                if not cached:
                    # Render SVG -> PNG bytes (reliable) and register that.
                    img = QtGui.QImage(64, 64, QtGui.QImage.Format_ARGB32)
                    img.fill(QtCore.Qt.transparent)
                    rnd = QtSvg.QSvgRenderer(path)
                    pnt = QtGui.QPainter(img)
                    rnd.render(pnt)
                    pnt.end()
                    buf = QtCore.QBuffer()
                    buf.open(QtCore.QIODevice.WriteOnly)
                    img.save(buf, "PNG")
                    _Gui.addIcon(reg_name, bytes(buf.data()), "PNG")
                _bnc_registered_icons[stem] = reg_name
            except Exception:
                pass
    except Exception:
        pass


def _resolve_pd_pixmap(name):
    """Return the custom-icon pixmap for a PartDesign command name: the
    registered "BNC_<name>" cache entry if available, else the absolute path to
    the custom SVG, else the plain name."""
    if not _bnc_registered_icons:
        _register_bnc_pd_icons()   # lazy: GUI may not have been ready at import
    if name in _bnc_registered_icons:
        return _bnc_registered_icons[name]
    try:
        if name:
            p = os.path.join(App.getHomePath(), "data", "Mod", "PartDesign",
                             "Resources", "icons", str(name) + ".svg")
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return name


class _BaseBodyCmd:
    """Base for body-context wrapper commands."""
    _PD_CMD = ""
    _MENU = ""
    _PIXMAP = ""
    _TOOLTIP = ""

    def GetResources(self):
        return {
            "Pixmap": _resolve_pd_pixmap(self._PIXMAP),
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
    _TOOLTIP = "Create a new sketch on the active body (opens the part with the full Part Design sketcher)."

    def Activated(self):
        # HARD FreeCAD limit: a sketch edited THROUGH a link (staying in the
        # assembly tab) cannot select/snap its own X/Y axes or origin — so
        # symmetry/dimension-from-origin is impossible there. The ONLY way to
        # get those native references is a native edit in the part's own doc.
        # So we switch to the part's tab, run the real Sketcher, and auto-return
        # to the assembly when the sketch closes. Assembly-level references are
        # available via "Reference Assembly" (cross-doc SubShapeBinders), so the
        # part tab loses nothing.
        _new_sketch_with_auto_return()


# ============================================================================
# PHASE 1 — Creo-style "Copy Geometry" for top-down design.
#
# Imports the assembly's datums (origin planes/axes/point) into the active part
# as associative PartDesign::SubShapeBinders. A SubShapeBinder is FreeCAD's only
# sanctioned cross-part / cross-document reference (the Sketcher explicitly
# refuses direct cross-part refs and says "should be done via shapebinders").
# Once imported, a sketch in the part can project these via Sketcher 'External
# geometry' and constrain/dimension to them; BindMode=Synchronized keeps them
# associative so they follow the assembly when it changes.
# ============================================================================

def _assembly_of_body(body):
    """Return the Assembly / App::Part that owns the assembly-level datums for
    this body (active assembly first, else nearest App::Part ancestor)."""
    try:
        asm = UtilsAssembly.activeAssembly()
        if asm is not None:
            return asm
    except Exception:
        pass
    seen = set()
    stack = list(getattr(body, "InList", []))
    while stack:
        o = stack.pop()
        if o is None or getattr(o, "Name", None) in seen:
            continue
        seen.add(o.Name)
        if getattr(o, "TypeId", "") in ("Assembly::AssemblyObject", "App::Part"):
            return o
        stack.extend(getattr(o, "InList", []))
    return None


def _assembly_datums(asm, selected_only=False):
    """Origin datum objects (App::Plane/Line/Point) of the assembly. When
    selected_only, return just the ones the user pre-selected (or [])."""
    try:
        all_datums = [o for o in asm.Origin.OutList
                      if getattr(o, "TypeId", "") in
                      ("App::Plane", "App::Line", "App::Point")]
    except Exception:
        all_datums = []
    if selected_only:
        try:
            names = {s.Name for s in Gui.Selection.getSelection()}
            return [d for d in all_datums if d.Name in names]
        except Exception:
            return []
    return all_datums


def _reference_assembly_geometry():
    """Import the assembly datums into the active part body as Synchronized
    SubShapeBinders so sketches can reference the assembly coordinate frame."""
    try:
        body = _get_active_body_in_view()
        if body is None:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Reference Assembly",
                "Activate a part first (no active body in the view).")
            return
        asm = _assembly_of_body(body)
        if asm is None:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Reference Assembly",
                "No assembly found for the active part.")
            return

        datums = _assembly_datums(asm, selected_only=True)
        if not datums:
            datums = _assembly_datums(asm, selected_only=False)
        if not datums:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Reference Assembly",
                "The assembly has no origin datums to reference.")
            return

        existing = {getattr(b, "Label", ""): b for b in getattr(body, "Group", [])
                    if getattr(b, "TypeId", "") == "PartDesign::SubShapeBinder"}
        made = []
        App.setActiveTransaction("Reference Assembly Geometry")
        try:
            for d in datums:
                role = getattr(d, "Role", "") or d.Name
                label = "Asm_" + role
                if label in existing:
                    continue
                binder = body.newObject("PartDesign::SubShapeBinder", "AsmRef")
                binder.Label = label
                try:
                    binder.Support = [(d, [""])]
                except Exception:
                    binder.Support = [(d, "")]
                for prop, val in (("BindMode", "Synchronized"), ("Relative", True)):
                    try:
                        setattr(binder, prop, val)
                    except Exception:
                        pass
                made.append(label)
            body.Document.recompute()
        finally:
            App.closeActiveTransaction()

        App.Console.PrintMessage(
            "[Asm] Reference Assembly: imported {} binder(s) into '{}': {}\n"
            .format(len(made), body.Label, ", ".join(made)))
        QtWidgets.QMessageBox.information(
            Gui.getMainWindow(), "Reference Assembly",
            "Imported {} assembly reference(s) into '{}':\n  {}\n\n"
            "Next: inside a sketch on this part, click Sketcher → "
            "'External geometry' and pick these imported axes / planes / origin "
            "to project them into the sketch. You can then dimension and "
            "constrain to them, and they update when the assembly moves."
            .format(len(made), body.Label,
                    ", ".join(made) if made else "(all already present)"))
    except Exception as e:
        try:
            App.closeActiveTransaction()
        except Exception:
            pass
        App.Console.PrintError("[Asm] Reference Assembly failed: {}\n".format(e))


# ----------------------------------------------------------------------------
# PHASE 2 — Copy Geometry from ANOTHER COMPONENT (part/sub-assembly edges/faces)
#
# FreeCAD's Sketcher hard-blocks external geometry across parts/bodies/docs
# (isExternalAllowed rejects rlOtherBody/rlOtherPart/rlOtherDoc) — the only
# sanctioned cross-part reference is a SubShapeBinder. This imports the
# pre-selected edges/faces of OTHER components into the active body as
# associative binders, so a sketch on the active part can then project them via
# Sketcher 'External geometry' and constrain/dimension to them.
# ----------------------------------------------------------------------------

def _reference_component_geometry():
    """Copy Geometry: import the pre-selected edges/faces of other components
    into the active body as Synchronized SubShapeBinders."""
    try:
        body = _get_active_body_in_view()
        if body is None:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Reference Part",
                "Activate the part you are designing first (no active body in "
                "the view).")
            return
        asm = _assembly_of_body(body)

        # Collect (sourceComponent, relativeSub) picks from the current selection.
        picks = []          # ordered list of (component, subname)
        try:
            sel_ex = Gui.Selection.getSelectionEx()
        except Exception:
            sel_ex = []
        for s in sel_ex:
            root = s.Object
            for sub in (getattr(s, "SubElementNames", []) or []):
                if not sub:
                    continue
                leaf = sub.split(".")[-1]
                if not (leaf.startswith("Edge") or leaf.startswith("Face")
                        or leaf.startswith("Vertex")):
                    continue
                comp, relsub = None, ""
                if asm is not None:
                    try:
                        comp, relsub = UtilsAssembly.getComponentReference(
                            asm, root, sub)
                    except Exception:
                        comp, relsub = None, ""
                if comp is None:
                    # Same-document body (no assembly-relative path) — reference
                    # the picked object/sub directly.
                    comp, relsub = root, sub
                # Nothing to copy from the active body itself.
                if comp is body:
                    continue
                picks.append((comp, relsub))

        if not picks:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Reference Part",
                "Select one or more edges / faces on ANOTHER part first, then "
                "run Reference Part.\n\nExternal projection cannot cross parts "
                "directly — this copies the picked geometry into the active "
                "part as an associative reference so a sketch can project it.")
            return

        # Group picks by source component so each binder carries one part's subs.
        groups = {}         # comp.Name -> [comp, [subs]]
        order = []
        for comp, relsub in picks:
            key = comp.Name
            if key not in groups:
                groups[key] = [comp, []]
                order.append(key)
            if relsub not in groups[key][1]:
                groups[key][1].append(relsub)

        made = []
        App.setActiveTransaction("Reference Part Geometry")
        try:
            for key in order:
                comp, subs = groups[key]
                binder = body.newObject("PartDesign::SubShapeBinder", "PartRef")
                binder.Label = "Ref_" + (getattr(comp, "Label", "") or comp.Name)
                try:
                    binder.Support = [(comp, subs)]
                except Exception:
                    binder.Support = [(comp, subs[0])]
                for prop, val in (("BindMode", "Synchronized"), ("Relative", True)):
                    try:
                        setattr(binder, prop, val)
                    except Exception:
                        pass
                if asm is not None:
                    try:
                        binder.Context = asm
                    except Exception:
                        pass
                # Make the binder visible so the Sketcher 'External geometry'
                # tool can pick its edges/faces inside a sketch (an invisible
                # binder cannot be clicked to project).
                try:
                    if binder.ViewObject is not None:
                        binder.ViewObject.Visibility = True
                except Exception:
                    pass
                made.append(binder.Label)
            body.Document.recompute()
        finally:
            App.closeActiveTransaction()

        App.Console.PrintMessage(
            "[Asm] Reference Part: imported {} binder(s) into '{}': {}\n"
            .format(len(made), body.Label, ", ".join(made)))
        QtWidgets.QMessageBox.information(
            Gui.getMainWindow(), "Reference Part",
            "Imported {} part reference(s) into '{}':\n  {}\n\n"
            "Next: inside a sketch on this part, click Sketcher → "
            "'External geometry' (G, X) and pick the imported edges/faces to "
            "project them. They update when the source part changes."
            .format(len(made), body.Label, ", ".join(made)))
    except Exception as e:
        try:
            App.closeActiveTransaction()
        except Exception:
            pass
        App.Console.PrintError("[Asm] Reference Part failed: {}\n".format(e))


class CommandReferenceAssembly:
    """Creo-style Copy Geometry: import assembly datums into the active part as
    associative references so sketches can constrain to the assembly frame."""

    def GetResources(self):
        return {
            "Pixmap": _resolve_pd_pixmap("PartDesign_SubShapeBinder"),
            "MenuText": "Reference Assembly",
            "ToolTip": "Import the assembly's origin/datums into the active part "
                       "as associative references (Copy Geometry), so sketches "
                       "can constrain to the assembly frame. Pre-select specific "
                       "assembly datums, or run with none selected to import all.",
        }

    def IsActive(self):
        try:
            gd = Gui.ActiveDocument
            return bool(gd and gd.ActiveView
                        and gd.ActiveView.getActiveObject("pdbody"))
        except Exception:
            return False

    def Activated(self):
        _reference_assembly_geometry()


class CommandReferenceComponent:
    """Creo-style Copy Geometry from another part: import pre-selected edges/
    faces of other components into the active part as associative references so
    a sketch can project them (External geometry)."""

    def GetResources(self):
        return {
            "Pixmap": _resolve_pd_pixmap("PartDesign_SubShapeBinder"),
            "MenuText": "Reference Part",
            "ToolTip": "Copy Geometry: import the selected edges/faces of "
                       "ANOTHER part into the active part as associative "
                       "references, so a sketch can project (External geometry) "
                       "and constrain to them. Pre-select edges/faces on the "
                       "other part, then run this.",
        }

    def IsActive(self):
        try:
            gd = Gui.ActiveDocument
            return bool(gd and gd.ActiveView
                        and gd.ActiveView.getActiveObject("pdbody"))
        except Exception:
            return False

    def Activated(self):
        _reference_component_geometry()


def _sketch_in_edit():
    """Return the Sketcher::SketchObject currently open for editing, else None."""
    try:
        vp = Gui.ActiveDocument.getInEdit()
        obj = getattr(vp, "Object", None) if vp is not None else None
        if obj is not None and getattr(obj, "TypeId", "") == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass
    # Fallback: a single selected sketch (not being edited yet).
    try:
        for s in Gui.Selection.getSelection():
            if getattr(s, "TypeId", "") == "Sketcher::SketchObject":
                return s
    except Exception:
        pass
    return None


def _body_of_sketch(sketch):
    for p in getattr(sketch, "InList", []):
        if getattr(p, "TypeId", "") == "PartDesign::Body":
            return p
    return _get_active_body_in_view()


def _project_external_into_current_sketch():
    """Creo-style 'project': copy the pre-selected edges/faces of OTHER parts
    into the sketch's body as SubShapeBinders AND immediately project them into
    the currently-edited sketch as external geometry. One click, inside the
    sketch, since FreeCAD forbids projecting another part's geometry directly."""
    try:
        sketch = _sketch_in_edit()
        if sketch is None:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Project External Part",
                "Open a sketch for editing first, then (in the 3D view) select "
                "edges/faces on ANOTHER part and click Project External Part.")
            return
        body = _body_of_sketch(sketch)
        if body is None:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Project External Part",
                "Could not find the part body that owns this sketch.")
            return
        asm = _assembly_of_body(body)

        picks = []
        try:
            sel_ex = Gui.Selection.getSelectionEx()
        except Exception:
            sel_ex = []
        for s in sel_ex:
            root = s.Object
            if root is sketch:
                continue
            for sub in (getattr(s, "SubElementNames", []) or []):
                if not sub:
                    continue
                leaf = sub.split(".")[-1]
                if not (leaf.startswith("Edge") or leaf.startswith("Face")
                        or leaf.startswith("Vertex")):
                    continue
                comp, relsub = None, ""
                if asm is not None:
                    try:
                        comp, relsub = UtilsAssembly.getComponentReference(
                            asm, root, sub)
                    except Exception:
                        comp, relsub = None, ""
                if comp is None:
                    comp, relsub = root, sub
                if comp is body:
                    continue
                picks.append((comp, relsub))

        if not picks:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Project External Part",
                "Select one or more edges / faces on ANOTHER part in the 3D "
                "view first, then click Project External Part.\n\n(FreeCAD can't "
                "project another part directly — this copies the picked geometry "
                "into this part and projects it into the sketch.)")
            return

        groups, order = {}, []
        for comp, relsub in picks:
            key = comp.Name
            if key not in groups:
                groups[key] = [comp, []]
                order.append(key)
            if relsub not in groups[key][1]:
                groups[key][1].append(relsub)

        total = 0
        App.setActiveTransaction("Project External Part")
        try:
            for key in order:
                comp, subs = groups[key]
                binder = body.newObject("PartDesign::SubShapeBinder", "PartRef")
                binder.Label = "Ref_" + (getattr(comp, "Label", "") or comp.Name)
                try:
                    binder.Support = [(comp, subs)]
                except Exception:
                    binder.Support = [(comp, subs[0])]
                for prop, val in (("BindMode", "Synchronized"), ("Relative", True)):
                    try:
                        setattr(binder, prop, val)
                    except Exception:
                        pass
                if asm is not None:
                    try:
                        binder.Context = asm
                    except Exception:
                        pass
                try:
                    if binder.ViewObject is not None:
                        binder.ViewObject.Visibility = True
                except Exception:
                    pass
                body.Document.recompute()
                # Project every edge of the imported geometry into the sketch.
                nedges = len(binder.Shape.Edges) if binder.Shape else 0
                for i in range(nedges):
                    try:
                        sketch.addExternal(binder.Name, "Edge%d" % (i + 1))
                        total += 1
                    except Exception:
                        pass
            body.Document.recompute()
        finally:
            App.closeActiveTransaction()

        try:
            if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
                Gui.ActiveDocument.ActiveView.redraw()
        except Exception:
            pass
        App.Console.PrintMessage(
            "[Asm] Project External Part: projected {} edge(s) into '{}'.\n"
            .format(total, sketch.Label))
        if total == 0:
            QtWidgets.QMessageBox.information(
                Gui.getMainWindow(), "Project External Part",
                "Created the reference but could not auto-project. Use Sketcher "
                "'External geometry' (G, X) and click the new 'Ref_...' edges.")
    except Exception as e:
        try:
            App.closeActiveTransaction()
        except Exception:
            pass
        App.Console.PrintError("[Asm] Project External Part failed: {}\n".format(e))


class CommandProjectExternalPart:
    """Creo-style project: while editing a sketch, project the pre-selected
    edges/faces of another part into the sketch (via an associative binder)."""

    def GetResources(self):
        return {
            "Pixmap": _resolve_pd_pixmap("PartDesign_SubShapeBinder"),
            "MenuText": "Project External Part",
            "ToolTip": "While editing a sketch, project the selected edges/faces "
                       "of ANOTHER part into the current sketch as external "
                       "geometry (Creo-style Project). Select the other part's "
                       "edges/faces in the 3D view first.",
        }

    def IsActive(self):
        try:
            return _sketch_in_edit() is not None
        except Exception:
            return False

    def Activated(self):
        _project_external_into_current_sketch()


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
    Gui.addCommand("Assembly_ReferenceAssembly", CommandReferenceAssembly())
    Gui.addCommand("Assembly_ReferenceComponent", CommandReferenceComponent())
    Gui.addCommand("Assembly_ProjectExternalPart", CommandProjectExternalPart())
    Gui.addCommand("Assembly_BodyNewSketch",  CommandBodyNewSketch())
    Gui.addCommand("Assembly_BodyPad",        CommandBodyPad())
    Gui.addCommand("Assembly_BodyPocket",     CommandBodyPocket())
    Gui.addCommand("Assembly_BodyRevolution", CommandBodyRevolution())
    Gui.addCommand("Assembly_BodyHole",       CommandBodyHole())
