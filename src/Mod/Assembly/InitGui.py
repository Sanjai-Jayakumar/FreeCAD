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

import re
import os
import Assembly_rc

# Register recolored icons folder so it overrides the embedded Assembly_rc icons
def _register_recolored_icons():
    try:
        import FreeCADGui as _Gui
        _icons_dir = os.path.join(os.path.dirname(__file__), "Resources", "icons", "recolored")
        if os.path.isdir(_icons_dir):
            _Gui.addIconPath(_icons_dir)
    except Exception:
        pass

_register_recolored_icons()


def _asm_clean_name(fn):
    """Given a file path ending in .asm/.prt/.drg, return the clean base name.
    Returns None if the file is not a recognised assembly file."""
    if not fn:
        return None
    basename = os.path.basename(fn)
    # Strip optional .FCStd container → "1222.001.asm.FCStd" → "1222.001.asm"
    no_fcstd = re.sub(r'\.FCStd$', '', basename, flags=re.IGNORECASE)
    if not re.search(r'\.(prt|asm|drg)$', no_fcstd, re.IGNORECASE):
        return None
    c = re.sub(r'\.(prt|asm|drg)$', '', no_fcstd, flags=re.IGNORECASE)  # "1222.001"
    c = re.sub(r'\.\d+$', '', c)                                         # "1222"
    return c or None


def _asm_apply_clean_label(doc):
    """Set the root AssemblyObject label in doc to the clean name if needed."""
    try:
        clean = _asm_clean_name(getattr(doc, 'FileName', ''))
        if not clean:
            return
        for obj in doc.Objects:
            if obj.isDerivedFrom("Assembly::AssemblyObject"):
                if obj.Label != clean:
                    obj.Label = clean
                break
    except Exception:
        pass


class _AsmLabelDocObserver:
    """Cleans root AssemblyObject labels on document recompute / activate.
    Self-contained — no references to module-level names (C++ callbacks run
    in a different namespace and cannot resolve them)."""

    @staticmethod
    def _clean(doc):
        try:
            import re as _re, os as _os
            fn = getattr(doc, 'FileName', '') or ''
            if not fn:
                return
            basename = _os.path.basename(fn)
            no_fcstd = _re.sub(r'\.FCStd$', '', basename, flags=_re.IGNORECASE)
            if not _re.search(r'\.(prt|asm|drg)$', no_fcstd, _re.IGNORECASE):
                return
            c = _re.sub(r'\.(prt|asm|drg)$', '', no_fcstd, flags=_re.IGNORECASE)
            c = _re.sub(r'\.\d+$', '', c)
            clean = c
            if not clean:
                return
            for obj in doc.Objects:
                if obj.isDerivedFrom('Assembly::AssemblyObject'):
                    if obj.Label != clean:
                        obj.Label = clean
                    break
        except Exception:
            pass

    def slotRecomputedDocument(self, doc):
        self._clean(doc)

    def slotFinishRestoreDocument(self, doc):
        self._clean(doc)

    def slotActivateDocument(self, doc):
        self._clean(doc)


import FreeCAD as _FC
_asm_label_observer = _AsmLabelDocObserver()
_FC.addDocumentObserver(_asm_label_observer)

# Fan-out save for STEP-imported assemblies: when a doc made of App::Part
# containers (no native Assembly::AssemblyObject) is saved, also write each
# container as a versioned .asm and each leaf Part::Feature as a versioned
# .prt into the same directory.
try:
    import AssemblyStepSplitSave  # noqa: F401  (module installs its own observer on import)
except Exception as _e:
    _FC.Console.PrintError(
        "[Assembly] Failed to load AssemblyStepSplitSave: {0}\n".format(_e)
    )


class AssemblyCommandGroup:
    def __init__(self, cmdlist, menu, tooltip=None):
        self.cmdlist = cmdlist
        self.menu = menu
        if tooltip is None:
            self.tooltip = menu
        else:
            self.tooltip = tooltip

    def GetCommands(self):
        return tuple(self.cmdlist)

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tooltip}

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            return True
        return False


