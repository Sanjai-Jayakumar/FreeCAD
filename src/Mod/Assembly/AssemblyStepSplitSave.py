# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Fan-out save for STEP-imported assemblies.

When the user opens a STEP file in FreeCAD it is loaded as a single document
containing a tree of App::Part containers and Part::Feature shapes. The
standard File > Save writes only that single .FCStd file. This module hooks
the save so that, in addition, every App::Part container at any depth is
written as a versioned .asm file and every leaf Part::Feature is written as
a versioned .prt file, all in the same directory as the saved assembly.

Naming follows the convention used by D:\\Macro\\Save.FCMacro:
    {Label}.{NNN}.{ext}      e.g.   WHEEL_1.001.prt, GUSSET_2.001.prt

The fan-out only fires for documents that look like a STEP import (have
App::Part containers but no native Assembly::AssemblyObject), so it does
not interfere with native FreeCAD assemblies.
"""

import os
import re
import FreeCAD as App


VERSIONED_NAME_RE = re.compile(
    r"^(?P<base>.+)\.(?P<version>\d{3})\.(?P<ext>prt|asm|drg)(?:\.FCStd)?$",
    re.IGNORECASE,
)

_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|]+')

# Re-entrancy guard: temp documents we open during fan-out also trigger the
# observer (saveCopy fires the save slots). This flag suppresses recursion.
_in_fanout = False


# ---------------------------------------------------------------------------
# Filename / version helpers (mirror Save.FCMacro)
# ---------------------------------------------------------------------------

def _strip_fcstd(name):
    if name.lower().endswith(".fcstd"):
        return name[:-6]
    return name


def _sanitize(label):
    s = _INVALID_FN_CHARS.sub("_", str(label)).strip()
    return s or "Unnamed"


def _highest_version(folder, base, ext):
    pat = re.compile(
        r"^" + re.escape(base) + r"\.(\d{3})" + re.escape(ext) + r"(?:\.FCStd)?$",
        re.IGNORECASE,
    )
    mx = 0
    try:
        for f in os.listdir(folder):
            m = pat.match(f)
            if m:
                v = int(m.group(1))
                if v > mx:
                    mx = v
    except Exception:
        pass
    return mx


# ---------------------------------------------------------------------------
# Tree walking
# ---------------------------------------------------------------------------

_SKIP_TYPES = {
    "App::Origin",
    "App::Plane",
    "App::Line",
    "App::OriginFeature",
    "App::LocalCoordinateSystem",
}


def _is_part_container(obj):
    """Containers that group child parts/sub-assemblies and have a Group
    property we can walk. Covers the App::Part used by STEP imports and the
    Assembly::AssemblyObject created by the Assembly workbench."""
    tid = getattr(obj, "TypeId", "")
    if tid == "App::Part":
        return True
    try:
        if obj.isDerivedFrom("Assembly::AssemblyObject"):
            return True
    except Exception:
        pass
    return False


def _is_link(obj):
    tid = getattr(obj, "TypeId", "")
    return tid in ("App::Link", "App::LinkGroup", "App::LinkElement")


def _resolve_link(obj):
    """Follow App::Link chains to the underlying object (one document only)."""
    seen = set()
    while _is_link(obj) and obj.Name not in seen:
        seen.add(obj.Name)
        linked = getattr(obj, "LinkedObject", None)
        if linked is None or linked is obj:
            break
        obj = linked
    return obj


def _children_of(container):
    if hasattr(container, "Group"):
        try:
            return [c for c in container.Group if c is not None]
        except Exception:
            return []
    return []


def _is_body(obj):
    """A PartDesign::Body — exported as a .prt (its own leaf part). In the
    single-file (Creo-style) workflow, parts are modelled as bodies living
    directly in the assembly document, so each Body is a standalone part."""
    try:
        if obj.isDerivedFrom("PartDesign::Body"):
            return True
    except Exception:
        pass
    return getattr(obj, "TypeId", "") == "PartDesign::Body"


def _is_leaf_shape(obj):
    """A Part::Feature (or subclass) that should be exported as a .prt."""
    tid = getattr(obj, "TypeId", "")
    if tid in _SKIP_TYPES:
        return False
    if tid in ("App::Part", "Assembly::AssemblyObject", "PartDesign::Body"):
        return False
    try:
        if obj.isDerivedFrom("Part::Feature"):
            return True
    except Exception:
        pass
    return False


def _looks_like_step_import(doc):
    """True ONLY for a pure STEP import: has App::Part containers but NO native
    Assembly::AssemblyObject.

    Native (BNC) assemblies are split into .asm/.prt by the BNC Save macro
    (Save.FCMacro) with change-detection and versioning. If this observer ALSO
    split them, every save would produce duplicate/extra files (e.g. 432.001.prt
    AND 432.002.prt). So we explicitly SKIP any doc that has an
    Assembly::AssemblyObject and let the Save macro own the split."""
    has_app_part = False
    for o in doc.Objects:
        try:
            if o.isDerivedFrom("Assembly::AssemblyObject") or \
               getattr(o, "TypeId", "") == "Assembly::AssemblyObject":
                return False  # native assembly — handled by the Save macro
        except Exception:
            pass
        if getattr(o, "TypeId", "") == "App::Part":
            has_app_part = True
    return has_app_part


def _root_containers(doc):
    """Top-level container objects (not held by another container's Group)."""
    owned = set()
    for obj in doc.Objects:
        if _is_part_container(obj):
            for child in _children_of(obj):
                owned.add(child.Name)
    return [o for o in doc.Objects if _is_part_container(o) and o.Name not in owned]


# ---------------------------------------------------------------------------
# Saving a single sub-tree
# ---------------------------------------------------------------------------

def _save_object_as(obj, folder, ext, log):
    """Copy obj (with deps) to a hidden temp doc and saveCopy as a versioned file."""
    base = _sanitize(obj.Label)
    nxt = _highest_version(folder, base, ext) + 1
    fname = "{0}.{1:03d}{2}".format(base, nxt, ext)
    full = os.path.join(folder, fname)

    # Hidden temp doc, unique-ish name
    tmp_name = "_StepSplit_{0}_{1}".format(re.sub(r'\W+', '_', base), nxt)
    tmp = None
    try:
        try:
            tmp = App.newDocument(tmp_name, hidden=True)
        except TypeError:
            # Older FreeCAD API: no `hidden` kwarg
            tmp = App.newDocument(tmp_name)
        tmp.copyObject(obj, True)  # copy with full dependency tree
        tmp.recompute()
        tmp.saveCopy(full)
        App.closeDocument(tmp.Name)
        tmp = None
        log["saved"].append(fname)
    except Exception as e:
        if tmp is not None:
            try:
                App.closeDocument(tmp.Name)
            except Exception:
                pass
        log["errors"].append("{0}: {1}".format(obj.Label, e))


def _walk_and_save(node, folder, log, visited):
    real = _resolve_link(node)
    key = real.Name
    if key in visited:
        return
    visited.add(key)

    if _is_part_container(real):
        _save_object_as(real, folder, ".asm", log)
        for child in _children_of(real):
            _walk_and_save(child, folder, log, visited)
    elif _is_body(real):
        # A PartDesign::Body is a standalone part → .prt. Do NOT recurse into
        # its features (Sketch/Pad/…) — they belong to the body.
        _save_object_as(real, folder, ".prt", log)
    elif _is_leaf_shape(real):
        _save_object_as(real, folder, ".prt", log)


# ---------------------------------------------------------------------------
# Top-level fan-out
# ---------------------------------------------------------------------------

def _fanout(doc):
    saved_path = getattr(doc, "FileName", "") or ""
    App.Console.PrintMessage(
        "[StepSplitSave] save observed: doc='{0}' file='{1}'\n".format(
            doc.Name, saved_path
        )
    )
    if not saved_path:
        return
    folder = os.path.dirname(saved_path)
    if not folder or not os.path.isdir(folder):
        return
    if not _looks_like_step_import(doc):
        App.Console.PrintMessage(
            "[StepSplitSave] no App::Part / Assembly container in doc — skipping\n"
        )
        return

    roots = _root_containers(doc)
    if not roots:
        App.Console.PrintMessage("[StepSplitSave] no root container — skipping\n")
        return
    App.Console.PrintMessage(
        "[StepSplitSave] roots: {0}\n".format([r.Label for r in roots])
    )

    log = {"saved": [], "errors": []}
    visited = set()

    # The root containers themselves represent the "main assembly" — already
    # saved by FreeCAD as part of the .FCStd. Fan out their CHILDREN only.
    for root in roots:
        for child in _children_of(root):
            _walk_and_save(child, folder, log, visited)

    # Restore the original document as active (closing temp docs may have shifted it)
    try:
        App.setActiveDocument(doc.Name)
        try:
            import FreeCADGui as Gui
            Gui.ActiveDocument = Gui.getDocument(doc.Name)
        except Exception:
            pass
    except Exception:
        pass

    if log["saved"]:
        App.Console.PrintMessage(
            "[StepSplitSave] {0} part/sub-assembly file(s) written to {1}\n"
            .format(len(log["saved"]), folder)
        )
        for f in log["saved"]:
            App.Console.PrintMessage("    " + f + "\n")
    if log["errors"]:
        for e in log["errors"]:
            App.Console.PrintError("[StepSplitSave] " + e + "\n")


# ---------------------------------------------------------------------------
# Document observer
# ---------------------------------------------------------------------------

def _handle_save(doc):
    global _in_fanout
    if _in_fanout:
        return
    try:
        if doc.Name.startswith("_StepSplit_"):
            return
    except Exception:
        return
    try:
        _in_fanout = True
        _fanout(doc)
    except Exception as e:
        try:
            App.Console.PrintError(
                "[StepSplitSave] Fan-out failed: {0}\n".format(e)
            )
        except Exception:
            pass
    finally:
        _in_fanout = False


class _StepSplitObserver:
    """Fires after a document is saved. FreeCAD 1.1 uses
    slotFinishSaveDocument(doc, filepath); older builds may use a 1-arg
    slotSavedDocument(doc). Implementing both keeps the hook portable."""

    def slotFinishSaveDocument(self, doc, filepath):
        _handle_save(doc)

    def slotSavedDocument(self, doc):
        _handle_save(doc)


# Guard against duplicate registration if this module is re-imported.
if not getattr(App, "_step_split_observer_installed", False):
    _step_split_observer = _StepSplitObserver()
    App.addDocumentObserver(_step_split_observer)
    App._step_split_observer_installed = True
    App.Console.PrintMessage("[StepSplitSave] Observer installed\n")
