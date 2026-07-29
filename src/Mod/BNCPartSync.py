# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Round-trip part sync for the single-file assembly workflow.

In the BNC single-file model the assembly document is the master and each part
is an embedded PartDesign::Body. On save, every body is ALSO exported as a
versioned .prt (a snapshot) by Save.FCMacro. This module adds the REVERSE
direction so the two stay in sync BOTH ways:

  * Edit a part INSIDE the assembly  -> already live (it's embedded).
  * Edit the exported <part>.NNN.prt SEPARATELY and save it -> this module
    re-imports the updated body back into the embedded copy in any open
    assembly (and on assembly open), so the assembly updates automatically.

The re-import copies the .prt's body (with its full, still-parametric feature
tree) into the assembly document, transfers the embedded body's Placement and
group membership, re-points every reference (joints etc.) from the old body to
the new one, then removes the old body. Validated headless: fillet added in the
.prt propagates to the assembly, placement/label/group preserved, Fillet stays
editable.
"""

import os
import re
import FreeCAD as App

_PRT_RE = re.compile(r"^(?P<base>.+)\.(?P<ver>\d{3})\.prt(?:\.FCStd)?$", re.IGNORECASE)

# Guard against re-entrancy (sync opens/saves docs which fire observers again).
_in_sync = False

# Edit-order tracking: a monotonically increasing counter records the LAST time
# each document was genuinely edited (recomputed by the user, not by a sync).
# Whichever side has the higher rank is the authoritative source of a change —
# robust for UNSAVED, in-session edits (file mtimes only update on save).
_edit_seq = {}
_seq_counter = [0]


def _note_edit(doc):
    _seq_counter[0] += 1
    _edit_seq[doc.Name] = _seq_counter[0]


def _edit_rank(doc):
    return _edit_seq.get(getattr(doc, "Name", None), -1)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _embedded_bodies(doc):
    """PartDesign::Body objects that live directly in `doc` (the assembly)."""
    return [o for o in doc.Objects
            if getattr(o, "TypeId", "") == "PartDesign::Body"
            and o.Document.Name == doc.Name]


def _main_body(doc):
    """The single PartDesign::Body a .prt represents (first one)."""
    for o in doc.Objects:
        if getattr(o, "TypeId", "") == "PartDesign::Body":
            return o
    return None


def _clean_base(label):
    s = str(label or "").strip()
    s = re.sub(r"\.FCStd$", "", s, flags=re.IGNORECASE)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\.(prt|asm|drg)$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\.\d{3,}$", "", s)
    return s


def _latest_prt_path(base, workdir):
    """Newest <base>.NNN.prt.FCStd in workdir, or None."""
    if not workdir or not os.path.isdir(workdir):
        return None
    best = None
    best_v = -1
    for f in os.listdir(workdir):
        m = _PRT_RE.match(f)
        if m and _clean_base(m.group("base")).lower() == base.lower():
            v = int(m.group("ver"))
            if v > best_v:
                best_v = v
                best = os.path.join(workdir, f)
    return best


def _body_sig(body):
    """A cheap change signature for a body's resulting shape."""
    try:
        sh = body.Shape
        if sh is None or sh.isNull():
            return "null"
        return "{:.6f}|{}|{}".format(sh.Volume, len(sh.Faces), len(sh.Edges))
    except Exception:
        return "err"


# ---------------------------------------------------------------------------
# core swap (headless-validated)
# ---------------------------------------------------------------------------

def _dedupe_group_memberships(doc):
    """Rewrite every container's Group to unique, non-null members. copyObject +
    addObject on an Assembly::AssemblyObject can leave a body listed twice in a
    Group (FreeCAD then warns 'duplicate child item' and shows the part twice)."""
    for o in doc.Objects:
        if not hasattr(o, "Group"):
            continue
        try:
            grp = list(o.Group)
        except Exception:
            continue
        seen = set()
        cleaned = []
        changed = False
        for x in grp:
            nm = getattr(x, "Name", None)
            if x is None or nm in seen:
                changed = True
                continue
            seen.add(nm)
            cleaned.append(x)
        if changed:
            try:
                o.Group = cleaned
            except Exception:
                pass


