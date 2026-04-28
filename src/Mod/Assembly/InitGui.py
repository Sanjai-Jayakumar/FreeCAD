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

import os as _os
import FreeCAD as _fc
_home = _fc.getHomePath()
_os.add_dll_directory(_os.path.join(_home, 'lib'))
_os.add_dll_directory(_os.path.join(_home, 'bin'))

import Assembly_rc


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

        import os, re, time, datetime, zipfile, inspect
        import xml.etree.ElementTree as ET
        from pathlib import Path
        import FreeCAD as App

        # Define BNC custom command class
        class CommandInsertFromWorkingDir:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_InsertWD.svg',
                    'MenuText': 'Insert Component (Working Dir)',
                    'ToolTip': 'Insert latest version component from Working Directory'
                }

            def IsActive(self):
                return App.ActiveDocument is not None

            def Activated(self):

                # â”€â”€ Versioned filename pattern â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                # Matches:  base.001.prt.FCStd  /  base.002.asm.FCStd  /  base.001.FCStd
                VERSIONED_RE = re.compile(
                    r"^(?P<base>.+?)\.(?P<ver>\d{3})"
                    r"(?:\.(?P<ext>prt|asm|drg|stp|stl))?"
                    r"\.fcstd$",
                    re.IGNORECASE,
                )

                def get_working_directory():
                    params = App.ParamGet("User parameter:BaseApp/Preferences/General")
                    return params.GetString("WorkingDirectory", "")

                def parse_versioned(filename):
                    """(base, version_int, ext_lower_or_None) or None."""
                    m = VERSIONED_RE.match(filename)
                    if not m:
                        return None
                    ext = m.group("ext")
                    return (m.group("base"), int(m.group("ver")), ext.lower() if ext else None)

                def collect_files(folder, show_all_versions=False, type_filter="All"):
                    """Return sorted list of versioned .FCStd filenames."""
                    raw = [f for f in os.listdir(folder) if f.lower().endswith(".fcstd")]
                    parsed = []
                    for f in raw:
                        info = parse_versioned(f)
                        if info:
                            parsed.append((f, info[0], info[1], info[2]))
                    if type_filter != "All":
                        tf = type_filter.lower()
                        parsed = [p for p in parsed if p[3] == tf]
                    if not show_all_versions:
                        best = {}
                        for fname, base, ver, ext in parsed:
                            key = (base.lower(), ext)
                            if key not in best or ver > best[key][1]:
                                best[key] = (fname, ver)
                        parsed = [p for p in parsed
                                  if p[0] == best.get((p[1].lower(), p[3]), (None,))[0]]
                    parsed.sort(key=lambda p: p[0].lower())
                    return [p[0] for p in parsed]

                def format_size(n):
                    if n < 1024:
                        return "{} B".format(n)
                    if n < 1024 * 1024:
                        return "{:.1f} KiB".format(n / 1024.0)
                    return "{:.1f} MiB".format(n / (1024.0 * 1024.0))

                def extract_thumbnail(filepath):
                    """Extract thumbnail PNG from FCStd (ZIP) â†’ QPixmap or None."""
                    try:
                        with zipfile.ZipFile(filepath, "r") as zf:
                            for name in zf.namelist():
                                if "thumbnail" in name.lower() and name.lower().endswith(".png"):
                                    data = zf.read(name)
                                    pix = QtGui.QPixmap()
                                    pix.loadFromData(data)
                                    if not pix.isNull():
                                        return pix
                    except Exception:
                        pass
                    return None

                def read_description_from_fcstd(filepath):
                    """Read MP_Description from the FCStd XML without opening in FreeCAD."""
                    try:
                        with zipfile.ZipFile(filepath, "r") as zf:
                            if "Document.xml" not in zf.namelist():
                                return ""
                            data = zf.read("Document.xml")
                            root = ET.fromstring(data)
                            for prop in root.iter("Property"):
                                if prop.get("name") == "MP_Description":
                                    s = prop.find("String")
                                    if s is not None:
                                        return s.get("value", "")
                    except Exception:
                        pass
                    return ""

                def find_insert_object(doc):
                    for obj in doc.Objects:
                        if obj.TypeId == "Assembly::AssemblyObject":
                            return obj
                    for obj in doc.Objects:
                        if obj.TypeId == "App::Part":
                            return obj
                    for obj in doc.Objects:
                        if obj.TypeId == "PartDesign::Body":
                            return obj
                    for obj in doc.Objects:
                        if obj.TypeId.startswith("Part::"):
                            return obj
                    return None

                def insert_component(filepath):
                    target_doc = App.ActiveDocument
                    if not target_doc:
                        QtGui.QMessageBox.warning(None, "Error", "No active document.")
                        return

                    target_name = target_doc.Name
                    abs_path = os.path.abspath(filepath)

                    if abs_path == os.path.abspath(target_doc.FileName):
                        QtGui.QMessageBox.warning(None, "Error", "Cannot insert current file.")
                        return

                    if not target_doc.FileName:
                        QtGui.QMessageBox.warning(None, "Error", "Please save assembly first.")
                        return

                    # Allow duplicate labels
                    pgrp = App.ParamGet("User parameter:BaseApp/Preferences/Document")
                    pgrp.SetBool("DuplicateLabels", True)

                    # Find the activated (currently edited) assembly
                    assembly = None

                    # Method 1: getInEdit()
                    try:
                        edit_vp = FreeCADGui.ActiveDocument.getInEdit()
                        if edit_vp is not None:
                            try:
                                obj = edit_vp.Object
                            except AttributeError:
                                obj = edit_vp
                            if hasattr(obj, 'TypeId') and obj.TypeId == 'Assembly::AssemblyObject':
                                assembly = obj
                    except Exception:
                        pass

                    # Method 2: ActiveView active-object registry
                    if assembly is None:
                        try:
                            view = FreeCADGui.ActiveDocument.ActiveView
                            for key in ('Assembly', 'assembly', 'part'):
                                obj = view.getActiveObject(key)
                                if obj and hasattr(obj, 'TypeId') and obj.TypeId == 'Assembly::AssemblyObject':
                                    assembly = obj
                                    break
                        except Exception:
                            pass

                    # Method 3: Walk all assemblies and check isEditing()
                    if assembly is None:
                        for obj in target_doc.Objects:
                            if obj.TypeId == 'Assembly::AssemblyObject':
                                try:
                                    if obj.ViewObject.isEditing():
                                        assembly = obj
                                        break
                                except Exception:
                                    continue

                    # Method 4: Fallback â€” first (root) assembly
                    if assembly is None:
                        for obj in target_doc.Objects:
                            if obj.TypeId == 'Assembly::AssemblyObject':
                                assembly = obj
                                break

                    if not assembly:
                        QtGui.QMessageBox.warning(None, "Error",
                                                  "No Assembly found in active file.")
                        return

                    # Open source document
                    source_doc = None
                    for doc in App.listDocuments().values():
                        if doc.FileName and os.path.abspath(doc.FileName) == abs_path:
                            source_doc = doc
                            break

                    already_open = source_doc is not None
                    if not already_open:
                        try:
                            source_doc = App.openDocument(filepath, False)
                        except Exception as e:
                            QtGui.QMessageBox.warning(
                                None, "Error",
                                "Failed to open file:\n{}\n\n"
                                "The file may be corrupted or incomplete.".format(e))
                            return

                    # Re-activate target assembly
                    App.setActiveDocument(target_name)
                    FreeCADGui.setActiveDocument(target_name)
                    target_doc = App.getDocument(target_name)

                    source_obj = find_insert_object(source_doc)
                    if not source_obj:
                        QtGui.QMessageBox.warning(None, "Error",
                                                  "No insertable object found in source.")
                        if not already_open:
                            App.closeDocument(source_doc.Name)
                        return

                    # Create link with unique internal name
                    desired_label = source_obj.Label
                    uid = "Link_{}".format(int(time.time() * 1000))
                    link = target_doc.addObject("App::Link", uid)
                    link.Label = desired_label
                    link.LinkedObject = source_obj
                    assembly.addObject(link)
                    link.Label = desired_label
                    target_doc.recompute()
                    link.Label = desired_label

                    # Keep assembly in front
                    App.setActiveDocument(target_name)
                    FreeCADGui.setActiveDocument(target_name)

                    print("Inserted:", link.Label)

                # â”€â”€ Dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                class InsertComponentDialog(QtGui.QDialog):

                    TYPES = ["All", "prt", "asm", "drg", "stp", "stl"]

                    _STYLE = """
                    QDialog { font-size: 9pt; }

                    #navBar {
                        background: palette(window);
                        border: 1px solid palette(mid);
                        border-radius: 3px;
                        padding: 2px 4px;
                    }
                    #pathBreadcrumb {
                        background: palette(base);
                        border: 1px solid palette(mid);
                        border-radius: 2px;
                        padding: 3px 6px;
                        font-size: 8.5pt;
                    }
                    #searchBox {
                        background: palette(base);
                        border: 1px solid palette(mid);
                        border-radius: 2px;
                        padding: 3px 6px;
                        font-size: 8.5pt;
                    }
                    QTreeWidget, QTableWidget {
                        border: 1px solid palette(mid);
                        border-radius: 3px;
                        font-size: 9pt;
                    }
                    QTreeWidget::item { padding: 2px 4px; }
                    QTreeWidget::item:selected {
                        background: palette(highlight);
                        color: palette(highlighted-text);
                    }
                    QHeaderView::section {
                        background: palette(button);
                        border: 1px solid palette(mid);
                        padding: 4px 6px;
                        font-weight: bold;
                        font-size: 8.5pt;
                    }
                    #previewFrame {
                        background: palette(base);
                        border: 1px solid palette(mid);
                        border-radius: 3px;
                    }
                    #previewLabel {
                        background: transparent;
                        color: palette(text);
                        font-size: 8.5pt;
                    }
                    #infoBar {
                        background: palette(window);
                        border: 1px solid palette(mid);
                        border-radius: 2px;
                        padding: 4px 8px;
                        font-size: 8.5pt;
                    }
                    #bottomPanel {
                        background: palette(window);
                        border-top: 1px solid palette(mid);
                        padding: 6px 0px 0px 0px;
                    }
                    #bottomPanel QLabel { font-size: 8.5pt; min-width: 70px; }
                    #bottomPanel QLineEdit, #bottomPanel QComboBox {
                        font-size: 8.5pt; padding: 3px 4px;
                    }
                    QPushButton { min-width: 80px; padding: 5px 16px; border-radius: 3px; font-size: 8.5pt; }
                    QPushButton#openBtn {
                        background: palette(highlight);
                        color: palette(highlighted-text);
                        border: 1px solid palette(highlight);
                        font-weight: bold;
                    }
                    QPushButton#openBtn:disabled {
                        background: palette(midlight);
                        color: palette(mid);
                        border: 1px solid palette(mid);
                    }
                    QPushButton#cancelBtn { background: palette(button); border: 1px solid palette(mid); }
                    QPushButton#cancelBtn:hover { background: palette(midlight); }
                    QCheckBox { font-size: 8.5pt; spacing: 4px; }
                    """

                    def __init__(self, folder, parent=None):
                        super(InsertComponentDialog, self).__init__(parent)
                        self.folder = folder
                        self.selected_file = None
                        self._desc_cache = {}
                        self._thumb_cache = {}
                        self.setWindowTitle("Insert Component")
                        self.setMinimumSize(750, 560)
                        self.resize(820, 620)
                        self.setStyleSheet(self._STYLE)
                        self._build_ui()
                        self._refresh()

                    def _build_ui(self):
                        root = QtGui.QVBoxLayout(self)
                        root.setContentsMargins(8, 8, 8, 8)
                        root.setSpacing(6)

                        # Nav bar
                        nav = QtGui.QFrame()
                        nav.setObjectName("navBar")
                        nav_lay = QtGui.QHBoxLayout(nav)
                        nav_lay.setContentsMargins(4, 2, 4, 2)
                        nav_lay.setSpacing(4)
                        parts = self.folder.replace("\\", "/").split("/")
                        crumb = " > ".join(parts[-4:]) if len(parts) > 4 else " > ".join(parts)
                        self.path_lbl = QtGui.QLineEdit(crumb)
                        self.path_lbl.setObjectName("pathBreadcrumb")
                        self.path_lbl.setReadOnly(True)
                        self.path_lbl.setToolTip(self.folder)
                        nav_lay.addWidget(self.path_lbl, 1)
                        nav_lay.addSpacing(8)
                        self.search = QtGui.QLineEdit()
                        self.search.setObjectName("searchBox")
                        self.search.setPlaceholderText("Search...")
                        self.search.setFixedWidth(200)
                        self.search.setClearButtonEnabled(True)
                        self.search.textChanged.connect(self._filter)
                        nav_lay.addWidget(self.search)
                        root.addWidget(nav)

                        # Main content splitter: files | preview
                        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)

                        # Left: stacked file views
                        left_widget = QtGui.QWidget()
                        left_lay = QtGui.QVBoxLayout(left_widget)
                        left_lay.setContentsMargins(0, 0, 0, 0)
                        self.stack = QtGui.QStackedWidget()

                        # View 0: Tree with Name + Description
                        self.tree = QtGui.QTreeWidget()
                        self.tree.setHeaderLabels(["Name", "Description"])
                        self.tree.setRootIsDecorated(False)
                        self.tree.setAlternatingRowColors(True)
                        self.tree.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
                        self.tree.header().setStretchLastSection(True)
                        self.tree.header().resizeSection(0, 300)
                        self.tree.currentItemChanged.connect(self._tree_sel)
                        self.tree.itemDoubleClicked.connect(self._tree_dbl)
                        self.stack.addWidget(self.tree)

                        # View 1: Detail table
                        self.table = QtGui.QTableWidget()
                        self.table.setColumnCount(5)
                        self.table.setHorizontalHeaderLabels(
                            ["Name", "Description", "Size", "Type", "Date Modified"])
                        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
                        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
                        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
                        self.table.verticalHeader().setVisible(False)
                        self.table.setSortingEnabled(True)
                        self.table.setAlternatingRowColors(True)
                        hdr = self.table.horizontalHeader()
                        hdr.setStretchLastSection(True)
                        hdr.resizeSection(0, 240)
                        hdr.resizeSection(1, 160)
                        hdr.resizeSection(2, 70)
                        hdr.resizeSection(3, 50)
                        self.table.itemSelectionChanged.connect(self._tbl_sel)
                        self.table.cellDoubleClicked.connect(self._tbl_dbl)
                        self.stack.addWidget(self.table)

                        left_lay.addWidget(self.stack)
                        self.splitter.addWidget(left_widget)

                        # Right: Preview panel
                        self.preview_panel = QtGui.QFrame()
                        self.preview_panel.setObjectName("previewFrame")
                        prev_lay = QtGui.QVBoxLayout(self.preview_panel)
                        prev_lay.setContentsMargins(4, 4, 4, 4)
                        prev_lay.setSpacing(0)
                        self.thumb_label = QtGui.QLabel()
                        self.thumb_label.setObjectName("previewLabel")
                        self.thumb_label.setAlignment(QtCore.Qt.AlignCenter)
                        self.thumb_label.setMinimumSize(180, 180)
                        self.thumb_label.setSizePolicy(
                            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
                        self.thumb_label.setText("No Preview")
                        prev_lay.addWidget(self.thumb_label, 1)
                        self.splitter.addWidget(self.preview_panel)
                        self.preview_panel.setVisible(False)
                        self.splitter.setStretchFactor(0, 3)
                        self.splitter.setStretchFactor(1, 2)
                        root.addWidget(self.splitter, 1)

                        # Info bar
                        self.info_bar = QtGui.QLabel("")
                        self.info_bar.setObjectName("infoBar")
                        self.info_bar.setWordWrap(True)
                        self.info_bar.setVisible(False)
                        root.addWidget(self.info_bar)

                        # Bottom panel
                        bottom = QtGui.QFrame()
                        bottom.setObjectName("bottomPanel")
                        bot_lay = QtGui.QVBoxLayout(bottom)
                        bot_lay.setContentsMargins(0, 8, 0, 0)
                        bot_lay.setSpacing(6)

                        r_name = QtGui.QHBoxLayout()
                        lbl_name = QtGui.QLabel("File name:")
                        lbl_name.setFixedWidth(75)
                        self.name_edit = QtGui.QLineEdit()
                        self.name_edit.setReadOnly(True)
                        r_name.addWidget(lbl_name)
                        r_name.addWidget(self.name_edit, 1)
                        bot_lay.addLayout(r_name)

                        r_type = QtGui.QHBoxLayout()
                        lbl_type = QtGui.QLabel("Type:")
                        lbl_type.setFixedWidth(75)
                        self.type_cb = QtGui.QComboBox()
                        for t in self.TYPES:
                            if t == "All":
                                self.type_cb.addItem("All types (*.FCStd)", "All")
                            else:
                                self.type_cb.addItem("{} files (*.{}.FCStd)".format(
                                    t.upper(), t), t)
                        self.type_cb.currentIndexChanged.connect(self._refresh)
                        r_type.addWidget(lbl_type)
                        r_type.addWidget(self.type_cb, 1)
                        bot_lay.addLayout(r_type)

                        r_btm = QtGui.QHBoxLayout()
                        self.all_ver = QtGui.QCheckBox("Show all versions")
                        self.all_ver.toggled.connect(self._refresh)
                        r_btm.addWidget(self.all_ver)
                        r_btm.addSpacing(12)
                        self.details = QtGui.QCheckBox("Show details")
                        self.details.toggled.connect(
                            lambda c: self.stack.setCurrentIndex(1 if c else 0))
                        r_btm.addWidget(self.details)
                        r_btm.addSpacing(12)
                        self.preview_chk = QtGui.QCheckBox("Preview")
                        self.preview_chk.toggled.connect(self._toggle_preview)
                        r_btm.addWidget(self.preview_chk)
                        r_btm.addStretch()
                        self.open_btn = QtGui.QPushButton("Open")
                        self.open_btn.setObjectName("openBtn")
                        self.open_btn.setEnabled(False)
                        self.open_btn.setDefault(True)
                        self.open_btn.clicked.connect(self._do_open)
                        r_btm.addWidget(self.open_btn)
                        r_btm.addSpacing(6)
                        cancel = QtGui.QPushButton("Cancel")
                        cancel.setObjectName("cancelBtn")
                        cancel.clicked.connect(self.reject)
                        r_btm.addWidget(cancel)
                        bot_lay.addLayout(r_btm)
                        root.addWidget(bottom)

                    def _get_desc(self, fname):
                        if fname not in self._desc_cache:
                            fpath = os.path.join(self.folder, fname)
                            self._desc_cache[fname] = read_description_from_fcstd(fpath)
                        return self._desc_cache[fname]

                    def _get_thumb(self, fname):
                        if fname not in self._thumb_cache:
                            fpath = os.path.join(self.folder, fname)
                            self._thumb_cache[fname] = extract_thumbnail(fpath)
                        return self._thumb_cache[fname]

                    def _cur_type(self):
                        return self.type_cb.itemData(self.type_cb.currentIndex())

                    def _refresh(self, *_):
                        files = collect_files(
                            self.folder,
                            show_all_versions=self.all_ver.isChecked(),
                            type_filter=self._cur_type())

                        self.tree.clear()
                        for f in files:
                            desc = self._get_desc(f)
                            item = QtGui.QTreeWidgetItem([f, desc])
                            item.setToolTip(0, f)
                            if desc:
                                item.setToolTip(1, desc)
                            self.tree.addTopLevelItem(item)

                        self.table.setSortingEnabled(False)
                        self.table.setRowCount(0)
                        for fname in files:
                            fpath = os.path.join(self.folder, fname)
                            desc = self._get_desc(fname)
                            try:
                                st = os.stat(fpath)
                                sz = format_size(st.st_size)
                                mt = datetime.datetime.fromtimestamp(
                                    st.st_mtime).strftime("%d-%m-%Y  %H:%M")
                            except Exception:
                                sz, mt = "", ""
                            info = parse_versioned(fname)
                            ft = info[2].upper() if info and info[2] else "FCStd"
                            r = self.table.rowCount()
                            self.table.insertRow(r)
                            self.table.setItem(r, 0, QtGui.QTableWidgetItem(fname))
                            self.table.setItem(r, 1, QtGui.QTableWidgetItem(desc))
                            self.table.setItem(r, 2, QtGui.QTableWidgetItem(sz))
                            self.table.setItem(r, 3, QtGui.QTableWidgetItem(ft))
                            self.table.setItem(r, 4, QtGui.QTableWidgetItem(mt))
                        self.table.setSortingEnabled(True)

                        self.name_edit.clear()
                        self.open_btn.setEnabled(False)
                        self.info_bar.setVisible(False)
                        self.thumb_label.setText("No Preview")
                        self._filter()

                    def _filter(self):
                        txt = self.search.text().strip().lower()
                        for i in range(self.tree.topLevelItemCount()):
                            it = self.tree.topLevelItem(i)
                            name_match = txt in it.text(0).lower() if txt else True
                            desc_match = txt in it.text(1).lower() if txt else False
                            it.setHidden(not (name_match or desc_match) if txt else False)
                        for r in range(self.table.rowCount()):
                            it0 = self.table.item(r, 0)
                            it1 = self.table.item(r, 1)
                            if it0:
                                name_match = txt in it0.text().lower() if txt else True
                                desc_match = txt in (it1.text().lower() if it1 else "") if txt else False
                                self.table.setRowHidden(
                                    r, not (name_match or desc_match) if txt else False)

                    def _toggle_preview(self, checked):
                        self.preview_panel.setVisible(checked)
                        if checked:
                            self._update_preview()

                    def _update_preview(self):
                        fname = self.name_edit.text().strip()
                        if not fname:
                            self.thumb_label.setText("No Preview")
                            self.info_bar.setVisible(False)
                            return
                        pix = self._get_thumb(fname)
                        if pix and not pix.isNull():
                            avail = self.thumb_label.size()
                            target_w = max(avail.width() - 12, 120)
                            target_h = max(avail.height() - 12, 120)
                            scaled = pix.scaled(
                                target_w, target_h,
                                QtCore.Qt.KeepAspectRatio,
                                QtCore.Qt.SmoothTransformation)
                            self.thumb_label.setPixmap(scaled)
                        else:
                            self.thumb_label.setText("No Preview Available")
                        fpath = os.path.join(self.folder, fname)
                        desc = self._get_desc(fname)
                        try:
                            st = os.stat(fpath)
                            mt = datetime.datetime.fromtimestamp(
                                st.st_mtime).strftime("%d-%b-%Y  %I:%M:%S %p")
                        except Exception:
                            mt = ""
                        info_parts = ["<b>File name:</b> {}".format(fname)]
                        if mt:
                            info_parts.append("<b>Date modified:</b> {}".format(mt))
                        if desc:
                            info_parts.append("<b>Description:</b> {}".format(desc))
                        self.info_bar.setText("  &nbsp;&nbsp;  ".join(info_parts))
                        self.info_bar.setVisible(True)

                    def _set_selected(self, name):
                        self.name_edit.setText(name)
                        self.open_btn.setEnabled(True)
                        if self.preview_panel.isVisible():
                            self._update_preview()

                    def _tree_sel(self, cur, prev):
                        if cur:
                            self._set_selected(cur.text(0))

                    def _tree_dbl(self, item, col):
                        if item:
                            self.selected_file = item.text(0)
                            self.accept()

                    def _tbl_sel(self):
                        rows = self.table.selectionModel().selectedRows()
                        if rows:
                            self._set_selected(self.table.item(rows[0].row(), 0).text())

                    def _tbl_dbl(self, row, col):
                        it = self.table.item(row, 0)
                        if it:
                            self.selected_file = it.text()
                            self.accept()

                    def _do_open(self):
                        t = self.name_edit.text().strip()
                        if t:
                            self.selected_file = t
                            self.accept()

                # â”€â”€ Main execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                wd = get_working_directory()
                if not wd or not os.path.exists(wd):
                    QtGui.QMessageBox.warning(None, "Error", "Working Directory not set.")
                    return

                if not collect_files(wd, show_all_versions=True):
                    QtGui.QMessageBox.information(None, "Info",
                                                  "No versioned files found in WD.")
                    return

                dlg = InsertComponentDialog(wd, FreeCADGui.getMainWindow())
                if dlg.exec_() == QtGui.QDialog.Accepted and dlg.selected_file:
                    insert_component(os.path.join(wd, dlg.selected_file))

        # Define BNC Create Part in Assembly command class with version saving
        class CommandCreatePartInAssembly:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_Create_part.svg',
                    'MenuText': 'Create New Part',
                    'ToolTip': 'Create a new part with version saving'
                }

            def IsActive(self):
                return App.ActiveDocument is not None

            def Activated(self):
                # â”€â”€â”€ Dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                class CreatePartDialog(QtGui.QDialog):
                    def __init__(self):
                        super(CreatePartDialog, self).__init__()
                        self.setWindowTitle("Create New...")
                        self.setModal(True)
                        self.resize(400, 200)

                        layout = QtGui.QVBoxLayout()

                        part_label = QtGui.QLabel("Enter part name:")
                        self.part_name_edit = QtGui.QLineEdit("Part")
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

                # â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                def get_working_directory():
                    param = App.ParamGet("User parameter:BaseApp/Preferences/General")
                    return param.GetString("WorkingDirectory", "")

                def check_name_exists(folder, base_name):
                    """Check if any versioned file with this base name exists in the folder."""
                    for ext in (".prt", ".asm", ".drg"):
                        pattern = re.compile(
                            rf"^{re.escape(base_name)}\.\d{{3}}{re.escape(ext)}(?:\.FCStd)?$",
                            re.IGNORECASE,
                        )
                        for f in os.listdir(folder):
                            if pattern.match(f):
                                return True
                    return False

                def check_name_in_assembly(doc, name):
                    """Check if a body with this label already exists in the document."""
                    for obj in doc.Objects:
                        if obj.TypeId == 'PartDesign::Body' and obj.Label == name:
                            return True
                    return False

                # â”€â”€â”€ Main execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                doc = App.ActiveDocument

                if not doc:
                    QtGui.QMessageBox.warning(
                        None,
                        "No Document",
                        "Please open or create a document first."
                    )
                    return

                # Find the activated (currently edited) assembly
                assembly = None

                # Method 1: getInEdit() â€“ works when the assembly's ViewProvider is in edit mode
                try:
                    edit_vp = FreeCADGui.ActiveDocument.getInEdit()
                    if edit_vp is not None:
                        try:
                            obj = edit_vp.Object
                        except AttributeError:
                            obj = edit_vp  # might already be the document object
                        if hasattr(obj, 'TypeId') and obj.TypeId == 'Assembly::AssemblyObject':
                            assembly = obj
                except Exception:
                    pass

                # Method 2: ActiveView active-object registry (Assembly workbench may register here)
                if assembly is None:
                    try:
                        view = FreeCADGui.ActiveDocument.ActiveView
                        for key in ('Assembly', 'assembly', 'part'):
                            obj = view.getActiveObject(key)
                            if obj and hasattr(obj, 'TypeId') and obj.TypeId == 'Assembly::AssemblyObject':
                                assembly = obj
                                break
                    except Exception:
                        pass

                # Method 3: Walk all assemblies and check their ViewObject.isEditing()
                if assembly is None:
                    for obj in doc.Objects:
                        if obj.TypeId == 'Assembly::AssemblyObject':
                            try:
                                if obj.ViewObject.isEditing():
                                    assembly = obj
                                    break
                            except Exception:
                                continue

                # Method 4: Fall back to root-level assembly
                if assembly is None:
                    for obj in doc.Objects:
                        if obj.TypeId == 'Assembly::AssemblyObject':
                            assembly = obj
                            break

                if not assembly:
                    QtGui.QMessageBox.warning(
                        None,
                        "No Assembly",
                        "No assembly found in the active document.\nPlease create an assembly first."
                    )
                    return

                # Get part name and description from user
                dialog = CreatePartDialog()
                if dialog.exec_() != QtGui.QDialog.Accepted:
                    return

                part_name, description = dialog.get_part_info()

                if not part_name:
                    QtGui.QMessageBox.warning(None, "Error", "Part name is required.")
                    return

                # Check if name already exists inside the current assembly
                if check_name_in_assembly(doc, part_name):
                    QtGui.QMessageBox.critical(
                        None, "Error",
                        f"A part named '{part_name}' already exists in this assembly!"
                    )
                    return

                # Check if name already exists in the working directory
                workdir = get_working_directory()
                if workdir and os.path.exists(workdir):
                    if check_name_exists(workdir, part_name):
                        QtGui.QMessageBox.critical(
                            None, "Error",
                            f"Name '{part_name}' already exists in the working directory!"
                        )
                        return

                # Create a new part (Body object)
                try:
                    # Create a new Body object which acts as a part container
                    body = doc.addObject('PartDesign::Body', 'Body')
                    body.Label = part_name  # Set label explicitly to preserve exact name

                    # Store description in the body
                    if description:
                        if not hasattr(body, 'Description'):
                            body.addProperty("App::PropertyString", "Description", "Base", "Part description")
                        body.Description = description

                    # Add the body to the assembly
                    assembly.addObject(body)

                    # Optionally create a basic shape (cube) as starting geometry
                    create_default_shape = QtGui.QMessageBox.question(
                        None,
                        "Add Default Shape",
                        "Would you like to add a default box shape to the new part?",
                        QtGui.QMessageBox.Yes | QtGui.QMessageBox.No
                    )

                    if create_default_shape == QtGui.QMessageBox.Yes:
                        # Set the body as active
                        FreeCADGui.ActiveDocument.setEdit(body)

                        # Create a sketch on XY plane
                        sketch = body.newObject('Sketcher::SketchObject', 'Sketch')
                        sketch.Support = (body.Origin.OriginFeatures[3], [''])
                        sketch.MapMode = 'FlatFace'

                        # Create a rectangle in the sketch
                        sketch.addGeometry(
                            App.Part.LineSegment(
                                App.Vector(-10, -10, 0),
                                App.Vector(10, -10, 0)
                            ),
                            False
                        )
                        sketch.addGeometry(
                            App.Part.LineSegment(
                                App.Vector(10, -10, 0),
                                App.Vector(10, 10, 0)
                            ),
                            False
                        )
                        sketch.addGeometry(
                            App.Part.LineSegment(
                                App.Vector(10, 10, 0),
                                App.Vector(-10, 10, 0)
                            ),
                            False
                        )
                        sketch.addGeometry(
                            App.Part.LineSegment(
                                App.Vector(-10, 10, 0),
                                App.Vector(-10, -10, 0)
                            ),
                            False
                        )

                        # Add constraints to make it a square
                        sketch.addConstraint(App.Sketcher.Constraint('Coincident', 0, 2, 1, 1))
                        sketch.addConstraint(App.Sketcher.Constraint('Coincident', 1, 2, 2, 1))
                        sketch.addConstraint(App.Sketcher.Constraint('Coincident', 2, 2, 3, 1))
                        sketch.addConstraint(App.Sketcher.Constraint('Coincident', 3, 2, 0, 1))

                        # Create a pad feature
                        pad = body.newObject('PartDesign::Pad', 'Pad')
                        pad.Profile = sketch
                        pad.Length = 10.0

                        FreeCADGui.ActiveDocument.resetEdit()

                    doc.recompute()

                    QtGui.QMessageBox.information(
                        None,
                        "Success",
                        f"Part '{part_name}' created successfully in the assembly!"
                    )

                except Exception as e:
                    QtGui.QMessageBox.critical(
                        None,
                        "Error",
                        f"Failed to create part:\n{str(e)}"
                    )

        # Define BNC Default constraint command class
        class CommandDefault:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_Default.svg',
                    'MenuText': 'Origin to Assembly Constraint',
                    'ToolTip': 'Constrain selected component origin to assembly origin (0,0,0)'
                }

            def IsActive(self):
                return App.ActiveDocument is not None

            def Activated(self):
                import os
                candidates = [
                    os.path.join(App.getUserMacroDir(True), "Default.FCMacro"),
                    os.path.join(App.getHomePath(), "Macro", "Default.FCMacro"),
                    os.path.join(App.getResourceDir(), "Macro", "Default.FCMacro"),
                ]
                macro_path = None
                for p in candidates:
                    if os.path.exists(p):
                        macro_path = p
                        break
                if macro_path:
                    with open(macro_path, encoding='utf-8') as fh:
                        ns = {'__name__': '__main__', '__file__': macro_path}
                        exec(compile(fh.read(), macro_path, 'exec'), ns)
                else:
                    QtGui.QMessageBox.warning(
                        None, "Macro Not Found",
                        "Default.FCMacro not found.\n"
                        "Please ensure the macro is installed in your Macro folder.")

        # Define BNC Regen Assembly command class
        class CommandRegen:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_Regen.svg',
                    'MenuText': 'Regen Assembly',
                    'ToolTip': 'Reset all part placements and re-solve all joints.\n'
                               'Also refreshes link labels and applies pending renames.'
                }

            def IsActive(self):
                return App.ActiveDocument is not None

            def Activated(self):
                import os
                candidates = [
                    os.path.join(App.getUserMacroDir(True), "Regen.FCMacro"),
                    os.path.join(App.getHomePath(), "Macro", "Regen.FCMacro"),
                    os.path.join(App.getResourceDir(), "Macro", "Regen.FCMacro"),
                ]
                macro_path = None
                for p in candidates:
                    if os.path.exists(p):
                        macro_path = p
                        break
                if macro_path:
                    with open(macro_path, encoding='utf-8') as fh:
                        ns = {'__name__': '__main__', '__file__': macro_path}
                        exec(compile(fh.read(), macro_path, 'exec'), ns)
                else:
                    from PySide import QtWidgets
                    QtWidgets.QMessageBox.warning(
                        None, "Macro Not Found",
                        "Regen.FCMacro not found.\n"
                        "Please ensure the macro is installed in your Macro folder.")

        # Define BNC BOM Export command class
        class CommandBOM:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_BOM.svg',
                    'MenuText': 'Bill of Materials',
                    'ToolTip': 'Export Bill of Materials (BOM) to Excel\n'
                               'Generates a detailed BOM from the active assembly.'
                }

            def IsActive(self):
                return App.ActiveDocument is not None

            def Activated(self):
                from PySide import QtWidgets
                import datetime

                # â”€â”€ openpyxl dependency â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                try:
                    from openpyxl import Workbook
                    from openpyxl.styles import (Font, Alignment, Border, Side,
                                                  PatternFill)
                    from openpyxl.utils import get_column_letter
                except ImportError:
                    import subprocess
                    import sys
                    _fc_bin = os.path.dirname(sys.executable)
                    _py = os.path.join(_fc_bin, 'python.exe')
                    if not os.path.isfile(_py):
                        _py = os.path.join(_fc_bin, 'python3.exe')
                    if not os.path.isfile(_py):
                        _py = 'python'
                    subprocess.check_call([_py, '-m', 'pip', 'install', 'openpyxl'])
                    from openpyxl import Workbook
                    from openpyxl.styles import (Font, Alignment, Border, Side,
                                                  PatternFill)
                    from openpyxl.utils import get_column_letter

                # ================================================================
                # CONSTANTS
                # ================================================================

                _SKIP_TYPES = frozenset({
                    'App::Origin',
                    'App::Line',
                    'App::Plane',
                    'Assembly::JointGroup',
                    'Assembly::JointObject',
                    'Assembly::JointFixed',
                    'Assembly::JointRevolute',
                    'Assembly::JointCylindrical',
                    'Assembly::JointSlider',
                    'Assembly::JointBall',
                    'Assembly::JointDistance',
                    'Assembly::GroundedJoint',
                    'App::PropertyContainer',
                    'App::GeometryPython',
                })

                _SKIP_NAME_RE = re.compile(
                    r'^(GroundedJoint|OriginToAssembly|Joint|Constraint)',
                    re.IGNORECASE
                )

                def _should_skip(obj):
                    type_id = getattr(obj, 'TypeId', '')
                    if type_id in _SKIP_TYPES:
                        return True
                    if type_id.startswith('Assembly::') and type_id != 'Assembly::AssemblyObject':
                        return True
                    name  = getattr(obj, 'Name',  '')
                    label = getattr(obj, 'Label', '')
                    if _SKIP_NAME_RE.match(name) or _SKIP_NAME_RE.match(label):
                        return True
                    return False

                def _joint_member_ids(asm_obj):
                    skip_ids = set()
                    if not hasattr(asm_obj, 'Group'):
                        return skip_ids
                    for child in asm_obj.Group:
                        type_id = getattr(child, 'TypeId', '')
                        if type_id in _SKIP_TYPES or \
                           (type_id.startswith('Assembly::') and type_id != 'Assembly::AssemblyObject'):
                            if hasattr(child, 'Group'):
                                for member in child.Group:
                                    skip_ids.add(id(member))
                            skip_ids.add(id(child))
                    return skip_ids

                COLUMNS = [
                    ('S.NO',            8),
                    ('LEVEL',           8),
                    ('PART NUMBER',    28),
                    ('DESCRIPTION',    45),
                    ('QTY',             6),
                    ('EBOM',            7),
                    ('MBOM',            7),
                    ('S-BOM',           7),
                    ('REVISION',       11),
                    ('MAKE / BUY',     13),
                    ('Sub-Ty',         14),
                    ('MATERIAL',       18),
                    ('IDENTIFICATION', 18),
                    ('CATEGORY',       16),
                    ('AGGREGATE',      22),
                ]

                BOM_COL_START = 6
                BOM_COL_END   = 8

                # ================================================================
                # HELPER UTILITIES
                # ================================================================

                def clean_doc_name(doc):
                    if not doc.FileName:
                        return doc.Name or ''
                    name = os.path.splitext(os.path.basename(str(doc.FileName)))[0]
                    name = re.sub(r'\.(prt|asm|drg)$', '', name, flags=re.IGNORECASE)
                    name = re.sub(r'\.\d+$', '', name)
                    return name

                def _mp(source, prop, default=''):
                    return getattr(source, prop, default) or default

                def find_mp_source(obj):
                    if hasattr(obj, 'MP_PartNumber') and getattr(obj, 'MP_PartNumber', ''):
                        return obj
                    if hasattr(obj, 'LinkedObject') and obj.LinkedObject is not None:
                        linked = obj.LinkedObject
                        if hasattr(linked, 'MP_PartNumber') and getattr(linked, 'MP_PartNumber', ''):
                            return linked
                        if getattr(linked, 'TypeId', '') == 'Assembly::AssemblyObject':
                            if hasattr(linked, 'Document'):
                                d = linked.Document
                                if hasattr(d, 'MP_PartNumber') and getattr(d, 'MP_PartNumber', ''):
                                    return d
                    if getattr(obj, 'TypeId', '') == 'Assembly::AssemblyObject':
                        if hasattr(obj, 'Document'):
                            d = obj.Document
                            if hasattr(d, 'MP_PartNumber') and getattr(d, 'MP_PartNumber', ''):
                                return d
                    return None

                def _mat_with_thk(src):
                    mat = _mp(src, 'MP_Material', '')
                    sub = _mp(src, 'MP_TypeSub', '')
                    thk = _mp(src, 'MP_THK', '')
                    if sub.lower() == 'fabrication' and thk:
                        mat = '{} THK {}'.format(mat, thk) if mat else 'THK {}'.format(thk)
                    return mat

                def extract_entry(obj, fallback_label=''):
                    src = find_mp_source(obj)
                    bom_type = _mp(src, 'MP_BOMType', '') if src else ''
                    pn = _mp(src, 'MP_PartNumber', '') if src else ''
                    if not pn:
                        pn = obj.Label if hasattr(obj, 'Label') else ''
                    desc = _mp(src, 'MP_Description', '') if src else ''
                    _type     = _mp(src, 'MP_Type', '')            if src else ''
                    _sub_type = _mp(src, 'MP_TypeSub', '')         if src else ''
                    _ident    = _mp(src, 'MP_Identification', '')   if src else ''
                    _category = _mp(src, 'MP_Category', '')         if src else ''
                    _material = _mat_with_thk(src)                  if src else ''
                    _aggregate = _mp(src, 'MP_Aggregate', '')       if src else ''
                    details_filled = any([_type, _sub_type, _ident, _material, _aggregate])
                    if details_filled:
                        return {
                            'part_number':    pn,
                            'description':    desc,
                            'ebom':           'E',
                            'mbom':           'M' if bom_type == 'M-BOM' else '',
                            'sbom':           'S' if bom_type == 'S-BOM' else '',
                            'revision':       _mp(src, 'MP_Revision')  if src else '',
                            'type':           _type,
                            'sub_type':       _sub_type,
                            'material':       _material,
                            'identification': _ident,
                            'category':       _category,
                            'aggregate':      _aggregate,
                        }
                    else:
                        return {
                            'part_number':    pn,
                            'description':    desc,
                            'ebom':           '',
                            'mbom':           '',
                            'sbom':           '',
                            'revision':       '',
                            'type':           '',
                            'sub_type':       '',
                            'material':       '',
                            'identification': '',
                            'category':       '',
                            'aggregate':      '',
                        }

                # ================================================================
                # ASSEMBLY TRAVERSAL
                # ================================================================

                def _find_root_asm(doc):
                    for obj in doc.Objects:
                        if obj.TypeId == 'Assembly::AssemblyObject':
                            if not any(p.TypeId == 'Assembly::AssemblyObject' for p in obj.InList):
                                return obj
                    return None

                def _resolve(obj):
                    if hasattr(obj, 'LinkedObject') and obj.LinkedObject is not None:
                        linked = obj.LinkedObject
                        doc = linked.Document if hasattr(linked, 'Document') else None
                        return linked, doc
                    return obj, None

                def _ident_key(child_obj, resolved, linked_doc):
                    for probe in (child_obj, resolved):
                        src = find_mp_source(probe)
                        if src:
                            pn = getattr(src, 'MP_PartNumber', '')
                            if pn:
                                return ('pn', pn)
                    if linked_doc and linked_doc.FileName:
                        return ('file', str(linked_doc.FileName))
                    lbl = getattr(resolved, 'Label', '') or getattr(child_obj, 'Label', '')
                    if lbl:
                        return ('label', lbl)
                    return ('id', id(resolved))

                def _stack_key(asm_obj):
                    doc = getattr(asm_obj, 'Document', None)
                    obj_name = getattr(asm_obj, 'Name', '')
                    if doc and doc.FileName:
                        return ('file', str(doc.FileName), obj_name)
                    return ('id', id(asm_obj))

                def traverse(asm_obj, level, results, _stack=None):
                    if _stack is None:
                        _stack = set()
                    sk = _stack_key(asm_obj)
                    if sk in _stack:
                        return
                    _stack.add(sk)
                    entry = extract_entry(asm_obj)
                    results.append({'level': level, 'entry': entry, 'qty': 1})
                    if not hasattr(asm_obj, 'Group'):
                        _stack.discard(sk)
                        return
                    asm_mp_src = find_mp_source(asm_obj)
                    joint_ids = _joint_member_ids(asm_obj)
                    ordered_children = []
                    for child in asm_obj.Group:
                        if _should_skip(child):
                            continue
                        if id(child) in joint_ids:
                            continue
                        resolved, linked_doc = _resolve(child)
                        sub_asm = None
                        if resolved.TypeId == 'Assembly::AssemblyObject':
                            sub_asm = resolved
                        elif linked_doc:
                            sub_asm = _find_root_asm(linked_doc)
                        if sub_asm is None:
                            child_mp_src = find_mp_source(child)
                            if (child_mp_src is not None
                                    and child_mp_src is asm_mp_src
                                    and not hasattr(child, 'MP_PartNumber')):
                                continue
                        if sub_asm is not None and _stack_key(sub_asm) in _stack:
                            continue
                        key = _ident_key(child, resolved, linked_doc)
                        ordered_children.append({
                            'key':        key,
                            'resolved':   resolved,
                            'linked_doc': linked_doc,
                            'sub_asm':    sub_asm,
                            'child_obj':  child,
                        })
                    merged = []
                    for info in ordered_children:
                        if merged and merged[-1]['key'] == info['key']:
                            merged[-1]['count'] += 1
                        else:
                            merged.append({
                                'key':        info['key'],
                                'resolved':   info['resolved'],
                                'linked_doc': info['linked_doc'],
                                'sub_asm':    info['sub_asm'],
                                'child_obj':  info['child_obj'],
                                'count':      1,
                            })
                    for info in merged:
                        qty = info['count']
                        if info['sub_asm']:
                            sub_start = len(results)
                            traverse(info['sub_asm'], level + 1, results, _stack)
                            if sub_start < len(results):
                                results[sub_start]['qty'] = qty
                        else:
                            row_entry = extract_entry(info['child_obj'])
                            results.append({'level': level + 1, 'entry': row_entry, 'qty': qty})
                    _stack.discard(sk)

                # ================================================================
                # EXCEL WORKBOOK GENERATION
                # ================================================================

                def write_bom_excel(results, doc, save_path):
                    wb = Workbook()
                    ws = wb.active
                    ws.title = 'BOM'
                    num_cols = len(COLUMNS)

                    dark_blue  = PatternFill('solid', fgColor='003366')
                    mid_blue   = PatternFill('solid', fgColor='1F4E79')
                    light_grey = PatternFill('solid', fgColor='D9E2F3')
                    white_fill = PatternFill('solid', fgColor='FFFFFF')

                    title_font = Font(name='Calibri', bold=True, color='FFFFFF', size=12)
                    proj_font  = Font(name='Calibri', bold=True, color='FFFFFF', size=9)
                    hdr_font   = Font(name='Calibri', bold=True, color='FFFFFF', size=10)
                    data_font  = Font(name='Calibri', size=9)

                    thin_side  = Side(style='thin', color='000000')
                    border_all = Border(left=thin_side, right=thin_side,
                                         top=thin_side, bottom=thin_side)

                    center     = Alignment(horizontal='center', vertical='center',
                                           wrap_text=True)
                    left_align = Alignment(horizontal='left',   vertical='center',
                                           wrap_text=True)

                    for i, (_, w) in enumerate(COLUMNS, 1):
                        ws.column_dimensions[get_column_letter(i)].width = w

                    ws.merge_cells(start_row=1, start_column=1,
                                   end_row=1,   end_column=num_cols - 2)
                    title_cell = ws.cell(row=1, column=1)

                    asm_label = ''
                    if doc.FileName:
                        asm_label = os.path.splitext(os.path.basename(str(doc.FileName)))[0]
                        asm_label = re.sub(r'\.FCStd$', '', asm_label, flags=re.IGNORECASE)
                        asm_label = re.sub(r'\.(prt|asm|drg)$', '', asm_label, flags=re.IGNORECASE)
                        asm_label = re.sub(r'\.\d+$', '', asm_label)
                    else:
                        asm_label = doc.Name or 'Assembly'

                    root_asm = _find_root_asm(doc)

                    title_cell.value     = f'{asm_label} - BILL OF MATERIALS'
                    title_cell.font      = title_font
                    title_cell.fill      = dark_blue
                    title_cell.alignment = Alignment(horizontal='center', vertical='center')

                    for c in range(1, num_cols + 1):
                        cell = ws.cell(row=1, column=c)
                        cell.fill   = dark_blue
                        cell.font   = title_font
                        cell.border = border_all

                    ws.merge_cells(start_row=1, start_column=num_cols - 1,
                                   end_row=1,   end_column=num_cols)
                    proj_cell = ws.cell(row=1, column=num_cols - 1)
                    today = datetime.date.today().strftime('%Y-%m-%d')
                    rev = ''
                    if root_asm:
                        src = find_mp_source(root_asm)
                        if src:
                            rev = _mp(src, 'MP_Revision')
                    proj_cell.value     = f'PROJECT CODE :\nREV : {rev}    DATE : {today}'
                    proj_cell.font      = proj_font
                    proj_cell.fill      = dark_blue
                    proj_cell.alignment = Alignment(horizontal='left', vertical='center',
                                                    wrap_text=True)
                    ws.row_dimensions[1].height = 36

                    ws.merge_cells(start_row=2, start_column=BOM_COL_START,
                                   end_row=2,   end_column=BOM_COL_END)
                    bom_lbl = ws.cell(row=2, column=BOM_COL_START)
                    bom_lbl.value     = 'BOM TYPE'
                    bom_lbl.font      = hdr_font
                    bom_lbl.fill      = mid_blue
                    bom_lbl.alignment = center
                    bom_lbl.border    = border_all

                    for i, (hdr_name, _) in enumerate(COLUMNS, 1):
                        if BOM_COL_START <= i <= BOM_COL_END:
                            c3 = ws.cell(row=3, column=i)
                            c3.value     = hdr_name
                            c3.font      = hdr_font
                            c3.fill      = mid_blue
                            c3.alignment = center
                            c3.border    = border_all
                        else:
                            ws.merge_cells(start_row=2, start_column=i,
                                           end_row=3,   end_column=i)
                            c2 = ws.cell(row=2, column=i)
                            c2.value     = hdr_name
                            c2.font      = hdr_font
                            c2.fill      = mid_blue
                            c2.alignment = center
                            c2.border    = border_all

                    for r in (2, 3):
                        for c in range(1, num_cols + 1):
                            cell = ws.cell(row=r, column=c)
                            if cell.fill.fgColor is None or str(cell.fill.fgColor.index) == '00000000':
                                cell.fill = mid_blue
                            cell.border = border_all

                    ws.row_dimensions[2].height = 22
                    ws.row_dimensions[3].height = 22

                    DATA_START = 4
                    for idx, row_data in enumerate(results):
                        r   = DATA_START + idx
                        lvl = row_data['level']
                        e   = row_data['entry']
                        qty = row_data['qty']

                        values = [
                            idx + 1,
                            lvl,
                            e['part_number'],
                            e['description'],
                            qty,
                            e['ebom'],
                            e['mbom'],
                            e['sbom'],
                            e['revision'],
                            e['type'],
                            e['sub_type'],
                            e['material'],
                            e['identification'],
                            e['category'],
                            e['aggregate'],
                        ]

                        fill = white_fill if idx % 2 == 0 else light_grey
                        for c, val in enumerate(values, 1):
                            cell = ws.cell(row=r, column=c, value=val)
                            cell.font   = data_font
                            cell.fill   = fill
                            cell.border = border_all
                            if c in (1, 2, 5, 6, 7, 8, 9):
                                cell.alignment = center
                            else:
                                cell.alignment = left_align

                        ws.row_dimensions[r].height = 18

                    last_col = get_column_letter(num_cols)
                    last_row = DATA_START + len(results) - 1 if results else DATA_START
                    ws.auto_filter.ref = f'A3:{last_col}{last_row}'

                    ws.freeze_panes = 'A4'

                    wb.save(save_path)
                    return save_path

                # ================================================================
                # MAIN BOM EXPORT
                # ================================================================

                doc = App.ActiveDocument
                if not doc:
                    QtWidgets.QMessageBox.warning(None, 'BOM Export',
                                                  'No active document.')
                    return

                root_asm = _find_root_asm(doc)
                if not root_asm:
                    QtWidgets.QMessageBox.warning(None, 'BOM Export',
                                                  'No assembly found in the active document.')
                    return

                results = []
                traverse(root_asm, level=1, results=results)

                if not results:
                    QtWidgets.QMessageBox.warning(None, 'BOM Export',
                                                  'No components found in the assembly.')
                    return

                if doc.FileName:
                    directory = os.path.dirname(str(doc.FileName))
                else:
                    param = App.ParamGet('User parameter:BaseApp/Preferences/General')
                    directory = param.GetString('WorkingDirectory',
                                                os.path.expanduser('~'))

                asm_name = clean_doc_name(doc)
                today    = datetime.date.today().strftime('%Y%m%d')
                filename = f'BOM_{asm_name}_{today}.xlsx'
                save_path = os.path.join(directory, filename)

                final_path = save_path
                for attempt in range(20):
                    try:
                        write_bom_excel(results, doc, final_path)
                        break
                    except PermissionError:
                        base, ext = os.path.splitext(save_path)
                        final_path = f'{base}_{attempt + 1}{ext}'
                else:
                    QtWidgets.QMessageBox.critical(
                        None, 'BOM Export',
                        f'Cannot save BOM â€“ the file is locked.\n'
                        f'Please close it in Excel and try again.\n\n{save_path}'
                    )
                    return

                QtWidgets.QMessageBox.information(
                    None, 'BOM Export',
                    f'BOM exported successfully!\n\n{final_path}'
                )

                App.Console.PrintMessage(f'BOM saved â†’ {final_path}\n')

        FreeCADGui.addLanguagePath(":/translations")
        FreeCADGui.addIconPath(":/icons")
        # Add local Resources/icons directory for custom icons
        try:
            import inspect
            assembly_module_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            assembly_icons_path = os.path.join(assembly_module_dir, "Resources", "icons")
            if os.path.exists(assembly_icons_path):
                FreeCADGui.addIconPath(assembly_icons_path)
        except:
            pass

        # Define BNC Separate Window command class
        class CommandSeparateWindow:
            def GetResources(self):
                return {
                    'Pixmap': 'Assembly_SeparateWindow.svg',
                    'MenuText': 'Separate Window',
                    'ToolTip': 'Open selected component in separate window\n'
                               'Opens component side-by-side with assembly (Creo-style)\n'
                               'Select a component, then click this button.'
                }

            def IsActive(self):
                if App.ActiveDocument is None:
                    return False
                sel = Gui.Selection.getSelection()
                if not sel:
                    return False
                obj = sel[0]
                # Allow any Link, object with LinkedObject, or objects in Assembly context
                if obj.TypeId == "App::Link":
                    return True
                if "Link" in obj.TypeId:
                    return True
                if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
                    return True
                # Allow PartDesign::Body or Part::Feature if they have a Document (can be opened)
                if obj.TypeId in ("PartDesign::Body", "Part::Feature") and hasattr(obj, "Document") and obj.Document:
                    return True
                return False

            def Activated(self):
                import os
                candidates = [
                    os.path.join(App.getUserMacroDir(True), "SeparateWindow.FCMacro"),
                    os.path.join(App.getHomePath(), "Macro", "SeparateWindow.FCMacro"),
                    os.path.join(App.getResourceDir(), "Macro", "SeparateWindow.FCMacro"),
                ]
                macro_path = None
                for p in candidates:
                    if os.path.exists(p):
                        macro_path = p
                        break
                if macro_path:
                    with open(macro_path, encoding='utf-8') as fh:
                        ns = {'__name__': '__main__', '__file__': macro_path}
                        exec(compile(fh.read(), macro_path, 'exec'), ns)
                else:
                    from PySide import QtWidgets
                    QtWidgets.QMessageBox.warning(
                        None, "Macro Not Found",
                        "SeparateWindow.FCMacro not found.\n"
                        "Please ensure the macro is installed in your Macro folder.")

        try:
            import inspect as _inspect
            _dir = os.path.dirname(os.path.abspath(_inspect.getfile(_inspect.currentframe())))
            _icons = os.path.join(_dir, 'Resources', 'icons')
            if os.path.exists(_icons): FreeCADGui.addIconPath(_icons)
        except Exception: pass

        # Register BNC custom commands
        FreeCADGui.addCommand('Assembly_InsertFromWorkingDir', CommandInsertFromWorkingDir())
        FreeCADGui.addCommand('Assembly_CreatePartInAssembly', CommandCreatePartInAssembly())
        FreeCADGui.addCommand('Assembly_Default', CommandDefault())
        FreeCADGui.addCommand('Assembly_Regen', CommandRegen())
        FreeCADGui.addCommand('Assembly_BOM', CommandBOM())
        FreeCADGui.addCommand('Assembly_SeparateWindow', CommandSeparateWindow())


        FreeCADGui.addLanguagePath(":/translations")
        FreeCADGui.addIconPath(":/icons")

        FreeCADGui.addPreferencePage(
            Preferences.PreferencesPage, QT_TRANSLATE_NOOP("QObject", "Assembly")
        )

        # build commands list
        cmdList = [
            "Assembly_CreateAssembly",
            "Assembly_Insert",
            "Assembly_SolveAssembly",
            "Assembly_CreateView",
            "Assembly_CreateSimulation",
            "Assembly_CreateBom",
        ]

        cmdListMenuOnly = [
            "Assembly_ExportASMT",
        ]

        cmdListJoints = [
            "Assembly_ToggleGrounded",
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


        # BNC Custom Assembly Tools
        cmdListBNC = [
            'Assembly_CreatePartInAssembly',
            'Assembly_InsertFromWorkingDir',
            'Assembly_Default',
            'Assembly_Regen',
            'Assembly_BOM',
            'Assembly_SeparateWindow',
        ]

        self.appendToolbar(QT_TRANSLATE_NOOP('Workbench', 'BNC Assembly Tools'), cmdListBNC)

        self.appendMenu(
            [QT_TRANSLATE_NOOP('Workbench', '&Assembly')],
            cmdList + cmdListMenuOnly + ['Separator'] + cmdListJoints + ['Separator'] + cmdListBNC,
        )


        # Add task watchers to provide contextual tools in the task panel
        self.setWatchers()

    def Deactivated(self):
        FreeCADGui.Control.clearTaskWatcher()

    def ContextMenu(self, recipient):
        pass

    def setWatchers(self):
        import UtilsAssembly

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

        class AssemblyActivateWatcher:
            """Shows 'Activate Assembly' when an assembly exists but is not active."""

            def __init__(self):
                self.commands = ["Assembly_ActivateAssembly"]
                self.title = translate("Assembly", "Activate")

            def shouldShow(self):
                doc = FreeCAD.ActiveDocument

                has_assembly = False
                if hasattr(doc, "RootObjects"):
                    for obj in doc.RootObjects:
                        if obj.isDerivedFrom("Assembly::AssemblyObject"):
                            has_assembly = True
                            break

                assembly = UtilsAssembly.activeAssembly()

                return has_assembly and (assembly is None or assembly.Document != doc)

        class AssemblyBaseWatcher:
            """Base class for watchers that require an active assembly."""

            def __init__(self):
                self.assembly = None

            def shouldShow(self):
                doc = FreeCAD.ActiveDocument

                self.assembly = UtilsAssembly.activeAssembly()
                return self.assembly is not None and self.assembly.Document == doc

        class AssemblyInsertWatcher(AssemblyBaseWatcher):
            """Shows 'Insert Component' when an assembly is active."""

            def __init__(self):
                super().__init__()
                self.commands = ["Assembly_Insert"]
                self.title = translate("Assembly", "Insert")

            def shouldShow(self):
                return super().shouldShow()

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

        watchers = [
            AssemblyCreateWatcher(),
            AssemblyActivateWatcher(),
            AssemblyInsertWatcher(),
            AssemblyGroundWatcher(),
            AssemblyJointsWatcher(),
            AssemblyToolsWatcher(),
            AssemblySimulationWatcher(),
        ]
        FreeCADGui.Control.addTaskWatcher(watchers)


Gui.addWorkbench(AssemblyWorkbench())
