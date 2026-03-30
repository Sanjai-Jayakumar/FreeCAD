# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# ***************************************************************************
# *   Copyright (c) 2024 BNC CAD                                            *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# ***************************************************************************

"""Version Open command for BNC CAD - Open version-controlled documents"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import re
import datetime
import zipfile
import xml.etree.ElementTree as ET


# ============================================================
# GET WORKING DIRECTORY
# ============================================================

def get_working_directory():
    params = App.ParamGet("User parameter:BaseApp/Preferences/General")
    return params.GetString("WorkingDirectory", "")


# ============================================================
# VERSIONED FILENAME PATTERN
# ============================================================
# Matches Save-macro names:  base.001.prt.FCStd  /  base.002.asm.FCStd
# Also matches plain:        base.001.FCStd

VERSIONED_RE = re.compile(
    r"^(?P<base>.+?)\.(?P<ver>\d{3})"
    r"(?:\.(?P<ext>prt|asm|drg|stp|stl))?"
    r"\.fcstd$",
    re.IGNORECASE,
)


def parse_versioned(filename):
    """(base, version_int, ext_lower_or_None) or None."""
    m = VERSIONED_RE.match(filename)
    if not m:
        return None
    ext = m.group("ext")
    return (m.group("base"), int(m.group("ver")), ext.lower() if ext else None)


# ============================================================
# COLLECT FILES
# ============================================================

def collect_files(folder, show_all_versions=False, type_filter="All"):
    """
    Return sorted list of versioned .FCStd filenames.
    type_filter : "All" | "prt" | "asm" | "drg" | "stp" | "stl"
    """
    raw = [f for f in os.listdir(folder) if f.lower().endswith(".fcstd")]

    parsed = []
    for f in raw:
        info = parse_versioned(f)
        if info:
            parsed.append((f, info[0], info[1], info[2]))

    # Type filter
    if type_filter != "All":
        tf = type_filter.lower()
        parsed = [p for p in parsed if p[3] == tf]

    # Latest only
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


# ============================================================
# THUMBNAIL & DESCRIPTION FROM .FCStd
# ============================================================

def extract_thumbnail(filepath):
    """Extract thumbnail PNG from FCStd (ZIP) -> QPixmap or None."""
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


# ============================================================
# DIALOG
# ============================================================

class OpenFileDialog(QtGui.QDialog):

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
        super(OpenFileDialog, self).__init__(parent)
        self.folder = folder
        self.selected_file = None
        self._desc_cache = {}
        self._thumb_cache = {}

        self.setWindowTitle("Open File")
        self.setMinimumSize(750, 560)
        self.resize(820, 620)
        self.setStyleSheet(self._STYLE)

        self._build_ui()
        self._refresh()

    # ────────────────────────────────────────────────────
    #  BUILD UI
    # ────────────────────────────────────────────────────
    def _build_ui(self):
        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ======= NAV BAR =======
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

        # ======= MAIN CONTENT AREA (splitter: files | preview) =======
        self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)

        # LEFT: stacked file views
        left_widget = QtGui.QWidget()
        left_lay = QtGui.QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 0, 0)

        self.stack = QtGui.QStackedWidget()

        # --- View 0: Tree with Name + Description columns ---
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

        # --- View 1: Detail table ---
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

        # RIGHT: Preview panel
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

        # ======= INFO BAR =======
        self.info_bar = QtGui.QLabel("")
        self.info_bar.setObjectName("infoBar")
        self.info_bar.setWordWrap(True)
        self.info_bar.setVisible(False)
        root.addWidget(self.info_bar)

        # ======= BOTTOM PANEL =======
        bottom = QtGui.QFrame()
        bottom.setObjectName("bottomPanel")
        bot_lay = QtGui.QVBoxLayout(bottom)
        bot_lay.setContentsMargins(0, 8, 0, 0)
        bot_lay.setSpacing(6)

        # File name row
        r_name = QtGui.QHBoxLayout()
        lbl_name = QtGui.QLabel("File name:")
        lbl_name.setFixedWidth(75)
        self.name_edit = QtGui.QLineEdit()
        self.name_edit.setReadOnly(True)
        r_name.addWidget(lbl_name)
        r_name.addWidget(self.name_edit, 1)
        bot_lay.addLayout(r_name)

        # Type row
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

        # Checkboxes + buttons
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

    # ────────────────────────────────────────────────────
    #  HELPERS
    # ────────────────────────────────────────────────────
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

    # ────────────────────────────────────────────────────
    #  REFRESH
    # ────────────────────────────────────────────────────
    def _refresh(self, *_):
        files = collect_files(
            self.folder,
            show_all_versions=self.all_ver.isChecked(),
            type_filter=self._cur_type())

        # Tree (Name + Description)
        self.tree.clear()
        for f in files:
            desc = self._get_desc(f)
            item = QtGui.QTreeWidgetItem([f, desc])
            item.setToolTip(0, f)
            if desc:
                item.setToolTip(1, desc)
            self.tree.addTopLevelItem(item)

        # Table (Name, Description, Size, Type, Date)
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

    # ────────────────────────────────────────────────────
    #  SEARCH
    # ────────────────────────────────────────────────────
    def _filter(self):
        txt = self.search.text().strip().lower()
        # Tree
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            name_match = txt in it.text(0).lower() if txt else True
            desc_match = txt in it.text(1).lower() if txt else False
            it.setHidden(not (name_match or desc_match) if txt else False)
        # Table
        for r in range(self.table.rowCount()):
            it0 = self.table.item(r, 0)
            it1 = self.table.item(r, 1)
            if it0:
                name_match = txt in it0.text().lower() if txt else True
                desc_match = txt in (it1.text().lower() if it1 else "") if txt else False
                self.table.setRowHidden(
                    r, not (name_match or desc_match) if txt else False)

    # ────────────────────────────────────────────────────
    #  PREVIEW
    # ────────────────────────────────────────────────────
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

        # Info bar
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

    # ────────────────────────────────────────────────────
    #  SLOTS
    # ────────────────────────────────────────────────────
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


# ============================================================
# MAIN
# ============================================================

def main():
    wd = get_working_directory()
    if not wd or not os.path.exists(wd):
        QtGui.QMessageBox.warning(None, "Error", "Working Directory not set.")
        return

    if not collect_files(wd, show_all_versions=True):
        QtGui.QMessageBox.information(None, "Info",
                                      "No versioned files found in WD.")
        return

    dlg = OpenFileDialog(wd, Gui.getMainWindow())
    if dlg.exec_() == QtGui.QDialog.Accepted and dlg.selected_file:
        file_path = os.path.join(wd, dlg.selected_file)
        App.openDocument(file_path)
        App.Console.PrintMessage(
            "Opened: {}\n".format(os.path.basename(file_path)))


# ============================================================
# FREECAD COMMAND WRAPPER
# ============================================================

class Std_VersionOpen:
    """Version Open - Standard FreeCAD Command"""

    def GetResources(self):
        return {
            'Pixmap': 'Open',
            'MenuText': 'Version Open',
            'Accel': 'Ctrl+O',
            'ToolTip': 'Open version-controlled documents from working directory.\nShows latest versions by default.\nCheck "Show all versions" to see all files.',
            'CmdType': 'ForEdit'
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            main()
        except Exception as e:
            QtGui.QMessageBox.critical(None, "Open", "Unexpected error:\n{}".format(str(e)))


# Register command
Gui.addCommand('Std_VersionOpen', Std_VersionOpen())

App.Console.PrintLog("Std_VersionOpen command registered\n")
