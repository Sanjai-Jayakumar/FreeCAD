# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import math
import FreeCAD
import FreeCADGui as Gui
from PySide import QtWidgets, QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP

_iconsDir = os.path.join(os.path.dirname(__file__), "Resources", "icons")

_PULL_DIRS = {
    "+Z (Up)":    FreeCAD.Vector(0, 0,  1),
    "-Z (Down)":  FreeCAD.Vector(0, 0, -1),
    "+Y":         FreeCAD.Vector(0,  1,  0),
    "-Y":         FreeCAD.Vector(0, -1,  0),
    "+X":         FreeCAD.Vector( 1, 0,  0),
    "-X":         FreeCAD.Vector(-1, 0,  0),
}

_overlays = {}


def _clear_overlay(doc_name):
    if doc_name not in _overlays:
        return
    node, hidden_obj = _overlays.pop(doc_name)
    try:
        from pivy import coin
        view = Gui.ActiveDocument.ActiveView
        sg = view.getSceneGraph()
        if sg.findChild(node) >= 0:
            sg.removeChild(node)
    except Exception:
        pass
    try:
        if hidden_obj:
            hidden_obj.ViewObject.Visibility = True
    except Exception:
        pass
    Gui.updateGui()


def _build_overlay(shape, colors):
    from pivy import coin
    root = coin.SoSeparator()
    lm = coin.SoLightModel()
    lm.model.setValue(coin.SoLightModel.BASE_COLOR)
    root.addChild(lm)
    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.UNKNOWN_ORDERING)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    root.addChild(hints)
    for face, color in zip(shape.Faces, colors):
        r, g, b = color[0], color[1], color[2]
        try:
            pts, tris = face.tessellate(0.5)
            if not pts or not tris:
                continue
            sep = coin.SoSeparator()
            bc = coin.SoBaseColor()
            bc.rgb.setValue(r, g, b)
            sep.addChild(bc)
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(pts), [(v.x, v.y, v.z) for v in pts])
            sep.addChild(coords)
            ifs = coin.SoIndexedFaceSet()
            idx = []
            for tri in tris:
                idx.extend([int(tri[0]), int(tri[1]), int(tri[2]), -1])
            ifs.coordIndex.setValues(0, len(idx), idx)
            sep.addChild(ifs)
            root.addChild(sep)
        except Exception:
            pass
    return root


class _UndercutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Undercut Analysis")
        self.resize(360, 200)
        layout = QtWidgets.QFormLayout(self)
        self.dirCombo = QtWidgets.QComboBox()
        self.dirCombo.addItems(list(_PULL_DIRS.keys()))
        layout.addRow("Pull Direction:", self.dirCombo)
        legend = QtWidgets.QLabel(
            "<b>Color Legend:</b><br>"
            "<span style='color:#cc0000'>&#9632;</span> Undercut — trapped face<br>"
            "<span style='color:#00aa00'>&#9632;</span> Clear — releases cleanly<br><br>"
            "<i>Run Undercut Analysis again to clear the overlay.</i>"
        )
        legend.setTextFormat(QtCore.Qt.RichText)
        layout.addRow(legend)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def getValues(self):
        return {"direction": _PULL_DIRS[self.dirCombo.currentText()]}


def _face_normal(face):
    try:
        pts, tris = face.tessellate(0.5)
        for tri in tris:
            if len(tri) < 3:
                continue
            p1, p2, p3 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
            n = (p2 - p1).cross(p3 - p1)
            if n.Length > 1e-10:
                return n.normalize()
    except Exception:
        pass
    try:
        umin, umax, vmin, vmax = face.ParameterRange
        us, vs = umax - umin, vmax - vmin
        for uf in (0.5, 0.25, 0.75):
            for vf in (0.5, 0.25, 0.75):
                try:
                    n = face.normalAt(umin + uf * us, vmin + vf * vs)
                    if n.Length > 1e-10:
                        return n.normalize()
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _compute_undercut_colors(shape, pull_dir):
    pull = pull_dir.normalize()
    colors = []
    for face in shape.Faces:
        n = _face_normal(face)
        if n is not None:
            colors.append((0.9, 0.05, 0.05, 0.0) if n.dot(pull) < -0.01
                          else (0.0, 0.85, 0.2, 0.0))
        else:
            colors.append((0.5, 0.5, 0.5, 0.0))
    return colors


class CommandUndercutAnalysis:
    def GetResources(self):
        return {
            "Pixmap":   os.path.join(_iconsDir, "MoldUndercutAnalysis.svg"),
            "MenuText": QT_TRANSLATE_NOOP("BNCMold_UndercutAnalysis", "Undercut Analysis"),
            "ToolTip":  QT_TRANSLATE_NOOP("BNCMold_UndercutAnalysis",
                        "Identify undercut faces. Run again to clear."),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc_name = FreeCAD.ActiveDocument.Name
        if doc_name in _overlays:
            _clear_overlay(doc_name)
            return

        sel = Gui.Selection.getSelectionEx()
        if not sel:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Undercut Analysis", "Select a solid body first.")
            return

        src_obj = sel[0].Object
        shape_src = src_obj.Tip if (hasattr(src_obj, "Tip") and src_obj.Tip) else src_obj

        if not hasattr(shape_src, "Shape") or shape_src.Shape.isNull():
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Undercut Analysis",
                "Selected object has no solid shape.")
            return

        shape = shape_src.Shape

        dlg = _UndercutDialog(Gui.getMainWindow())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        vals = dlg.getValues()
        colors = _compute_undercut_colors(shape, vals["direction"])

        try:
            from pivy import coin
        except ImportError:
            QtWidgets.QMessageBox.critical(
                Gui.getMainWindow(), "Undercut Analysis",
                "pivy (Coin3D) not available in this FreeCAD build.")
            return

        try:
            src_obj.ViewObject.Visibility = False
            node = _build_overlay(shape, colors)
            Gui.ActiveDocument.ActiveView.getSceneGraph().addChild(node)
            _overlays[doc_name] = (node, src_obj)
            Gui.updateGui()
        except Exception as e:
            try:
                src_obj.ViewObject.Visibility = True
            except Exception:
                pass
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "Undercut Analysis",
                "Failed:\n" + str(e))


Gui.addCommand("BNCMold_UndercutAnalysis", CommandUndercutAnalysis())
