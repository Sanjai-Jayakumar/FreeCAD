# SPDX-License-Identifier: LGPL-2.1-or-later
# ANVIL CAD: Make Projection Group views freely movable.
#
# FreeCAD's core TechDraw C++ (DrawProjGroup::addProjection) locks the
# anchor ("Front") view of every Projection Group — it sets LockPosition
# True and marks the property ReadOnly, so the user cannot drag it.
# ANVIL CAD wants ProjGroup views (incl. exploded pictorials placed via a
# ProjGroup) to behave like any other view: freely draggable.
#
# Rather than patch/recompile the C++, this installs a document observer
# that clears the lock. Verified details against the TechDraw C++ source:
#
#  1) Refresh gap — ViewProviderDrawingView::updateData() only re-applies
#     the Qt "movable" flag on an X/Y change, NOT on a LockPosition change.
#     So after clearing LockPosition we nudge X to force updateView(true).
#
#  2) Two trigger paths, handled differently:
#       - Fresh creation: catch the lock the instant it is set
#         (slotChangedObject) and clear it SYNCHRONOUSLY — deferred timers
#         raced against the creation dialog closing.
#       - Opened/recovered docs: slotCreatedObject is unreliable, so also
#         sweep on slotFinishRestoreDocument / slotCreatedDocument, with a
#         few timed retries to beat GUI page-build timing.
#
# Safe because ANVIL CAD defaults AutoDistribute OFF (AutoDist=0), so
# DrawProjGroup::execute() never repositions/re-locks the views.
#
# Debug log: %TEMP%\bnc_projgroup_unlock.log

import os
import FreeCAD

_PROJITEM_TIDS = ("TechDraw::DrawProjGroupItem", "TechDraw::DrawViewPart")
_LOG_PATH = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                         "bnc_projgroup_unlock.log")


def _log(msg):
    try:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (ts, msg))
    except Exception:
        pass


def _in_projgroup(obj):
    try:
        return any(p.TypeId == "TechDraw::DrawProjGroup" for p in obj.InList)
    except Exception:
        return False


def _refresh_movable_flag(obj):
    """updateData() only calls updateView() on an X/Y change, so nudge X to
    force the QGIView to re-read isLocked() and update ItemIsMovable."""
    try:
        x = obj.X.Value
    except Exception:
        try:
            x = float(obj.X)
        except Exception:
            return
    try:
        obj.X = x + 0.001
        obj.X = x
    except Exception:
        pass


def _unlock_one(obj, why):
    try:
        if obj.TypeId not in _PROJITEM_TIDS:
            return
        if not _in_projgroup(obj):
            return
        if "LockPosition" not in obj.PropertiesList:
            return
        locked_before = bool(obj.LockPosition)
        try:
            obj.setEditorMode("LockPosition", 0)
        except Exception:
            pass
        if obj.LockPosition:
            obj.LockPosition = False
        _refresh_movable_flag(obj)
        _log("unlock_one(%s) %s: was_locked=%s now=%s" %
             (why, obj.Name, locked_before, bool(obj.LockPosition)))
    except Exception as e:
        _log("unlock_one ERROR on %r: %s" % (getattr(obj, 'Name', '?'), e))


def _unlock_doc(doc, why):
    if doc is None:
        return
    try:
        objs = list(doc.Objects)
    except Exception:
        return
    n = 0
    for obj in objs:
        try:
            if obj.TypeId in _PROJITEM_TIDS and _in_projgroup(obj):
                _unlock_one(obj, why)
                n += 1
        except Exception:
            pass
    _log("unlock_doc(%s) doc=%s scanned, %d projgroup views" %
         (why, getattr(doc, 'Name', '?'), n))


# ── deferred sweep (GC-safe) for the restore path ──────────────────────
_pending = set()


def _run_pending():
    names = list(_pending)
    _pending.clear()
    for name in names:
        try:
            doc = FreeCAD.getDocument(name)
        except Exception:
            doc = None
        _unlock_doc(doc, "deferred")


def _schedule_unlock(doc):
    if doc is None:
        return
    try:
        _pending.add(doc.Name)
    except Exception:
        return
    try:
        from PySide import QtCore
        for delay in (0, 300, 900, 1800):
            QtCore.QTimer.singleShot(delay, _run_pending)
    except Exception:
        _run_pending()


class _ProjGroupUnlockObserver:
    def slotChangedObject(self, obj, prop):
        # Fresh-creation path: the instant the C++ sets LockPosition True on
        # a ProjGroup view, clear it synchronously (deferred raced the dialog).
        try:
            if prop != "LockPosition":
                return
            if obj.TypeId not in _PROJITEM_TIDS:
                return
            if obj.LockPosition and _in_projgroup(obj):
                _log("slotChangedObject: %s LockPosition->True, clearing" % obj.Name)
                _unlock_one(obj, "changed")
        except Exception as e:
            _log("slotChangedObject ERROR: %s" % e)

    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId == "TechDraw::DrawProjGroup" or obj.TypeId in _PROJITEM_TIDS:
                _log("slotCreatedObject: %s (%s)" % (obj.Name, obj.TypeId))
                _schedule_unlock(obj.Document)
        except Exception:
            pass

    def slotFinishRestoreDocument(self, doc):
        _log("slotFinishRestoreDocument: %s" % getattr(doc, 'Name', '?'))
        _schedule_unlock(doc)

    def slotCreatedDocument(self, doc):
        _log("slotCreatedDocument: %s" % getattr(doc, 'Name', '?'))
        _schedule_unlock(doc)


_observer = _ProjGroupUnlockObserver()


def install():
    try:
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            f.write("=== BNCUnlockProjGroupViews install ===\n")
    except Exception:
        pass
    FreeCAD.addDocumentObserver(_observer)
    try:
        for doc in FreeCAD.listDocuments().values():
            _schedule_unlock(doc)
    except Exception:
        pass
    _log("observer installed")
    FreeCAD.Console.PrintLog(
        "ANVIL CAD: ProjGroup view unlock observer installed\n")


install()