def _remove_body_completely(doc, body):
    """Remove a PartDesign::Body AND everything it owns — its features
    (Pad/Pocket/Fillet), sketches, datums, and its Origin + planes/axes/point.
    Plain doc.removeObject(body) removes only the body container and ORPHANS the
    features (the stray 'Pad' bug), so we delete the whole graph, features first
    (a few passes to satisfy dependency order), then the body."""
    victims = []
    seen = set()
    for o in list(getattr(body, "Group", []) or []):
        if o is not None and o.Name not in seen:
            seen.add(o.Name); victims.append(o)
    org = getattr(body, "Origin", None)
    if org is not None:
        for o in list(getattr(org, "OutList", []) or []):
            if o is not None and o.Name not in seen:
                seen.add(o.Name); victims.append(o)
        if org.Name not in seen:
            seen.add(org.Name); victims.append(org)
    # remove features/origin (leaves) first, retrying for dependency order
    for _ in range(4):
        if not victims:
            break
        remaining = []
        for o in victims:
            try:
                if doc.getObject(o.Name) is not None:
                    doc.removeObject(o.Name)
            except Exception:
                remaining.append(o)
        victims = remaining
    # finally the body itself
    try:
        if doc.getObject(body.Name) is not None:
            doc.removeObject(body.Name)
    except Exception:
        pass


def _replace_body(target_doc, target_body, source_body):
    """Replace `target_body` (and any duplicates of it) in `target_doc` with a
    fresh copy of `source_body`, preserving Placement, group membership, label,
    MP_* metadata and all references (joints). Direction-agnostic: used for both
    part->assembly and assembly->part. Returns the new body, or None."""
    if source_body is None or target_body is None:
        return None

    base = _clean_base(target_body.Label)
    # ALL bodies representing this part — handles any pre-existing duplicates so
    # we always converge to exactly ONE body.
    old_bodies = [b for b in _embedded_bodies(target_doc)
                  if _clean_base(b.Label).lower() == base.lower()]
    if target_body not in old_bodies:
        old_bodies.append(target_body)

    template = old_bodies[0]
    old_label = template.Label
    old_placement = App.Placement(template.Placement)
    mp = {}
    for p in ("MP_PartNumber", "MP_Description", "MP_Material"):
        if hasattr(template, p):
            try:
                mp[p] = getattr(template, p)
            except Exception:
                pass
    parents = [o for o in target_doc.Objects
               if hasattr(o, "Group") and any(b in o.Group for b in old_bodies)]
    old_names = set(b.Name for b in old_bodies)

    App.setActiveTransaction("Sync part")
    try:
        new_body = target_doc.copyObject(source_body, True)  # deep copy w/ features
        new_body.Label = old_label
        try:
            new_body.Placement = old_placement
        except Exception:
            pass
        for prop, val in mp.items():
            try:
                setattr(new_body, prop, val)
            except Exception:
                pass
        for p in parents:
            try:
                if new_body not in list(p.Group):
                    p.addObject(new_body)
            except Exception:
                pass

        # Re-point every reference (joints etc.) from ANY old body to the new one
        # BEFORE deleting the old ones.
        for obj in target_doc.Objects:
            if obj is new_body:
                continue
            for prop in obj.PropertiesList:
                try:
                    val = getattr(obj, prop)
                except Exception:
                    continue
                try:
                    if getattr(val, "Name", None) in old_names:
                        setattr(obj, prop, new_body)
                    elif isinstance(val, (list, tuple)) and any(
                            getattr(x, "Name", None) in old_names for x in val):
                        setattr(obj, prop,
                                [new_body if getattr(x, "Name", None) in old_names else x
                                 for x in val])
                except Exception:
                    pass

        # Remove EVERY old body AND its whole feature tree (features, sketches,
        # origin + planes/axes) — plain removeObject(body) would orphan the Pad
        # and could leave a duplicate.
        for b in old_bodies:
            _remove_body_completely(target_doc, b)
        # Belt-and-suspenders: ensure no container lists the new body twice.
        _dedupe_group_memberships(target_doc)
        target_doc.recompute()
        _dedupe_group_memberships(target_doc)
    finally:
        App.closeActiveTransaction()

    App.Console.PrintMessage(
        "[PartSync] '{}' in '{}' updated — removed {} old, 1 new (vol {})\n".format(
            old_label, target_doc.Label, len(old_bodies), _body_sig(new_body)))
    return new_body


