import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import re
import hashlib

VERSIONED_NAME_RE = re.compile(
    r"^(?P<base>.+)\.(?P<version>\d{3})\.(?P<ext>prt|asm|drg)(?:\.FCStd)?$",
    re.IGNORECASE,
)
_PARAM_GRP = "User parameter:BaseApp/Preferences/Macro/SaveVersionMacro"

# =====================================================
# CUSTOM DIALOG FOR PART NAME AND DESCRIPTION
# =====================================================

class PartNameDialog(QtGui.QDialog):
    def __init__(self):
        super(PartNameDialog, self).__init__()
        self.setWindowTitle("Add Part Information")
        self.setModal(True)
        self.resize(400, 200)

        layout = QtGui.QVBoxLayout()

        part_label = QtGui.QLabel("Part Name:")
        self.part_name_edit = QtGui.QLineEdit()
        layout.addWidget(part_label)
        layout.addWidget(self.part_name_edit)

        desc_label = QtGui.QLabel("Description:")
        self.description_edit = QtGui.QTextEdit()
        self.description_edit.setMaximumHeight(80)
        layout.addWidget(desc_label)
        layout.addWidget(self.description_edit)

        button_layout = QtGui.QHBoxLayout()
        ok_button = QtGui.QPushButton("OK")
        cancel_button = QtGui.QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_part_info(self):
        return self.part_name_edit.text().strip(), self.description_edit.toPlainText().strip()

# =====================================================
# APPLY NAME & DESCRIPTION TO FIRST BODY
# =====================================================

def apply_info_to_first_body(doc, name, description):
    """Set Label and Description on the first PartDesign::Body or root
    Assembly::AssemblyObject in the document, whichever comes first."""
    for obj in doc.Objects:
        if obj.TypeId in ('PartDesign::Body', 'Assembly::AssemblyObject'):
            obj.Label = name
            if not hasattr(obj, 'Description'):
                obj.addProperty('App::PropertyString', 'Description',
                                'Base', 'Description')
            obj.Description = description
            break  # only the first matching object

# =====================================================
# GET WORKING DIRECTORY
# =====================================================

def get_working_directory():
    param = App.ParamGet("User parameter:BaseApp/Preferences/General")
    return param.GetString("WorkingDirectory", "")

# =====================================================
# CHANGE DETECTION — external signature in user params
# =====================================================

def _param_key(file_path):
    norm = os.path.normcase(os.path.abspath(file_path)).replace("\\", "/")
    return hashlib.md5(norm.encode("utf-8")).hexdigest()


def _get_saved_sig(file_path):
    if not file_path:
        return ""
    return App.ParamGet(_PARAM_GRP).GetString(_param_key(file_path), "")


def _set_saved_sig(file_path, sig):
    if not file_path:
        return
    App.ParamGet(_PARAM_GRP).SetString(_param_key(file_path), sig)


def _compute_sig(doc):
    """Deterministic, minimal signature from stable object data only."""
    lines = []
    objects = sorted(doc.Objects, key=lambda o: o.Name)
    lines.append(f"count:{len(objects)}")

    for obj in objects:
        row = [obj.Name, obj.TypeId, obj.Label]

        # Sketch geometry / constraint counts
        if hasattr(obj, "GeometryCount"):
            try:
                row.append(f"G{obj.GeometryCount}")
            except Exception:
                pass
        if hasattr(obj, "ConstraintCount"):
            try:
                row.append(f"C{obj.ConstraintCount}")
            except Exception:
                pass

        # Stable shape metrics (Volume / Area rounded)
        if hasattr(obj, "Shape"):
            try:
                s = obj.Shape
                row.append(f"V{s.Volume:.4f}")
                row.append(f"A{s.Area:.4f}")
                bb = s.BoundBox
                row.append(f"B{bb.XLen:.4f},{bb.YLen:.4f},{bb.ZLen:.4f}")
            except Exception:
                pass

        lines.append("|".join(row))

    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


def has_document_changes(doc):
    """Compare current document state against last-saved signature."""
    current = _compute_sig(doc)
    stored = _get_saved_sig(doc.FileName)
    if not stored:
        # First time this file is checked — treat as changed
        return True
    return current != stored

# =====================================================
# DETERMINE FILE EXTENSION BASED ON DOCUMENT TYPE
# =====================================================

