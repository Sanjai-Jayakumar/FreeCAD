import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui
import os
import re
import zipfile
import json

_RENAME_MAP_FILE = os.path.join(App.getUserAppDataDir(), '.rename_map.json')


def _write_rename_entry(old_name, new_name):
    """Append an old_name -> new_name entry to the shared rename-map file."""
    data = {}
    if os.path.exists(_RENAME_MAP_FILE):
        try:
            with open(_RENAME_MAP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[old_name] = new_name
    with open(_RENAME_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _is_root_assembly(obj):
    """Return True if obj is the top-level (root) Assembly in the document."""
    if obj.TypeId != 'Assembly::AssemblyObject':
        return False
    # A root assembly has no parent that is also an Assembly
    for parent in obj.InList:
        if parent.TypeId == 'Assembly::AssemblyObject':
            return False          # it's nested -> sub-assembly
    return True


def _immediate_parent_assembly(obj):
    """Return the Assembly::AssemblyObject that directly contains obj (the
    immediate parent -- a sub-assembly when the part lives inside one), or
    None if obj is only held by the document root. Prefers a true Group
    containment match before falling back to any assembly in the InList."""
    for parent in getattr(obj, 'InList', []):
        if parent.TypeId == 'Assembly::AssemblyObject' and obj in getattr(parent, 'Group', []):
            return parent
    for parent in getattr(obj, 'InList', []):
        if parent.TypeId == 'Assembly::AssemblyObject':
            return parent
    return None


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
            if hasattr(obj, 'MP_Description'):
                obj.MP_Description = description
            break  # only the first matching object


def _read_obj_description(obj):
    """Effective description of a Body/Assembly object, matching the priority
    the Model Parameters macro uses: plain .Description first, then the
    MP_Description property (Model Parameters stores the value there)."""
    if hasattr(obj, "Description") and obj.Description:
        return obj.Description
    if hasattr(obj, "MP_Description") and obj.MP_Description:
        return obj.MP_Description
    return ""


def _effective_description(container_doc):
    """Description to pre-fill in the Rename dialog. Reads the first
    Body/Assembly object (where Model Parameters writes MP_Description) before
    falling back to the document-level Description / Comment, so a description
    entered via Model Parameters shows up here too."""
    for obj in container_doc.Objects:
        if obj.TypeId in ('PartDesign::Body', 'Assembly::AssemblyObject'):
            d = _read_obj_description(obj)
            if d:
                return d
            break  # only the first matching object
    # Model Parameters stores MP_Description on the DOCUMENT when it is run
    # with nothing selected (get_target() falls back to App.ActiveDocument).
    if hasattr(container_doc, "MP_Description") and container_doc.MP_Description:
        return container_doc.MP_Description
    if hasattr(container_doc, "Description") and container_doc.Description:
        return container_doc.Description
    if hasattr(container_doc, "Comment") and container_doc.Comment:
        return container_doc.Comment
    return ""


def main():
    # ============================================================
    # VALIDATE ACTIVE DOCUMENT
    # ============================================================

    doc = App.ActiveDocument
    if not doc:
        QtGui.QMessageBox.warning(None, "Error", "No Active Document.")
        return

    # ============================================================
    # DETERMINE TARGET: INTERNAL OBJECT / LINKED COMPONENT / TOP-LEVEL
    # ============================================================
    # rename_mode:
    #   "document" -- rename the top-level document (file on disk)
    #   "linked"   -- rename an externally-linked part/sub-assembly file
    #   "internal" -- rename a Body/Part created inside the current assembly
    # ============================================================

    rename_mode = "document"
    target_doc = doc
    parent_doc = None
    link_obj = None
    selected_obj = None

    # Types that should NOT be offered for rename (utility objects)
    _SKIP_TYPES = {
        'App::Origin',
        'App::Line',
        'App::Plane',
        'Assembly::JointGroup',
    }

    sel = Gui.Selection.getSelection()
    if sel:
        obj = sel[0]

        # --- Case 1: App::Link pointing to an external document ----------
        if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
            linked = obj.LinkedObject
            if hasattr(linked, "Document") and linked.Document != doc:
                rename_mode = "linked"
                target_doc = linked.Document
                parent_doc = doc
                link_obj = obj

        # --- Case 2: Internal object inside the assembly -----------------
        #     (bodies, sub-assemblies, etc. -- but NOT the root assembly
        #      or utility objects like Origin, Joints, etc.)
        if rename_mode == "document" and obj.TypeId not in _SKIP_TYPES:
            # Skip the root assembly -- that falls through to document rename
            if not _is_root_assembly(obj):
                # Verify an assembly exists in this document (we're inside an asm)
                has_assembly = any(
                    o.TypeId == 'Assembly::AssemblyObject' for o in doc.Objects
                )
                if has_assembly:
                    rename_mode = "internal"
                    selected_obj = obj

    # ============================================================
    # GATHER CURRENT NAME / DESCRIPTION BASED ON MODE
    # ============================================================

    if rename_mode == "internal":
        # Internal object -- work with Label and Description property
        base_name = selected_obj.Label
        current_desc = _read_obj_description(selected_obj)
        logical_ext = None  # not applicable
        file_saved = True   # parent doc is used for save context

    elif rename_mode == "linked":
        file_saved = bool(target_doc.FileName)
        if file_saved:
            file_path = str(target_doc.FileName)
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)

            pattern = r"^(.*)\.(\d{3})\.(prt|asm|drg)\.FCStd$"
            match = re.match(pattern, filename)
            if not match:
                QtGui.QMessageBox.warning(
                    None, "Invalid Format",
                    "File name must follow format:\nBaseName.001.prt.FCStd"
                )
                return

            base_name = match.group(1)
            logical_ext = match.group(3)
        else:
            base_name = target_doc.Name if target_doc.Name else "Untitled"
            logical_ext = "prt"

        current_desc = _effective_description(target_doc)

    else:  # "document"
        file_saved = bool(doc.FileName)
        target_doc = doc
        if file_saved:
            file_path = str(doc.FileName)
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)

            pattern = r"^(.*)\.(\d{3})\.(prt|asm|drg)\.FCStd$"
            match = re.match(pattern, filename)
            if not match:
                QtGui.QMessageBox.warning(
                    None, "Invalid Format",
                    "File name must follow format:\nBaseName.001.prt.FCStd"
                )
                return

            base_name = match.group(1)
            logical_ext = match.group(3)
        else:
            base_name = doc.Name if doc.Name else "Untitled"
            logical_ext = "prt"

        current_desc = _effective_description(doc)

    # ============================================================
    # CREATE PROFESSIONAL DIALOG
    # ============================================================

    dialog = QtGui.QDialog()
    if rename_mode == "internal":
        _is_sub_asm = selected_obj.TypeId == 'Assembly::AssemblyObject'
        dialog.setWindowTitle("Rename Sub Assembly" if _is_sub_asm else "Rename Part")
    elif rename_mode == "linked":
        kind = "Assembly" if logical_ext == "asm" else "Part"
        dialog.setWindowTitle(f"Rename {kind}")
    else:
        dialog.setWindowTitle("Rename Model")
    dialog.setMinimumWidth(450)

    main_layout = QtGui.QVBoxLayout(dialog)
    main_layout.setSpacing(12)

    # ------------------------------
    # MODEL INFORMATION GROUP
    # ------------------------------
    info_group = QtGui.QGroupBox("Model Information")
    info_layout = QtGui.QFormLayout()

    current_name_label = QtGui.QLabel(base_name)
    current_desc_label = QtGui.QLabel(current_desc if current_desc else "-")

    info_layout.addRow("Name:", current_name_label)
    info_layout.addRow("Description:", current_desc_label)

    if rename_mode == "internal":
        _type_text = "Sub Assembly" if selected_obj.TypeId == 'Assembly::AssemblyObject' else selected_obj.TypeId.split("::")[-1]
        type_label = QtGui.QLabel(_type_text)
        info_layout.addRow("Type:", type_label)
        # Show the immediate containing assembly (the sub-assembly when the part
        # lives inside one), not just the top-level document file.
        _parent_asm = _immediate_parent_assembly(selected_obj)
        if _parent_asm is not None:
            asm_file = _parent_asm.Label
        else:
            asm_file = os.path.basename(str(doc.FileName)) if doc.FileName else doc.Name
        info_layout.addRow("Parent Assembly:", QtGui.QLabel(asm_file))

    elif rename_mode == "linked":
        kind_label = QtGui.QLabel(logical_ext.upper())
        info_layout.addRow("Type:", kind_label)
        parent_label = QtGui.QLabel(
            os.path.basename(str(parent_doc.FileName)) if parent_doc.FileName else parent_doc.Name
        )
        info_layout.addRow("Parent Assembly:", parent_label)

    info_group.setLayout(info_layout)
    main_layout.addWidget(info_group)

    # ------------------------------
    # EDIT DETAILS GROUP
    # ------------------------------
    edit_group = QtGui.QGroupBox("Edit Details")
    edit_layout = QtGui.QFormLayout()

    name_edit = QtGui.QLineEdit()
    name_edit.setText(base_name)

    desc_edit = QtGui.QLineEdit()
    desc_edit.setText(current_desc)

    edit_layout.addRow("New Name:", name_edit)
    edit_layout.addRow("New Description:", desc_edit)

    # File type selector -- only when saving an unsaved document
    type_combo = QtGui.QComboBox()
    type_combo.addItems(["prt", "asm", "drg"])
    if rename_mode == "document" and not file_saved:
        type_combo.setCurrentIndex(type_combo.findText(logical_ext))
        edit_layout.addRow("File Type:", type_combo)

    edit_group.setLayout(edit_layout)
    main_layout.addWidget(edit_group)

    # ------------------------------
    # BUTTONS
    # ------------------------------
    buttons = QtGui.QDialogButtonBox(
        QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
    )
    main_layout.addWidget(buttons)

    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    if dialog.exec_() != QtGui.QDialog.Accepted:
        return

    new_name = name_edit.text().strip()
    new_desc = desc_edit.text().strip()
    new_type = type_combo.currentText()

    # ============================================================
    # VALIDATION
    # ============================================================

    if not re.match(r"^[A-Za-z0-9_]+$", new_name):
        QtGui.QMessageBox.warning(
            None,
            "Invalid Name",
            "Only letters, numbers and underscore allowed."
        )
        return

    # ================================================================
    #   MODE: INTERNAL OBJECT  (Body / Part inside assembly)
    # ================================================================

    if rename_mode == "internal":
        # Check for duplicate label inside the same assembly
        for o in doc.Objects:
            if o != selected_obj and o.Label == new_name:
                QtGui.QMessageBox.warning(
                    None, "Duplicate Name",
                    f"An object named '{new_name}' already exists in this assembly."
                )
                return

        selected_obj.Label = new_name

        # Set or create Description property
        if hasattr(selected_obj, "Description"):
            selected_obj.Description = new_desc
        elif new_desc:
            selected_obj.addProperty(
                "App::PropertyString", "Description", "Base", "Part description"
            )
            selected_obj.Description = new_desc

        # Sync Model Parameters properties
        if hasattr(selected_obj, "MP_PartNumber"):
            selected_obj.MP_PartNumber = new_name
        if hasattr(selected_obj, "MP_Description"):
            selected_obj.MP_Description = new_desc

        doc.recompute()
        doc.save()

        if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
            Gui.ActiveDocument.ActiveView.fitAll()

        _success_kind = "Sub Assembly" if selected_obj.TypeId == 'Assembly::AssemblyObject' else "Part"
        QtGui.QMessageBox.information(
            None,
            "Rename Successful",
            f"{_success_kind} Rename Successful!\n\n"
            f"New Name: {new_name}\n"
            f"New Description: {new_desc if new_desc else '-'}"
        )
        # Done -- skip the file-rename logic below
        return

    # ================================================================
    #   MODE: DOCUMENT / LINKED  (file rename on disk)
    # ================================================================

    # ================================================================
    #   NAME UNCHANGED  ->  DESCRIPTION-ONLY UPDATE (no file rename)
    # ================================================================
    # If the user only edited the description (the name is identical to
    # the current one) there is nothing to rename on disk. Skip the whole
    # close / os.rename / XML-patch / strip-Group-prefixes / reopen
    # sequence -- that sequence is only meant for an actual filename
    # change and is destructive for assemblies (it rewrites the Group
    # link values and reopens the document, which was dropping the root
    # Assembly object out of the model tree). Just update the Description
    # in place and report an update -- not a rename.
    if new_name == base_name and file_saved:
        if hasattr(target_doc, "Description"):
            target_doc.Description = new_desc
        apply_info_to_first_body(target_doc, new_name, new_desc)
        if hasattr(target_doc, "MP_PartNumber"):
            target_doc.MP_PartNumber = new_name
        if hasattr(target_doc, "MP_Description"):
            target_doc.MP_Description = new_desc

        target_doc.recompute()
        target_doc.purgeTouched()
        try:
            target_doc.save()
        except Exception:
            pass

        if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
            Gui.ActiveDocument.ActiveView.fitAll()

        QtGui.QMessageBox.information(
            None,
            "Details Updated",
            "Description Updated!\n\n"
            f"Name: {new_name} (unchanged)\n"
            f"New Description: {new_desc if new_desc else '-'}"
        )
        return

    # ============================================================
    # HANDLE UNSAVED FILE -- RENAME FIRST, THEN SAVE
    # ============================================================

    if not file_saved:
        directory = QtGui.QFileDialog.getExistingDirectory(
            None, "Select Save Directory", os.path.expanduser("~")
        )
        if not directory:
            return

        new_filename = f"{new_name}.001.{new_type}.FCStd"
        new_full_path = os.path.join(directory, new_filename)

        if os.path.exists(new_full_path):
            QtGui.QMessageBox.warning(
                None,
                "File Exists",
                f"File already exists:\n{new_filename}"
            )
            return

        # Update description before saving
        if hasattr(target_doc, "Description"):
            target_doc.Description = new_desc

        # Apply name & description to first body
        apply_info_to_first_body(target_doc, new_name, new_desc)

        # Sync Model Parameters properties
        if hasattr(target_doc, "MP_PartNumber"):
            target_doc.MP_PartNumber = new_name
        if hasattr(target_doc, "MP_Description"):
            target_doc.MP_Description = new_desc

        target_doc.saveAs(new_full_path)
        target_doc.recompute()
        Gui.ActiveDocument.ActiveView.fitAll()

        QtGui.QMessageBox.information(
            None,
            "Rename Successful",
            f"Rename Successful!\n\n"
            f"New Name: {new_name}\n"
            f"New Description: {new_desc if new_desc else '-'}\n"
            f"Saved to: {new_full_path}"
        )
        return  # Stop here for unsaved files

    # ============================================================
    # FIND ALL VERSIONS (saved file path)
    # Only the LATEST version is renamed to new_name.001.
    # Older versions stay under the old name as archived history.
    # This ensures version numbering restarts from .001 after a rename.
    # ============================================================

    files = os.listdir(directory)
    version_files = []

    for f in files:
        m = re.match(rf"^{re.escape(base_name)}\.(\d{{3}})\.{re.escape(logical_ext)}\.FCStd$", f)
        if m:
            ver_num = int(m.group(1))
            old_full = os.path.join(directory, f)
            version_files.append((ver_num, old_full))

    if not version_files:
        QtGui.QMessageBox.warning(None, "Error", "No version files found.")
        return

    # Sort ascending and take only the latest version
    version_files.sort(key=lambda x: x[0])
    _latest_ver_num, latest_old_path = version_files[-1]

    new_filename_001 = f"{new_name}.001.{logical_ext}.FCStd"
    new_full_001 = os.path.join(directory, new_filename_001)
    rename_list = [(latest_old_path, new_full_001, "001")]

    # ============================================================
    # CHECK TARGET FILE DOESN'T ALREADY EXIST
    # ============================================================

    for old_path, new_path, ver in rename_list:
        if old_path != new_path and os.path.exists(new_path):
            QtGui.QMessageBox.warning(
                None,
                "File Exists",
                f"Target file already exists:\n{os.path.basename(new_path)}\n\n"
                f"A file with the name '{new_name}' already has a version history."
            )
            return

    # ============================================================
    # UPDATE LINK LABELS IN ALL OPEN REFERENCING ASSEMBLIES
    # Do this BEFORE closing anything — target_doc is still alive so
    # LinkedObject resolution works reliably.
    # ============================================================

    def _update_link_labels_in_doc(asm_doc):
        """Rename every App::Link (and embedded object) in asm_doc whose
        label matches base_name and whose LinkedObject lives in target_doc."""
        for obj in asm_doc.Objects:
            # Case 1 — App::Link or similar: linked object is in the part doc
            lo = getattr(obj, 'LinkedObject', None)
            if lo is not None:
                lo_doc = getattr(lo, 'Document', None)
                if lo_doc is not None and lo_doc.Name == target_doc.Name:
                    obj.Label = new_name
                    continue
            # Case 2 — embedded Body or sub-assembly with matching old label
            if (obj.TypeId in ('PartDesign::Body', 'Assembly::AssemblyObject')
                    and obj.Document.Name == asm_doc.Name
                    and obj.Label == base_name):
                obj.Label = new_name

    def _fcstd_contains_name(fpath, search_name):
        """Return True if the FCStd zip's Document.xml mentions search_name."""
        try:
            with zipfile.ZipFile(fpath, 'r') as zf:
                if 'Document.xml' not in zf.namelist():
                    return False
                xml = zf.read('Document.xml').decode('utf-8', errors='replace')
                return search_name in xml
        except Exception:
            return False

    def _patch_fcstd_xml(fpath, fname_map):
        """Rewrite ALL xml entries inside the FCStd zip, replacing every key in
        fname_map with its value (bytes-level replacement of filename strings).
        FreeCAD stores XLink references in both Document.xml and GuiDocument.xml,
        so we patch every *.xml file in the archive.
        Works on the file in-place via a temp file + atomic replace.
        Returns True if any replacement was made, False otherwise.
        """
        tmp_path = fpath + '.patch_tmp'
        total_replacements = 0
        try:
            with zipfile.ZipFile(fpath, 'r') as zin:
                with zipfile.ZipFile(tmp_path, 'w',
                                     compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        data = zin.read(item.filename)
                        # Patch every XML file in the archive
                        if item.filename.lower().endswith('.xml'):
                            for old_fn, new_fn in fname_map.items():
                                old_bytes = old_fn.encode('utf-8')
                                new_bytes = new_fn.encode('utf-8')
                                count = data.count(old_bytes)
                                if count:
                                    data = data.replace(old_bytes, new_bytes)
                                    total_replacements += count
                                    print(f'    [{item.filename}] '
                                          f'{old_fn} -> {new_fn} ({count}x)')
                        zout.writestr(item, data)
            os.replace(tmp_path, fpath)
            return total_replacements > 0
        except Exception as e:
            print(f'  Warning: could not patch XML in {fpath}: {e}')
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def _find_referencing_asm_files_on_disk(search_dir, already_open_paths):
        """Find all closed .asm.FCStd files in search_dir that reference
        the old base_name.  Returns list of full file paths.
        Does NOT open any files — only checks Document.xml in the zip."""
        found = []
        asm_pattern = re.compile(r"^.+\.\d{3}\.asm\.FCStd$", re.IGNORECASE)

        for fname in sorted(os.listdir(search_dir)):
            if not asm_pattern.match(fname):
                continue
            fpath = os.path.join(search_dir, fname)
            norm_fpath = os.path.normcase(os.path.abspath(fpath))

            # Skip files that are already open
            if norm_fpath in already_open_paths:
                continue

            # Skip the target file itself (it will be renamed separately)
            norm_target = os.path.normcase(os.path.abspath(str(target_doc.FileName)))
            if norm_fpath == norm_target:
                continue

            # Quick XML scan — avoid processing files that don't reference old name
            if not _fcstd_contains_name(fpath, base_name):
                continue

            found.append(fpath)
        return found

    referencing_docs_info = []   # list of (doc_name, file_path) still needed for close/reopen
    target_doc_name = target_doc.Name

    for d in list(App.listDocuments().values()):
        if d == target_doc:
            continue
        has_ref = False
        for obj in d.Objects:
            lo = getattr(obj, 'LinkedObject', None)
            if lo is not None:
                lo_doc = getattr(lo, 'Document', None)
                if lo_doc is not None and lo_doc.Name == target_doc.Name:
                    has_ref = True
                    break
        if has_ref:
            referencing_docs_info.append((d.Name, str(d.FileName)))
            _update_link_labels_in_doc(d)
            d.recompute()
            d.purgeTouched()
            d.save()

    # Also update the immediate parent assembly (linked mode)
    parent_file_path = None
    if rename_mode == "linked" and parent_doc:
        _update_link_labels_in_doc(parent_doc)
        parent_doc.recompute()
        parent_doc.purgeTouched()
        parent_doc.save()
        parent_file_path = str(parent_doc.FileName)

    # ============================================================
    # SCAN ALL CLOSED ASSEMBLY FILES ON DISK FOR REFERENCES
    # Pure file-level scan — does NOT open files in FreeCAD.
    # Collects paths for XML patching after disk rename.
    # ============================================================

    already_open = set(
        os.path.normcase(os.path.abspath(str(d.FileName)))
        for d in App.listDocuments().values()
        if d.FileName
    )
    disk_asm_files = _find_referencing_asm_files_on_disk(directory, already_open)
    if disk_asm_files:
        for fn in disk_asm_files:
            print(f"  Closed assembly references old name: {os.path.basename(fn)}")

    # ============================================================
    # STORE RENAME MAPPING FOR REGEN MACRO
    # Written to a JSON file on disk so ANY FreeCAD instance
    # (even a separate window/process) can read it.
    # ============================================================
    _write_rename_entry(base_name, new_name)

    # ============================================================
    # CLOSE REFERENCING DOCS + TARGET DOCUMENT
    # Save their paths now — needed for XML patching after rename.
    # ============================================================

    for ref_doc_name, _ref_doc_path in referencing_docs_info:
        try:
            App.closeDocument(ref_doc_name)
        except Exception:
            pass

    App.closeDocument(target_doc_name)

    # ============================================================
    # RENAME FILES ON DISK
    # ============================================================

    for old_path, new_path, ver in rename_list:
        if old_path != new_path:
            os.rename(old_path, new_path)

    # ============================================================
    # PATCH XML FILE REFERENCES IN ALL REFERENCING ASSEMBLY FILES
    # Replace old filename(s) with new filename(s) in Document.xml
    # inside every assembly FCStd that was saved above, so FreeCAD
    # can resolve the link when those assemblies are reopened.
    # ============================================================

    # Build old-filename -> new-filename map.
    # The assembly XLink might reference ANY old version (not just the
    # latest), so map EVERY old version filename to the new .001 file.
    new_fn = os.path.basename(new_full_001)
    fname_map = {}
    for _ver_num, old_ver_path in version_files:
        old_fn = os.path.basename(old_ver_path)
        if old_fn != new_fn:
            fname_map[old_fn] = new_fn

    # Also add label-level replacements so link Labels in the XML are
    # updated too (without needing to open files in FreeCAD).
    # Use XML-safe attribute syntax to avoid false positives.
    if base_name != new_name:
        # Covers  Label="OldName"  in XML attributes
        fname_map['Label="{}"'.format(base_name)] = 'Label="{}"'.format(new_name)
        # Covers  <String value="OldName"/>  in XML property blocks
        fname_map['value="{}"'.format(base_name)] = 'value="{}"'.format(new_name)
    print(f"  fname_map: {fname_map}")

    if fname_map:
        # Collect all assembly files that need XML patching
        asm_files_to_patch = []
        for _ref_doc_name, ref_doc_path in referencing_docs_info:
            if ref_doc_path and os.path.exists(ref_doc_path):
                asm_files_to_patch.append(ref_doc_path)
        for fpath in disk_asm_files:        # closed assembly files found on disk
            if os.path.exists(fpath):
                asm_files_to_patch.append(fpath)
        if parent_file_path and os.path.exists(parent_file_path):
            asm_files_to_patch.append(parent_file_path)

        seen_patch = set()
        for asm_path in asm_files_to_patch:
            norm = os.path.normcase(os.path.abspath(asm_path))
            if norm in seen_patch:
                continue
            seen_patch.add(norm)
            patched = _patch_fcstd_xml(asm_path, fname_map)
            if patched:
                print(f'  XML references patched: {os.path.basename(asm_path)}')
            else:
                print(f'  XML patch: no matching references found in {os.path.basename(asm_path)}')

    # ============================================================
    # REOPEN LATEST VERSION OF RENAMED DOCUMENT
    # ============================================================

    rename_list.sort(key=lambda x: x[1])
    latest_file = rename_list[-1][1]

    new_doc = App.openDocument(latest_file)

    # Recompute first so all objects (Body, Assembly) are fully initialised
    # before we write to them — otherwise Label changes may not persist.
    new_doc.recompute()

    if hasattr(new_doc, "Description"):
        new_doc.Description = new_desc

    # Apply name & description to first body / root assembly
    apply_info_to_first_body(new_doc, new_name, new_desc)

    # Sync Model Parameters properties
    if hasattr(new_doc, "MP_PartNumber"):
        new_doc.MP_PartNumber = new_name
    if hasattr(new_doc, "MP_Description"):
        new_doc.MP_Description = new_desc

    new_doc.recompute()
    new_doc.purgeTouched()
    new_doc.save()

    # ============================================================
    # REOPEN REFERENCING DOCUMENTS (parent assemblies)
    # Labels were already updated before close — just reopen.
    # ============================================================

    for ref_doc_name, ref_doc_path in referencing_docs_info:
        if ref_doc_path and os.path.exists(ref_doc_path):
            try:
                ref_reopened = App.openDocument(ref_doc_path)
                if ref_reopened:
                    ref_reopened.recompute()
                    ref_reopened.purgeTouched()
                    ref_reopened.save()
            except Exception:
                pass

    if rename_mode == "linked" and parent_file_path and os.path.exists(parent_file_path):
        parent_already_open = False
        for d in App.listDocuments().values():
            if str(d.FileName) == parent_file_path:
                d.recompute()
                d.purgeTouched()
                d.save()
                App.setActiveDocument(d.Name)
                parent_already_open = True
                break
        if not parent_already_open:
            parent_reopened = App.openDocument(parent_file_path)
            if parent_reopened:
                parent_reopened.recompute()
                parent_reopened.purgeTouched()
                parent_reopened.save()
            App.setActiveDocument(parent_reopened.Name)

    # Recompute and fit view
    active = App.ActiveDocument
    if active:
        active.recompute()
        if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
            Gui.ActiveDocument.ActiveView.fitAll()

    # ============================================================
    # SUCCESS MESSAGE
    # ============================================================

    if rename_mode == "linked":
        kind = "Assembly" if logical_ext == "asm" else "Part"
        QtGui.QMessageBox.information(
            None,
            "Rename Successful",
            f"{kind} Rename Successful!\n\n"
            f"New Name: {new_name}\n"
            f"New Description: {new_desc if new_desc else '-'}\n"
            f"Files renamed: {len(rename_list)}"
        )
    else:
        QtGui.QMessageBox.information(
            None,
            "Rename Successful",
            f"Rename Successful!\n\n"
            f"New Name: {new_name}\n"
            f"New Description: {new_desc if new_desc else '-'}"
        )


main()