def sync_embedded_from_prt(asm_doc, embedded_body, prt_doc):
    """part -> assembly: replace the assembly's embedded body with the .prt's."""
    return _replace_body(asm_doc, embedded_body, _main_body(prt_doc))


# ---------------------------------------------------------------------------
# matching + public entry points
# ---------------------------------------------------------------------------

def _workdir_of(doc):
    try:
        if doc.FileName:
            return os.path.dirname(doc.FileName)
    except Exception:
        pass
    try:
        params = App.ParamGet("User parameter:BaseApp/Preferences/General")
        return params.GetString("WorkingDirectory", "").strip()
    except Exception:
        return ""


def sync_assembly_from_prts(asm_doc, force=False):
    """For each embedded body in `asm_doc`, if a NEWER <label>.NNN.prt exists,
    re-import it. A .prt is only pulled in when its file is newer than the
    assembly file — otherwise the assembly (embedded body) is the master and we
    must NOT overwrite it with a stale export. Returns count."""
    global _in_sync
    if _in_sync:
        return 0
    workdir = _workdir_of(asm_doc)
    if not workdir:
        return 0
    # Assembly file mtime — a .prt must be newer than this to win.
    try:
        asm_mtime = (os.path.getmtime(asm_doc.FileName)
                     if asm_doc.FileName and os.path.exists(asm_doc.FileName) else 0)
    except Exception:
        asm_mtime = 0
    n = 0
    _in_sync = True
    opened = []
    handled = set()
    try:
        for body in list(_embedded_bodies(asm_doc)):
            base = _clean_base(body.Label)
            if base.lower() in handled:
                continue  # one sync per part (the swap collapses duplicates)
            prt_path = _latest_prt_path(base, workdir)
            if not prt_path or not os.path.exists(prt_path):
                continue
            # Only pull a .prt that was edited AFTER the assembly was last saved.
            try:
                if not force and os.path.getmtime(prt_path) <= asm_mtime:
                    continue
            except Exception:
                pass
            # open the .prt (hidden) to compare / import
            prt_doc = None
            for d in App.listDocuments().values():
                if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(prt_path):
                    prt_doc = d
                    break
            close_after = False
            if prt_doc is None:
                try:
                    prt_doc = App.openDocument(prt_path, hidden=True)
                except TypeError:
                    prt_doc = App.openDocument(prt_path)
                close_after = True
                opened.append(prt_doc.Name)
            prt_b = _main_body(prt_doc)
            if prt_b is None:
                continue
            if not force and _body_sig(prt_b) == _body_sig(body):
                handled.add(base.lower())
                continue  # already in sync
            sync_embedded_from_prt(asm_doc, body, prt_doc)
            handled.add(base.lower())
            n += 1
    finally:
        for name in opened:
            try:
                App.closeDocument(name)
            except Exception:
                pass
        _in_sync = False
    if n:
        App.Console.PrintMessage(
            "[PartSync] synced {} part(s) into assembly '{}'\n".format(n, asm_doc.Label))
    return n