def get_file_extension(doc):
    has_assembly = False
    has_drawing = False

    for obj in doc.Objects:
        obj_type = obj.TypeId
        if "Assembly" in obj_type or "Link" in obj_type:
            has_assembly = True
        elif "TechDraw" in obj_type or "Drawing" in obj_type:
            has_drawing = True

    if has_drawing:
        return ".drg"
    elif has_assembly:
        return ".asm"
    else:
        return ".prt"

# =====================================================
# FILENAME HELPERS
# =====================================================

def strip_fcstd_suffix(filename):
    if filename.lower().endswith(".fcstd"):
        return filename[:-6]
    return filename


def parse_versioned_name(filename):
    bare = strip_fcstd_suffix(os.path.basename(filename))
    m = VERSIONED_NAME_RE.match(bare)
    if m:
        return m.group("base"), int(m.group("version")), "." + m.group("ext").lower()
    return None, None, None

# =====================================================
# VERSION HELPERS
# =====================================================

def get_highest_version(folder, base_name, extension):
    pattern = re.compile(
        rf"^{re.escape(base_name)}\.(\d{{3}}){re.escape(extension)}(?:\.FCStd)?$",
        re.IGNORECASE,
    )
    max_v = 0
    for f in os.listdir(folder):
        m = pattern.match(f)
        if m:
            v = int(m.group(1))
            if v > max_v:
                max_v = v
    return max_v


def check_name_exists(folder, base_name):
    for ext in (".prt", ".asm", ".drg"):
        pattern = re.compile(
            rf"^{re.escape(base_name)}\.(\d{{3}}){re.escape(ext)}(?:\.FCStd)?$",
            re.IGNORECASE,
        )
        for f in os.listdir(folder):
            if pattern.match(f):
                return True
    return False

# =====================================================
# LINKED DOCUMENT DETECTION & SAVING
# =====================================================

def get_linked_documents(doc):
    """Find all unique external documents linked from this assembly."""
    linked_docs = {}
    for obj in doc.Objects:
        # App::Link objects
        if hasattr(obj, 'LinkedObject') and obj.LinkedObject is not None:
            try:
                linked_doc = obj.LinkedObject.Document
                if linked_doc and linked_doc.Name != doc.Name:
                    linked_docs[linked_doc.Name] = linked_doc
            except Exception:
                pass
        # Other link types via getLinkedObject()
        if hasattr(obj, 'getLinkedObject'):
            try:
                linked_obj = obj.getLinkedObject()
                if linked_obj and linked_obj.Document and linked_obj.Document.Name != doc.Name:
                    linked_docs[linked_obj.Document.Name] = linked_obj.Document
            except Exception:
                pass
    return list(linked_docs.values())


def save_linked_part(linked_doc):
    """Save a linked part document with versioning.
    Returns (was_saved: bool, message: str or None).
    """
    if not linked_doc.FileName:
        return False, f"Part '{linked_doc.Label}' has no filename \u2014 save it manually first."

    if not has_document_changes(linked_doc):
        return False, None  # no changes

    folder = os.path.dirname(linked_doc.FileName)
    if not folder or not os.path.exists(folder):
        return False, f"Folder for '{linked_doc.Label}' not found."

    parsed_base, _, _ = parse_versioned_name(os.path.basename(linked_doc.FileName))
    if parsed_base:
        base_name = parsed_base
    else:
        base_name = strip_fcstd_suffix(os.path.basename(linked_doc.FileName))

    extension = get_file_extension(linked_doc)
    highest = get_highest_version(folder, base_name, extension)
    next_version = highest + 1

    new_filename = f"{base_name}.{str(next_version).zfill(3)}{extension}"
    full_path = os.path.join(folder, new_filename)

    try:
        linked_doc.saveAs(full_path)
        linked_doc.Label = base_name  # override filename-based label FreeCAD auto-assigns
        linked_doc.recompute()
        _set_saved_sig(linked_doc.FileName or full_path, _compute_sig(linked_doc))
        return True, new_filename
    except Exception as e:
        return False, f"Failed to save '{linked_doc.Label}': {str(e)}"

# =====================================================
# EMBEDDED BODY DETECTION & SAVING (parts inside asm)
# =====================================================

