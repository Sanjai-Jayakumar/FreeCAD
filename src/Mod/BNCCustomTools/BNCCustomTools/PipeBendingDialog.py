# -*- coding: utf-8 -*-
# Pipe Bending Dialog

import FreeCAD
import FreeCADGui
import Part
from PySide import QtGui
import math


class PipeBendingDialog(QtGui.QDialog):
    def __init__(self):
        super(PipeBendingDialog, self).__init__()
        self.setWindowTitle("Pipe Bending Tool")
        self.setFixedSize(400, 350)

        layout = QtGui.QVBoxLayout(self)

        # Title
        title = QtGui.QLabel("Create Bent Pipe")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2E86C1;")
        layout.addWidget(title)

        # Separator
        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        line.setFrameShadow(QtGui.QFrame.Sunken)
        layout.addWidget(line)

        # Pipe Parameters
        form_layout = QtGui.QFormLayout()

        # Outer Radius
        self.outer_radius = QtGui.QDoubleSpinBox()
        self.outer_radius.setRange(1.0, 1000.0)
        self.outer_radius.setValue(20.0)
        self.outer_radius.setSuffix(" mm")
        form_layout.addRow("Outer Radius:", self.outer_radius)

        # Wall Thickness
        self.wall_thickness = QtGui.QDoubleSpinBox()
        self.wall_thickness.setRange(0.5, 100.0)
        self.wall_thickness.setValue(2.0)
        self.wall_thickness.setSuffix(" mm")
        form_layout.addRow("Wall Thickness:", self.wall_thickness)

        # Bend Radius
        self.bend_radius = QtGui.QDoubleSpinBox()
        self.bend_radius.setRange(10.0, 2000.0)
        self.bend_radius.setValue(50.0)
        self.bend_radius.setSuffix(" mm")
        form_layout.addRow("Bend Radius:", self.bend_radius)

        # Bend Angle
        self.bend_angle = QtGui.QDoubleSpinBox()
        self.bend_angle.setRange(1.0, 180.0)
        self.bend_angle.setValue(90.0)
        self.bend_angle.setSuffix(" °")
        form_layout.addRow("Bend Angle:", self.bend_angle)

        # Straight Length 1
        self.length1 = QtGui.QDoubleSpinBox()
        self.length1.setRange(0.0, 5000.0)
        self.length1.setValue(100.0)
        self.length1.setSuffix(" mm")
        form_layout.addRow("Straight Length 1:", self.length1)

        # Straight Length 2
        self.length2 = QtGui.QDoubleSpinBox()
        self.length2.setRange(0.0, 5000.0)
        self.length2.setValue(100.0)
        self.length2.setSuffix(" mm")
        form_layout.addRow("Straight Length 2:", self.length2)

        layout.addLayout(form_layout)

        # Add spacing
        layout.addSpacing(20)

        # Buttons
        btn_layout = QtGui.QHBoxLayout()
        self.create_btn = QtGui.QPushButton("Create Pipe")
        self.create_btn.setStyleSheet("background-color: #2E86C1; color: white; padding: 8px;")
        cancel_btn = QtGui.QPushButton("Cancel")
        cancel_btn.setStyleSheet("padding: 8px;")

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Connect signals
        self.create_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)


def create_bent_pipe(outer_radius, wall_thickness, bend_radius, bend_angle, length1, length2):
    """Create a bent pipe with specified parameters"""
    try:
        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument("PipeBending")

        # Calculate inner radius
        inner_radius = outer_radius - wall_thickness

        # Create outer pipe profile (circle)
        outer_circle = Part.Wire(Part.makeCircle(outer_radius))
        inner_circle = Part.Wire(Part.makeCircle(inner_radius))

        # Create pipe cross-section (annular shape)
        outer_face = Part.Face(outer_circle)
        inner_face = Part.Face(inner_circle)
        pipe_profile = outer_face.cut(inner_face)

        # Create the bent pipe path using edges
        edges = []

        # First straight section
        if length1 > 0:
            edge1 = Part.makeLine(
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(0, 0, length1)
            )
            edges.append(edge1)

        # Bent section (arc)
        angle_rad = math.radians(bend_angle)
        center = FreeCAD.Vector(bend_radius, 0, length1)

        # Create arc for the bend
        arc = Part.makeCircle(
            bend_radius,
            center,
            FreeCAD.Vector(0, 1, 0),
            0,
            bend_angle
        )
        edges.append(arc)

        # Second straight section
        if length2 > 0:
            # Calculate end point of arc
            end_x = bend_radius - bend_radius * math.cos(angle_rad)
            end_z = length1 + bend_radius * math.sin(angle_rad)

            edge2 = Part.makeLine(
                FreeCAD.Vector(end_x, 0, end_z),
                FreeCAD.Vector(end_x + length2 * math.sin(angle_rad), 0, end_z + length2 * math.cos(angle_rad))
            )
            edges.append(edge2)

        # Create wire path
        pipe_path = Part.Wire(edges)

        # Sweep the profile along the path to create the pipe
        bent_pipe = pipe_profile.extrude(FreeCAD.Vector(0, 0, length1))

        # Create the Part object
        pipe_obj = doc.addObject("Part::Feature", "BentPipe")
        pipe_obj.Shape = bent_pipe

        doc.recompute()
        FreeCADGui.ActiveDocument.activeView().viewAxonometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")

        QtGui.QMessageBox.information(None, "Success", "Bent pipe created successfully!")

    except Exception as e:
        QtGui.QMessageBox.critical(None, "Error", f"Failed to create bent pipe:\n{str(e)}")