def sync_part_into_open_assemblies(prt_doc):
    """After a .prt is saved, push it into every OPEN assembly that embeds a
    body with the same base name. Returns count."""
    global _in_sync
    if _in_sync:
        return 0
    prt_b = _main_body(prt_doc)
    if prt_b is None:
        return 0
    base = _clean_base(prt_doc.Label or (
        os.path.basename(prt_doc.FileName) if prt_doc.FileName else ""))
    if not base:
        base = _clean_base(prt_b.Label)
    App.Console.PrintMessage(
        "[PartSync] push: part base='{}' sig={}\n".format(base, _body_sig(prt_b)))
    n = 0
    _in_sync = True
    try:
        for doc in list(App.listDocuments().values()):
            if doc is prt_doc:
                continue
            has_assembly = any(getattr(o, "TypeId", "") == "Assembly::AssemblyObject"
                               for o in doc.Objects)
            if not has_assembly:
                continue
            for body in _embedded_bodies(doc):
                bbase = _clean_base(body.Label)
                if bbase.lower() != base.lower():
                    App.Console.PrintMessage(
                        "[PartSync] push:   '{}' body '{}' (base '{}') != '{}' — skip\n".format(
                            doc.Label, body.Label, bbase, base))
                    continue
                if _body_sig(prt_b) == _body_sig(body):
                    App.Console.PrintMessage(
                        "[PartSync] push:   '{}' already in sync — skip\n".format(body.Label))
                    continue
                App.Console.PrintMessage(
                    "[PartSync] push:   MATCH '{}' in '{}' — syncing\n".format(
                        body.Label, doc.Label))
                sync_embedded_from_prt(doc, body, prt_doc)
                n += 1
                break  # the swap collapses ALL matching bodies — one call per doc
    finally:
        _in_sync = False
    return n


def _doc_is_modified(doc):
    try:
        import FreeCADGui as _Gui
        gd = _Gui.getDocument(doc.Name)
        return bool(gd is not None and getattr(gd, "Modified", False))
    except Exception:
        return False


def _doc_in_edit(doc):
    """True while an object in `doc` is being edited (sketch/feature open), so we
    can defer syncing until the edit closes (avoids churn mid-drag)."""
    try:
        import FreeCADGui as _Gui
        gd = _Gui.getDocument(doc.Name)
        return gd is not None and gd.getInEdit() is not None
    except Exception:
        return False


def push_assembly_to_open_parts(asm_doc):
    """assembly -> open standalone part docs: after an in-assembly edit +
    recompute, push each changed embedded body into its open part document.
    Sig-based (works for UNSAVED edits — the recomputed assembly is the
    authoritative side). Skips a part that has its own unsaved edits."""
    global _in_sync
    if _in_sync:
        return 0
    n = 0
    _in_sync = True
    try:
        parts = {}
        for d in App.listDocuments().values():
            if d is asm_doc or _is_native_assembly(d):
                continue
            pb = _main_body(d)
            if pb is None:
                continue
            b = _clean_base(d.Label or (
                os.path.basename(d.FileName) if d.FileName else pb.Label)).lower()
            parts.setdefault(b, []).append((d, pb))
        asm_rank = _edit_rank(asm_doc)
        for body in _embedded_bodies(asm_doc):
            for (pdoc, pbody) in parts.get(_clean_base(body.Label).lower(), []):
                # Only skip while the user is ACTIVELY editing the part (a sketch
                # / feature open), or if the part was edited MORE recently than
                # the assembly. Do NOT use the 'modified' flag — a prior sync
                # leaves the part modified, which would wrongly block later pushes
                # (e.g. deleting a feature in the assembly not reaching the part).
                if _doc_in_edit(pdoc):
                    continue
                if _edit_rank(pdoc) > asm_rank:
                    continue
                if _body_sig(pbody) == _body_sig(body):
                    continue
                _replace_body(pdoc, pbody, body)
                n += 1
    finally:
        _in_sync = False
    return n