_BODY_SIG_GRP = "User parameter:BaseApp/Preferences/Macro/SaveVersionMacro/BodySigs"
_SUBASM_SIG_GRP = "User parameter:BaseApp/Preferences/Macro/SaveVersionMacro/SubAsmSigs"


def _body_param_key(asm_path, body_label):
    """Unique key for a body inside a specific assembly."""
    raw = f"{os.path.normcase(os.path.abspath(asm_path)).replace(chr(92), '/')}::{body_label}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _compute_body_sig(body):
    """Compute a signature for a single PartDesign::Body and its children."""
    lines = []
    # Collect the body itself + all child objects
    children = body.OutListRecursive if hasattr(body, 'OutListRecursive') else []
    objects = sorted([body] + list(children), key=lambda o: o.Name)
    lines.append(f"count:{len(objects)}")

    for obj in objects:
        row = [obj.Name, obj.TypeId, obj.Label]
        if hasattr(obj, "GeometryCount"):
            try:
                row.append(f"G{obj.GeometryCount}")
            except Exception:
                pass
        if hasattr(obj, "ConstraintCount"):
            try:
                row.append(f"C{obj.ConstraintCount}")
            except Exception:
                pass
        if hasattr(obj, "Shape"):
            try:
                s = obj.Shape
                row.append(f"V{s.Volume:.4f}")
                row.append(f"A{s.Area:.4f}")
                bb = s.BoundBox
                row.append(f"B{bb.XLen:.4f},{bb.YLen:.4f},{bb.ZLen:.4f}")
            except Exception:
                pass
        lines.append("|".join(row))

    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


def _get_saved_body_sig(asm_path, body_label):
    if not asm_path:
        return ""
    return App.ParamGet(_BODY_SIG_GRP).GetString(_body_param_key(asm_path, body_label), "")


def _set_saved_body_sig(asm_path, body_label, sig):
    if not asm_path:
        return
    App.ParamGet(_BODY_SIG_GRP).SetString(_body_param_key(asm_path, body_label), sig)


def has_body_changes(asm_path, body):
    """Check if an embedded body has changed since last save."""
    current = _compute_body_sig(body)
    stored = _get_saved_body_sig(asm_path, body.Label)
    if not stored:
        return True  # never saved — treat as changed
    return current != stored


def get_embedded_bodies(doc):
    """Find all PartDesign::Body objects embedded directly in the assembly."""
    bodies = []
    for obj in doc.Objects:
        if obj.TypeId == 'PartDesign::Body':
            # Only include bodies that belong to THIS document (not from linked external files)
            if obj.Document.Name == doc.Name:
                bodies.append(obj)
    return bodies


def save_embedded_body(doc, body, workdir):
    """Export an embedded body as a separate versioned .prt file.
    Returns (was_saved: bool, message: str or None).
    """
    base_name = body.Label
    asm_path = doc.FileName or ""

    # Check for changes
    if not has_body_changes(asm_path, body):
        return False, None  # no changes

    extension = ".prt"
    highest = get_highest_version(workdir, base_name, extension)
    next_version = highest + 1

    new_filename = f"{base_name}.{str(next_version).zfill(3)}{extension}"
    full_path = os.path.join(workdir, new_filename)

    temp_doc_name = f"_TempSave_{base_name}"
    temp_doc = None
    try:
        # Create a temporary document, copy the body into it, save, close
        temp_doc = App.newDocument(temp_doc_name)
        temp_doc.copyObject(body, True)  # True = copy with dependencies
        temp_doc.recompute()

        # Use saveCopy instead of saveAs — saveCopy does NOT change the
        # document's Name property, so closeDocument(temp_doc_name) works.
        # saveAs would rename the document internally, causing the close to
        # fail and leaving orphaned documents in the tree.
        temp_doc.saveCopy(full_path)
        App.closeDocument(temp_doc_name)
        temp_doc = None

        # Re-activate the original assembly document
        App.setActiveDocument(doc.Name)
        Gui.ActiveDocument = Gui.getDocument(doc.Name)

        # Store body signature AFTER successful save
        _set_saved_body_sig(asm_path, body.Label, _compute_body_sig(body))

        return True, new_filename
    except Exception as e:
        # Clean up temp doc on failure — try both original and current name
        if temp_doc is not None:
            for name in set([temp_doc_name, temp_doc.Name]):
                try:
                    App.closeDocument(name)
                except Exception:
                    pass
        try:
            App.setActiveDocument(doc.Name)
            Gui.ActiveDocument = Gui.getDocument(doc.Name)
        except Exception:
            pass
        return False, f"Failed to save body '{body.Label}': {str(e)}"

