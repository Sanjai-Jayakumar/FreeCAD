"""
ANVIL CAD Macro Setup

Binds the BNC file-operation keyboard shortcuts and auto-runs the Selection
Filter widget on startup.

IMPORTANT: the BNC macros live ONLY in the application macro directory
(<FreeCAD home>/Macro), NOT in the user macro directory. That keeps the user's
"Execute Macro" list clean — only macros the USER creates show up there. The
toolbar buttons and the shortcuts below run the BNC macros straight from the
app macro dir by file path, so they work without polluting the user list.
"""

import os
import re
import FreeCAD
import FreeCADGui

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:                       # PySide2 fallback
    from PySide2 import QtCore, QtGui, QtWidgets

# QAction moved from QtWidgets (PySide2/Qt5) to QtGui (PySide6/Qt6).
QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction

_MACRO_DIR = os.path.join(FreeCAD.getHomePath(), "Macro")

# macro file -> (accelerator, label, native commands whose shortcut to release
# so the BNC macro owns the key — prevents a Qt "ambiguous shortcut" clash).
_SHORTCUTS = [
    ("SetWorkingDirectory.FCMacro", "Ctrl+Shift+W", "BNC Set Working Directory", []),
    ("New_File.FCMacro",            "Ctrl+N",       "BNC New File",   ["Std_New"]),
    ("Save.FCMacro",                "Ctrl+S",       "BNC Save",       ["Std_Save"]),
    ("Save_As.FCMacro",             "Ctrl+Shift+S", "BNC Save As",    ["Std_SaveAs"]),
    ("OPEN_File.FCMacro",           "Ctrl+O",       "BNC Open File",  ["Std_Open"]),
]

# keep references so the QActions are not garbage-collected
_bnc_actions = []


def _run_macro_file(path):
    """Execute a macro file in a fresh __main__ namespace (like the toolbar buttons)."""
    try:
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), path, "exec"), {"__name__": "__main__"})
    except Exception as exc:
        import traceback
        FreeCAD.Console.PrintError(
            "BNC macro error (%s): %s\n" % (os.path.basename(path), exc))
        FreeCAD.Console.PrintError(traceback.format_exc())


def _clear_native_shortcut(mw, accel):
    """Release `accel` from any existing QAction so the BNC action owns it
    (avoids Qt ambiguous-shortcut, which would disable the key entirely)."""
    try:
        seq = QtGui.QKeySequence(accel)
        for act in mw.findChildren(QAction):
            try:
                if act in _bnc_actions:
                    continue
                for sc in act.shortcuts():
                    if sc == seq:
                        act.setShortcuts([])
                        break
            except Exception:
                pass
    except Exception:
        pass


def setup_bnc_shortcuts():
    mw = FreeCADGui.getMainWindow()
    if mw is None or not os.path.isdir(_MACRO_DIR):
        return
    sc_param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Shortcut")
    for macro, accel, label, clear_cmds in _SHORTCUTS:
        path = os.path.join(_MACRO_DIR, macro)
        if not os.path.isfile(path):
            continue
        # release the key from native commands (persistent param)
        for cmd in clear_cmds:
            try:
                sc_param.SetString(cmd, "")
            except Exception:
                pass
        # drop the stale MacroPath-based execute shortcut (the macro is no
        # longer in the user macro dir, so that command no longer exists)
        try:
            sc_param.RemString("Std_DlgMacroExecute_" + macro)
        except Exception:
            pass
        # release the key from any live native action this session
        _clear_native_shortcut(mw, accel)

        act = QAction(label, mw)
        act.setShortcut(QtGui.QKeySequence(accel))
        act.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        act.triggered.connect(lambda checked=False, p=path: _run_macro_file(p))
        mw.addAction(act)
        _bnc_actions.append(act)


# ---------------------------------------------------------------------------
# FIRST-BODY NAMING OBSERVER
#
# Guarantees the first PartDesign::Body (for a part) or the root
# Assembly::AssemblyObject (for an assembly) is labelled to match the file's
# clean name — so the tree shows "<PartName>" instead of the generic "Body".
#
# This fires on EVERY save (native toolbar button, File menu, keyboard, or the
# BNC Save/Save As macros), so the body name stays in sync no matter how the
# user saves. It runs in slotStartSaveDocument, BEFORE the file is written, so
# the saved file already carries the correct label.
# ---------------------------------------------------------------------------

