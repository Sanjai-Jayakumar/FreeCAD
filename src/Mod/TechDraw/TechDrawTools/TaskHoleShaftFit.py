# ***************************************************************************
# *   Copyright (c) 2023 edi <edi271@a1.net>                                *
# *   ANVIL CAD: full ISO 286-2 shaft & hole tolerance grades.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL).   *
# ***************************************************************************
"""Provides the TechDraw HoleShaftFit Task Dialog (ISO 286-2)."""

__title__ = "TechDrawTools.TaskHoleShaftFit"
__author__ = "edi / ANVIL CAD"

import os
from functools import partial

import FreeCAD as App
import FreeCADGui as Gui

translate = App.Qt.translate

# full lists exactly as the ISO 286-2 tables (shaft a12..r6, hole E6..R7)
SHAFT_GRADES = ["a12", "d6", "e6", "e13", "f5", "f6", "f7", "g5", "g6", "g7",
                "h4", "h5", "h6", "h7", "h8", "h9", "h10", "h11", "h12",
                "j5", "j6", "j7", "js5", "js6", "js7", "k5", "k6", "k7",
                "m5", "m6", "m7", "n5", "n6", "n7", "p5", "p6", "r6"]
HOLE_GRADES = ["E6", "E7", "E11", "E12", "E13", "F6", "F7", "F8", "G6", "G7",
               "G8", "H6", "H7", "H8", "H9", "H10", "H11", "J6", "J7", "J8",
               "JS6", "JS7", "JS8", "K6", "K7", "K8", "M6", "M7", "M8",
               "N6", "N7", "N8", "P6", "P7", "P8", "R6", "R7"]


def _split(grade):
    """'js5' -> ('js', 5) ; 'H7' -> ('H', 7)."""
    i = 0
    while i < len(grade) and not grade[i].isdigit():
        i += 1
    return grade[:i], int(grade[i:])


class TaskHoleShaftFit:
    def __init__(self, sel):
        self.sel = sel
        self.applyHole = False   # False = the selected dimension is a SHAFT

        self._uiPath = os.path.join(
            App.getHomePath(),
            "Mod/TechDraw/TechDrawTools/Gui/TaskHoleShaftFit.ui")
        self.form = Gui.PySideUic.loadUi(self._uiPath)
        self.form.setWindowTitle(
            translate("TechDraw_HoleShaftFit", "Hole/Shaft Fit ISO 286"))

        self.form.rbHoleBase.clicked.connect(partial(self.on_HoleShaftChanged, True))
        self.form.rbShaftBase.clicked.connect(partial(self.on_HoleShaftChanged, False))
        self.form.cbField.currentIndexChanged.connect(self.on_FieldChanged)
        try:
            self.form.rbShaftBase.setChecked(True)
        except Exception:
            pass
        self._populate()
        App.setActiveTransaction("Add hole or shaft fit")

    def _grades(self):
        return HOLE_GRADES if self.applyHole else SHAFT_GRADES

    def _populate(self):
        cb = self.form.cbField
        cb.blockSignals(True)
        for _ in range(cb.count()):
            cb.removeItem(0)
        for g in self._grades():
            cb.addItem(g)
        cb.blockSignals(False)
        self.on_FieldChanged()

    def on_HoleShaftChanged(self, applyHole):
        self.applyHole = applyHole
        self._populate()

    def on_FieldChanged(self):
        idx = self.form.cbField.currentIndex()
        grades = self._grades()
        if idx < 0 or idx >= len(grades):
            return
        grade = grades[idx]
        try:
            dim = self.sel[0].Object
            up, lo = ISO286().deviation(dim.getRawValue(), grade)
            self.form.lbFitType.setText(grade)
            self.form.lbBaseField.setText(
                "   {:+.3f} / {:+.3f} mm".format(up / 1000.0, lo / 1000.0))
        except Exception:
            self.form.lbFitType.setText(grade)
            self.form.lbBaseField.setText("")

    def accept(self):
        idx = self.form.cbField.currentIndex()
        grade = self._grades()[idx]
        dim = self.sel[0].Object
        up, lo = ISO286().deviation(dim.getRawValue(), grade)   # micrometres
        dim.FormatSpec = dim.FormatSpec + " " + grade
        dim.EqualTolerance = False
        dim.OverTolerance = up / 1000.0
        dim.UnderTolerance = lo / 1000.0
        dim.ArbitraryTolerances = True
        dim.FormatSpecOverTolerance = self._fmtTol(up / 1000.0)
        dim.FormatSpecUnderTolerance = self._fmtTol(lo / 1000.0)
        Gui.Control.closeDialog()
        App.closeActiveTransaction()

    @staticmethod
    def _fmtTol(value_mm):
        s = "{:.4f}".format(abs(value_mm))
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        if s == "":
            s = "0"
        if value_mm > 1e-9:
            return "(+" + s + ")"
        if value_mm < -1e-9:
            return "(-" + s + ")"
        return "( 0)"

    def reject(self):
        App.closeActiveTransaction(True)
        return True