# =====================================================
# EMBEDDED SUB-ASSEMBLY DETECTION & SAVING
# =====================================================

def _subasm_param_key(parent_path, subasm_label):
    """Unique key for a sub-assembly inside a specific parent assembly."""
    raw = f"{os.path.normcase(os.path.abspath(parent_path)).replace(chr(92), '/')}::subasm::{subasm_label}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _compute_subasm_sig(subasm):
    """Compute a signature for an embedded sub-assembly and all its children."""
    lines = []
    children = subasm.OutListRecursive if hasattr(subasm, 'OutListRecursive') else []
    objects = sorted([subasm] + list(children), key=lambda o: o.Name)
    lines.append(f"subasm_count:{len(objects)}")

    for obj in objects:
        row = [obj.Name, obj.TypeId, obj.Label]
        if hasattr(obj, "GeometryCount"):
            try:
                row.append(f"G{obj.GeometryCount}")
            except Exception:
                pass
        if hasattr(obj, "ConstraintCount"):
            try:
                row.append(f"C{obj.ConstraintCount}")
            except Exception:
                pass
        if hasattr(obj, "Shape"):
            try:
                s = obj.Shape
                row.append(f"V{s.Volume:.4f}")
                row.append(f"A{s.Area:.4f}")
                bb = s.BoundBox
                row.append(f"B{bb.XLen:.4f},{bb.YLen:.4f},{bb.ZLen:.4f}")
            except Exception:
                pass
        if hasattr(obj, "Placement"):
            try:
                p = obj.Placement
                row.append(f"P{p.Base.x:.4f},{p.Base.y:.4f},{p.Base.z:.4f}")
            except Exception:
                pass
        # Joint property values
        if hasattr(obj, "TypeId") and "Joint" in obj.TypeId:
            for prop in obj.PropertiesList:
                try:
                    row.append(f"{prop}={getattr(obj, prop)}")
                except Exception:
                    pass
        lines.append("|".join(row))

    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


def _get_saved_subasm_sig(parent_path, subasm_label):
    if not parent_path:
        return ""
    return App.ParamGet(_SUBASM_SIG_GRP).GetString(_subasm_param_key(parent_path, subasm_label), "")


def _set_saved_subasm_sig(parent_path, subasm_label, sig):
    if not parent_path:
        return
    App.ParamGet(_SUBASM_SIG_GRP).SetString(_subasm_param_key(parent_path, subasm_label), sig)


def has_subasm_changes(parent_path, subasm):
    """Check if an embedded sub-assembly has changed since last save."""
    current = _compute_subasm_sig(subasm)
    stored = _get_saved_subasm_sig(parent_path, subasm.Label)
    if not stored:
        return True  # never saved
    return current != stored


def get_embedded_subassemblies(doc):
    """Find all Assembly::AssemblyObject objects that are children of the
    root assembly (i.e. sub-assemblies, not the root itself)."""
    root_asm = None
    all_asms = []
    for obj in doc.Objects:
        if obj.TypeId == "Assembly::AssemblyObject" and obj.Document.Name == doc.Name:
            all_asms.append(obj)

    if not all_asms:
        return []

    child_names = set()
    for asm in all_asms:
        if hasattr(asm, 'Group'):
            for child in asm.Group:
                child_names.add(child.Name)

    sub_asms = []
    for asm in all_asms:
        if asm.Name in child_names:
            sub_asms.append(asm)

    return sub_asms


