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
import time
import datetime
import zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App

from PySide.QtCore import QT_TRANSLATE_NOOP

if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtCore, QtGui, QtWidgets
    from PySide.QtGui import QIcon

import UtilsAssembly
import Preferences
import CommandCreateJoint

# ---------------------------------------------------------------------------
# Working-Directory helpers (versioned file support)
# ---------------------------------------------------------------------------

_VERSIONED_RE = re.compile(
    r"^(?P<base>.+?)\.(?P<ver>\d{3})"
    r"(?:\.(?P<ext>prt|asm|drg|stp|stl))?"
    r"\.fcstd$",
    re.IGNORECASE,
)


def _wd_get_working_directory():
    params = App.ParamGet("User parameter:BaseApp/Preferences/General")
    return params.GetString("WorkingDirectory", "")


def _wd_parse_versioned(filename):
    """Return (base, version_int, ext_lower_or_None) or None."""
    m = _VERSIONED_RE.match(filename)
    if not m:
        return None
    ext = m.group("ext")
    return (m.group("base"), int(m.group("ver")), ext.lower() if ext else None)


def _wd_collect_files(folder, show_all_versions=False, type_filter="All"):
    """Return sorted list of versioned .FCStd filenames in *folder*."""
    try:
        raw = [f for f in os.listdir(folder) if f.lower().endswith(".fcstd")]
    except OSError:
        return []

    parsed = []
    for f in raw:
        info = _wd_parse_versioned(f)
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


def _wd_format_size(n):
    if n < 1024:
        return "{} B".format(n)
    if n < 1024 * 1024:
        return "{:.1f} KiB".format(n / 1024.0)
    return "{:.1f} MiB".format(n / (1024.0 * 1024.0))


def _wd_extract_thumbnail(filepath):
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


def _wd_read_description(filepath):
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


def _wd_find_insert_object(doc):
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


__title__ = "Assembly Command Insert Component"
__author__ = "Ondsel"
__url__ = "https://www.freecad.org"


tooltip = QT_TRANSLATE_NOOP(
    "Assembly_InsertLink",
    "<p>Inserts a component into the active assembly. This will create dynamic links to parts, bodies, primitives, and assemblies. To insert external components, make sure that the file is <b>open in the current session</b></p>"
    "<ul>"
    "<li>Insert by left clicking items in the list.</li>"
    "<li>Remove by right clicking items in the list.</li>"
    "<li>Press shift to add several instances of the component while clicking on the view.</li>"
    "</ul>",
)


