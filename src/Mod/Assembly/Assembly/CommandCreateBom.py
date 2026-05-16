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
import datetime
import FreeCAD as App

from PySide.QtCore import QT_TRANSLATE_NOOP

if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtCore, QtGui, QtWidgets
    from PySide.QtWidgets import QPushButton, QMenu

import UtilsAssembly
import Preferences
from functools import partial

__title__ = "Assembly Command Create Bill of Materials"
__author__ = "Ondsel"
__url__ = "https://www.freecad.org"

translate = App.Qt.translate

# ============================================================
# Excel BOM helpers (ported from BOM.FCMacro)
# ============================================================

_BOM_SKIP_TYPES = frozenset({
    'App::Origin', 'App::Line', 'App::Plane',
    'Assembly::JointGroup', 'Assembly::JointObject', 'Assembly::JointFixed',
    'Assembly::JointRevolute', 'Assembly::JointCylindrical',
    'Assembly::JointSlider', 'Assembly::JointBall', 'Assembly::JointDistance',
    'Assembly::GroundedJoint', 'App::PropertyContainer', 'App::GeometryPython',
})
_BOM_SKIP_NAME_RE = re.compile(
    r'^(GroundedJoint|OriginToAssembly|Joint|Constraint)', re.IGNORECASE)

# Model Parameter fields used to detect whether an object/doc has MP data
_MP_DETECT_FIELDS = (
    'MP_PartNumber', 'MP_Description', 'MP_BOMType', 'MP_Type',
    'MP_TypeSub', 'MP_Category', 'MP_Identification', 'MP_Material',
    'MP_Aggregate', 'MP_Revision',
)


def _bom_has_mp(obj):
    """Return True if obj carries any non-empty Model Parameter field."""
    return any(getattr(obj, f, '') for f in _MP_DETECT_FIELDS if hasattr(obj, f))

_BOM_COLUMNS = [
    ('S.NO', 8), ('LEVEL', 8), ('PART NUMBER', 28), ('DESCRIPTION', 45),
    ('QTY', 6), ('EBOM', 7), ('MBOM', 7), ('S-BOM', 7),
    ('REVISION', 11), ('MAKE / BUY', 13), ('Sub-Ty', 14), ('MATERIAL', 18),
    ('IDENTIFICATION', 18), ('CATEGORY', 16), ('AGGREGATE', 22),
]
_BOM_COL_START = 6
_BOM_COL_END   = 8


def _bom_should_skip(obj):
    type_id = getattr(obj, 'TypeId', '')
    if type_id in _BOM_SKIP_TYPES:
        return True
    # Allow Assembly::AssemblyLink — these are external subassembly references.
    # Skip all other Assembly:: sub-types (joints, constraints, etc.).
    if (type_id.startswith('Assembly::')
            and type_id not in ('Assembly::AssemblyObject', 'Assembly::AssemblyLink')):
        return True
    name  = getattr(obj, 'Name',  '')
    label = getattr(obj, 'Label', '')
    if _BOM_SKIP_NAME_RE.match(name) or _BOM_SKIP_NAME_RE.match(label):
        return True
    return False


def _bom_joint_member_ids(asm_obj):
    skip_ids = set()
    if not hasattr(asm_obj, 'Group'):
        return skip_ids
    for child in asm_obj.Group:
        type_id = getattr(child, 'TypeId', '')
        if type_id in _BOM_SKIP_TYPES or \
           (type_id.startswith('Assembly::')
                and type_id not in ('Assembly::AssemblyObject', 'Assembly::AssemblyLink')):
            if hasattr(child, 'Group'):
                for member in child.Group:
                    skip_ids.add(id(member))
            skip_ids.add(id(child))
    return skip_ids


def _bom_mp(source, prop, default=''):
    return getattr(source, prop, default) or default


def _bom_find_mp_source(obj):
    # 1. Check the object itself — any non-empty MP_ field qualifies
    if _bom_has_mp(obj):
        return obj

    # Determine the parent document so we can guard against inheriting
    # the parent assembly's own MP_ data
    parent_doc = getattr(obj, 'Document', None)

    if hasattr(obj, 'LinkedObject') and obj.LinkedObject is not None:
        linked = obj.LinkedObject
        linked_doc = getattr(linked, 'Document', None)

        # 2. Check the resolved linked object (catches sync_mp_to_bodies case)
        if _bom_has_mp(linked):
            return linked

        # 3. Check the linked document — for ANY external file (not just
        #    assemblies). Guard: only when the linked object lives in a
        #    DIFFERENT document (external file) so we don't inherit the
        #    parent assembly's document-level MP data.
        if linked_doc is not None and linked_doc is not parent_doc:
            if _bom_has_mp(linked_doc):
                return linked_doc

            # 4. Walk all objects in the linked document looking for MP_ data
            #    (handles the case where sync_mp_to_bodies wrote to a body
            #    but the document-level property was not set)
            for child in getattr(linked_doc, 'Objects', []):
                if _bom_has_mp(child):
                    return child

    # 5. Check the object's own document — only when the object itself IS an
    #    assembly (avoids attributing the parent assembly's metadata to its children)
    if getattr(obj, 'TypeId', '') == 'Assembly::AssemblyObject':
        if parent_doc is not None and _bom_has_mp(parent_doc):
            return parent_doc

    return None


def _bom_mat_with_thk(src):
    mat = _bom_mp(src, 'MP_Material', '')
    sub = _bom_mp(src, 'MP_TypeSub', '')
    thk = _bom_mp(src, 'MP_THK', '')
    if sub.lower() == 'fabrication' and thk:
        mat = '{} THK {}'.format(mat, thk) if mat else 'THK {}'.format(thk)
    return mat