def save_embedded_subassembly(doc, subasm, workdir):
    """Export an embedded sub-assembly as a separate versioned .asm file.
    Returns (was_saved: bool, message: str or None).
    """
    base_name = subasm.Label
    parent_path = doc.FileName or ""

    if not has_subasm_changes(parent_path, subasm):
        return False, None  # no changes

    extension = ".asm"
    highest = get_highest_version(workdir, base_name, extension)
    next_version = highest + 1

    new_filename = f"{base_name}.{str(next_version).zfill(3)}{extension}"
    full_path = os.path.join(workdir, new_filename)

    temp_doc_name = f"_TempSave_SubAsm_{base_name}"
    temp_doc = None
    try:
        temp_doc = App.newDocument(temp_doc_name)
        # Copy the sub-assembly with all dependencies (joints, bodies, etc.)
        temp_doc.copyObject(subasm, True)
        temp_doc.recompute()
        temp_doc.saveCopy(full_path)
        App.closeDocument(temp_doc_name)
        temp_doc = None

        # Re-activate the original document
        App.setActiveDocument(doc.Name)
        Gui.ActiveDocument = Gui.getDocument(doc.Name)

        _set_saved_subasm_sig(parent_path, subasm.Label, _compute_subasm_sig(subasm))
        return True, new_filename
    except Exception as e:
        if temp_doc is not None:
            for name in set([temp_doc_name, temp_doc.Name]):
                try:
                    App.closeDocument(name)
                except Exception:
                    pass
        try:
            App.setActiveDocument(doc.Name)
            Gui.ActiveDocument = Gui.getDocument(doc.Name)
        except Exception:
            pass
        return False, f"Failed to save sub-assembly '{subasm.Label}': {str(e)}"


# =====================================================
# ASSEMBLY-STRUCTURE vs PART CHANGE DETECTION
# =====================================================

_ASM_STRUCT_SIG_GRP = "User parameter:BaseApp/Preferences/Macro/SaveVersionMacro/AsmStructSigs"


def _compute_assembly_structure_sig(doc):
    """Signature of assembly-level objects only (joints, links, structure).
    Excludes PartDesign::Body internals and sub-assembly internals so that
    feature edits inside a part/sub-assembly do NOT register as an
    assembly-structure change."""
    # Collect body names and all their recursive children
    body_names = set()
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body":
            body_names.add(obj.Name)
            children = obj.OutListRecursive if hasattr(obj, "OutListRecursive") else []
            for child in children:
                body_names.add(child.Name)

    # Also exclude sub-assembly internals
    for subasm in get_embedded_subassemblies(doc):
        body_names.add(subasm.Name)
        children = subasm.OutListRecursive if hasattr(subasm, "OutListRecursive") else []
        for child in children:
            body_names.add(child.Name)

    lines = []
    asm_objects = sorted(
        [o for o in doc.Objects if o.Name not in body_names],
        key=lambda o: o.Name,
    )
    lines.append(f"asm_count:{len(asm_objects)}")

    for obj in asm_objects:
        row = [obj.Name, obj.TypeId, obj.Label]
        # Placement of links / positioned objects
        if hasattr(obj, "Placement"):
            try:
                p = obj.Placement
                row.append(f"P{p.Base.x:.4f},{p.Base.y:.4f},{p.Base.z:.4f}")
                q = p.Rotation.Q
                row.append(f"R{q[0]:.6f},{q[1]:.6f},{q[2]:.6f},{q[3]:.6f}")
            except Exception:
                pass
        # Joint property values
        if hasattr(obj, "TypeId") and "Joint" in obj.TypeId:
            for prop in obj.PropertiesList:
                try:
                    row.append(f"{prop}={getattr(obj, prop)}")
                except Exception:
                    pass
        lines.append("|".join(row))

    return hashlib.md5("\n".join(lines).encode("utf-8")).hexdigest()


def _get_asm_struct_sig(file_path):
    if not file_path:
        return ""
    return App.ParamGet(_ASM_STRUCT_SIG_GRP).GetString(_param_key(file_path), "")


def _set_asm_struct_sig(file_path, sig):
    if not file_path:
        return
    App.ParamGet(_ASM_STRUCT_SIG_GRP).SetString(_param_key(file_path), sig)


def has_assembly_structure_changes(doc):
    """True when something OTHER than body features changed (joints, links, ...)."""
    if not doc.FileName:
        return True
    current = _compute_assembly_structure_sig(doc)
    stored = _get_asm_struct_sig(doc.FileName)
    if not stored:
        return True
    return current != stored


# =====================================================
# HELPER: update all stored signatures for a document
# =====================================================

