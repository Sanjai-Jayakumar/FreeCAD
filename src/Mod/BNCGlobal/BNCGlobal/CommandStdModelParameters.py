# -*- coding: utf-8 -*-
# ANVIL CAD - Model Parameters Command
# Edits industrial PDM attributes (MP_*) on the active document / selected object.

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import re

# PySide compatibility: alias QtWidgets to QtGui (FreeCAD uses PySide1)
QtWidgets = QtGui


# ============================================================
# GET TARGET
# ============================================================

def get_target():
    sel = Gui.Selection.getSelection()
    if sel:
        return sel[0]
    return App.ActiveDocument


# ============================================================
# ENSURE PROPERTIES
# ============================================================

def ensure_properties(obj):

    props = {
        "MP_PartNumber": "App::PropertyString",
        "MP_Description": "App::PropertyString",
        "MP_Revision": "App::PropertyString",
        "MP_Weight": "App::PropertyFloat",
        "MP_BOMType": "App::PropertyString",
        "MP_Type": "App::PropertyString",
        "MP_TypeSub": "App::PropertyString",
        "MP_Identification": "App::PropertyString",
        "MP_Category": "App::PropertyString",
        "MP_Material": "App::PropertyString",
        "MP_THK": "App::PropertyString",
        "MP_Aggregate": "App::PropertyString"
    }

    for name, ptype in props.items():
        if not hasattr(obj, name):
            obj.addProperty(ptype, name, "Model Parameters")


# ============================================================
# CLEAN DOCUMENT NAME
# ============================================================

def clean_doc_name(doc):
    if not doc.FileName:
        return ""
    name = os.path.splitext(os.path.basename(doc.FileName))[0]
    name = re.sub(r"\.(prt|asm|drg)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.\d+$", "", name)
    return name


# ============================================================
# DESCRIPTION READERS
# ============================================================

def _read_obj_description(obj):
    """Effective description that belongs to *this* object only.

    Reads the object's own ``.Description`` first, then its ``MP_Description``
    (the create-part dialog stores the value there). Deliberately does NOT fall
    back to the owning document / parent assembly -- otherwise a part with no
    description of its own would show the parent assembly's description
    (e.g. a top-down part showing 'dttc' from the main assembly)."""
    if hasattr(obj, "Description") and obj.Description:
        return obj.Description
    if hasattr(obj, "MP_Description") and obj.MP_Description:
        return obj.MP_Description
    return ""


def _effective_description(container_doc):
    """Description for a *document* target: first Body/Assembly object, then the
    document-level MP_Description (Model Parameters writes it there when nothing
    is selected), then plain Description / Comment."""
    for obj in container_doc.Objects:
        if obj.TypeId in ('PartDesign::Body', 'Assembly::AssemblyObject'):
            d = _read_obj_description(obj)
            if d:
                return d
            break  # only the first matching object
    if hasattr(container_doc, "MP_Description") and container_doc.MP_Description:
        return container_doc.MP_Description
    if hasattr(container_doc, "Description") and container_doc.Description:
        return container_doc.Description
    if hasattr(container_doc, "Comment") and container_doc.Comment:
        return container_doc.Comment
    return ""


# ============================================================
# MAIN DIALOG
# ============================================================

class ModelDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(ModelDialog, self).__init__(parent)

        self.target = get_target()
        ensure_properties(self.target)

        self.setWindowTitle("Model Parameters")
        self.setFixedWidth(420)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(10)

        row = 0
        field_w = 220
        small_w = 80
        h = 22

        # Part Number
        grid.addWidget(QtWidgets.QLabel("Part Number"), row, 0)
        self.partNumber = QtWidgets.QLineEdit()
        self.partNumber.setFixedSize(field_w, h)
        grid.addWidget(self.partNumber, row, 1)
        row += 1

        # Description
        grid.addWidget(QtWidgets.QLabel("Description"), row, 0)
        self.description = QtWidgets.QLineEdit()
        self.description.setFixedSize(field_w, h)
        grid.addWidget(self.description, row, 1)
        row += 1

        # Revision + Weight
        grid.addWidget(QtWidgets.QLabel("Revision"), row, 0)

        self.revision = QtWidgets.QComboBox()
        self.revision.addItems(["NR", "A", "B", "C", "D"])
        # Was 60px -- too narrow for the dark-theme combo padding + dropdown
        # arrow, which squeezed the selected text (e.g. "B") to nothing so the
        # field looked blank. Widen to comfortably show the current value.
        self.revision.setFixedSize(90, h)

        self.weight = QtWidgets.QLineEdit()
        self.weight.setFixedSize(small_w, h)

        revLayout = QtWidgets.QHBoxLayout()
        revLayout.addWidget(self.revision)
        revLayout.addWidget(QtWidgets.QLabel("Weight"))
        revLayout.addWidget(self.weight)
        revLayout.addStretch()

        grid.addLayout(revLayout, row, 1)
        row += 1

        # BOM
        grid.addWidget(QtWidgets.QLabel("BOM Type"), row, 0)

        self.ebom = QtWidgets.QCheckBox("E-BOM")
        self.ebom.setChecked(True)
        self.ebom.setEnabled(False)

        self.mbom = QtWidgets.QRadioButton("M-BOM")
        self.sbom = QtWidgets.QRadioButton("S-BOM")
        self.mbom.setChecked(True)

        bomLayout = QtWidgets.QHBoxLayout()
        bomLayout.addWidget(self.ebom)
        bomLayout.addWidget(self.mbom)
        bomLayout.addWidget(self.sbom)
        bomLayout.addStretch()

        grid.addLayout(bomLayout, row, 1)
        row += 1

        # Type + SubType
        grid.addWidget(QtWidgets.QLabel("Type"), row, 0)

        self.typeBox = QtWidgets.QComboBox()
        self.typeBox.addItems(["", "MAKE", "BUY"])
        self.typeBox.setFixedSize(100, h)
        self.typeBox.currentIndexChanged.connect(lambda: self.type_changed(self.typeBox.currentText()))
        self.typeBox.currentIndexChanged.connect(lambda: self.update_thk_visibility())

        self.typeSub = QtWidgets.QComboBox()
        self.typeSub.setFixedSize(110, h)

        typeLayout = QtWidgets.QHBoxLayout()
        typeLayout.addWidget(self.typeBox)
        typeLayout.addWidget(QtWidgets.QLabel("Sub-Type"))
        typeLayout.addWidget(self.typeSub)
        typeLayout.addStretch()

        self.typeSub.currentIndexChanged.connect(lambda: self.update_thk_visibility())

        grid.addLayout(typeLayout, row, 1)
        row += 1

        # Identification
        grid.addWidget(QtWidgets.QLabel("Identification"), row, 0)
        self.identification = QtWidgets.QComboBox()
        self.identification.addItems(["", "Serialized", "Batch Code"])
        self.identification.setFixedSize(field_w, h)
        grid.addWidget(self.identification, row, 1)
        row += 1

        # Category
        grid.addWidget(QtWidgets.QLabel("Category"), row, 0)
        self.category = QtWidgets.QComboBox()
        self.category.setFixedSize(field_w, h)
        self.category.addItems([
            "Main Assembly",
            "Aggregate Assembly",
            "Sub-Assembly",
            "Weld-Assembly",
            "Part",
            "Fastner"
        ])
        self.category.currentIndexChanged.connect(lambda: self.update_thk_visibility())
        grid.addWidget(self.category, row, 1)
        row += 1

        # Material + THK
        grid.addWidget(QtWidgets.QLabel("Material"), row, 0)
        self.material = QtWidgets.QLineEdit()
        self.material.setFixedSize(130, h)

        self.thkLabel = QtWidgets.QLabel("THK")
        self.thk = QtWidgets.QLineEdit()
        self.thk.setFixedSize(50, h)
        self.thkMmLabel = QtWidgets.QLabel("mm")

        matLayout = QtWidgets.QHBoxLayout()
        matLayout.addWidget(self.material)
        matLayout.addWidget(self.thkLabel)
        matLayout.addWidget(self.thk)
        matLayout.addWidget(self.thkMmLabel)
        matLayout.addStretch()

        grid.addLayout(matLayout, row, 1)
        row += 1

        # Initially hide THK
        self.thkLabel.setVisible(False)
        self.thk.setVisible(False)
        self.thkMmLabel.setVisible(False)

        # Aggregate (Manual)
        grid.addWidget(QtWidgets.QLabel("Aggregate"), row, 0)
        self.aggregate = QtWidgets.QLineEdit()
        self.aggregate.setFixedSize(field_w, h)
        grid.addWidget(self.aggregate, row, 1)

        layout.addLayout(grid)

        # Save
        btnLayout = QtWidgets.QHBoxLayout()
        btnLayout.addStretch()
        saveBtn = QtWidgets.QPushButton("Save")
        saveBtn.setFixedSize(80, 26)
        saveBtn.clicked.connect(self.save_data)
        btnLayout.addWidget(saveBtn)
        layout.addLayout(btnLayout)

        self.setLayout(layout)

        self.load_data()


    # ============================================================
    # TYPE CHANGE
    # ============================================================

    def update_thk_visibility(self):
        show = (
            self.typeBox.currentText() == "MAKE"
            and self.typeSub.currentText() == "Fabrication"
            and self.category.currentText() == "Part"
        )
        self.thkLabel.setVisible(show)
        self.thk.setVisible(show)
        self.thkMmLabel.setVisible(show)


    def type_changed(self, text):

        self.typeSub.clear()

        if text == "MAKE":
            self.typeSub.addItems([
                "Fabrication",
                "Machining",
                "Casting",
                "Forging",
                "Extrusion",
                "Plastic",
                "Foam",
                "Rubber",
                "Harness",
                "Consumables",
                "Sticker"
            ])
        elif text == "BUY":
            self.typeSub.addItems([
                "Electrical",
                "Mechanical"
            ])


    # ============================================================
    # LOAD DATA
    # ============================================================

    def load_data(self):

        if isinstance(self.target, App.Document):
            current_name = clean_doc_name(self.target)
            current_desc = _effective_description(self.target)
        else:
            current_name = self.target.Label
            # Read only THIS object's own description (own .Description or its
            # MP_Description) -- never the parent assembly's, so a top-down part
            # shows its own 'part_1', not the main assembly's 'dttc'.
            current_desc = _read_obj_description(self.target)

        # Always use the current file/object name and description as source of truth
        self.partNumber.setText(current_name)
        self.description.setText(current_desc)

        rev = getattr(self.target, "MP_Revision", "") or "NR"
        idx = self.revision.findText(rev)
        self.revision.setCurrentIndex(idx if idx >= 0 else 0)

        weight_val = getattr(self.target, "MP_Weight", 0.0)
        if weight_val:
            self.weight.setText(str(weight_val))

        # Restore BOM
        bom_type = getattr(self.target, "MP_BOMType", "") or ""
        if bom_type == "S-BOM":
            self.sbom.setChecked(True)
        else:
            self.mbom.setChecked(True)

        # Restore Type & SubType
        mp_type = getattr(self.target, "MP_Type", "") or ""
        self.typeBox.setCurrentIndex(self.typeBox.findText(mp_type) if self.typeBox.findText(mp_type) >= 0 else 0)
        self.type_changed(mp_type)
        mp_typesub = getattr(self.target, "MP_TypeSub", "") or ""
        idx2 = self.typeSub.findText(mp_typesub)
        if idx2 >= 0:
            self.typeSub.setCurrentIndex(idx2)

        # Restore others
        mp_ident = getattr(self.target, "MP_Identification", "") or ""
        idx3 = self.identification.findText(mp_ident)
        self.identification.setCurrentIndex(idx3 if idx3 >= 0 else 0)

        mp_cat = getattr(self.target, "MP_Category", "") or ""
        idx4 = self.category.findText(mp_cat)
        self.category.setCurrentIndex(idx4 if idx4 >= 0 else 0)

        self.material.setText(getattr(self.target, "MP_Material", "") or "")
        self.thk.setText(getattr(self.target, "MP_THK", "") or "")
        self.aggregate.setText(getattr(self.target, "MP_Aggregate", "") or "")
        self.update_thk_visibility()


    # ============================================================
    # SAVE DATA
    # ============================================================

    def save_data(self):

        if not self.aggregate.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Aggregate", "Please Enter Aggregate Type")
            return

        self.target.MP_PartNumber = self.partNumber.text()
        self.target.MP_Description = self.description.text()
        self.target.MP_Revision = self.revision.currentText()

        try:
            self.target.MP_Weight = float(self.weight.text())
        except Exception:
            self.target.MP_Weight = 0.0

        self.target.MP_BOMType = "S-BOM" if self.sbom.isChecked() else "M-BOM"
        self.target.MP_Type = self.typeBox.currentText()
        self.target.MP_TypeSub = self.typeSub.currentText()
        self.target.MP_Identification = self.identification.currentText()
        self.target.MP_Category = self.category.currentText()
        self.target.MP_Material = self.material.text()
        self.target.MP_THK = self.thk.text().strip() if self.thk.isVisible() else ""
        self.target.MP_Aggregate = self.aggregate.text().strip()

        App.ActiveDocument.recompute()
        App.ActiveDocument.save()
        self.accept()


# ============================================================
# COMMAND CLASS
# ============================================================

class Std_ModelParameters:

    def GetResources(self):
        icon_path = os.path.join(
            App.getResourceDir(),
            "Mod", "BNCGlobal", "Resources", "icons", "model_parameters.svg"
        )
        return {
            'Pixmap': icon_path,
            'MenuText': 'Model Parameters',
            'ToolTip': 'Edit industrial PDM attributes (part number, description, material, revision…)',
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            dlg = ModelDialog(Gui.getMainWindow())
            dlg.exec_()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Model Parameters",
                "Unexpected error:\n{}".format(str(e))
            )


# Register the command
Gui.addCommand("BNC_ModelParameters", Std_ModelParameters())