class AssemblyWorkbench(Workbench):
    "Assembly workbench"

    def __init__(self):
        self.__class__.Icon = (
            FreeCAD.getResourceDir() + "Mod/Assembly/Resources/icons/AssemblyWorkbench.svg"
        )
        self.__class__.MenuText = "Assembly"
        self.__class__.ToolTip = "Assembly workbench"

    def Initialize(self):
        global AssemblyCommandGroup

        translate = FreeCAD.Qt.translate

        # load the builtin modules
        from PySide import QtCore, QtGui
        from PySide.QtCore import QT_TRANSLATE_NOOP
        import CommandCreateAssembly, CommandInsertLink, CommandInsertNewPart, CommandCreateJoint, CommandSolveAssembly, CommandExportASMT, CommandCreateView, CommandCreateSimulation, CommandCreateBom
        import Preferences

        FreeCADGui.addLanguagePath(":/translations")
        FreeCADGui.addIconPath(":/icons")

        # Register filesystem icon path for custom icons (e.g. Default Joint)
        import os as _os
        _custom_icons = _os.path.join(
            FreeCAD.getHomePath(), "Mod", "Assembly", "Resources", "icons"
        )
        if _os.path.isdir(_custom_icons):
            FreeCADGui.addIconPath(_custom_icons)

        FreeCADGui.addPreferencePage(
            Preferences.PreferencesPage, QT_TRANSLATE_NOOP("QObject", "Assembly")
        )

        # build commands list
        cmdList = [
            "Assembly_CreateAssembly",
            "Assembly_Insert",
            "Assembly_InsertNewBodyInline",
            "Assembly_InsertNewAssembly",
            "Assembly_SolveAssembly",
            "Assembly_CreateView",
            "Assembly_CreateSimulation",
            "Assembly_CreateBom",
        ]

        cmdListMenuOnly = [
            "Assembly_ExportASMT",
            "Assembly_ActivateMainAssembly",
        ]

        cmdListJoints = [
            "Assembly_ToggleGrounded",
            "Assembly_CreateJointDefault",
            "Separator",
            "Assembly_CreateJointFixed",
            "Assembly_CreateJointRevolute",
            "Assembly_CreateJointCylindrical",
            "Assembly_CreateJointSlider",
            "Assembly_CreateJointBall",
            "Separator",
            "Assembly_CreateJointDistance",
            "Assembly_CreateJointParallel",
            "Assembly_CreateJointPerpendicular",
            "Assembly_CreateJointAngle",
            "Separator",
            "Assembly_CreateJointRackPinion",
            "Assembly_CreateJointScrew",
            "Assembly_CreateJointGearBelt",
        ]

        self.appendToolbar(QT_TRANSLATE_NOOP("Workbench", "Assembly"), cmdList)
        self.appendToolbar(QT_TRANSLATE_NOOP("Workbench", "Assembly Joints"), cmdListJoints)

        self.appendMenu(
            [QT_TRANSLATE_NOOP("Workbench", "&Assembly")],
            cmdList + cmdListMenuOnly + ["Separator"] + cmdListJoints,
        )

    def Activated(self):
        # update the translation engine
        FreeCADGui.updateLocale()

        # Install workbench listener that prevents auto-switch to PartDesign
        # when a body is activated inside an assembly context
        self._install_wb_lock()

        # Clean immediately for any already-open documents
        try:
            for doc in FreeCAD.listDocuments().values():
                _asm_apply_clean_label(doc)
        except Exception:
            pass

        # Delayed clean — catches documents that finish loading after Activated() returns
        try:
            from PySide.QtCore import QTimer

            def _delayed_clean():
                try:
                    for doc in FreeCAD.listDocuments().values():
                        _asm_apply_clean_label(doc)
                except Exception:
                    pass

            QTimer.singleShot(800, _delayed_clean)
            QTimer.singleShot(2000, _delayed_clean)
        except Exception:
            pass

        # Install Ctrl+A shortcut overriding FreeCAD's global Select All — runs
        # the Assembly_ActivateMainAssembly command instead.
        self._install_activate_main_shortcut()

        # Install event filter that renames FreeCAD's built-in "Active object"
        # context-menu entry to "Activate Main Assembly".
        self._install_menu_renamer()

        # Add task watchers to provide contextual tools in the task panel
        self._stop_link_sync_timer()
        self.setWatchers()

    def Deactivated(self):
        self._stop_link_sync_timer()
        self._remove_activate_main_shortcut()
        self._remove_menu_renamer()
        self._remove_wb_lock()
        FreeCADGui.Control.clearTaskWatcher()

    def _install_activate_main_shortcut(self):
        try:
            from PySide import QtGui
            from PySide.QtCore import Qt
            mw = FreeCADGui.getMainWindow()
            if mw is None:
                return
            # Remove any existing one first so reactivating the workbench doesn't stack
            self._remove_activate_main_shortcut()
            sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+A"), mw)
            sc.setContext(Qt.ApplicationShortcut)

            def _trigger():
                try:
                    FreeCADGui.runCommand("Assembly_ActivateMainAssembly")
                except Exception:
                    pass

            sc.activated.connect(_trigger)
            self._activate_main_shortcut = sc
        except Exception:
            pass

    def _remove_activate_main_shortcut(self):
        sc = getattr(self, "_activate_main_shortcut", None)
        if sc is not None:
            try:
                sc.setEnabled(False)
                sc.deleteLater()
            except Exception:
                pass
            self._activate_main_shortcut = None

    def _install_menu_renamer(self):
        try:
            from PySide import QtCore, QtGui
            from PySide.QtWidgets import QMenu

            class _MenuRenamer(QtCore.QObject):
                """Renames FreeCAD's built-in context-menu actions while the
                Assembly workbench is active. Also makes 'Activate Subassembly'
                checkable, with state reflecting whether the selected target
                is the currently active subassembly."""
                _RENAMES = {
                    "Active object": "Activate Main Assembly",
                    "Active Body":   "Activate Part",
                    "Active body":   "Activate Part",
                }

                def eventFilter(self, obj, event):
                    try:
                        if event.type() == QtCore.QEvent.Show and isinstance(obj, QMenu):
                            for action in obj.actions():
                                txt = action.text()
                                new = self._RENAMES.get(txt)
                                if new is not None:
                                    action.setText(new)
                                # If we just renamed the native "Active object"
                                # to "Activate Main Assembly", redirect its
                                # trigger to our own command so the body gets
                                # cleared and root is properly activated.
                                if action.text() == "Activate Main Assembly":
                                    self._redirect_to_main_assembly_cmd(action)
                                # Same for Activate Part — use our command that
                                # doesn't auto-switch workbench
                                if action.text() == "Activate Part":
                                    self._redirect_to_activate_part_cmd(action)
                                if action.text() == "Activate Subassembly":
                                    self._mark_subasm_action(action)
                    except Exception:
                        pass
                    return False  # do not consume

                @staticmethod
                def _redirect_to_main_assembly_cmd(action):
                    """Disconnect any existing handler and connect to our
                    Assembly_ActivateMainAssembly command."""
                    if getattr(action, "_asm_redirected", False):
                        return  # already redirected
                    try:
                        try:
                            action.triggered.disconnect()
                        except Exception:
                            pass
                        def _trigger(_checked=False):
                            try:
                                FreeCADGui.runCommand("Assembly_ActivateMainAssembly")
                            except Exception:
                                pass
                        action.triggered.connect(_trigger)
                        action._asm_redirected = True
                    except Exception:
                        pass

                @staticmethod
                def _redirect_to_activate_part_cmd(action):
                    """Redirect 'Activate Part' to our command that doesn't
                    auto-switch workbench."""
                    if getattr(action, "_asm_part_redirected", False):
                        return
                    try:
                        try:
                            action.triggered.disconnect()
                        except Exception:
                            pass
                        def _trigger(_checked=False):
                            try:
                                FreeCADGui.runCommand("Assembly_ActivatePart")
                            except Exception:
                                pass
                        action.triggered.connect(_trigger)
                        action._asm_part_redirected = True
                    except Exception:
                        pass

                @staticmethod
                def _mark_subasm_action(action):
                    """Make the action checkable and set checked state based on whether
                    the currently selected subassembly target is the active one."""
                    try:
                        import UtilsAssembly as _UA
                        # Locate the selected activation target (same logic the command uses)
                        from CommandCreateAssembly import _selected_assembly_activation_target
                        target = _selected_assembly_activation_target()
                        cache = getattr(_UA, "_active_asm_link_target", None)
                        is_active = False
                        if target is not None and cache is not None:
                            try:
                                c_doc, c_obj, _ = cache
                                if c_doc == target[0] and c_obj == target[1]:
                                    is_active = True
                            except Exception:
                                pass
                        action.setCheckable(True)
                        action.setChecked(is_active)
                    except Exception:
                        pass

            mw = FreeCADGui.getMainWindow()
            if mw is None:
                return
            self._remove_menu_renamer()
            app = QtCore.QCoreApplication.instance()
            renamer = _MenuRenamer(mw)
            app.installEventFilter(renamer)
            self._menu_renamer = renamer
        except Exception:
            pass

    def _remove_menu_renamer(self):
        renamer = getattr(self, "_menu_renamer", None)
        if renamer is not None:
            try:
                from PySide import QtCore
                QtCore.QCoreApplication.instance().removeEventFilter(renamer)
                renamer.deleteLater()
            except Exception:
                pass
            self._menu_renamer = None

    def _install_wb_lock(self):
        """Install a workbench listener that snaps back to AssemblyWorkbench
        when an assembly is open and another workbench (typically PartDesign)
        gets auto-activated."""
        try:
            class _WBLock:
                _suppress = False  # avoid feedback loop while we switch back

                def workbenchActivated(self, wb_name):
                    if _WBLock._suppress:
                        return
                    if wb_name == "AssemblyWorkbench":
                        return
                    # Only act when an assembly document is open
                    try:
                        has_asm = False
                        for d in FreeCAD.listDocuments().values():
                            for o in d.Objects:
                                if o.TypeId == "Assembly::AssemblyObject":
                                    has_asm = True
                                    break
                            if has_asm:
                                break
                        if not has_asm:
                            return
                    except Exception:
                        return
                    # Snap back to Assembly workbench
                    try:
                        from PySide.QtCore import QTimer
                        def _switch_back():
                            try:
                                _WBLock._suppress = True
                                FreeCADGui.activateWorkbench("AssemblyWorkbench")
                            finally:
                                _WBLock._suppress = False
                        QTimer.singleShot(0, _switch_back)
                    except Exception:
                        pass

                def workbenchDeactivated(self, wb_name):
                    pass

            # In FreeCAD 1.1 there's no addWorkbenchListener — use a 200ms
            # QTimer to snap back to Assembly when another workbench gets active.
            from PySide.QtCore import QTimer
            self._wb_lock = _WBLock()
            self._wb_lock_timer = QTimer()
            def _check():
                try:
                    name = FreeCADGui.activeWorkbench().__class__.__name__
                    if name != "AssemblyWorkbench":
                        self._wb_lock.workbenchActivated(name)
                except Exception:
                    pass
            self._wb_lock_timer.timeout.connect(_check)
            self._wb_lock_timer.start(200)
        except Exception as e:
            FreeCAD.Console.PrintMessage("[Asm] _install_wb_lock failed: {}\n".format(e))

    def _remove_wb_lock(self):
        t = getattr(self, "_wb_lock_timer", None)
        if t is not None:
            try:
                t.stop()
                t.deleteLater()
            except Exception:
                pass
            self._wb_lock_timer = None
        self._wb_lock = None

    def ContextMenu(self, recipient):
        if recipient != "Tree":
            return

        def _is_asm_related(obj):
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

        # Strategy 1: getSelectionEx with both call forms (no-arg = all docs in some builds,
        # "" arg = all docs in others). For nested objects, s.Object may be a parent link
        # with the child encoded in SubElementNames — we walk that path too.
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
            lambda: FreeCADGui.Selection.getSelectionEx(),
            lambda: FreeCADGui.Selection.getSelectionEx(""),
        ):
            try:
                for s in _get():
                    try:
                        obj = s.Object
                        if obj is None:
                            continue
                        if _is_asm_related(obj):
                            self.appendContextMenu("", ["Assembly_ActivateObject"])
                            return
                        for subname in (getattr(s, "SubElementNames", None) or []):
                            deepest = _walk_to_deepest(obj, subname)
                            if deepest is not obj and _is_asm_related(deepest):
                                self.appendContextMenu("", ["Assembly_ActivateObject"])
                                return
                    except Exception:
                        pass
            except Exception:
                pass

        # Strategy 2: explicit per-document getSelection
        for doc_name in FreeCAD.listDocuments():
            try:
                for obj in FreeCADGui.Selection.getSelection(doc_name):
                    if _is_asm_related(obj):
                        self.appendContextMenu("", ["Assembly_ActivateObject"])
                        return
            except Exception:
                pass

        # Strategy 3 (last resort): match the Qt tree widget's selected item label
        # against all open documents' objects. This works for any nesting depth and
        # remains correct after activation (unlike the activeAssembly().Group approach
        # which breaks once a leaf assembly is active).
        try:
            mw = FreeCADGui.getMainWindow()
            from PySide import QtGui as _QtGui
            selected_labels = set()
            for tree in mw.findChildren(_QtGui.QTreeWidget):
                for item in tree.selectedItems():
                    lbl = item.text(0)
                    if lbl:
                        selected_labels.add(lbl)
            if selected_labels:
                for doc in FreeCAD.listDocuments().values():
                    for obj in doc.Objects:
                        try:
                            if obj.Label not in selected_labels:
                                continue
                            linked = getattr(obj, "LinkedObject", None)
                            if linked is None:
                                continue
                            if (linked.isDerivedFrom("Assembly::AssemblyObject")
                                    or getattr(linked, "TypeId", "") == "Assembly::AssemblyObject"):
                                self.appendContextMenu("", ["Assembly_ActivateObject"])
                                return
                        except Exception:
                            pass
        except Exception:
            pass

    def _stop_link_sync_timer(self):
        timer = getattr(self, "_link_sync_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
            self._link_sync_timer = None

    def setWatchers(self):
        import UtilsAssembly
        from PySide import QtCore, QtGui

        translate = FreeCAD.Qt.translate

        class AssemblyCreateWatcher:
            """Shows 'Create Assembly' when no assembly exists in the document."""

            def __init__(self):
                self.commands = ["Assembly_CreateAssembly"]
                self.title = translate("Assembly", "Create")

            def shouldShow(self):
                doc = FreeCAD.ActiveDocument

                if hasattr(doc, "RootObjects"):
                    for obj in doc.RootObjects:
                        if obj.isDerivedFrom("Assembly::AssemblyObject"):
                            return False
                return True

        class AssemblyBaseWatcher:
            """Base class for watchers that require an active assembly."""

            def __init__(self):
                self.assembly = None

            def shouldShow(self):
                self.assembly = UtilsAssembly.activeAssembly()
                return self.assembly is not None

        class AssemblyInsertWatcher(AssemblyBaseWatcher):
            """Shows 'Insert Component' when an assembly is active."""

            def __init__(self):
                super().__init__()
                self.commands = [
                    "Assembly_Insert",
                    "Assembly_InsertNewBodyInline",
                    "Assembly_InsertNewAssembly",
                ]
                # FreeCAD reads .title at panel-creation time, before shouldShow().
                # Read the cache immediately so the correct assembly label appears
                # on the very first display (critical for L-2+ activation).
                asm = UtilsAssembly.activeAssembly()
                if asm is not None:
                    self.title = "Insert  ▶  {}".format(asm.Label)
                else:
                    self.title = translate("Assembly", "Insert")

            def shouldShow(self):
                result = super().shouldShow()
                # Show which assembly is currently active in the panel title so the
                # user has clear confirmation when a nested level is activated.
                if self.assembly is not None:
                    self.title = "Insert  ▶  {}".format(self.assembly.Label)
                else:
                    self.title = translate("Assembly", "Insert")
                return result

        class AssemblyGroundWatcher(AssemblyBaseWatcher):
            """Shows 'Ground' when the active assembly has no grounded parts."""

            def __init__(self):
                super().__init__()
                self.commands = ["Assembly_ToggleGrounded"]
                self.title = translate("Assembly", "Grounding")

            def shouldShow(self):
                if not super().shouldShow():
                    return False
                return (
                    UtilsAssembly.assembly_has_at_least_n_parts(1)
                    and not UtilsAssembly.isAssemblyGrounded()
                )

        class AssemblyJointsWatcher(AssemblyBaseWatcher):
            """Shows Joint, View, and BOM tools when there are enough parts."""

            def __init__(self):
                super().__init__()
                self.commands = [
                    "Assembly_CreateJointDefault",
                    "Separator",
                    "Assembly_CreateJointFixed",
                    "Assembly_CreateJointRevolute",
                    "Assembly_CreateJointCylindrical",
                    "Assembly_CreateJointSlider",
                    "Assembly_CreateJointBall",
                    "Separator",
                    "Assembly_CreateJointDistance",
                    "Assembly_CreateJointParallel",
                    "Assembly_CreateJointPerpendicular",
                    "Assembly_CreateJointAngle",
                ]
                self.title = translate("Assembly", "Constraints")

            def shouldShow(self):
                if not super().shouldShow():
                    return False
                return UtilsAssembly.assembly_has_at_least_n_parts(2)

        class AssemblyToolsWatcher(AssemblyBaseWatcher):
            """Shows Joint, View, and BOM tools when there are enough parts."""

            def __init__(self):
                super().__init__()
                self.commands = [
                    "Assembly_CreateView",
                    "Assembly_CreateBom",
                ]
                self.title = translate("Assembly", "Tools")

            def shouldShow(self):
                if not super().shouldShow():
                    return False
                return UtilsAssembly.assembly_has_at_least_n_parts(1)

        class AssemblySimulationWatcher(AssemblyBaseWatcher):
            """Shows 'Create Simulation' when specific motional joints exist."""

            def __init__(self):
                super().__init__()
                self.commands = ["Assembly_CreateSimulation"]
                self.title = translate("Assembly", "Simulation")

            def shouldShow(self):
                if not super().shouldShow():
                    return False

                joint_types = ["Revolute", "Slider", "Cylindrical"]
                joints = UtilsAssembly.getJointsOfType(self.assembly, joint_types)
                return len(joints) > 0

        class AssemblyBodyActiveWatcher:
            """Shows sketch + Part Design feature commands when a Part Design
            body is active (replaces the empty 'Start Part / New Part' panel
            shown when the active body lives inside a linked document)."""

            def __init__(self):
                self.commands = [
                    "Assembly_BodyNewSketch",
                    "Separator",
                    "Assembly_BodyPad",
                    "Assembly_BodyPocket",
                    "Assembly_BodyRevolution",
                    "Assembly_BodyHole",
                ]
                self.title = translate("Assembly", "Part Tools")

            def shouldShow(self):
                try:
                    gd = FreeCADGui.ActiveDocument
                    if gd is None or gd.ActiveView is None:
                        return False
                    return gd.ActiveView.getActiveObject("pdbody") is not None
                except Exception:
                    return False

        watchers = [
            AssemblyCreateWatcher(),
            AssemblyInsertWatcher(),
            AssemblyGroundWatcher(),
            AssemblyJointsWatcher(),
            AssemblyToolsWatcher(),
            AssemblySimulationWatcher(),
            AssemblyBodyActiveWatcher(),
        ]
        FreeCADGui.Control.addTaskWatcher(watchers)

        # --- Timer: sync linked-assembly edit state to the parent view ---
        # When the user right-clicks a linked sub-assembly and chooses
        # "Active object", FreeCAD calls setEdit() on the link which forwards
        # it to the linked assembly's ViewProvider in its own document.
        # The parent document's view never gets setActiveObject("assembly",...)
        # automatically, so the Insert/Constraints panel never appears.
        # This timer detects that state and registers the linked assembly as
        # the active assembly in the parent view — the same way PartDesign
        # registers an active body via setActiveObject("pdbody", body).
        _sync_timer = QtCore.QTimer()
        # Tracks which tree-item label is currently bolded by us so we can
        # unbold it when the active subassembly changes.
        _bolded_label_state = {"label": None}

        def _refresh_active_subassembly_bold():
            """Bold the tree items matching the active subassembly's label.

            FreeCAD's view provider auto-bolds the object set as active via
            setActiveObject. For nested (level-2+) subassemblies the link lives
            in a sub-document and FreeCAD cannot mark it active in the root view,
            so we apply the bold styling directly via Qt.
            """
            try:
                import UtilsAssembly as _UA
                cache = getattr(_UA, "_active_asm_link_target", None)
                target_label = None
                if cache is not None:
                    try:
                        tgt_doc, tgt_obj, _linked = cache
                        link_doc = FreeCAD.getDocument(tgt_doc)
                        if link_doc is not None:
                            link_obj = link_doc.getObject(tgt_obj)
                            if link_obj is not None:
                                target_label = link_obj.Label
                    except Exception:
                        pass

                prev_label = _bolded_label_state["label"]
                # ALWAYS re-apply on every tick — FreeCAD rebuilds tree items on
                # many operations (recompute, link expansion, etc.) which silently
                # drops our bold styling. We need to keep restoring it.
                mw = FreeCADGui.getMainWindow()
                if mw is None:
                    return

                def _walk(item):
                    """Yield item and all descendants (recursive)."""
                    yield item
                    try:
                        for i in range(item.childCount()):
                            for sub in _walk(item.child(i)):
                                yield sub
                    except Exception:
                        pass

                def _all_items(tree):
                    try:
                        for i in range(tree.topLevelItemCount()):
                            for sub in _walk(tree.topLevelItem(i)):
                                yield sub
                    except Exception:
                        pass

                trees = mw.findChildren(QtGui.QTreeWidget)
                for tree in trees:
                    for item in _all_items(tree):
                        try:
                            text = item.text(0)
                            # Unbold/clear items matching the PREVIOUS active label
                            # (only when the active changed).
                            if (prev_label is not None
                                    and prev_label != target_label
                                    and text == prev_label):
                                f = item.font(0)
                                if f.bold():
                                    f.setBold(False)
                                    item.setFont(0, f)
                                item.setBackground(0, QtGui.QBrush())
                            # Bold/highlight items matching the CURRENT active label.
                            if target_label is not None and text == target_label:
                                f = item.font(0)
                                if not f.bold():
                                    f.setBold(True)
                                    item.setFont(0, f)
                                item.setBackground(
                                    0,
                                    QtGui.QBrush(QtGui.QColor(0, 160, 0, 100)),
                                )
                        except Exception:
                            pass
                _bolded_label_state["label"] = target_label
            except Exception:
                pass

        def _sync_linked_assembly():
            try:
                # ── Label clean — before any early-exit, every 200 ms ────────────
                # Handles both "name.NNN.asm" and "name.NNN.asm.FCStd" filenames.
                import re as _re2, os as _os2
                for _d in FreeCAD.listDocuments().values():
                    try:
                        _fn = getattr(_d, 'FileName', '') or ''
                        if not _fn:
                            continue
                        _basename = _os2.path.basename(_fn)
                        # Strip optional .FCStd container suffix → "1222.001.asm.FCStd" → "1222.001.asm"
                        _no_fcstd = _re2.sub(r'\.FCStd$', '', _basename, flags=_re2.IGNORECASE)
                        # Must end in an assembly/part/drawing extension to qualify
                        if not _re2.search(r'\.(prt|asm|drg)$', _no_fcstd, _re2.IGNORECASE):
                            continue
                        # Strip extension → "1222.001", then strip version → "1222"
                        _c = _re2.sub(r'\.(prt|asm|drg)$', '', _no_fcstd, flags=_re2.IGNORECASE)
                        _c = _re2.sub(r'\.\d+$', '', _c)
                        _clean = _c
                        if not _clean:
                            continue
                        for _obj in _d.Objects:
                            if _obj.isDerivedFrom('Assembly::AssemblyObject'):
                                if _obj.Label != _clean:
                                    _obj.Label = _clean
                                break
                    except Exception:
                        pass

                # ── Active-assembly / link-token sync (needs active view) ──────────
                doc = FreeCAD.ActiveDocument
                if not doc:
                    return
                gui_doc = FreeCADGui.ActiveDocument
                if not gui_doc:
                    return
                active_view = gui_doc.ActiveView
                if not active_view:
                    return

                # ── Body activation supersedes assembly activation ──────────────
                # If a Part Design body has been activated, exit any active
                # assembly so only one thing is active at a time.
                try:
                    if active_view.getActiveObject("pdbody") is not None:
                        if active_view.getActiveObject("assembly") is not None:
                            active_view.setActiveObject("assembly", None)
                        import UtilsAssembly as _UA0
                        _UA0.clearActiveAsmLinkTarget()
                        for _o in doc.Objects:
                            if _o.isDerivedFrom("Assembly::AssemblyObject"):
                                try:
                                    if _o.ViewObject.isInEditMode():
                                        gui_doc.resetEdit()
                                except Exception:
                                    pass
                        # Also clear any bold tree highlight from a prior subassembly activation
                        _refresh_active_subassembly_bold()
                        return
                except Exception:
                    pass

                # If an Assembly::AssemblyLink is cached as active (level-1 or level-2+),
                # _activate_assembly owns the setActiveObject call. Skip the edit-mode scan
                # to avoid overwriting a level-2 activation with the level-1 ancestor token.
                try:
                    import UtilsAssembly as _UA
                    cache = getattr(_UA, "_active_asm_link_target", None)
                    if cache is not None:
                        tgt_doc, tgt_obj, linked_asm = cache
                        link_doc = FreeCAD.getDocument(tgt_doc)
                        if link_doc is not None and link_doc.getObject(tgt_obj) is not None:
                            # Before honouring the cache, check whether the user has
                            # activated a DIFFERENT (root) AssemblyObject via the built-in
                            # "Active object" menu — that puts the root in edit mode.
                            # If so, the cached subassembly is no longer the active one.
                            _root_asm_active = False
                            try:
                                for _o in doc.Objects:
                                    if not _o.isDerivedFrom("Assembly::AssemblyObject"):
                                        continue
                                    if _o is linked_asm:
                                        continue  # the cached one — ignore
                                    if _o.ViewObject.isInEditMode():
                                        _root_asm_active = True
                                        break
                            except Exception:
                                pass
                            if _root_asm_active:
                                _UA._active_asm_link_target = None  # user switched away
                                # Fall through to normal active-link detection below
                            else:
                                # Cache is live — skip setActiveObject logic; just refresh bold.
                                _refresh_active_subassembly_bold()
                                return
                        else:
                            _UA._active_asm_link_target = None  # stale — clear it
                except Exception:
                    pass

                active_link_token = None
                for obj in doc.Objects:
                    # Check both App::Link and Assembly::AssemblyLink
                    if not obj.isDerivedFrom("App::Link") and not obj.isDerivedFrom("Assembly::AssemblyLink"):
                        continue
                    linked = getattr(obj, "LinkedObject", None)
                    if not linked or not linked.isDerivedFrom("Assembly::AssemblyObject"):
                        continue
                    try:
                        # Check both the link itself AND the linked assembly
                        # for edit mode — different FreeCAD builds set one or the other
                        if obj.ViewObject.isInEditMode() or linked.ViewObject.isInEditMode():
                            active_link_token = obj
                            break
                    except Exception:
                        pass

                current = active_view.getActiveObject("assembly")

                if active_link_token is not None and current is not active_link_token:
                    active_view.setActiveObject("assembly", active_link_token)
                elif active_link_token is None and current is not None:
                    # Auto-clear only App::Link tokens set by this timer via isInEditMode.
                    # Assembly::AssemblyLink tokens are registered manually by _activate_assembly
                    # (setEdit is skipped for that type) and must persist until the user
                    # explicitly activates a different assembly.
                    if current.isDerivedFrom("App::Link") and not current.isDerivedFrom("Assembly::AssemblyLink"):
                        active_view.setActiveObject("assembly", None)

                # Visual highlight for nested (level-2+) active subassembly.
                _refresh_active_subassembly_bold()

            except Exception:
                pass

        _sync_timer.timeout.connect(_sync_linked_assembly)
        _sync_timer.start(200)
        # Prevent garbage collection by storing on the workbench instance
        self._link_sync_timer = _sync_timer

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(AssemblyWorkbench())