def _update_all_sigs(doc):
    """Refresh every stored signature so the next save detects future changes."""
    path = doc.FileName
    if not path:
        return
    _set_saved_sig(path, _compute_sig(doc))
    if get_file_extension(doc) == ".asm":
        _set_asm_struct_sig(path, _compute_assembly_structure_sig(doc))
        for body in get_embedded_bodies(doc):
            _set_saved_body_sig(path, body.Label, _compute_body_sig(body))
        for subasm in get_embedded_subassemblies(doc):
            _set_saved_subasm_sig(path, subasm.Label, _compute_subasm_sig(subasm))


# =====================================================
# MAIN SAVE FUNCTION
# =====================================================

def save_version():
    doc = App.ActiveDocument

    if not doc:
        QtGui.QMessageBox.warning(None, "Save", "No active document.")
        return

    workdir = get_working_directory()

    if not workdir or not os.path.exists(workdir):
        QtGui.QMessageBox.warning(None, "Save", "Working Directory not set.")
        return

    is_new_file = not doc.FileName

    # ==================================================================
    # NEW FILE — show name dialog, establish initial .001 filename
    # (saveAs is required here because doc.save() needs an existing path)
    # ==================================================================
    if is_new_file:
        dialog = PartNameDialog()
        if dialog.exec_() != QtGui.QDialog.Accepted:
            return

        part_name, description = dialog.get_part_info()
        if not part_name:
            QtGui.QMessageBox.warning(None, "Save", "Part name is required.")
            return
        if check_name_exists(workdir, part_name):
            QtGui.QMessageBox.critical(None, "Save",
                                       f"Name '{part_name}' already exists!")
            return

        if not hasattr(doc, "Description"):
            doc.addProperty("App::PropertyString", "Description",
                            "Base", "Part description")
        doc.Description = description
        apply_info_to_first_body(doc, part_name, description)

        extension = get_file_extension(doc)
        new_filename = f"{part_name}.001{extension}"
        full_path = os.path.join(workdir, new_filename)

        try:
            doc.recompute()
            doc.purgeTouched()
            doc.saveAs(full_path)
            doc.Label = part_name  # override filename-based label FreeCAD auto-assigns
            doc.save()  # clear modified flag (asterisk) after saveAs
            App.setActiveDocument(doc.Name)
            Gui.ActiveDocument = Gui.getDocument(doc.Name)
            _update_all_sigs(doc)
            QtGui.QMessageBox.information(None, "Save", "File saved successfully")
        except Exception as e:
            QtGui.QMessageBox.critical(None, "Save", f"Failed to save: {e}")
        return

    # ==================================================================
    # EXISTING FILE — save in place, no version bump
    # ==================================================================
    try:
        is_assembly = get_file_extension(doc) == ".asm"

        if is_assembly:
            # Save externally-linked documents in place if they have changes
            for ldoc in get_linked_documents(doc):
                if ldoc.FileName and has_document_changes(ldoc):
                    try:
                        ldoc.recompute()
                        ldoc.save()
                        _set_saved_sig(ldoc.FileName, _compute_sig(ldoc))
                    except Exception as e:
                        App.Console.PrintWarning(f"Could not save '{ldoc.Label}': {e}\n")

        doc.recompute()
        doc.purgeTouched()
        doc.save()
        _update_all_sigs(doc)
        QtGui.QMessageBox.information(None, "Save", "File saved successfully")

    except Exception as e:
        QtGui.QMessageBox.critical(None, "Save", f"Failed to save: {e}")

# =====================================================
# FREECAD COMMAND CLASS
# =====================================================

class Std_VersionSave:
    """Version Save — Standard FreeCAD Command (save in place)."""

    def GetResources(self):
        return {
            'Pixmap': 'save',
            'MenuText': 'Save',
            'Accel': 'Ctrl+S',
            'ToolTip': 'Save the active document in place.\nNew documents are saved as Name.001.ext.',
            'CmdType': 'ForEdit'
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        import os
        macro_path = os.path.join(App.getHomePath(), "Macro", "Save.FCMacro")
        if os.path.exists(macro_path):
            try:
                exec(open(macro_path, encoding="utf-8").read(), {"__name__": "__main__"})
            except Exception as e:
                App.Console.PrintError(f"BNC Save error: {e}\n")
        else:
            App.Console.PrintError(f"BNC Save: macro not found at {macro_path}\n")

try:
    Gui.addCommand('Std_VersionSave', Std_VersionSave())
except Exception:
    pass