def _bom_extract_entry(obj):
    src = _bom_find_mp_source(obj)
    bom_type = _bom_mp(src, 'MP_BOMType', '') if src else ''

    # Part Number: prefer MP_PartNumber (clean filename-style values), then doc name, then label
    pn = _bom_clean_label(_bom_mp(src, 'MP_PartNumber', '')) if src else ''
    if not pn:
        if src is not None and isinstance(src, App.Document):
            pn = _bom_clean_doc_name(src)
        else:
            pn = _bom_clean_label(getattr(obj, 'Label', '') or '')
    if not pn:
        linked = getattr(obj, 'LinkedObject', None)
        if linked is not None:
            pn = _bom_clean_label(getattr(linked, 'Label', '') or '')

    # Description: MP_Description → obj.Description → doc.Description → doc.Comment
    desc = _bom_mp(src, 'MP_Description', '') if src else ''
    if not desc:
        desc = str(getattr(obj, 'Description', '') or '').strip()
    if not desc:
        _obj_doc = getattr(obj, 'Document', None)
        if _obj_doc:
            desc = str(getattr(_obj_doc, 'Description', '') or '').strip()
            if not desc:
                desc = str(getattr(_obj_doc, 'Comment', '') or '').strip()

    _type     = _bom_mp(src, 'MP_Type', '')            if src else ''
    _sub_type = _bom_mp(src, 'MP_TypeSub', '')         if src else ''
    _ident    = _bom_mp(src, 'MP_Identification', '')  if src else ''
    _category = _bom_mp(src, 'MP_Category', '')        if src else ''
    _aggregate = _bom_mp(src, 'MP_Aggregate', '')      if src else ''
    _revision  = _bom_mp(src, 'MP_Revision', '')       if src else ''

    # Material: prefer MP_Material (with thickness annotation); if empty, try
    # reading the material applied via the Apply Material macro from the
    # linked document's objects.
    _material = _bom_mat_with_thk(src) if src else ''
    if not _material:
        linked_obj = getattr(obj, 'LinkedObject', None)
        linked_doc = getattr(linked_obj, 'Document', None) if linked_obj else None
        parent_doc = getattr(obj, 'Document', None)
        if linked_doc is not None and linked_doc is not parent_doc:
            for child in getattr(linked_doc, 'Objects', []):
                mat_dict = getattr(child, 'Material', None)
                if isinstance(mat_dict, dict):
                    for key in ('Name', 'CardName'):
                        val = str(mat_dict.get(key, '') or '').strip()
                        if val:
                            _material = val
                            break
                if not _material:
                    val = str(getattr(child, 'Mat_Name', '') or '').strip()
                    if val:
                        _material = val
                if _material:
                    break

    # EBOM/MBOM/SBOM show whenever BOM Type is set OR any detail field is filled
    details_filled = any([bom_type, _type, _sub_type, _ident, _material, _aggregate])
    if details_filled:
        return {'part_number': pn, 'description': desc,
                'ebom': 'E', 'mbom': 'M' if bom_type == 'M-BOM' else '',
                'sbom': 'S' if bom_type == 'S-BOM' else '',
                'revision': _revision,
                'type': _type, 'sub_type': _sub_type, 'material': _material,
                'identification': _ident, 'category': _category, 'aggregate': _aggregate}
    else:
        return {'part_number': pn, 'description': desc,
                'ebom': '', 'mbom': '', 'sbom': '', 'revision': _revision,
                'type': '', 'sub_type': '', 'material': '',
                'identification': '', 'category': '', 'aggregate': ''}


def _bom_find_root_asm(doc):
    for obj in doc.Objects:
        if obj.TypeId == 'Assembly::AssemblyObject':
            if not any(p.TypeId == 'Assembly::AssemblyObject' for p in obj.InList):
                return obj
    return None


def _bom_resolve(obj):
    if hasattr(obj, 'LinkedObject') and obj.LinkedObject is not None:
        linked = obj.LinkedObject
        doc = linked.Document if hasattr(linked, 'Document') else None
        return linked, doc
    return obj, None


def _bom_ident_key(child_obj, resolved, linked_doc):
    for probe in (child_obj, resolved):
        src = _bom_find_mp_source(probe)
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


def _bom_stack_key(asm_obj):
    doc = getattr(asm_obj, 'Document', None)
    obj_name = getattr(asm_obj, 'Name', '')
    if doc and doc.FileName:
        return ('file', str(doc.FileName), obj_name)
    return ('id', id(asm_obj))


def _bom_traverse(asm_obj, level, results, _stack=None):
    if _stack is None:
        _stack = set()
    sk = _bom_stack_key(asm_obj)
    if sk in _stack:
        return
    _stack.add(sk)
    entry = _bom_extract_entry(asm_obj)
    results.append({'level': level, 'entry': entry, 'qty': 1})
    if not hasattr(asm_obj, 'Group'):
        _stack.discard(sk)
        return
    asm_mp_src = _bom_find_mp_source(asm_obj)
    joint_ids  = _bom_joint_member_ids(asm_obj)
    ordered_children = []
    for child in asm_obj.Group:
        if _bom_should_skip(child):
            continue
        if id(child) in joint_ids:
            continue
        resolved, linked_doc = _bom_resolve(child)
        sub_asm = None
        if resolved.TypeId == 'Assembly::AssemblyObject':
            sub_asm = resolved
        elif linked_doc:
            sub_asm = _bom_find_root_asm(linked_doc)
        if sub_asm is None:
            child_mp_src = _bom_find_mp_source(child)
            if (child_mp_src is not None and child_mp_src is asm_mp_src
                    and not hasattr(child, 'MP_PartNumber')):
                continue
        if sub_asm is not None and _bom_stack_key(sub_asm) in _stack:
            continue
        key = _bom_ident_key(child, resolved, linked_doc)
        ordered_children.append({'key': key, 'resolved': resolved,
                                  'linked_doc': linked_doc, 'sub_asm': sub_asm,
                                  'child_obj': child})
    merged = []
    for info in ordered_children:
        if merged and merged[-1]['key'] == info['key']:
            merged[-1]['count'] += 1
        else:
            merged.append({**info, 'count': 1})
    for info in merged:
        qty = info['count']
        if info['sub_asm']:
            sub_start = len(results)
            _bom_traverse(info['sub_asm'], level + 1, results, _stack)
            if sub_start < len(results):
                results[sub_start]['qty'] = qty
        else:
            row_entry = _bom_extract_entry(info['child_obj'])
            results.append({'level': level + 1, 'entry': row_entry, 'qty': qty})
    _stack.discard(sk)