class ISO286:
    """ISO 286-2 tolerance calculator: IT grades, shaft/hole fundamental
    deviations, and the hole Delta-rule for K/M/N (<=IT8) and P/R (<=IT7).
    All values are micrometres, on the 25 standard size ranges (0..500 mm)."""

    # size range upper bounds (mm); index 0 = 0..3, 1 = 3..6, ... 24 = 450..500
    _BOUNDS = [3, 6, 10, 14, 18, 24, 30, 40, 50, 65, 80, 100, 120, 140, 160,
               180, 200, 225, 250, 280, 315, 355, 400, 450, 500]

    _IT = {
        4:  [3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 10, 10, 12, 12, 12, 14, 14, 14, 16, 16, 18, 18, 20, 20],
        5:  [4, 5, 6, 8, 8, 9, 9, 11, 11, 13, 13, 15, 15, 18, 18, 18, 20, 20, 20, 23, 23, 25, 25, 27, 27],
        6:  [6, 8, 9, 11, 11, 13, 13, 16, 16, 19, 19, 22, 22, 25, 25, 25, 29, 29, 29, 32, 32, 36, 36, 40, 40],
        7:  [10, 12, 15, 18, 18, 21, 21, 25, 25, 30, 30, 35, 35, 40, 40, 40, 46, 46, 46, 52, 52, 57, 57, 63, 63],
        8:  [14, 18, 22, 27, 27, 33, 33, 39, 39, 46, 46, 54, 54, 63, 63, 63, 72, 72, 72, 81, 81, 89, 89, 97, 97],
        9:  [25, 30, 36, 43, 43, 52, 52, 62, 62, 74, 74, 87, 87, 100, 100, 100, 115, 115, 115, 130, 130, 140, 140, 155, 155],
        10: [40, 48, 58, 70, 70, 84, 84, 100, 100, 120, 120, 140, 140, 160, 160, 160, 185, 185, 185, 210, 210, 230, 230, 250, 250],
        11: [60, 75, 90, 110, 110, 130, 130, 160, 160, 190, 190, 220, 220, 250, 250, 250, 290, 290, 290, 320, 320, 360, 360, 400, 400],
        12: [100, 120, 150, 180, 180, 210, 210, 250, 250, 300, 300, 350, 350, 400, 400, 400, 460, 460, 460, 520, 520, 570, 570, 630, 630],
        13: [140, 180, 220, 270, 270, 330, 330, 390, 390, 460, 460, 540, 540, 630, 630, 630, 720, 720, 720, 810, 810, 890, 890, 970, 970],
    }
    # shaft fundamental deviation es (upper) for clearance letters a,c,d,e,f,g
    _ES = {
        "a": [-270, -270, -280, -290, -290, -300, -300, -310, -320, -340, -360, -380, -410, -460, -520, -580, -660, -740, -820, -920, -1050, -1200, -1350, -1500, -1650],
        "c": [-60, -70, -80, -95, -95, -110, -110, -120, -130, -140, -150, -170, -180, -200, -210, -230, -240, -260, -280, -300, -330, -360, -400, -440, -480],
        "d": [-20, -30, -40, -50, -50, -65, -65, -80, -80, -100, -100, -120, -120, -145, -145, -145, -170, -170, -170, -190, -190, -210, -210, -230, -230],
        "e": [-14, -20, -25, -32, -32, -40, -40, -50, -50, -60, -60, -72, -72, -85, -85, -85, -100, -100, -100, -110, -110, -125, -125, -135, -135],
        "f": [-6, -10, -13, -16, -16, -20, -20, -25, -25, -30, -30, -36, -36, -43, -43, -43, -50, -50, -50, -56, -56, -62, -62, -68, -68],
        "g": [-2, -4, -5, -6, -6, -7, -7, -9, -9, -10, -10, -12, -12, -14, -14, -14, -15, -15, -15, -17, -17, -18, -18, -20, -20],
    }
    # shaft fundamental deviation ei (lower) for interference letters k,m,n,p,r
    _EI = {
        "k": [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 5, 5],
        "m": [2, 4, 6, 7, 7, 8, 8, 9, 9, 11, 11, 13, 13, 15, 15, 15, 17, 17, 17, 20, 20, 21, 21, 23, 23],
        "n": [4, 8, 10, 12, 12, 15, 15, 17, 17, 20, 20, 23, 23, 27, 27, 27, 31, 31, 31, 34, 34, 37, 37, 40, 40],
        "p": [6, 12, 15, 18, 18, 22, 22, 26, 26, 32, 32, 37, 37, 43, 43, 43, 50, 50, 50, 56, 56, 62, 62, 68, 68],
        "r": [10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114, 126, 132],
    }
    # shaft j (irregular): grade -> (es[25], ei[25])
    _J_SHAFT = {
        5: ([2, 3, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7],
            [-2, -2, -2, -3, -3, -4, -4, -5, -5, -7, -7, -9, -9, -11, -11, -11, -13, -13, -13, -16, -16, -18, -18, -18, -18]),
        6: ([4, 6, 7, 8, 8, 9, 9, 11, 11, 12, 12, 13, 13, 14, 14, 14, 16, 16, 16, 16, 16, 18, 18, 18, 18],
            [-2, -2, -2, -3, -3, -4, -4, -5, -5, -7, -7, -9, -9, -11, -11, -11, -13, -13, -13, -16, -16, -18, -18, -18, -18]),
        7: ([6, 8, 10, 12, 12, 13, 13, 15, 15, 18, 18, 20, 20, 22, 22, 22, 25, 25, 25, 26, 26, 29, 29, 29, 29],
            [-4, -4, -5, -6, -6, -8, -8, -10, -10, -12, -12, -15, -15, -18, -18, -18, -21, -21, -21, -26, -26, -28, -28, -28, -28]),
    }
    # hole J (irregular): grade -> (ES[25], EI[25])
    _J_HOLE = {
        6: ([5, 5, 5, 6, 6, 8, 8, 10, 10, 13, 13, 16, 16, 18, 18, 18, 22, 22, 22, 25, 25, 29, 29, 29, 29],
            [-3, -3, -4, -5, -5, -5, -5, -6, -6, -6, -6, -6, -6, -7, -7, -7, -7, -7, -7, -7, -7, -7, -7, -7, -7]),
        7: ([4, 6, 8, 10, 10, 12, 12, 14, 14, 18, 18, 22, 22, 26, 26, 26, 30, 30, 30, 36, 36, 39, 39, 39, 39],
            [-6, -6, -7, -8, -8, -9, -9, -11, -11, -12, -12, -13, -13, -14, -14, -14, -16, -16, -16, -16, -16, -18, -18, -18, -18]),
        8: ([6, 10, 12, 15, 15, 20, 20, 24, 24, 28, 28, 34, 34, 41, 41, 41, 47, 47, 47, 55, 55, 60, 60, 60, 60],
            [-8, -8, -10, -12, -12, -13, -13, -15, -15, -18, -18, -20, -20, -22, -22, -22, -25, -25, -25, -26, -26, -29, -29, -29, -29]),
    }

    def _ri(self, size):
        s = abs(size)
        for i, b in enumerate(self._BOUNDS):
            if s <= b:
                return i
        return len(self._BOUNDS) - 1

    def _it(self, grade, ri):
        return self._IT[grade][ri]

    def deviation(self, size, grade):
        """Return (upper, lower) deviation in micrometres for e.g. 'g6','H7','js6'."""
        letter, g = _split(grade)
        ri = self._ri(size)
        it = self._it(g, ri)
        isHole = letter[0].isupper()
        low = letter.lower()

        # symmetric js / JS
        if low == "js":
            half = it / 2.0
            return (half, -half)

        if not isHole:      # ---------- SHAFT ----------
            if low == "h":
                return (0, -it)
            if low == "j":
                es, ei = self._J_SHAFT[g]
                return (es[ri], ei[ri])
            if low in self._ES:            # a,c,d,e,f,g : es-based
                es = self._ES[low][ri]
                return (es, es - it)
            if low in self._EI:            # k,m,n,p,r : ei-based
                ei = self._EI[low][ri]
                return (ei + it, ei)
            raise ValueError("unknown shaft field " + grade)

        # ---------- HOLE ----------
        if low == "h":
            return (it, 0)                 # EI = 0, ES = +IT
        if low == "j":
            es, ei = self._J_HOLE[g]
            return (es[ri], ei[ri])
        if low in ("e", "f", "g"):         # EI = -es(shaft), ES = EI + IT
            ei = -self._ES[low][ri]
            return (ei + it, ei)
        # K,M,N (<=IT8) and P,R (<=IT7): Delta-rule from the shaft
        useDelta = (low in ("k", "m", "n") and g <= 8) or (low in ("p", "r") and g <= 7)
        es_s, ei_s = self.deviation(size, low + str(g))   # shaft same letter/grade
        if useDelta:
            delta = it - self._it(g - 1, ri)
            return (-ei_s + delta, -es_s + delta)
        return (-ei_s, -es_s)              # plain mirror