def _clean_base_from_path(filepath):
    """Derive the clean model name from a (possibly versioned) file path.

    Handles both conventions used by the BNC macros:
        Name.001.FCStd            (Save As macro — no logical ext)
        Name.001.prt.FCStd        (Save macro — .prt/.asm/.drg logical ext)
    Returns '' if nothing sensible can be derived.
    """
    base = os.path.basename(str(filepath or ""))
    base = re.sub(r"\.FCStd$", "", base, flags=re.IGNORECASE)   # strip .FCStd
    # Strip logical-ext and version suffixes REPEATEDLY so compounded names like
    # '123.001.001.asm' collapse fully to '123' (a single pass left '123.001').
    prev = None
    while prev != base:
        prev = base
        base = re.sub(r"\.(prt|asm|drg)$", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\.\d{3,}$", "", base)
    return base.strip()


def _rename_first_body_to(doc, clean):
    """Set the first Body / root Assembly label to `clean` (best-effort)."""
    if not clean:
        return
    try:
        # Temp docs created during fan-out / part export must never be touched.
        if doc.Name.startswith(("_StepSplit_", "_TempSave_")):
            return

        # Keep the DOCUMENT label clean too (the tab/tree title). The version
        # lives only in the filename on disk; the displayed label should be the
        # clean base so it never shows '123.001.001'. Also, any save path that
        # derives its version from doc.Label then reads a clean base and can't
        # compound.
        try:
            if doc.Label != clean:
                doc.Label = clean
        except Exception:
            pass

        asms = [o for o in doc.Objects
                if o.TypeId == "Assembly::AssemblyObject"
                and o.Document.Name == doc.Name]
        if asms:
            # Root assembly = the one not held inside another assembly's Group.
            child_names = set()
            for a in asms:
                for c in getattr(a, "Group", []):
                    child_names.add(c.Name)
            root = next((a for a in asms if a.Name not in child_names), asms[0])
            if root.Label != clean:
                root.Label = clean
            return

        bodies = [o for o in doc.Objects
                  if o.TypeId == "PartDesign::Body"
                  and o.Document.Name == doc.Name]
        # Only auto-name when there is exactly one body (an unambiguous part).
        if len(bodies) == 1 and bodies[0].Label != clean:
            bodies[0].Label = clean
    except Exception:
        pass


class _BNCFirstBodyNamer:
    """Document observer that keeps the first body named after the file."""

    def slotStartSaveDocument(self, doc, filepath):
        _rename_first_body_to(doc, _clean_base_from_path(filepath))


def install_body_namer():
    if getattr(FreeCAD, "_bnc_body_namer_installed", False):
        return
    try:
        FreeCAD.addDocumentObserver(_BNCFirstBodyNamer())
        FreeCAD._bnc_body_namer_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC body-namer install failed: %s\n" % exc)


# ---------------------------------------------------------------------------
# AUTO-REMOVE REDUNDANT HORIZONTAL/VERTICAL AFTER A SYMMETRY CONSTRAINT
#
# When the user adds a Symmetry constraint that makes some Horizontal/Vertical
# constraints redundant (e.g. making a rectangle symmetric about the axes), the
# symmetry already implies those H/V — so this deletes exactly the H/V
# constraints FreeCAD itself flagged as redundant, keeping the symmetry.
#
# Safety rules (never break a sketch):
#   * Only deletes constraints that are BOTH (a) flagged redundant by the solver
#     and (b) of type Horizontal or Vertical. Never coincidences, symmetry,
#     dimensions, or anything else.
#   * Skips sketches that are conflicting/malformed (not ours to fix).
#   * Wrapped in one transaction → a single Ctrl+Z undoes the whole cleanup.
#   * If the geometry degenerates after removal, the transaction is aborted
#     (rolled back) so the sketch is left exactly as the user had it.
#   * Runs deferred (QTimer) after the symmetry command fully completes.
# ---------------------------------------------------------------------------

class _BNCSymmetryHVCleaner:

    def __init__(self):
        self._busy = False
        self._counts = {}

    def slotChangedObject(self, obj, prop):
        if self._busy:
            return
        try:
            if getattr(obj, "TypeId", "") != "Sketcher::SketchObject":
                return
            if prop != "Constraints":
                return
            cons = obj.Constraints
            key = obj.Document.Name + "#" + obj.Name
            prev = self._counts.get(key, 0)
            cur = len(cons)
            self._counts[key] = cur
            if cur <= prev:
                return
            # Only react when the change ADDED a Symmetric constraint.
            if not any(c.Type == "Symmetric" for c in cons[prev:cur]):
                return
        except Exception:
            return

        self._busy = True
        try:
            from PySide.QtCore import QTimer
            QTimer.singleShot(0, lambda o=obj, k=key: self._clean(o, k))
        except Exception:
            # No event loop (headless): run inline.
            self._clean(obj, key)

    def _clean(self, obj, key):
        try:
            # RedundantConstraints is populated by the GUI's last solve. Do NOT
            # call solve() ourselves — that can move under-constrained geometry.
            red = list(getattr(obj, "RedundantConstraints", []) or [])
            if not red:
                return
            # Never touch a sketch the solver considers broken.
            if (list(getattr(obj, "ConflictingConstraints", []) or [])
                    or list(getattr(obj, "MalformedConstraints", []) or [])):
                return
            cons = obj.Constraints
            # RedundantConstraints is 1-based; delConstraint is 0-based.
            hv = sorted({r - 1 for r in red
                         if 0 <= r - 1 < len(cons)
                         and cons[r - 1].Type in ("Horizontal", "Vertical")},
                        reverse=True)
            if not hv:
                return

            App = FreeCAD
            App.setActiveTransaction("Auto-remove redundant H/V")
            for i in hv:
                try:
                    obj.delConstraint(i)
                except Exception:
                    pass

            # Degenerate-geometry guard: if the shape collapsed, roll back so the
            # user keeps their (redundant but intact) sketch.
            bad = False
            try:
                obj.Document.recompute()
                shp = getattr(obj, "Shape", None)
                if shp is None or not shp.isValid() or shp.BoundBox.DiagonalLength < 1e-6:
                    bad = True
            except Exception:
                bad = True

            if bad:
                App.closeActiveTransaction(True)   # abort → undo
            else:
                App.closeActiveTransaction()
        except Exception:
            try:
                FreeCAD.closeActiveTransaction(True)
            except Exception:
                pass
        finally:
            self._busy = False
            try:
                self._counts[key] = len(obj.Constraints)
            except Exception:
                pass


def install_symmetry_hv_cleaner():
    if getattr(FreeCAD, "_bnc_sym_hv_cleaner_installed", False):
        return
    try:
        FreeCAD.addDocumentObserver(_BNCSymmetryHVCleaner())
        FreeCAD._bnc_sym_hv_cleaner_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC symmetry-cleaner install failed: %s\n" % exc)


# ---------------------------------------------------------------------------
# RELABEL "New Body" -> "New Part"
#
# The PartDesign "New Body" command (compiled string in CommandBody.cpp) is what
# the empty-document "Start Part" panel and the Part Design menu both show. We
# rename its shared QAction at runtime so the panel/menu read "New Part" without
# rebuilding FreeCAD. The action is created when the PartDesign workbench first
# loads, so a light watchdog retries until it exists, then stops.
# ---------------------------------------------------------------------------

_BODY_CMD_NAME = "PartDesign_Body"
_BODY_NEW_TEXT = "New Part"
_BODY_NEW_TIP = "Creates a new part and activates it"


def _relabel_body_command():
    """Rename the PartDesign_Body action to 'New Part'. Returns True if done."""
    mw = FreeCADGui.getMainWindow()
    if mw is None:
        return False
    for act in mw.findChildren(QAction):
        try:
            if act.objectName() == _BODY_CMD_NAME:
                if act.text() != _BODY_NEW_TEXT:
                    act.setText(_BODY_NEW_TEXT)
                    act.setToolTip(_BODY_NEW_TIP)
                    act.setStatusTip(_BODY_NEW_TIP)
                return True
        except Exception:
            pass
    return False


def install_body_label_patch():
    """Watchdog: relabel the command once its action exists, then stop."""
    try:
        if _relabel_body_command():
            return  # already present — done in one shot
        timer = QtCore.QTimer(FreeCADGui.getMainWindow())
        timer.setInterval(1500)

        def _tick():
            if _relabel_body_command():
                timer.stop()

        timer.timeout.connect(_tick)
        timer.start()
        _bnc_actions.append(timer)   # keep a reference alive
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC body-label patch failed: %s\n" % exc)


def auto_run_selection_filter():
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            return
        setattr(mw, '_sel_filter_auto_run', True)
        macro_path = os.path.join(_MACRO_DIR, "SelectionFilter.FCMacro")
        if os.path.exists(macro_path):
            with open(macro_path, encoding="utf-8") as f:
                exec(f.read(), {"__name__": "__main__"})
        setattr(mw, '_sel_filter_auto_run', False)
    except Exception as e:
        import traceback
        FreeCAD.Console.PrintError("Failed to load Selection Filter: " + str(e) + "\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


# ---------------------------------------------------------------------------
# THIN EDGE LINES
#
# FreeCAD draws object edges at width 2 by default, which looks heavy. Set the
# global default to 1 (thin) AND re-thin objects as documents are opened, so
# existing parts (saved with width 2) also render with thin edges.
# ---------------------------------------------------------------------------

_THIN_EDGE_WIDTH = 1.0


def _apply_thin_edges(doc):
    try:
        for obj in doc.Objects:
            vo = getattr(obj, "ViewObject", None)
            if vo is None or not hasattr(vo, "LineWidth"):
                continue
            try:
                if vo.LineWidth != _THIN_EDGE_WIDTH:
                    vo.LineWidth = _THIN_EDGE_WIDTH
            except Exception:
                pass
    except Exception:
        pass


class _BNCThinEdges:
    """Document observer: apply thin edge line width when a document opens."""

    def slotFinishRestoreDocument(self, doc):
        _apply_thin_edges(doc)


def install_thin_edges():
    if getattr(FreeCAD, "_bnc_thin_edges_installed", False):
        return
    try:
        # Global default width for newly created objects.
        FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/View").SetInt(
            "DefaultShapeLineWidth", int(_THIN_EDGE_WIDTH))
        FreeCAD.addDocumentObserver(_BNCThinEdges())
        # Re-thin any already-open documents.
        for d in FreeCAD.listDocuments().values():
            _apply_thin_edges(d)
        FreeCAD._bnc_thin_edges_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC thin-edges install failed: %s\n" % exc)


class _BNCSheetMetalTouchFixer:
    """Sheet Metal base/wall features are PartDesign-type features. As an
    assembly component in FreeCAD 1.1 they can remain 'Touched' after a
    recompute (the solver keeps nudging the component), which spams
    'still touched after recompute' and keeps the document perpetually dirty /
    re-recomputing. The geometry is already computed at that point, so we clear
    the stray flag on Sheet Metal features (and the App::Part / Body holding
    them) once the recompute has finished."""

    @staticmethod
    def _is_sheetmetal(obj):
        try:
            p = getattr(obj, "Proxy", None)
            if p is not None and type(p).__name__.startswith("SM"):
                return True
            for c in (getattr(obj, "Group", None) or []):
                cp = getattr(c, "Proxy", None)
                if cp is not None and type(cp).__name__.startswith("SM"):
                    return True
        except Exception:
            pass
        return False

    _busy = False

    def slotRecomputedDocument(self, doc):
        # Re-entrancy guard: never let purgeTouched trigger a nested recompute
        # that loops back into this slot (which would hang the GUI).
        if _BNCSheetMetalTouchFixer._busy:
            return
        _BNCSheetMetalTouchFixer._busy = True
        try:
            for o in doc.Objects:
                try:
                    if "Touched" in o.State and self._is_sheetmetal(o):
                        o.purgeTouched()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            _BNCSheetMetalTouchFixer._busy = False


def install_sheetmetal_touch_fix():
    if getattr(FreeCAD, "_bnc_sm_touch_fix_installed", False):
        return
    try:
        FreeCAD.addDocumentObserver(_BNCSheetMetalTouchFixer())
        FreeCAD._bnc_sm_touch_fix_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError(
            "BNC sheet-metal touch-fix install failed: %s\n" % exc)


# ---------------------------------------------------------------------------
# CUSTOM TREE ICONS  (App::Part containers)
#
# An App::Part's tree icon comes from the compiled C++ ViewProviderPart, which
# is hard-locked to Geofeaturegroup.svg / Geoassembly.svg — a Python view
# provider proxy cannot override it (App::PartPython is not exported). To give
# BNC "sheet-metal part" containers their own icon we tag the App::Part with a
# hidden BNC_TreeIcon property and paint the icon straight onto its tree
# QTreeWidgetItem. FreeCAD re-sets item icons on status changes, so a light
# watchdog timer keeps ours applied — it re-paints ONLY when FreeCAD has
# overwritten the icon (cacheKey compare), so it is a near-free no-op otherwise.
# ---------------------------------------------------------------------------

_TREE_ICON_PROP = "BNC_TreeIcon"
_tree_icon_cache = {}   # icon path -> QIcon


def _resolve_tree_icon(token):
    """Map a BNC_TreeIcon token (or literal path) to an absolute icon file."""
    if not token:
        return None
    if token == "SheetMetal":
        p = os.path.normpath(os.path.join(
            FreeCAD.getHomePath(), "Mod", "Start", "Resources",
            "icons", "SheetMetalPart.svg"))
        return p if os.path.isfile(p) else None
    return token if os.path.isfile(token) else None


def _marked_tree_icons():
    """{label: icon_path} for every open object carrying BNC_TreeIcon."""
    result = {}
    try:
        for doc in FreeCAD.listDocuments().values():
            for obj in doc.Objects:
                path = _resolve_tree_icon(getattr(obj, _TREE_ICON_PROP, None))
                if path:
                    result[obj.Label] = path
    except Exception:
        pass
    return result


def _paint_item(item, targets, depth, budget):
    """Recursively re-paint custom icons on an item and its children. BOUNDED by
    depth and a shared item budget so a deep/cyclic tree can never hang the GUI."""
    if depth > 40 or budget[0] <= 0:
        return
    budget[0] -= 1
    try:
        path = targets.get(item.text(0))
        if path:
            icon = _tree_icon_cache.get(path)
            if icon is None:
                icon = QtGui.QIcon(path)
                _tree_icon_cache[path] = icon
            # Only set when FreeCAD has overwritten our icon (avoid churn).
            if item.icon(0).cacheKey() != icon.cacheKey():
                item.setIcon(0, icon)
    except Exception:
        pass
    try:
        for i in range(item.childCount()):
            if budget[0] <= 0:
                break
            _paint_item(item.child(i), targets, depth + 1, budget)
    except Exception:
        pass


def _apply_tree_icons():
    """Re-paint custom icons on matching tree items. Cheap no-op when none.
    Re-entrancy-guarded and item-budgeted so one tick is always bounded."""
    if getattr(_apply_tree_icons, "_busy", False):
        return
    try:
        targets = _marked_tree_icons()
        if not targets:
            return
        mw = FreeCADGui.getMainWindow()
        if mw is None:
            return
        _apply_tree_icons._busy = True
        for tree in mw.findChildren(QtWidgets.QTreeWidget):
            budget = [3000]   # max items touched per tree per tick
            for i in range(tree.topLevelItemCount()):
                if budget[0] <= 0:
                    break
                _paint_item(tree.topLevelItem(i), targets, 0, budget)
    except Exception:
        pass
    finally:
        _apply_tree_icons._busy = False


def install_tree_icons():
    if getattr(FreeCAD, "_bnc_tree_icons_installed", False):
        return
    try:
        timer = QtCore.QTimer(FreeCADGui.getMainWindow())
        timer.setInterval(800)
        timer.timeout.connect(_apply_tree_icons)
        timer.start()
        _bnc_actions.append(timer)   # keep a reference alive
        FreeCAD._bnc_tree_icons_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC tree-icon patch failed: %s\n" % exc)


# ---------------------------------------------------------------------------
# PREFERENCES GROUP RENAME  ("TechDraw" -> "Drawing")
#
# The Preferences category label is a C++ QObject::tr("TechDraw") baked into
# the group tree, so it can't be changed by config. Instead of a global
# translator (which crashed startup), a lightweight event filter renames just
# that one tree item WHEN the Preferences dialog is shown. Installed AFTER
# startup so it can never block the app from opening.
# ---------------------------------------------------------------------------

def _rename_pref_group(dialog):
    try:
        renamed = False
        for tree in dialog.findChildren(QtWidgets.QTreeView, "groupsTreeView"):
            model = tree.model()
            if model is None:
                continue
            for row in range(model.rowCount()):
                idx = model.index(row, 0)
                txt = idx.data()
                if txt is not None and "TechDraw" in str(txt):
                    model.setData(idx, str(txt).replace("TechDraw", "Drawing"))
                    renamed = True
        if renamed:
            FreeCAD.Console.PrintLog("BNC: renamed TechDraw preferences group to Drawing\n")
    except Exception:
        pass


def _is_pref_dialog(obj):
    try:
        cls = obj.metaObject().className()
    except Exception:
        cls = ""
    if "DlgPreferences" in cls:
        return True
    try:
        if obj.objectName() == "DlgPreferences":
            return True
    except Exception:
        pass
    # structural fallback, but only for dialogs so the filter stays cheap
    try:
        if isinstance(obj, QtWidgets.QDialog):
            return obj.findChild(QtWidgets.QTreeView, "groupsTreeView") is not None
    except Exception:
        pass
    return False


class _BNCPrefRenamer(QtCore.QObject):
    """Renames the TechDraw preferences group to Drawing when the dialog opens."""

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Show and _is_pref_dialog(obj):
                QtCore.QTimer.singleShot(60, lambda d=obj: _rename_pref_group(d))
        except Exception:
            pass
        return False


def install_pref_renamer():
    if getattr(FreeCAD, "_bnc_pref_renamer_installed", False):
        return
    try:
        app = QtWidgets.QApplication.instance()
        if app is None:
            QtCore.QTimer.singleShot(1000, install_pref_renamer)
            return
        FreeCAD._bnc_pref_renamer = _BNCPrefRenamer()
        app.installEventFilter(FreeCAD._bnc_pref_renamer)
        FreeCAD._bnc_pref_renamer_installed = True
    except Exception as exc:
        FreeCAD.Console.PrintError("BNC pref renamer install failed: %s\n" % exc)


try:
    # The body-namer observer needs no GUI — install it immediately so it is
    # active for the very first save of the session.
    install_body_namer()
    install_symmetry_hv_cleaner()
    install_thin_edges()
    # DISABLED: the sheet-metal touch-fix observer runs on every recompute and
    # could re-enter via purgeTouched, hanging the GUI. The "still touched after
    # recompute" it targeted is only a cosmetic warning. Re-enable only if the
    # re-entrancy guard is proven safe.
    # install_sheetmetal_touch_fix()
    # Deferred so a failure here can never prevent the app from opening.
    QtCore.QTimer.singleShot(3000, install_pref_renamer)
    # Round-trip part sync (edit .prt separately -> assembly updates). Install
    # here too (belt-and-suspenders alongside the BNC_Init import) so the
    # observer is guaranteed active this session.
    try:
        import BNCPartSync
        BNCPartSync.install_part_sync()
    except Exception as _e:
        FreeCAD.Console.PrintError("BNC part-sync install failed: %s\n" % _e)
    # Delay until the main window + native command actions exist, so clearing
    # the native shortcuts and registering ours takes effect this session.
    QtCore.QTimer.singleShot(1500, setup_bnc_shortcuts)
    QtCore.QTimer.singleShot(2000, auto_run_selection_filter)
    QtCore.QTimer.singleShot(2500, install_body_label_patch)
    # DISABLED PERMANENTLY: the tree-icon watchdog hangs the GUI even when bounded
    # (setIcon on FreeCAD tree items from a timer deadlocks with FreeCAD's own
    # tree updates). App::Part tree icons cannot be customised this way — a C++
    # patch would be required. Sheet-metal parts keep the default container icon.
    # QtCore.QTimer.singleShot(2800, install_tree_icons)
except Exception as e:
    import traceback
    FreeCAD.Console.PrintError("BNC Macro setup failed: " + str(e) + "\n")
    FreeCAD.Console.PrintError(traceback.format_exc())