def _bom_clean_label(label):
    """Strip assembly file extensions and version suffixes from a label/part-number.
    Only strips the .NNN version suffix when the label has a known asm extension,
    so real part numbers like 'P12345.001' are left untouched.
    """
    if re.search(r'\.(prt|asm|drg|fcstd)', label, re.IGNORECASE):
        name = re.sub(r'\.(prt|asm|drg|fcstd)$', '', label, flags=re.IGNORECASE)
        name = re.sub(r'\.\d+$', '', name)
        return name or label
    return label


def _bom_clean_doc_name(doc):
    if not doc.FileName:
        return doc.Name or ''
    name = os.path.splitext(os.path.basename(str(doc.FileName)))[0]
    name = re.sub(r'\.(prt|asm|drg)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.\d+$', '', name)
    return name


def _bom_write_excel(results, doc, save_path):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise RuntimeError(
            "openpyxl is not installed.\n"
            "Install it via: pip install openpyxl"
        )

    wb = Workbook()
    ws = wb.active
    ws.title = 'BOM'
    num_cols = len(_BOM_COLUMNS)

    dark_blue  = PatternFill('solid', fgColor='003366')
    mid_blue   = PatternFill('solid', fgColor='1F4E79')
    light_grey = PatternFill('solid', fgColor='D9E2F3')
    white_fill = PatternFill('solid', fgColor='FFFFFF')
    title_font = Font(name='Calibri', bold=True, color='FFFFFF', size=12)
    proj_font  = Font(name='Calibri', bold=True, color='FFFFFF', size=9)
    hdr_font   = Font(name='Calibri', bold=True, color='FFFFFF', size=10)
    data_font  = Font(name='Calibri', size=9)
    thin_side  = Side(style='thin', color='000000')
    border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    center     = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_align = Alignment(horizontal='left',   vertical='center', wrap_text=True)

    for i, (_, w) in enumerate(_BOM_COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Row 1: title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols - 2)
    asm_label = ''
    if doc.FileName:
        asm_label = os.path.splitext(os.path.basename(str(doc.FileName)))[0]
        asm_label = re.sub(r'\.FCStd$', '', asm_label, flags=re.IGNORECASE)
        asm_label = re.sub(r'\.(prt|asm|drg)$', '', asm_label, flags=re.IGNORECASE)
        asm_label = re.sub(r'\.\d+$', '', asm_label)
    else:
        asm_label = doc.Name or 'Assembly'

    root_asm = _bom_find_root_asm(doc)
    title_cell = ws.cell(row=1, column=1)
    title_cell.value     = '{} - BILL OF MATERIALS'.format(asm_label)
    title_cell.font      = title_font
    title_cell.fill      = dark_blue
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    for c in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill   = dark_blue
        cell.font   = title_font
        cell.border = border_all

    ws.merge_cells(start_row=1, start_column=num_cols - 1, end_row=1, end_column=num_cols)
    proj_cell = ws.cell(row=1, column=num_cols - 1)
    today = datetime.date.today().strftime('%Y-%m-%d')
    rev = ''
    if root_asm:
        src = _bom_find_mp_source(root_asm)
        if src:
            rev = _bom_mp(src, 'MP_Revision')
    proj_cell.value     = 'PROJECT CODE :\nREV : {}    DATE : {}'.format(rev, today)
    proj_cell.font      = proj_font
    proj_cell.fill      = dark_blue
    proj_cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 36

    # Rows 2-3: column headers
    ws.merge_cells(start_row=2, start_column=_BOM_COL_START,
                   end_row=2,   end_column=_BOM_COL_END)
    bom_lbl = ws.cell(row=2, column=_BOM_COL_START)
    bom_lbl.value     = 'BOM TYPE'
    bom_lbl.font      = hdr_font
    bom_lbl.fill      = mid_blue
    bom_lbl.alignment = center
    bom_lbl.border    = border_all
    for i, (hdr_name, _) in enumerate(_BOM_COLUMNS, 1):
        if _BOM_COL_START <= i <= _BOM_COL_END:
            c3 = ws.cell(row=3, column=i)
            c3.value = hdr_name; c3.font = hdr_font; c3.fill = mid_blue
            c3.alignment = center; c3.border = border_all
        else:
            ws.merge_cells(start_row=2, start_column=i, end_row=3, end_column=i)
            c2 = ws.cell(row=2, column=i)
            c2.value = hdr_name; c2.font = hdr_font; c2.fill = mid_blue
            c2.alignment = center; c2.border = border_all
    for r in (2, 3):
        for c in range(1, num_cols + 1):
            cell = ws.cell(row=r, column=c)
            if cell.fill.fgColor is None or str(cell.fill.fgColor.index) == '00000000':
                cell.fill = mid_blue
            cell.border = border_all
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 22

    # Data rows
    DATA_START = 4
    for idx, row_data in enumerate(results):
        r   = DATA_START + idx
        lvl = row_data['level']
        e   = row_data['entry']
        qty = row_data['qty']
        values = [idx + 1, lvl, e['part_number'], e['description'], qty,
                  e['ebom'], e['mbom'], e['sbom'], e['revision'],
                  e['type'], e['sub_type'], e['material'],
                  e['identification'], e['category'], e['aggregate']]
        fill = white_fill if idx % 2 == 0 else light_grey
        for c, val in enumerate(values, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = data_font; cell.fill = fill; cell.border = border_all
            cell.alignment = center if c in (1, 2, 5, 6, 7, 8, 9) else left_align
        ws.row_dimensions[r].height = 18

    last_col = get_column_letter(num_cols)
    last_row = DATA_START + len(results) - 1 if results else DATA_START
    ws.auto_filter.ref = 'A3:{}{}'. format(last_col, last_row)
    ws.freeze_panes = 'A4'
    wb.save(save_path)
    return save_path

# ============================================================
# End Excel BOM helpers
# ============================================================

TranslatedColumnNames = [
    translate("Assembly", "Index (auto)"),
    translate("Assembly", "Name (auto)"),
    translate("Assembly", "Description"),
    translate("Assembly", "File Name (auto)"),
    translate("Assembly", "Quantity (auto)"),
]

ColumnNames = [
    "Index",
    "Name",
    "Description",
    "File Name",
    "Quantity",
]


class CommandCreateBom:
    def __init__(self):
        pass

    def GetResources(self):
        return {
            "Pixmap": "Assembly_BillOfMaterials",
            "MenuText": QT_TRANSLATE_NOOP("Assembly_CreateBom", "Bill of Materials"),
            "Accel": "O",
            "ToolTip": QT_TRANSLATE_NOOP(
                "Assembly_CreateBom",
                "<p>Creates a bill of materials of the current assembly. If an assembly is active, it will be a BOM of this assembly. Else it will be a BOM of the whole document.</p>"
                "<p>The BOM object is a document object that stores the settings of your BOM. It is also a spreadsheet object so you can easily visualize the BOM. If you do not need the BOM object to be saved as a document object, you can simply export and cancel the task.</p>"
                "<p>The columns 'Index', 'Name', 'File Name' and 'Quantity' are automatically generated on recompute. The 'Description' and custom columns are not overwritten.</p>",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        self.panel = TaskAssemblyCreateBom()
        dialog = Gui.Control.showDialog(self.panel)
        if dialog is not None:
            dialog.setAutoCloseOnDeletedDocument(True)
            dialog.setDocumentName(App.ActiveDocument.Name)


######### Create Exploded View Task ###########
class TaskAssemblyCreateBom(QtCore.QObject):
    def __init__(self, bomObj=None):
        super().__init__()

        self.form = Gui.PySideUic.loadUi(":/panels/TaskAssemblyCreateBom.ui")
        # Keep a stable reference to the original loaded form widget so that
        # all attribute accesses (columnList, CheckBox_xxx, etc.) keep working
        # after self.form is replaced by the tab wrapper below.
        self._fc_bom_form = self.form

        # Set the QListWidget properties to support drag and drop
        self.form.columnList.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.form.columnList.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.form.columnList.setDragEnabled(True)
        self.form.columnList.setAcceptDrops(True)
        self.form.columnList.setDropIndicatorShown(True)
        self.form.columnList.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)

        self.form.columnList.installEventFilter(self)

        self.form.btnAddColumn.clicked.connect(self.showAddColumnMenu)
        self.form.btnExport.clicked.connect(self.export)

        self.form.helpButton.clicked.connect(self.showHelpDialog)

        pref = Preferences.preferences()

        if bomObj:
            App.setActiveTransaction("Edit Bill Of Materials")

            for name in bomObj.columnsNames:
                if name in ColumnNames:
                    index = ColumnNames.index(name)
                    name = TranslatedColumnNames[index]

                self.addColItem(name)

            self.bomObj = bomObj
        else:
            App.setActiveTransaction("Create Bill Of Materials")

            # Add the columns
            for name in TranslatedColumnNames:
                self.addColItem(name)

            self.createBomObject()
            self.bomObj.onlyParts = pref.GetBool("BOMOnlyParts", False)
            self.bomObj.detailParts = pref.GetBool("BOMDetailParts", True)
            self.bomObj.detailSubAssemblies = pref.GetBool("BOMDetailSubAssemblies", True)

        self.form.CheckBox_onlyParts.setChecked(self.bomObj.onlyParts)
        self.form.CheckBox_detailParts.setChecked(self.bomObj.detailParts)
        self.form.CheckBox_detailSubAssemblies.setChecked(self.bomObj.detailSubAssemblies)

        self.form.columnList.model().rowsMoved.connect(self.onItemsReordered)
        self.form.columnList.itemChanged.connect(self.itemUpdated)

        self.form.CheckBox_onlyParts.stateChanged.connect(self.onIncludeSolids)
        self.form.CheckBox_detailParts.stateChanged.connect(self.onDetailParts)
        self.form.CheckBox_detailSubAssemblies.stateChanged.connect(self.onDetailSubAssemblies)

        self.updateColumnList()

        # ── Excel Export tab ────────────────────────────────────────
        self._excel_build_tab()

    # ── Excel Export tab helpers ─────────────────────────────────────────

    def _excel_build_tab(self):
        """Wrap the loaded .ui form and a new Excel Export page in a
        QTabWidget, then replace self.form with a wrapper that holds it.
        The original loaded form is kept as self._fc_bom_form so that all
        existing attribute references (columnList, CheckBox_xxx, etc.) work."""
        fc_bom_page = self._fc_bom_form  # original loaded .ui widget as first tab

        # "Excel Export" page
        xl_page = QtWidgets.QWidget()
        xl_lay = QtWidgets.QVBoxLayout(xl_page)
        xl_lay.setContentsMargins(8, 8, 8, 8)
        xl_lay.setSpacing(6)

        # -- Save path row --
        # Row 1: "Save to:" label + Browse button side-by-side (left-anchored, always visible)
        path_top = QtWidgets.QHBoxLayout()
        path_top.addWidget(QtWidgets.QLabel("Save to:"))
        self._xl_browse_btn = QtWidgets.QPushButton("Browse…")
        self._xl_browse_btn.setFixedWidth(72)
        self._xl_browse_btn.clicked.connect(self._excel_browse)
        path_top.addWidget(self._xl_browse_btn)
        path_top.addStretch()
        xl_lay.addLayout(path_top)
        # Row 2: path display — full width, right-aligned so filename end is always visible
        self._xl_path_edit = QtWidgets.QLineEdit()
        self._xl_path_edit.setReadOnly(True)
        self._xl_path_edit.setPlaceholderText("(auto: working directory)")
        self._xl_path_edit.setAlignment(QtCore.Qt.AlignRight)
        xl_lay.addWidget(self._xl_path_edit)

        # -- Preview table --
        preview_lbl = QtWidgets.QLabel("<b>Preview</b>")
        xl_lay.addWidget(preview_lbl)

        self._xl_preview = QtWidgets.QTableWidget()
        self._xl_preview.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._xl_preview.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._xl_preview.setAlternatingRowColors(True)
        self._xl_preview.verticalHeader().setVisible(False)
        xl_col_names = [c[0] for c in _BOM_COLUMNS]
        self._xl_preview.setColumnCount(len(xl_col_names))
        self._xl_preview.setHorizontalHeaderLabels(xl_col_names)
        self._xl_preview.horizontalHeader().setStretchLastSection(True)
        xl_lay.addWidget(self._xl_preview, 1)

        # -- Status label --
        self._xl_status = QtWidgets.QLabel("")
        self._xl_status.setWordWrap(True)
        xl_lay.addWidget(self._xl_status)

        # -- Buttons row --
        btn_row = QtWidgets.QHBoxLayout()
        self._xl_refresh_btn = QtWidgets.QPushButton("Refresh Preview")
        self._xl_refresh_btn.clicked.connect(self._excel_refresh_preview)
        btn_row.addWidget(self._xl_refresh_btn)
        self._xl_sheet_btn = QtWidgets.QPushButton("Open in Spreadsheet")
        self._xl_sheet_btn.clicked.connect(self._open_in_spreadsheet)
        btn_row.addWidget(self._xl_sheet_btn)
        btn_row.addStretch()
        self._xl_export_btn = QtWidgets.QPushButton("Export")
        self._xl_export_btn.setDefault(False)
        self._xl_export_btn.setToolTip("Export to Excel (reads spreadsheet edits if open, else uses preview data)")
        self._xl_export_btn.clicked.connect(self._excel_export)
        btn_row.addWidget(self._xl_export_btn)
        xl_lay.addLayout(btn_row)

        # -- Assemble tab widget --
        self._bom_tab = QtWidgets.QTabWidget()
        self._bom_tab.addTab(fc_bom_page, "Custom BOM")
        self._bom_tab.addTab(xl_page, "BNC CAD BOM")
        self._bom_tab.currentChanged.connect(self._excel_on_tab_changed)

        # Replace self.form with a wrapper containing the tab widget.
        # FreeCAD's task panel displays self.form; all widget attribute
        # accesses use self._fc_bom_form which still points to the original.
        wrapper = QtWidgets.QWidget()
        w_lay = QtWidgets.QVBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.addWidget(self._bom_tab)
        self.form = wrapper

        # Populate save path from working directory
        self._excel_update_default_path()

    def _excel_on_tab_changed(self, index):
        if index == 1:
            self._excel_update_default_path()
            self._excel_refresh_preview()

    def _excel_update_default_path(self):
        """Set the default save path if none is chosen yet."""
        if self._xl_path_edit.text():
            return
        doc = App.ActiveDocument
        if doc and doc.FileName:
            directory = os.path.dirname(str(doc.FileName))
        else:
            p = App.ParamGet('User parameter:BaseApp/Preferences/General')
            directory = p.GetString('WorkingDirectory', '')
        if directory:
            asm_name = _bom_clean_doc_name(doc) if doc else 'Assembly'
            today    = datetime.date.today().strftime('%Y%m%d')
            filename = 'BOM_{}_{}.xlsx'.format(asm_name, today)
            self._xl_path_edit.setText(os.path.join(directory, filename))

    def _excel_browse(self):
        current = self._xl_path_edit.text()
        start = os.path.dirname(current) if current else ''
        if not start:
            p = App.ParamGet('User parameter:BaseApp/Preferences/General')
            start = p.GetString('WorkingDirectory', '')
        doc = App.ActiveDocument
        asm_name = _bom_clean_doc_name(doc) if (doc and doc.FileName) else 'Assembly'
        today    = datetime.date.today().strftime('%Y%m%d')
        default  = os.path.join(start, 'BOM_{}_{}.xlsx'.format(asm_name, today))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, "Save BOM Excel", default,
            "Excel Workbook (*.xlsx)")
        if path:
            self._xl_path_edit.setText(path)

    def _excel_refresh_preview(self):
        """Refresh preview — reads from spreadsheet if it has been opened, else traverses assembly."""
        if getattr(self, '_bom_sheet_name', None) and App.ActiveDocument:
            sheet = App.ActiveDocument.getObject(self._bom_sheet_name)
            if sheet is not None and getattr(sheet, 'TypeId', '') == 'Spreadsheet::Sheet':
                self._refresh_preview_from_sheet(sheet)
                return
        self._refresh_preview_from_assembly()

    def _refresh_preview_from_sheet(self, sheet):
        """Read BOM data from the FreeCAD spreadsheet (includes user edits) and fill the preview."""
        self._xl_preview.setRowCount(0)
        self._xl_status.setText("")
        col_letter = self._bom_col_letter

        def _cell(ci, row_num):
            try:
                v = sheet.get(col_letter(ci) + str(row_num))
                return str(v) if v is not None else ''
            except Exception:
                return ''

        _COL_FIELDS = [
            None, None, 'part_number', 'description', None,
            'ebom', 'mbom', 'sbom', 'revision', 'type', 'sub_type',
            'material', 'identification', 'category', 'aggregate',
        ]
        results = []
        row_num = 2
        while row_num < 10002:
            sno = _cell(0, row_num)
            pn  = _cell(2, row_num)
            if not sno and not pn:
                break
            try:
                lvl = int(float(_cell(1, row_num))) if _cell(1, row_num) else 1
            except Exception:
                lvl = 1
            try:
                qty = int(float(_cell(4, row_num))) if _cell(4, row_num) else 1
            except Exception:
                qty = 1
            entry = {f: '' for f in ('part_number', 'description', 'ebom', 'mbom', 'sbom',
                                     'revision', 'type', 'sub_type', 'material',
                                     'identification', 'category', 'aggregate')}
            for ci, field in enumerate(_COL_FIELDS):
                if field:
                    entry[field] = _cell(ci, row_num)
            results.append({'level': lvl, 'entry': entry, 'qty': qty})
            row_num += 1

        if not results:
            self._xl_status.setText("Spreadsheet appears empty.")
            return

        self._xl_preview.setSortingEnabled(False)
        self._xl_preview.setRowCount(len(results))
        for idx, row_data in enumerate(results):
            e   = row_data['entry']
            lvl = row_data['level']
            qty = row_data['qty']
            values = [str(idx + 1), str(lvl), e['part_number'], e['description'],
                      str(qty), e['ebom'], e['mbom'], e['sbom'], e['revision'],
                      e['type'], e['sub_type'], e['material'],
                      e['identification'], e['category'], e['aggregate']]
            for c, val in enumerate(values):
                self._xl_preview.setItem(idx, c, QtWidgets.QTableWidgetItem(val))
        self._xl_preview.setSortingEnabled(True)
        self._xl_preview.resizeColumnsToContents()
        self._bom_sheet_rows = len(results)
        self._xl_results = results
        self._xl_status.setText("{} rows (from spreadsheet — includes your edits).".format(len(results)))

    def _refresh_preview_from_assembly(self):
        """Traverse the assembly and fill the preview table."""
        self._xl_preview.setRowCount(0)
        self._xl_status.setText("")
        doc = App.ActiveDocument
        if not doc:
            self._xl_status.setText("No active document.")
            return
        root_asm = _bom_find_root_asm(doc)
        if not root_asm:
            self._xl_status.setText("No assembly found in the active document.")
            return
        results = []
        try:
            _bom_traverse(root_asm, level=1, results=results)
        except Exception as e:
            self._xl_status.setText("Error traversing assembly: {}".format(e))
            return
        if not results:
            self._xl_status.setText("No components found.")
            return

        self._xl_preview.setSortingEnabled(False)
        self._xl_preview.setRowCount(len(results))
        for idx, row_data in enumerate(results):
            e   = row_data['entry']
            lvl = row_data['level']
            qty = row_data['qty']
            values = [str(idx + 1), str(lvl), e['part_number'], e['description'],
                      str(qty), e['ebom'], e['mbom'], e['sbom'], e['revision'],
                      e['type'], e['sub_type'], e['material'],
                      e['identification'], e['category'], e['aggregate']]
            for c, val in enumerate(values):
                self._xl_preview.setItem(idx, c, QtWidgets.QTableWidgetItem(val))
        self._xl_preview.setSortingEnabled(True)
        self._xl_preview.resizeColumnsToContents()
        self._xl_status.setText("{} rows ready for export.".format(len(results)))
        self._xl_results = results

    def _excel_export(self):
        """Export to Excel — reads from spreadsheet (with user edits) if open, else uses preview data."""
        doc = App.ActiveDocument
        if not doc:
            QtWidgets.QMessageBox.warning(None, "Export BOM", "No active document.")
            return

        # If spreadsheet is open, sync preview from it first so edits are captured
        if getattr(self, '_bom_sheet_name', None):
            sheet = doc.getObject(self._bom_sheet_name)
            if sheet is not None and getattr(sheet, 'TypeId', '') == 'Spreadsheet::Sheet':
                self._refresh_preview_from_sheet(sheet)

        # Ensure we have results
        if not hasattr(self, '_xl_results') or not self._xl_results:
            self._excel_refresh_preview()
        results = getattr(self, '_xl_results', [])
        if not results:
            QtWidgets.QMessageBox.warning(None, "Export BOM",
                                          "No data found. Click Refresh Preview first.")
            return

        save_path = self._xl_path_edit.text().strip()
        if not save_path:
            self._excel_update_default_path()
            save_path = self._xl_path_edit.text().strip()
        if not save_path:
            QtWidgets.QMessageBox.warning(None, "Export BOM", "Please set a save path first.")
            return

        final_path = save_path
        for attempt in range(20):
            try:
                _bom_write_excel(results, doc, final_path)
                break
            except RuntimeError as e:
                QtWidgets.QMessageBox.critical(None, "Export BOM",
                                               "Missing dependency:\n{}".format(e))
                return
            except PermissionError:
                base, ext = os.path.splitext(save_path)
                final_path = '{}_{}{}'.format(base, attempt + 1, ext)
        else:
            QtWidgets.QMessageBox.critical(
                None, "Export BOM",
                "Cannot save — the file is locked.\n"
                "Please close it in Excel and try again.\n\n{}".format(save_path))
            return
        self._xl_status.setText("Exported: {}".format(final_path))
        QtWidgets.QMessageBox.information(None, "Export BOM",
                                          "BOM exported successfully!\n\n{}".format(final_path))
        App.Console.PrintMessage("BOM saved → {}\n".format(final_path))

    # ── Open in Spreadsheet ──────────────────────────────────────────────

    @staticmethod
    def _bom_col_letter(n):
        """Convert 0-based column index to Excel-style letter(s)."""
        result = ''
        n += 1
        while n:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    def _open_in_spreadsheet(self):
        """Create / refresh a FreeCAD Spreadsheet with BOM data and open it for editing."""
        if not hasattr(self, '_xl_results') or not self._xl_results:
            self._excel_refresh_preview()
        results = getattr(self, '_xl_results', [])
        if not results:
            QtWidgets.QMessageBox.warning(None, "BOM Spreadsheet",
                                          "No components found. Click Refresh Preview first.")
            return

        doc = App.ActiveDocument
        if not doc:
            return

        col_letter = self._bom_col_letter
        col_names = [c[0] for c in _BOM_COLUMNS]
        last_col = col_letter(len(col_names) - 1)

        # Find existing BNC_BOM sheet or create a new one
        sheet = None
        for obj in doc.Objects:
            if getattr(obj, 'TypeId', '') == 'Spreadsheet::Sheet' and obj.Name == 'BNC_BOM':
                sheet = obj
                break
        if sheet is None:
            sheet = doc.addObject('Spreadsheet::Sheet', 'BNC_BOM')
            sheet.Label = 'BNC CAD BOM'

        # Clear previous content
        try:
            sheet.clearAll()
        except Exception:
            try:
                sheet.clear('A1:Z2000')
            except Exception:
                pass

        def _sset(cell, val):
            """Set a string cell value — prefix with ' to prevent FreeCAD unit parsing
            (e.g. '1A' would otherwise become 1 Ampere = '1.00 A')."""
            if val:
                sheet.set(cell, "'" + str(val))

        # ── Header row (row 1) ───────────────────────────────────────────
        for ci, name in enumerate(col_names):
            _sset(col_letter(ci) + '1', name)
        header_range = 'A1:{}1'.format(last_col)
        try:
            sheet.setStyle(header_range, 'bold')
            sheet.setBackground(header_range, (0.13, 0.29, 0.49, 1.0))
            sheet.setForeground(header_range, (1.0, 1.0, 1.0, 1.0))
            sheet.setAlignment(header_range, 'center|vcenter')
        except Exception:
            pass

        # ── Data rows ────────────────────────────────────────────────────
        for ri, row_data in enumerate(results):
            e   = row_data['entry']
            lvl = row_data['level']
            qty = row_data['qty']
            row_num = ri + 2
            # Numeric columns set as numbers; all other columns forced as strings
            sheet.set(col_letter(0) + str(row_num), str(ri + 1))   # S.NO
            sheet.set(col_letter(1) + str(row_num), str(lvl))       # LEVEL
            sheet.set(col_letter(4) + str(row_num), str(qty))       # QTY
            str_cols = [
                (2, e['part_number']), (3, e['description']),
                (5, e['ebom']), (6, e['mbom']), (7, e['sbom']),
                (8, e['revision']), (9, e['type']), (10, e['sub_type']),
                (11, e['material']), (12, e['identification']),
                (13, e['category']), (14, e['aggregate']),
            ]
            for ci, val in str_cols:
                _sset(col_letter(ci) + str(row_num), val)
            # Alternate row shading
            try:
                row_range = 'A{}:{}{}'.format(row_num, last_col, row_num)
                if ri % 2 == 1:
                    sheet.setBackground(row_range, (0.93, 0.95, 0.98, 1.0))
            except Exception:
                pass

        # ── Column widths ────────────────────────────────────────────────
        col_widths = [50, 50, 150, 250, 40, 50, 50, 50, 80, 90, 90, 120, 120, 110, 150]
        try:
            for ci, w in enumerate(col_widths):
                sheet.setColumnWidth(col_letter(ci), w)
        except Exception:
            pass

        # ── Save row count for export-from-spreadsheet ───────────────────
        self._bom_sheet_name = sheet.Name
        self._bom_sheet_rows = len(results)

        doc.recompute()

        # ── Open the spreadsheet WITHOUT closing this task panel ─────────
        # doubleClicked() / setEdit() would close the task panel, so we instead
        # click the spreadsheet's tab in the MDI area directly.
        _opened = False
        try:
            mw = Gui.getMainWindow()
            mdi = mw.centralWidget()
            for subwin in mdi.subWindowList():
                widget = subwin.widget()
                # FreeCAD MDI sub-windows for spreadsheets carry a 'sheet' attribute
                if getattr(widget, 'sheet', None) is sheet:
                    mdi.setActiveSubWindow(subwin)
                    _opened = True
                    break
        except Exception:
            pass
        if not _opened:
            try:
                sheet.ViewObject.doubleClicked()
            except Exception:
                pass

        self._xl_status.setText(
            "Spreadsheet ready. Edit in 'BNC CAD BOM' tab, "
            "then click 'Export Spreadsheet' to save as Excel.")

    # ── End Excel Export tab ─────────────────────────────────────────────

    def accept(self):
        self.deactivate()
        App.closeActiveTransaction()

        self.bomObj.recompute()

        self.bomObj.ViewObject.showSheetMdi()

        return True

    def reject(self):
        self.deactivate()
        App.closeActiveTransaction(True)
        return True

    def deactivate(self):
        pref = Preferences.preferences()
        pref.SetBool("BOMOnlyParts", self._fc_bom_form.CheckBox_onlyParts.isChecked())
        pref.SetBool("BOMDetailParts", self._fc_bom_form.CheckBox_detailParts.isChecked())
        pref.SetBool("BOMDetailSubAssemblies", self._fc_bom_form.CheckBox_detailSubAssemblies.isChecked())

        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()

    def onIncludeSolids(self, val):
        self.bomObj.onlyParts = val

    def onDetailParts(self, val):
        self.bomObj.detailParts = val

    def onDetailSubAssemblies(self, val):
        self.bomObj.detailSubAssemblies = val

    def addColumn(self):
        new_name = translate("Assembly", "Default")
        if self.isNameDuplicate(new_name):
            # Find a unique name
            counter = 1
            while self.isNameDuplicate(f"{new_name}_{counter}"):
                counter += 1
            new_name = f"{new_name}_{counter}"

        item = self.addColItem(new_name)

        # Ensure the new item is selected and starts editing
        self._fc_bom_form.columnList.setCurrentItem(item)
        self._fc_bom_form.columnList.editItem(item)
        self.updateColumnList()

    def addColItem(self, name):
        item = QtWidgets.QListWidgetItem(name)

        isCustomCol = self.isCustomColumn(name)

        if isCustomCol:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        else:
            font = item.font()
            font.setBold(True)
            item.setFont(font)

        self._fc_bom_form.columnList.addItem(item)
        return item

    def showAddColumnMenu(self):
        menu = QtWidgets.QMenu()
        # Get the current columns in the list
        current_columns = [
            self._fc_bom_form.columnList.item(i).text() for i in range(self._fc_bom_form.columnList.count())
        ]

        # Add actions for columns that are not currently in the list
        noneAdded = True
        for name in TranslatedColumnNames:
            if name not in current_columns:
                action = QtGui.QAction(f"Add '{name}' column", self)
                action.triggered.connect(partial(self.addColItem, name))
                menu.addAction(action)
                noneAdded = False

        if noneAdded:
            self.addColumn()
            return

        # Add the action for adding a custom column
        action = QtGui.QAction("Add custom column", self)
        action.triggered.connect(self.addColumn)
        menu.addAction(action)

        # Show the menu below the button
        menu.exec_(
            self._fc_bom_form.btnAddColumn.mapToGlobal(QtCore.QPoint(0, self._fc_bom_form.btnAddColumn.height()))
        )

    def isCustomColumn(self, name):
        isCustomCol = True
        if name in TranslatedColumnNames:
            # Description column is currently not auto generated so it's a custom column
            index = TranslatedColumnNames.index(name)
            if ColumnNames[index] != "Description":
                isCustomCol = False
        return isCustomCol

    def onItemsReordered(self, parent, start, end, destination, row):
        self.updateColumnList()

    def updateColumnList(self):
        if self.bomObj:
            new_names = []
            for i in range(self._fc_bom_form.columnList.count()):
                text = self._fc_bom_form.columnList.item(i).text()
                if text in TranslatedColumnNames:
                    index = TranslatedColumnNames.index(text)
                    text = ColumnNames[index]
                new_names.append(text)
            self.bomObj.columnsNames = new_names

    def itemUpdated(self, item):
        new_text = item.text()
        item_row = self._fc_bom_form.columnList.row(item)

        # Check for duplicate names
        duplicate_found = False
        for i in range(self._fc_bom_form.columnList.count()):
            if i != item_row and self._fc_bom_form.columnList.item(i).text() == new_text:
                duplicate_found = True
                break

        if duplicate_found:
            QtWidgets.QMessageBox.warning(
                self._fc_bom_form,
                translate("Assembly", "Duplicate Name"),
                translate("Assembly", "This name is already used. Please choose a different name."),
            )

            # Revert the change
            old_text = (
                self.bomObj.columnsNames[item_row]
                if self.bomObj and item_row < len(self.bomObj.columnsNames)
                else ""
            )
            item.setText(old_text)
        else:
            isCustomCol = self.isCustomColumn(new_text)

            if not isCustomCol:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                # Use a single-shot timer to defer changing the flags (else FC crashes)
                QtCore.QTimer.singleShot(0, lambda: self.makeItemNonEditable(item))

            self.updateColumnList()

    def makeItemNonEditable(self, item):
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

    def isNameDuplicate(self, name):
        for i in range(self._fc_bom_form.columnList.count()):
            if self._fc_bom_form.columnList.item(i).text() == name:
                return True
        return False

    def createBomObject(self):
        assembly = UtilsAssembly.activeAssembly()
        Gui.addModule("UtilsAssembly")
        if assembly is not None:
            commands = (
                "assembly = UtilsAssembly.activeAssembly()\n"
                "bom_group = UtilsAssembly.getBomGroup(assembly)\n"
                'bomObj = bom_group.newObject("Assembly::BomObject", "Bill of Materials")'
            )
        else:
            commands = 'bomObj = App.activeDocument().addObject("Assembly::BomObject", "Bill of Materials")'
        Gui.doCommand(commands)
        self.bomObj = Gui.doCommandEval("bomObj")

    def export(self):
        self.bomObj.recompute()
        self.bomObj.ViewObject.exportAsFile()

    def eventFilter(self, watched, event):
        if self._fc_bom_form is not None and watched == self._fc_bom_form.columnList:
            if event.type() == QtCore.QEvent.ShortcutOverride:
                if event.key() == QtCore.Qt.Key_Delete:
                    event.accept()  # Accept the event only if the key is Delete
                    return True  # Indicate that the event has been handled
                return False

            elif event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Delete:
                    selected_indexes = self._fc_bom_form.columnList.selectedIndexes()
                    items_to_remove = []

                    for index in selected_indexes:
                        self._fc_bom_form.columnList.takeItem(index.row())

                    self.updateColumnList()
                    return True  # Consume the event

        return super().eventFilter(watched, event)

    def showHelpDialog(self):
        help_dialog = QtWidgets.QDialog(self._fc_bom_form)
        help_dialog.setWindowFlags(QtCore.Qt.Popup)
        help_dialog.setWindowModality(QtCore.Qt.NonModal)
        help_dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        options_title = QtWidgets.QLabel("<b>" + translate("Assembly", "Options") + "</b>")
        options_text = QtWidgets.QLabel(
            " - "
            + translate(
                "Assembly",
                "Sub-assembly children: the children of sub-assemblies will be included in the bill of materials",
            )
            + "\n"
            " - "
            + translate(
                "Assembly",
                "Parts children: the children of parts will be added to the bill of materials",
            )
            + "\n"
            " - "
            + translate(
                "Assembly",
                "Only parts: adds only part containers and sub-assemblies to the bill of materials. Solids like Part Design bodies, fasteners, or Part workbench primitives are ignored.",
            )
            + "\n"
        )
        columns_title = QtWidgets.QLabel("<b>" + translate("Assembly", "Columns") + "</b>")
        columns_text = QtWidgets.QLabel(
            " - "
            + translate(
                "Assembly",
                "Auto columns :  (Index, Quantity, Name...) are populated automatically. Any modification you make will be overridden. These columns cannot be renamed.",
            )
            + "\n"
            " - "
            + translate(
                "Assembly",
                "Custom columns : 'Description' and other custom columns you add by clicking on 'Add column' will not have their data overwritten. If a column name starts with '.' followed by a property name (e.g. '.Length'), it will be auto-populated with that property value. These columns can be renamed by double-clicking or pressing F2 (renaming a column will currently lose its data).",
            )
            + "\n"
            "\n"
            + translate(
                "Assembly",
                "Any column (custom or not), can be deleted by pressing the Delete key",
            )
            + "\n"
        )
        export_title = QtWidgets.QLabel("<b>" + translate("Assembly", "Export") + "</b>")
        export_text = QtWidgets.QLabel(
            " - "
            + translate(
                "Assembly",
                "The exported file format can be customized in the Spreadsheet workbench preferences",
            )
            + "\n"
        )

        options_text.setWordWrap(True)
        columns_text.setWordWrap(True)
        export_text.setWordWrap(True)

        layout.addWidget(options_title)
        layout.addWidget(options_text)
        layout.addWidget(columns_title)
        layout.addWidget(columns_text)
        layout.addWidget(export_title)
        layout.addWidget(export_text)

        help_dialog.setLayout(layout)
        help_dialog.setFixedWidth(500)

        help_dialog.show()


if App.GuiUp:
    Gui.addCommand("Assembly_CreateBom", CommandCreateBom())