def sync_prt_from_assembly(part_doc):
    """assembly -> part: when the user edited a body INSIDE the assembly, refresh
    the open standalone part document from the assembly's embedded body. Pulls
    only when the assembly file is NEWER than the part file (assembly is the
    authoritative side) and the part has NO unsaved edits — so a part-side edit
    is never clobbered. Returns count."""
    global _in_sync
    if _in_sync:
        return 0
    part_body = _main_body(part_doc)
    if part_body is None or _is_native_assembly(part_doc):
        return 0
    if _doc_is_modified(part_doc):
        return 0  # don't overwrite unsaved part edits
    base = _clean_base(part_doc.Label or (
        os.path.basename(part_doc.FileName) if part_doc.FileName else ""))
    if not base:
        base = _clean_base(part_body.Label)
    try:
        part_mtime = (os.path.getmtime(part_doc.FileName)
                      if part_doc.FileName and os.path.exists(part_doc.FileName) else 0)
    except Exception:
        part_mtime = 0
    part_rank = _edit_rank(part_doc)
    n = 0
    _in_sync = True
    try:
        for doc in list(App.listDocuments().values()):
            if doc is part_doc or not _is_native_assembly(doc):
                continue
            try:
                asm_mtime = (os.path.getmtime(doc.FileName)
                             if doc.FileName and os.path.exists(doc.FileName) else 0)
            except Exception:
                asm_mtime = 0
            asm_rank = _edit_rank(doc)
            for body in _embedded_bodies(doc):
                if _clean_base(body.Label).lower() != base.lower():
                    continue
                if _body_sig(body) == _body_sig(part_body):
                    continue  # already in sync
                # Authority: prefer in-session edit order; fall back to file mtime
                # only when neither side was edited this session.
                if asm_rank >= 0 or part_rank >= 0:
                    if asm_rank <= part_rank:
                        continue  # part edited at least as recently — don't clobber
                elif asm_mtime <= part_mtime:
                    continue
                _replace_body(part_doc, part_body, body)
                n += 1
                break
            if n:
                break
    finally:
        _in_sync = False
    return n


# ---------------------------------------------------------------------------
# observer — wires both directions automatically
# ---------------------------------------------------------------------------

_SKIP_PREFIX = ("_StepSplit_", "_TempSave_", "_exp", "_e")


def _is_native_assembly(doc):
    try:
        return any(getattr(o, "TypeId", "") == "Assembly::AssemblyObject"
                   for o in doc.Objects)
    except Exception:
        return False


def _push_from_edited_doc(doc, why):
    """`doc` was just edited (recompute or edit-dialog close) — it is the
    authoritative source; push its change to the other side."""
    try:
        if _in_sync or doc.Name.startswith(_SKIP_PREFIX):
            return 0
        _note_edit(doc)
        if _is_native_assembly(doc):
            n = push_assembly_to_open_parts(doc)
            if n:
                App.Console.PrintMessage(
                    "[PartSync] {}: pushed {} part(s) from '{}'\n".format(why, n, doc.Label))
            return n
        if _main_body(doc) is not None:
            n = sync_part_into_open_assemblies(doc)
            if n:
                App.Console.PrintMessage(
                    "[PartSync] {}: pushed part '{}' into assembly\n".format(why, doc.Label))
            return n
    except Exception as e:
        App.Console.PrintError("[PartSync] {}: {}\n".format(why, e))
    return 0


class _PartSyncGuiObserver:
    """GUI-level observer: fires when a feature/sketch EDIT DIALOG CLOSES. This
    is the reliable moment a parameter edit (e.g. Fillet radius) is finalised —
    slotRecomputedDocument can fire while the edit is still technically open and
    get skipped, so this guarantees the change propagates."""

    def slotResetEdit(self, viewObj):
        try:
            doc = viewObj.Object.Document
        except Exception:
            return
        # Defer briefly so FreeCAD finishes the post-edit recompute first.
        try:
            from PySide import QtCore
            QtCore.QTimer.singleShot(60, lambda: _push_from_edited_doc(doc, "edit-done"))
        except Exception:
            _push_from_edited_doc(doc, "edit-done")