class CommandGroupInsert:
    def GetCommands(self):
        return ("Assembly_InsertLink",)

    def GetResources(self):
        """Set icon, menu and tooltip."""

        return {
            "Pixmap": "Assembly_InsertLink",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_Insert", "Insert Component"),
            "ToolTip": tooltip,
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()


class CommandInsertLink:
    def __init__(self):
        pass

    def GetResources(self):
        return {
            "Pixmap": "Assembly_InsertLink",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_InsertLink", "Component"),
            "Accel": "I",
            "ToolTip": tooltip,
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return UtilsAssembly.isAssemblyCommandActive()

    def Activated(self):
        assembly = UtilsAssembly.activeAssembly()
        if not assembly:
            return
        view = Gui.activeDocument().activeView()
        self.panel = TaskAssemblyInsertLink(assembly, view)
        Gui.Control.showDialog(self.panel)


class InsertLinkObserver:
    def __init__(self, callback):
        self.callback = callback

    def slotDeletedObject(self, obj):
        self.callback(obj)


class TaskAssemblyInsertLink(QtCore.QObject):
    def __init__(self, assembly, view):
        super().__init__()

        self.assembly = assembly
        self.view = view
        self.doc = App.ActiveDocument
        self.showHidden = False

        self.form = Gui.PySideUic.loadUi(":/panels/TaskAssemblyInsertLink.ui")
        self.form.installEventFilter(self)
        self.form.partList.installEventFilter(self)

        pref = Preferences.preferences()
        self.form.CheckBox_ShowOnlyParts.setChecked(pref.GetBool("InsertShowOnlyParts", False))
        self.form.CheckBox_RigidSubAsm.setChecked(pref.GetBool("InsertRigidSubAssemblies", True))

        # Actions
        self.form.openFileButton.clicked.connect(self.openFiles)
        self.form.partList.itemClicked.connect(self.onItemClicked)
        self.form.filterPartList.textChanged.connect(self.onFilterChange)
        self.form.CheckBox_ShowOnlyParts.stateChanged.connect(self.buildPartList)

        self.form.partList.header().hide()

        self.translation = 0
        # self.partMoving = False
        self.totalTranslation = App.Vector()
        self.prevScreenCenter = App.Vector()
        self.groundedObj = None

        self.insertionStack = []  # used to handle cancellation of insertions.
        self.doc_item_map = {}

        self.buildPartList()

        # ── Working Directory tab ──────────────────────────────────────────
        self._wd_desc_cache = {}
        self._wd_thumb_cache = {}
        self._wd_build_tab()

        App.setActiveTransaction("Insert Component")

        # Listen for external deletions to keep the list in sync
        self.docObserver = InsertLinkObserver(self.onObjectDeleted)
        App.addDocumentObserver(self.docObserver)

    # ── Working Directory tab ──────────────────────────────────────────────

    _WD_TYPES = ["All", "prt", "asm", "drg", "stp", "stl"]

    def _wd_build_tab(self):
        """Inject a QTabWidget into the loaded .ui form, moving existing
        content to 'Open Documents' and adding a 'Working Directory' tab."""

        # ------------------------------------------------------------------
        # Grab the form's top-level layout children so we can re-parent them
        # into a tab page.
        # ------------------------------------------------------------------
        form = self.form
        existing_layout = form.layout()

        # Collect all widgets currently in the form layout
        items = []
        while existing_layout.count():
            item = existing_layout.takeAt(0)
            if item.widget():
                items.append(item.widget())
            elif item.layout():
                # Wrap sub-layout in a container widget
                container = QtWidgets.QWidget()
                container.setLayout(item.layout())
                items.append(container)

        # Build "Open Documents" page from existing widgets
        open_doc_page = QtWidgets.QWidget()
        od_layout = QtWidgets.QVBoxLayout(open_doc_page)
        od_layout.setContentsMargins(4, 4, 4, 4)
        for w in items:
            od_layout.addWidget(w)

        # Build "Working Directory" page
        wd_page = QtWidgets.QWidget()
        wd_layout = QtWidgets.QVBoxLayout(wd_page)
        wd_layout.setContentsMargins(4, 4, 4, 4)
        wd_layout.setSpacing(4)

        # -- Nav bar: path label + search --
        nav = QtWidgets.QWidget()
        nav_lay = QtWidgets.QHBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(4)

        wd = _wd_get_working_directory()
        parts = wd.replace("\\", "/").split("/") if wd else []
        crumb = " > ".join(parts[-4:]) if len(parts) > 4 else " > ".join(parts) if parts else "(not set)"
        self._wd_path_lbl = QtWidgets.QLineEdit(crumb)
        self._wd_path_lbl.setReadOnly(True)
        self._wd_path_lbl.setToolTip(wd)
        nav_lay.addWidget(self._wd_path_lbl, 1)

        self._wd_search = QtWidgets.QLineEdit()
        self._wd_search.setPlaceholderText("Search...")
        self._wd_search.setFixedWidth(180)
        self._wd_search.setClearButtonEnabled(True)
        self._wd_search.textChanged.connect(self._wd_filter)
        nav_lay.addWidget(self._wd_search)
        wd_layout.addWidget(nav)

        # -- Stacked view: tree | detail table --
        self._wd_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        left_w = QtWidgets.QWidget()
        left_lay = QtWidgets.QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)

        self._wd_stack = QtWidgets.QStackedWidget()

        # View 0: tree (Name + Description)
        self._wd_tree = QtWidgets.QTreeWidget()
        self._wd_tree.setHeaderLabels(["Name", "Description"])
        self._wd_tree.setRootIsDecorated(False)
        self._wd_tree.setAlternatingRowColors(True)
        self._wd_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._wd_tree.header().setStretchLastSection(True)
        self._wd_tree.header().resizeSection(0, 280)
        self._wd_tree.currentItemChanged.connect(self._wd_tree_sel)
        self._wd_tree.itemDoubleClicked.connect(self._wd_tree_dbl)
        self._wd_stack.addWidget(self._wd_tree)

        # View 1: detail table
        self._wd_table = QtWidgets.QTableWidget()
        self._wd_table.setColumnCount(5)
        self._wd_table.setHorizontalHeaderLabels(["Name", "Description", "Size", "Type", "Date Modified"])
        self._wd_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._wd_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._wd_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._wd_table.verticalHeader().setVisible(False)
        self._wd_table.setSortingEnabled(True)
        self._wd_table.setAlternatingRowColors(True)
        hdr = self._wd_table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.resizeSection(0, 220)
        hdr.resizeSection(1, 140)
        hdr.resizeSection(2, 60)
        hdr.resizeSection(3, 45)
        self._wd_table.itemSelectionChanged.connect(self._wd_tbl_sel)
        self._wd_table.cellDoubleClicked.connect(self._wd_tbl_dbl)
        self._wd_stack.addWidget(self._wd_table)

        left_lay.addWidget(self._wd_stack)
        self._wd_splitter.addWidget(left_w)

        # Preview panel (right side of splitter)
        self._wd_preview_panel = QtWidgets.QFrame()
        self._wd_preview_panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        prev_lay = QtWidgets.QVBoxLayout(self._wd_preview_panel)
        prev_lay.setContentsMargins(4, 4, 4, 4)
        self._wd_thumb_lbl = QtWidgets.QLabel("No Preview")
        self._wd_thumb_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._wd_thumb_lbl.setMinimumSize(160, 160)
        self._wd_thumb_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        prev_lay.addWidget(self._wd_thumb_lbl, 1)
        self._wd_preview_panel.setVisible(False)
        self._wd_splitter.addWidget(self._wd_preview_panel)
        self._wd_splitter.setStretchFactor(0, 3)
        self._wd_splitter.setStretchFactor(1, 2)

        wd_layout.addWidget(self._wd_splitter, 1)

        # -- Info bar --
        self._wd_info_bar = QtWidgets.QLabel("")
        self._wd_info_bar.setWordWrap(True)
        self._wd_info_bar.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._wd_info_bar.setVisible(False)
        wd_layout.addWidget(self._wd_info_bar)

        # -- Bottom controls --
        bot_w = QtWidgets.QWidget()
        bot_lay = QtWidgets.QVBoxLayout(bot_w)
        bot_lay.setContentsMargins(0, 4, 0, 0)
        bot_lay.setSpacing(4)

        # File name row
        r_name = QtWidgets.QHBoxLayout()
        r_name.addWidget(QtWidgets.QLabel("File name:"))
        self._wd_name_edit = QtWidgets.QLineEdit()
        self._wd_name_edit.setReadOnly(True)
        r_name.addWidget(self._wd_name_edit, 1)
        self._wd_browse_btn = QtWidgets.QPushButton("Browse…")
        self._wd_browse_btn.setFixedWidth(80)
        self._wd_browse_btn.clicked.connect(self._wd_browse)
        r_name.addWidget(self._wd_browse_btn)
        bot_lay.addLayout(r_name)

        # Type filter row
        r_type = QtWidgets.QHBoxLayout()
        r_type.addWidget(QtWidgets.QLabel("Type:"))
        self._wd_type_cb = QtWidgets.QComboBox()
        for t in self._WD_TYPES:
            if t == "All":
                self._wd_type_cb.addItem("All types (*.FCStd)", "All")
            else:
                self._wd_type_cb.addItem("{} files (*.{}.FCStd)".format(t.upper(), t), t)
        self._wd_type_cb.currentIndexChanged.connect(self._wd_refresh)
        r_type.addWidget(self._wd_type_cb, 1)
        bot_lay.addLayout(r_type)

        # Checkboxes + Insert button
        r_btm = QtWidgets.QHBoxLayout()
        self._wd_all_ver_chk = QtWidgets.QCheckBox("Show all versions")
        self._wd_all_ver_chk.toggled.connect(self._wd_refresh)
        r_btm.addWidget(self._wd_all_ver_chk)
        r_btm.addSpacing(8)
        self._wd_details_chk = QtWidgets.QCheckBox("Show details")
        self._wd_details_chk.toggled.connect(
            lambda c: self._wd_stack.setCurrentIndex(1 if c else 0))
        r_btm.addWidget(self._wd_details_chk)
        r_btm.addSpacing(8)
        self._wd_preview_chk = QtWidgets.QCheckBox("Preview")
        self._wd_preview_chk.toggled.connect(self._wd_toggle_preview)
        r_btm.addWidget(self._wd_preview_chk)
        r_btm.addStretch()

        self._wd_insert_btn = QtWidgets.QPushButton("Insert")
        self._wd_insert_btn.setEnabled(False)
        self._wd_insert_btn.setDefault(False)
        self._wd_insert_btn.clicked.connect(self._wd_do_insert)
        r_btm.addWidget(self._wd_insert_btn)
        bot_lay.addLayout(r_btm)

        wd_layout.addWidget(bot_w)

        # -- Assemble tab widget --
        self._wd_tab = QtWidgets.QTabWidget()
        self._wd_tab.addTab(open_doc_page, "Open Documents")
        self._wd_tab.addTab(wd_page, "Working Directory")
        self._wd_tab.currentChanged.connect(self._wd_on_tab_changed)

        existing_layout.addWidget(self._wd_tab)

        # Initial population
        self._wd_refresh()

    def _wd_on_tab_changed(self, index):
        if index == 1:
            # Refresh working directory listing when tab is activated
            wd = _wd_get_working_directory()
            if wd:
                parts = wd.replace("\\", "/").split("/")
                crumb = " > ".join(parts[-4:]) if len(parts) > 4 else " > ".join(parts)
                self._wd_path_lbl.setText(crumb)
                self._wd_path_lbl.setToolTip(wd)
            self._wd_refresh()

    def _wd_cur_type(self):
        return self._wd_type_cb.itemData(self._wd_type_cb.currentIndex())

    def _wd_refresh(self, *_):
        wd = _wd_get_working_directory()
        if not wd or not os.path.isdir(wd):
            self._wd_tree.clear()
            self._wd_table.setRowCount(0)
            return

        files = _wd_collect_files(
            wd,
            show_all_versions=self._wd_all_ver_chk.isChecked(),
            type_filter=self._wd_cur_type())

        # Populate tree
        self._wd_tree.clear()
        for f in files:
            desc = self._wd_get_desc(wd, f)
            item = QtWidgets.QTreeWidgetItem([f, desc])
            item.setToolTip(0, f)
            if desc:
                item.setToolTip(1, desc)
            self._wd_tree.addTopLevelItem(item)

        # Populate table
        self._wd_table.setSortingEnabled(False)
        self._wd_table.setRowCount(0)
        for fname in files:
            fpath = os.path.join(wd, fname)
            desc = self._wd_get_desc(wd, fname)
            try:
                st = os.stat(fpath)
                sz = _wd_format_size(st.st_size)
                mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d-%m-%Y  %H:%M")
            except Exception:
                sz, mt = "", ""
            info = _wd_parse_versioned(fname)
            ft = info[2].upper() if info and info[2] else "FCStd"
            r = self._wd_table.rowCount()
            self._wd_table.insertRow(r)
            self._wd_table.setItem(r, 0, QtWidgets.QTableWidgetItem(fname))
            self._wd_table.setItem(r, 1, QtWidgets.QTableWidgetItem(desc))
            self._wd_table.setItem(r, 2, QtWidgets.QTableWidgetItem(sz))
            self._wd_table.setItem(r, 3, QtWidgets.QTableWidgetItem(ft))
            self._wd_table.setItem(r, 4, QtWidgets.QTableWidgetItem(mt))
        self._wd_table.setSortingEnabled(True)

        self._wd_name_edit.clear()
        self._wd_insert_btn.setEnabled(False)
        self._wd_info_bar.setVisible(False)
        self._wd_thumb_lbl.setText("No Preview")
        self._wd_filter()

    def _wd_filter(self):
        txt = self._wd_search.text().strip().lower()
        for i in range(self._wd_tree.topLevelItemCount()):
            it = self._wd_tree.topLevelItem(i)
            name_m = txt in it.text(0).lower() if txt else True
            desc_m = txt in it.text(1).lower() if txt else False
            it.setHidden(not (name_m or desc_m) if txt else False)
        for r in range(self._wd_table.rowCount()):
            it0 = self._wd_table.item(r, 0)
            it1 = self._wd_table.item(r, 1)
            if it0:
                name_m = txt in it0.text().lower() if txt else True
                desc_m = txt in (it1.text().lower() if it1 else "") if txt else False
                self._wd_table.setRowHidden(r, not (name_m or desc_m) if txt else False)

    def _wd_get_desc(self, folder, fname):
        key = os.path.join(folder, fname)
        if key not in self._wd_desc_cache:
            self._wd_desc_cache[key] = _wd_read_description(key)
        return self._wd_desc_cache[key]

    def _wd_get_thumb(self, folder, fname):
        key = os.path.join(folder, fname)
        if key not in self._wd_thumb_cache:
            self._wd_thumb_cache[key] = _wd_extract_thumbnail(key)
        return self._wd_thumb_cache[key]

    def _wd_set_selected(self, fname):
        self._wd_name_edit.setText(fname)
        self._wd_insert_btn.setEnabled(bool(fname))
        if self._wd_preview_panel.isVisible():
            self._wd_update_preview()

    def _wd_tree_sel(self, cur, prev):
        if cur:
            self._wd_set_selected(cur.text(0))

    def _wd_tree_dbl(self, item, col):
        if item:
            self._wd_name_edit.setText(item.text(0))
            self._wd_do_insert()

    def _wd_tbl_sel(self):
        rows = self._wd_table.selectionModel().selectedRows()
        if rows:
            it = self._wd_table.item(rows[0].row(), 0)
            if it:
                self._wd_set_selected(it.text())

    def _wd_tbl_dbl(self, row, col):
        it = self._wd_table.item(row, 0)
        if it:
            self._wd_name_edit.setText(it.text())
            self._wd_do_insert()

    def _wd_toggle_preview(self, checked):
        self._wd_preview_panel.setVisible(checked)
        if checked:
            self._wd_update_preview()

    def _wd_update_preview(self):
        fname = self._wd_name_edit.text().strip()
        wd = _wd_get_working_directory()
        if not fname or not wd:
            self._wd_thumb_lbl.setText("No Preview")
            self._wd_info_bar.setVisible(False)
            return

        pix = self._wd_get_thumb(wd, fname)
        if pix and not pix.isNull():
            avail = self._wd_thumb_lbl.size()
            tw = max(avail.width() - 12, 120)
            th = max(avail.height() - 12, 120)
            scaled = pix.scaled(tw, th, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self._wd_thumb_lbl.setPixmap(scaled)
        else:
            self._wd_thumb_lbl.setText("No Preview Available")

        fpath = os.path.join(wd, fname)
        desc = self._wd_get_desc(wd, fname)
        try:
            st = os.stat(fpath)
            mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d-%b-%Y  %I:%M:%S %p")
        except Exception:
            mt = ""
        info_parts = ["<b>File:</b> {}".format(fname)]
        if mt:
            info_parts.append("<b>Modified:</b> {}".format(mt))
        if desc:
            info_parts.append("<b>Description:</b> {}".format(desc))
        self._wd_info_bar.setText("  &nbsp;&nbsp;  ".join(info_parts))
        self._wd_info_bar.setVisible(True)

    def _wd_browse(self):
        """Let the user pick any .FCStd file from any location."""
        wd = _wd_get_working_directory() or ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Select FreeCAD File",
            wd,
            "FreeCAD Document (*.FCStd *.fcstd);;All files (*)",
        )
        if not path:
            return

        # Store the full absolute path so _wd_do_insert can find it
        self._wd_browse_path = os.path.abspath(path)
        self._wd_name_edit.setText(os.path.basename(path))
        self._wd_insert_btn.setEnabled(True)

        # Show info bar
        desc = _wd_read_description(self._wd_browse_path)
        try:
            st = os.stat(self._wd_browse_path)
            mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d-%b-%Y  %I:%M:%S %p")
        except Exception:
            mt = ""
        info_parts = ["<b>File:</b> {}".format(os.path.basename(path))]
        if mt:
            info_parts.append("<b>Modified:</b> {}".format(mt))
        if desc:
            info_parts.append("<b>Description:</b> {}".format(desc))
        self._wd_info_bar.setText("  &nbsp;&nbsp;  ".join(info_parts))
        self._wd_info_bar.setVisible(True)

        # Update preview if enabled
        if self._wd_preview_panel.isVisible():
            pix = _wd_extract_thumbnail(self._wd_browse_path)
            if pix and not pix.isNull():
                avail = self._wd_thumb_lbl.size()
                tw = max(avail.width() - 12, 120)
                th = max(avail.height() - 12, 120)
                scaled = pix.scaled(tw, th, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self._wd_thumb_lbl.setPixmap(scaled)
            else:
                self._wd_thumb_lbl.setText("No Preview Available")

    def _wd_do_insert(self):
        """Open the selected versioned file and insert it as a link, then accept."""
        fname = self._wd_name_edit.text().strip()
        if not fname:
            return

        wd = _wd_get_working_directory()

        # If the user picked a file via Browse, use that full path directly;
        # otherwise build the path from the working directory.
        browse_path = getattr(self, "_wd_browse_path", None)
        if browse_path and os.path.basename(browse_path) == fname:
            filepath = browse_path
        else:
            self._wd_browse_path = None  # clear stale browse path
            if not wd:
                QtWidgets.QMessageBox.warning(None, "Error", "Working Directory is not set.")
                return
            filepath = os.path.join(wd, fname)

        if not os.path.isfile(filepath):
            QtWidgets.QMessageBox.warning(None, "Error", "File not found:\n{}".format(filepath))
            return

        target_doc = self.doc
        if not target_doc.FileName:
            msgBox = QtWidgets.QMessageBox()
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText("The current document must be saved before inserting external parts.")
            msgBox.setWindowTitle("Save Document")
            saveButton = msgBox.addButton("Save", QtWidgets.QMessageBox.AcceptRole)
            msgBox.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
            msgBox.exec_()
            if msgBox.clickedButton() != saveButton:
                return
            # Open save dialog starting at the working directory
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                None,
                "Save Assembly",
                os.path.join(wd, "Unnamed.FCStd"),
                "FreeCAD Document (*.FCStd)",
            )
            if not save_path:
                return
            target_doc.saveAs(save_path)
            if not target_doc.FileName:
                return

        abs_path = os.path.abspath(filepath)

        # Find or open source document
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
                QtWidgets.QMessageBox.warning(
                    None, "Error", "Failed to open file:\n{}\n\n{}".format(filepath, e))
                return

        # Re-activate target assembly document
        App.setActiveDocument(target_doc.Name)
        Gui.setActiveDocument(target_doc.Name)
        target_doc = App.getDocument(target_doc.Name)

        source_obj = _wd_find_insert_object(source_doc)
        if not source_obj:
            QtWidgets.QMessageBox.warning(None, "Error",
                                          "No insertable object found in:\n{}".format(fname))
            if not already_open:
                App.closeDocument(source_doc.Name)
            return

        # Determine link type
        if source_obj.TypeId == "Assembly::AssemblyObject":
            obj_type = "Assembly::AssemblyLink"
        else:
            obj_type = "App::Link"

        pgrp = App.ParamGet("User parameter:BaseApp/Preferences/Document")
        pgrp.SetBool("DuplicateLabels", True)

        added_object = self.assembly.newObject(obj_type, source_obj.Label)
        added_object.LinkedObject = source_obj
        added_object.Label = source_obj.Label
        added_object.recompute()

        # Position at screen centre
        view = Gui.activeView()
        x, y = view.getSize()
        screen_center = view.getPointOnFocalPlane(x // 2, y // 2)
        try:
            bbox_center = added_object.ViewObject.getBoundingBox().Center
            added_object.Placement.Base = screen_center - bbox_center
        except Exception:
            added_object.Placement.Base = screen_center

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(target_doc.Name, added_object.Name, "")

        insertion_dict = {
            "addedObject": added_object,
            "translation": App.Vector(),
            "item": None,
        }
        self.insertionStack.append(insertion_dict)

        # Clear browse path after use
        self._wd_browse_path = None

        # Accept immediately (single-insert mode)
        Gui.Control.closeDialog()

    # ── End Working Directory tab ──────────────────────────────────────────

    def accept(self):
        self.deactivated()

        Gui.addModule("UtilsAssembly")
        commands = "assembly = UtilsAssembly.activeAssembly()\n"
        for insertionItem in self.insertionStack:
            object = insertionItem["addedObject"]
            translation = insertionItem["translation"]

            # Check if object.Name & object.LinkedObject.Name exists
            if (
                not hasattr(object, "Name")
                or not hasattr(object, "LinkedObject")
                or not hasattr(object.LinkedObject, "Name")
            ):
                continue

            commands = commands + (
                f'item = assembly.newObject("App::Link", "{object.Name}")\n'
                f'item.LinkedObject = App.ActiveDocument.getObject("{object.LinkedObject.Name}")\n'
                f'item.Label = "{object.Label}"\n'
            )

            if translation != App.Vector():
                commands = commands + (
                    f"item.Placement.base = App.Vector({translation.x},"
                    f"{translation.y},"
                    f"{translation.z})\n"
                )

        # Ground the first item if that happened
        if self.groundedObj:
            commands = (
                commands
                + f'CommandCreateJoint.createGroundedJoint(App.ActiveDocument.getObject("{self.groundedObj.Name}"))\n'
            )

        Gui.doCommandSkip(commands[:-1])  # Get rid of last \n
        App.closeActiveTransaction()
        return True

    def reject(self):
        self.deactivated()

        App.closeActiveTransaction(True)
        return True

    def deactivated(self):
        if hasattr(self, "docObserver") and self.docObserver:
            App.removeDocumentObserver(self.docObserver)
            self.docObserver = None

        pref = Preferences.preferences()
        pref.SetBool("InsertShowOnlyParts", self.form.CheckBox_ShowOnlyParts.isChecked())
        pref.SetBool("InsertRigidSubAssemblies", self.form.CheckBox_RigidSubAsm.isChecked())
        Gui.Selection.clearSelection()

    def buildPartList(self):
        self.form.partList.clear()
        self.doc_item_map.clear()

        docList = App.listDocuments().values()

        for doc in docList:
            # Create a new tree item for the document
            docItem = QtGui.QTreeWidgetItem()
            itemName = doc.Label
            icon = QIcon.fromTheme("add", QIcon(":/icons/Document.svg"))
            if doc.Partial:
                itemName = (
                    itemName + " (" + QT_TRANSLATE_NOOP("Assembly_Insert", "Partially loaded") + ")"
                )
                icon = self.createDisabledIcon(icon)
            docItem.setText(0, itemName)
            docItem.setIcon(0, icon)
            self.doc_item_map[docItem] = doc

            if not any(
                (child.isDerivedFrom("Part::Feature") or child.isDerivedFrom("App::Part"))
                for child in doc.Objects
            ):
                continue  # Skip this doc if no relevant objects

            self.form.partList.addTopLevelItem(docItem)

            def process_objects(objs, item):
                onlyParts = self.form.CheckBox_ShowOnlyParts.isChecked()
                for obj in objs:
                    if obj == self.assembly:
                        continue  # Skip current assembly

                    if obj in self.assembly.InListRecursive:
                        continue  # Prevent dependency loop.
                        # For instance if asm1/asm2 with asm2 active, we don't want to have asm1 in the list

                    if not obj.ViewObject.ShowInTree and not self.showHidden:
                        continue

                    if (
                        obj.isDerivedFrom("Part::Feature")
                        or obj.isDerivedFrom("App::Part")
                        or obj.isDerivedFrom("App::DocumentObjectGroup")
                    ):
                        # Special handling for DocumentObjectGroup: only add if it contains relevant child objects
                        if obj.isDerivedFrom("App::DocumentObjectGroup"):
                            if not any(
                                (
                                    (not onlyParts and child.isDerivedFrom("Part::Feature"))
                                    or child.isDerivedFrom("App::Part")
                                )
                                for child in obj.ViewObject.claimChildrenRecursive()
                            ):
                                continue  # Skip this object if no relevant children

                        if obj.isDerivedFrom("Part::Feature"):
                            if onlyParts:
                                continue  # Ignore solids if we show only Parts

                        # Now add the object under the document item
                        objItem = QtGui.QTreeWidgetItem(item)
                        objItem.setText(0, obj.Label)
                        objItem.setIcon(
                            0, obj.ViewObject.Icon if hasattr(obj, "ViewObject") else QtGui.QIcon()
                        )  # Use object's icon if available

                        if not obj.isDerivedFrom("App::DocumentObjectGroup"):
                            objItem.setData(0, QtCore.Qt.UserRole, obj)

                        if obj.isDerivedFrom("App::Part") or obj.isDerivedFrom(
                            "App::DocumentObjectGroup"
                        ):
                            process_objects(obj.ViewObject.claimChildren(), objItem)

            guiDoc = Gui.getDocument(doc.Name)
            process_objects(guiDoc.TreeRootObjects, docItem)
            self.form.partList.expandAll()

        self.adjustTreeWidgetSize()

    def adjustTreeWidgetSize(self):
        # Adjust the height of the part list based on item count
        item_count = 1

        def count_items(item):
            nonlocal item_count
            item_count += 1
            for i in range(item.childCount()):
                count_items(item.child(i))

        for i in range(self.form.partList.topLevelItemCount()):
            count_items(self.form.partList.topLevelItem(i))

        item_height = self.form.partList.sizeHintForRow(0)
        total_height = item_count * item_height
        max_height = 500

        self.form.partList.setMinimumHeight(min(total_height, max_height))

    def onFilterChange(self):
        filter_str = self.form.filterPartList.text().strip().lower()

        def filter_tree_item(item):
            # This function recursively filters items based on the filter string.
            item_text = item.text(0).lower()  # Assuming the relevant text is in the first column
            is_visible = filter_str in item_text if filter_str else True

            child_count = item.childCount()
            for i in range(child_count):
                child = item.child(i)
                child_is_visible = filter_tree_item(child)  # Recursively filter children
                is_visible = (
                    is_visible or child_is_visible
                )  # Parent is visible if any child matches

            item.setHidden(not is_visible)
            return is_visible

        root_count = self.form.partList.topLevelItemCount()
        for i in range(root_count):
            root_item = self.form.partList.topLevelItem(i)
            filter_tree_item(root_item)  # Filter from each root item

    def openFiles(self):
        selected_files, _ = QtGui.QFileDialog.getOpenFileNames(
            None,
            "Select FreeCAD documents to import parts from",
            "",
            "Supported Formats (*.FCStd *.fcstd);;All files (*)",
        )

        for filename in selected_files:
            requested_file = os.path.split(filename)[1]
            import_doc_is_open = any(
                requested_file == os.path.split(doc.FileName)[1]
                for doc in App.listDocuments().values()
            )

            if not import_doc_is_open:
                if filename.lower().endswith(".fcstd"):
                    App.openDocument(filename, True)
                    App.setActiveDocument(self.doc.Name)
                    self.buildPartList()

    def onItemClicked(self, item):
        selectedPart = item.data(0, QtCore.Qt.UserRole)
        if not selectedPart:
            # If there's no part associated, toggle the expanded state
            item.setExpanded(not item.isExpanded())
            return

        # check that the current document had been saved or that it's the same document as that of the selected part
        if not self.doc == selectedPart.Document:
            if self.doc.FileName == "":
                msgBox = QtWidgets.QMessageBox()
                msgBox.setIcon(QtWidgets.QMessageBox.Warning)
                msgBox.setText(
                    "The current document must be saved before inserting external parts."
                )
                msgBox.setWindowTitle("Save Document")
                saveButton = msgBox.addButton("Save", QtWidgets.QMessageBox.AcceptRole)
                cancelButton = msgBox.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)

                msgBox.exec_()

                if not (msgBox.clickedButton() == saveButton and Gui.ActiveDocument.saveAs()):
                    return

            # check that the selectedPart document is saved.
            if selectedPart.Document.FileName == "":
                msgBox = QtWidgets.QMessageBox()
                msgBox.setIcon(QtWidgets.QMessageBox.Warning)
                msgBox.setText("The selected object's document must be saved before inserting it.")
                msgBox.setWindowTitle("Save Document")
                saveButton = msgBox.addButton("Save", QtWidgets.QMessageBox.AcceptRole)
                cancelButton = msgBox.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)

                msgBox.exec_()

                if not (
                    msgBox.clickedButton() == saveButton
                    and selectedPart.ViewObject.Document.saveAs()
                ):
                    return

                # Update the document item text - useless because Document.Name still return 'Unnamed'
                """documentItem = item
                while documentItem.parent() is not None:
                    documentItem = documentItem.parent()
                newDocName = selectedPart.Document.Name
                print(selectedPart.Document.Name)
                documentItem.setText(0, f"{newDocName}.FCStd")"""

        if selectedPart.isDerivedFrom("Assembly::AssemblyObject"):
            objType = "Assembly::AssemblyLink"
        else:
            objType = "App::Link"

        addedObject = self.assembly.newObject(objType, selectedPart.Label)

        # set placement of the added object to the center of the screen.
        view = Gui.activeView()
        x, y = view.getSize()
        screenCenter = view.getPointOnFocalPlane(x // 2, y // 2)
        screenCorner = view.getPointOnFocalPlane(x, y)

        addedObject.LinkedObject = selectedPart
        addedObject.Label = selectedPart.Label  # non-ASCII characters fails with newObject. #12164
        addedObject.recompute()

        insertionDict = {}
        insertionDict["item"] = item
        insertionDict["addedObject"] = addedObject
        self.insertionStack.append(insertionDict)
        self.increment_counter(item)

        translation = App.Vector()
        resetThreshold = (screenCorner - screenCenter).Length * 0.1
        if len(self.insertionStack) == 1:
            translation = App.Vector()  # No translation for first object.
        elif (self.prevScreenCenter - screenCenter).Length > resetThreshold:
            self.totalTranslation = App.Vector()
            self.prevScreenCenter = screenCenter
        else:
            translation = self.getTranslationVec(addedObject)

        insertionDict["translation"] = translation
        self.totalTranslation += translation

        originX, originY = view.getPointOnViewport(App.Vector() + translation)
        if originX > 0 and originX < x and originY > 0 and originY < y:
            # If the origin is within view then we insert at the origin.
            addedObject.Placement.Base = self.totalTranslation
        else:
            #
            bboxCenter = addedObject.ViewObject.getBoundingBox().Center
            addedObject.Placement.Base = screenCenter - bboxCenter + self.totalTranslation

        self.prevScreenCenter = screenCenter

        # We turn it flexible after changing the position so that it uses the logic in
        # AssemblyLink::onChanged to handle positioning correctly.
        if selectedPart.isDerivedFrom("Assembly::AssemblyObject"):
            addedObject.Rigid = self.form.CheckBox_RigidSubAsm.isChecked()

        # highlight the link
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(self.doc.Name, addedObject.Name, "")

        item.setSelected(False)

        if len(self.insertionStack) == 1 and not UtilsAssembly.isAssemblyGrounded():
            self.handleFirstInsertion()

    def handleFirstInsertion(self):
        pref = Preferences.preferences()
        fixPart = False
        fixPartPref = pref.GetInt("GroundFirstPart", 0)
        if fixPartPref == 0:  # unset
            msgBox = QtWidgets.QMessageBox()
            msgBox.setWindowTitle("Ground Part?")
            msgBox.setText(
                "Do you want to ground the first inserted part automatically?\nYou need at least one grounded part in your assembly."
            )
            msgBox.setIcon(QtWidgets.QMessageBox.Question)

            yesButton = msgBox.addButton("Yes", QtWidgets.QMessageBox.YesRole)
            noButton = msgBox.addButton("No", QtWidgets.QMessageBox.RejectRole)
            yesAlwaysButton = msgBox.addButton("Always", QtWidgets.QMessageBox.YesRole)
            noAlwaysButton = msgBox.addButton("Never", QtWidgets.QMessageBox.NoRole)

            msgBox.exec_()

            clickedButton = msgBox.clickedButton()
            if clickedButton == yesButton:
                fixPart = True
            elif clickedButton == yesAlwaysButton:
                fixPart = True
                pref.SetInt("GroundFirstPart", 1)
            elif clickedButton == noAlwaysButton:
                pref.SetInt("GroundFirstPart", 2)

        elif fixPartPref == 1:  # Yes always
            fixPart = True

        if fixPart:
            # Create groundedJoint.
            if len(self.insertionStack) != 1:
                return

            targetObj = self.insertionStack[0]["addedObject"]

            # If the object is a flexible AssemblyLink, we should ground its internal 'base' part
            if targetObj.isDerivedFrom("Assembly::AssemblyLink") and not targetObj.Rigid:
                linkedAsm = targetObj.LinkedObject
                if linkedAsm and hasattr(linkedAsm, "Group"):
                    srcGrounded = None
                    # Attempt to find the grounded joint in the source assembly
                    # We look for a joint where JointType is 'Grounded'
                    for obj in linkedAsm.InListRecursive:
                        if hasattr(obj, "ObjectToGround"):
                            srcGrounded = obj.ObjectToGround
                            break

                    # Search the sub-assembly group for the link pointing to the source grounded object
                    # Fallback to the first valid part if no grounded joint was found in source
                    candidate = None
                    for child in targetObj.Group:
                        if not candidate and (
                            child.isDerivedFrom("App::Link") or child.isDerivedFrom("Part::Feature")
                        ):
                            candidate = child

                        if (
                            srcGrounded
                            and hasattr(child, "LinkedObject")
                            and child.LinkedObject == srcGrounded
                        ):
                            candidate = child
                            break

                    if not candidate:  # Nothing to ground
                        return

                    targetObj = candidate

            self.groundedObj = targetObj
            self.groundedJoint = CommandCreateJoint.createGroundedJoint(self.groundedObj)

    def increment_counter(self, item):
        text = item.text(0)
        match = re.search(r"(\d+) inserted$", text)

        if match:
            # Counter exists, increment it
            counter = int(match.group(1)) + 1
            new_text = re.sub(r"\d+ inserted$", f"{counter} inserted", text)
        else:
            # Counter does not exist, add it
            new_text = f"{text} : 1 inserted"

        item.setText(0, new_text)

    def decrement_counter(self, item):
        text = item.text(0)
        match = re.search(r"(\d+) inserted$", text)

        if match:
            counter = int(match.group(1)) - 1
            if counter > 0:
                # Update the counter
                new_text = re.sub(r"\d+ inserted$", f"{counter} inserted", text)
            elif counter == 0:
                # Remove the counter part from the text
                new_text = re.sub(r" : \d+ inserted$", "", text)
            else:
                return

            item.setText(0, new_text)

    """def clickMouse(self, info):
        if info["Button"] == "BUTTON1" and info["State"] == "DOWN":
            Gui.Selection.clearSelection()
            if info["ShiftDown"]:
                # Create a new link and moves this one now
                addedObject = self.insertionStack[-1]["addedObject"]
                currentPos = addedObject.Placement.Base
                selectedPart = addedObject
                if addedObject.TypeId == "App::Link":
                    selectedPart = addedObject.LinkedObject

                addedObject = self.assembly.newObject("App::Link", selectedPart.Label)
                addedObject.LinkedObject = selectedPart
                addedObject.Placement.Base = currentPos

                insertionDict = {}
                insertionDict["translation"] = App.Vector()
                insertionDict["item"] = self.insertionStack[-1]["item"]
                insertionDict["addedObject"] = addedObject
                self.insertionStack.append(insertionDict)

            else:
                self.endMove()

        elif info["Button"] == "BUTTON2" and info["State"] == "DOWN":
            self.dismissPart()"""

    # Taskbox keyboard event handler
    def eventFilter(self, watched, event):

        if event.type() == QtCore.QEvent.ContextMenu and watched is self.form.partList:
            item = watched.itemAt(event.pos())

            if item:
                if item.parent() is None:
                    doc = self.doc_item_map.get(item)
                    if doc and doc.Partial:
                        menu = QtWidgets.QMenu()
                        load_action_text = QT_TRANSLATE_NOOP(
                            "Assembly_Insert", "Fully load document"
                        )
                        load_action = menu.addAction(load_action_text)
                        load_action.triggered.connect(lambda: self.fullyLoadDocument(doc))
                        menu.exec_(event.globalPos())
                        return True  # Event was handled

                # Iterate through the insertionStack in reverse
                for i in reversed(range(len(self.insertionStack))):
                    stack_item = self.insertionStack[i]

                    if stack_item["item"] == item:
                        obj = stack_item["addedObject"]

                        # ONLY remove the object from the document.
                        # The Observer (onObjectDeleted) will handle the rest.
                        if obj and obj.Document:
                            UtilsAssembly.removeObjAndChilds(obj)

                        return True
            else:
                menu = QtWidgets.QMenu()

                # Add the checkbox action
                showHiddenAction = QtWidgets.QAction("Show objects hidden in tree view", menu)
                showHiddenAction.setCheckable(True)
                showHiddenAction.setChecked(self.showHidden)

                # Connect the action to toggle `self.showHidden`
                showHiddenAction.toggled.connect(self.toggleShowHidden)
                menu.addAction(showHiddenAction)
                menu.exec_(event.globalPos())
                return True

        return super().eventFilter(watched, event)

    def fullyLoadDocument(self, doc_to_load):
        """Closes and re-opens a document to load it fully."""
        if not doc_to_load.FileName:
            return

        # Save UI state
        scrollbar = self.form.partList.verticalScrollBar()
        scroll_position = scrollbar.value()

        # Perform the reload
        App.open(doc_to_load.FileName)
        App.setActiveDocument(self.doc.Name)

        # Refresh the UI
        self.buildPartList()

        # Restore UI state
        scrollbar.setValue(scroll_position)

    def createDisabledIcon(self, icon):
        if icon.isNull():
            return QIcon()

        # Get a pixmap from the icon at a standard size
        pixmap = icon.pixmap(icon.actualSize(QtCore.QSize(16, 16)))

        # Ask the application's style to generate a disabled version of the pixmap
        style = QtWidgets.QApplication.style()
        disabled_pixmap = style.generatedIconPixmap(
            QtGui.QIcon.Disabled, pixmap, QtWidgets.QStyleOption()
        )

        return QIcon(disabled_pixmap)

    def toggleShowHidden(self, checked):
        self.showHidden = checked
        self.buildPartList()

    def getTranslationVec(self, part):
        bb = part.Shape.BoundBox
        if bb:
            translation = (bb.XMax + bb.YMax + bb.ZMax) * 0.15
        else:
            translation = 10
        return App.Vector(translation, translation, translation)

    def onObjectDeleted(self, obj):
        """
        Handles cleanup when an object is deleted (via Right Click OR Tree View).
        """
        # Iterate backwards to safely delete
        for i in reversed(range(len(self.insertionStack))):
            stack_item = self.insertionStack[i]

            if stack_item["addedObject"] == obj:
                # 1. Revert translation
                self.totalTranslation -= stack_item["translation"]

                # 2. Update UI counter
                item = stack_item["item"]
                if item is not None:
                    self.decrement_counter(item)

                # 3. Handle Grounded Joint cleanup
                if self.groundedObj == obj:
                    if self.groundedJoint:
                        try:
                            # Remove the joint if it still exists
                            if self.groundedJoint.Document:
                                self.groundedJoint.Document.removeObject(self.groundedJoint.Name)
                        except Exception:
                            pass
                    self.groundedObj = None
                    self.groundedJoint = None

                # 4. Remove from stack
                del self.insertionStack[i]

                # 5. Clear selection
                if item:
                    item.setSelected(False)


if App.GuiUp:
    Gui.addCommand("Assembly_InsertLink", CommandInsertLink())
    Gui.addCommand("Assembly_Insert", CommandGroupInsert())
