# -*- coding: utf-8 -*-
# New File Dialog

from PySide import QtGui
import os


class NewFileDialog(QtGui.QDialog):
    def __init__(self):
        super(NewFileDialog, self).__init__()
        self.setWindowTitle("New File")
        self.setFixedSize(400, 280)

        layout = QtGui.QVBoxLayout(self)

        # Working directory display
        wd_layout = QtGui.QHBoxLayout()
        wd_layout.addWidget(QtGui.QLabel("WD:"))
        self.wd_label = QtGui.QLabel()
        self.wd_label.setText(os.getcwd())
        self.wd_label.setStyleSheet("QLabel { color: gray; }")
        wd_layout.addWidget(self.wd_label)
        wd_layout.addStretch()
        layout.addLayout(wd_layout)

        # Separator line
        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        line.setFrameShadow(QtGui.QFrame.Sunken)
        layout.addWidget(line)

        # File type - Radio buttons in 2x2 grid
        layout.addWidget(QtGui.QLabel("File Type:"))

        radio_container = QtGui.QWidget()
        radio_layout = QtGui.QGridLayout(radio_container)
        radio_layout.setContentsMargins(0, 0, 0, 0)

        # Create radio buttons
        self.sketch_radio = QtGui.QRadioButton("Sketch")
        self.part_radio = QtGui.QRadioButton("Part Design")
        self.assembly_radio = QtGui.QRadioButton("Assembly")
        self.drawing_radio = QtGui.QRadioButton("Drawing")

        # Set default selection
        self.sketch_radio.setChecked(True)

        # Arrange in 2x2 grid
        radio_layout.addWidget(self.sketch_radio, 0, 0)
        radio_layout.addWidget(self.part_radio, 1, 0)
        radio_layout.addWidget(self.assembly_radio, 0, 1)
        radio_layout.addWidget(self.drawing_radio, 1, 1)

        radio_layout.setHorizontalSpacing(20)
        radio_layout.setVerticalSpacing(5)

        layout.addWidget(radio_container)

        # Part name
        layout.addWidget(QtGui.QLabel("Part Name:"))
        self.partName = QtGui.QLineEdit()
        layout.addWidget(self.partName)

        # Part description
        layout.addWidget(QtGui.QLabel("Part Description:"))
        self.partDesc = QtGui.QLineEdit()
        layout.addWidget(self.partDesc)

        # Add some spacing
        layout.addSpacing(10)

        # Buttons
        btns = QtGui.QHBoxLayout()
        okBtn = QtGui.QPushButton("OK")
        cancelBtn = QtGui.QPushButton("Cancel")
        btns.addWidget(okBtn)
        btns.addWidget(cancelBtn)
        layout.addLayout(btns)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.reject)

    def get_selected_type(self):
        """Get the selected file type from radio buttons"""
        if self.sketch_radio.isChecked():
            return "Sketch"
        elif self.part_radio.isChecked():
            return "Part Design"
        elif self.assembly_radio.isChecked():
            return "Assembly"
        elif self.drawing_radio.isChecked():
            return "Drawing"
        else:
            return "Sketch"