class _PartSyncObserver:
    """After a PART's .prt is saved, push it into open assemblies; when an
    assembly is opened, pull in any NEWER .prt for its embedded parts."""

    def slotFinishSaveDocument(self, doc, filepath):
        try:
            if _in_sync or doc.Name.startswith(_SKIP_PREFIX):
                return
            is_asm = _is_native_assembly(doc)
            has_body = _main_body(doc) is not None
            App.Console.PrintMessage(
                "[PartSync] save-hook: doc='{}' label='{}' is_asm={} has_body={}\n".format(
                    doc.Name, doc.Label, is_asm, has_body))
            if is_asm:
                return  # an assembly was saved, not a part
            if not has_body:
                return  # not a PartDesign part
            n = sync_part_into_open_assemblies(doc)
            App.Console.PrintMessage("[PartSync] save-hook: synced {} assembly part(s)\n".format(n))
        except Exception as e:
            import traceback
            App.Console.PrintError("[PartSync] save-hook: {}\n{}\n".format(e, traceback.format_exc()))

    def slotRecomputedDocument(self, doc):
        # Fires on the Recompute/Refresh button AND when a feature edit closes —
        # so the change propagates WITHOUT needing a save. The recomputed doc is
        # the authoritative (just-edited) side. Deferred while an edit is open.
        try:
            if _in_sync or doc.Name.startswith(_SKIP_PREFIX):
                return
            if _doc_in_edit(doc):
                return  # mid sketch/feature edit — the edit-close hook handles it
            _push_from_edited_doc(doc, "recompute")
        except Exception as e:
            App.Console.PrintError("[PartSync] recompute-hook: {}\n".format(e))

    def slotFinishRestoreDocument(self, doc):
        self._pull(doc, "restore")

    def slotActivateDocument(self, doc):
        # Fires when the user switches to a tab — the exact moment they expect
        # the assembly to reflect any part edited since it was last saved. The
        # mtime guard in sync_assembly_from_prts makes this cheap (no .prt is
        # opened unless it is newer than the assembly file).
        self._pull(doc, "activate")

    def _pull(self, doc, why):
        try:
            if _in_sync or doc.Name.startswith(_SKIP_PREFIX):
                return
            if _is_native_assembly(doc):
                # assembly tab: pull any newer .prt into the embedded parts
                n = sync_assembly_from_prts(doc)
                if n:
                    App.Console.PrintMessage(
                        "[PartSync] {}-hook: pulled {} part(s) into '{}'\n".format(
                            why, n, doc.Label))
            elif _main_body(doc) is not None:
                # part tab: refresh the standalone part from the assembly if the
                # part was edited IN the assembly (assembly is newer).
                n = sync_prt_from_assembly(doc)
                if n:
                    App.Console.PrintMessage(
                        "[PartSync] {}-hook: refreshed part '{}' from assembly\n".format(
                            why, doc.Label))
        except Exception as e:
            App.Console.PrintError("[PartSync] {}-hook: {}\n".format(why, e))


def install_part_sync():
    if getattr(App, "_bnc_part_sync_installed", False):
        return
    try:
        App.addDocumentObserver(_PartSyncObserver())
        try:
            import FreeCADGui as _Gui
            _Gui.addDocumentObserver(_PartSyncGuiObserver())
        except Exception as _ge:
            App.Console.PrintError("[PartSync] gui-observer install failed: {}\n".format(_ge))
        App._bnc_part_sync_installed = True
        App.Console.PrintMessage("[PartSync] round-trip observer installed\n")
    except Exception as e:
        App.Console.PrintError("[PartSync] install failed: {}\n".format(e))


if App.GuiUp:
    install_part_sync()
