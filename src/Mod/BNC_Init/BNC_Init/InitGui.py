import FreeCAD
import sys
import os
import importlib.util

# ── Register BNC icon overrides before any icons are cached ───────────────────
# FreeCAD registers Qt resource paths (:/icons/, :/Icons/) at startup via
# addPath(), so addIconPath() appends AFTER them — Qt resources always win.
# We must INSERT at index 0 so our file-system path is searched FIRST.
try:
    from PySide.QtCore import QDir
    _icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    if os.path.isdir(_icons_dir):
        _paths = QDir.searchPaths("icons")
        _paths.insert(0, _icons_dir)
        QDir.setSearchPaths("icons", _paths)
except Exception:
    pass

# ── ANVIL CAD version — single source of truth: Start/UpdateChecker.py ─────────
# Load CURRENT_VERSION directly from UpdateChecker.py so that bumping the
# version in that one file is all that is ever needed.
def _read_bnc_version():
    try:
        _path = os.path.join(FreeCAD.getHomePath(), "Mod", "Start", "UpdateChecker.py")
        _spec = importlib.util.spec_from_file_location("_bnc_update_checker", _path)
        _mod  = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return _mod.CURRENT_VERSION
    except Exception:
        return "1.1.2"   # fallback if file is missing

_BNC_VERSION = _read_bnc_version()
_BNC_TITLE   = f"ANVIL CAD {_BNC_VERSION}"

# Patch mConfig so getNameWithVersion() returns the right version for all
# future title updates (document open/close, etc.).
try:
    _major, _minor, _patch = _BNC_VERSION.split(".")
    FreeCAD.ConfigSet("BuildVersionMajor", _major)
    FreeCAD.ConfigSet("BuildVersionMinor", _minor)
    FreeCAD.ConfigSet("BuildVersionPoint", _patch)
except Exception:
    pass

# The title bar was already rendered before this module loaded, so push the
# corrected title directly to the main window now.
def _apply_title():
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
        if mw:
            mw.setWindowTitle(_BNC_TITLE)
        else:
            try:
                from PySide.QtCore import QTimer
            except ImportError:
                from PySide2.QtCore import QTimer
            QTimer.singleShot(200, _apply_title)
    except Exception:
        pass

_apply_title()

# ── Tessellation quality — prevent coarse triangulation on complex shapes ─────
# FreeCAD's default mesh deviation (0.5 %) makes Additive Pipe and other swept
# solids look faceted/collapsed.  Two fixes are needed:
#   1. Global preference — affects new objects created after this runs.
#   2. Per-object ViewObject.Deviation — existing .prt files have per-object
#      values stored that override the preference. We force-update every object
#      in every open document and hook into documentOpened for future opens.

def _apply_tessellation(doc=None):
    """Set high-quality tessellation on all objects in one or all documents."""
    try:
        docs = [doc] if doc else list(FreeCAD.listDocuments().values())
        for d in docs:
            if d is None:
                continue
            for obj in d.Objects:
                try:
                    vobj = obj.ViewObject
                    if hasattr(vobj, "Deviation") and vobj.Deviation > 0.15:
                        vobj.Deviation = 0.1
                    if hasattr(vobj, "AngularDeflection") and \
                            vobj.AngularDeflection > 15.0:
                        vobj.AngularDeflection = 10.0
                except Exception:
                    pass
    except Exception:
        pass

try:
    _pp = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Part")
    if _pp.GetFloat("MeshDeviation", 0.5) > 0.15:
        _pp.SetFloat("MeshDeviation", 0.1)
    if _pp.GetFloat("MeshAngularDeflection", 28.65) > 15.0:
        _pp.SetFloat("MeshAngularDeflection", 10.0)
except Exception:
    pass

# Apply to all already-open documents now
_apply_tessellation()

# Re-apply whenever a document is opened (handles newly opened .prt/.asm files)
try:
    import FreeCADGui as _FGui

    def _fix_obj_tess(obj):
        """Apply tessellation quality to a single object."""
        try:
            vobj = obj.ViewObject
            if hasattr(vobj, "Deviation") and vobj.Deviation > 0.15:
                vobj.Deviation = 0.1
            if hasattr(vobj, "AngularDeflection") and vobj.AngularDeflection > 15.0:
                vobj.AngularDeflection = 10.0
        except Exception:
            pass

    class _TessObserver:
        def slotActivatedDocument(self, doc):
            # Apply to all objects when switching to a document
            _apply_tessellation(doc)

        def slotChangedObject(self, doc, obj):
            # Fires when any object is recomputed (new Pad, Pipe, Fillet, etc.)
            # Immediately correct tessellation on the just-computed feature.
            _fix_obj_tess(obj)

        def slotCreatedDocument(self, doc):  pass
        def slotDeletedDocument(self, doc):  pass
        def slotRelabelDocument(self, doc):  pass

    _tess_obs = _TessObserver()
    _FGui.addDocumentObserver(_tess_obs)
except Exception:
    pass

# ── Add Mod directory to path so BNC_MacroSetup is importable
_mod_dir = os.path.join(FreeCAD.getHomePath(), "Mod")
if _mod_dir not in sys.path:
    sys.path.append(_mod_dir)

try:
    import BNC_MacroSetup
except Exception as e:
    FreeCAD.Console.PrintError("ANVIL CAD initialization error: " + str(e) + "\n")
