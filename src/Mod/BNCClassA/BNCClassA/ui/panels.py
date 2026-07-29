# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared task-panel infrastructure for BNCClassA commands."""
import FreeCAD
import FreeCADGui as Gui

from .qtcompat import QtWidgets, QtCore, HORIZONTAL, BTN_CLOSE, BTN_OK, BTN_CANCEL
from . import overlays


# --------------------------------------------------------------------------
# Selection helpers
# --------------------------------------------------------------------------

def selected_faces():
    """[(obj, face, label)] from the current selection.

    Face sub-elements come through individually; a whole selected object
    contributes all of its faces.
    """
    out = []
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        picked_face = False
        for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
            if getattr(sub_obj, "ShapeType", "") == "Face":
                out.append((obj, sub_obj, "%s.%s" % (obj.Label, sub)))
                picked_face = True
        if not picked_face and hasattr(obj, "Shape"):
            for i, f in enumerate(obj.Shape.Faces):
                out.append((obj, f, "%s.Face%d" % (obj.Label, i + 1)))
    return out


def selected_edges():
    """[(obj, edge, label)] edge sub-elements from the current selection.

    A whole selected object contributes all of its edges."""
    out = []
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        picked = False
        for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
            if getattr(sub_obj, "ShapeType", "") == "Edge":
                out.append((obj, sub_obj, "%s.%s" % (obj.Label, sub)))
                picked = True
        if not picked and hasattr(obj, "Shape") and not obj.Shape.Faces:
            for i, e in enumerate(obj.Shape.Edges):
                out.append((obj, e, "%s.Edge%d" % (obj.Label, i + 1)))
    return out


def selected_shapes():
    """[(obj, shape)] whole shapes from the current selection."""
    out = []
    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Shape") and not obj.Shape.isNull():
            out.append((obj, obj.Shape))
    return out


def selection_subelements():
    """Flat [(obj, subname, subshape)] of all picked sub-elements."""
    out = []
    for sel in Gui.Selection.getSelectionEx():
        for sub, sub_obj in zip(sel.SubElementNames, sel.SubObjects):
            out.append((sel.Object, sub, sub_obj))
    return out


# --------------------------------------------------------------------------
# Background worker
# --------------------------------------------------------------------------

class FuncWorker(QtCore.QThread):
    """Run a callable off the GUI thread; Coin3D nodes must still be built on
    the main thread from the emitted result (BNCMoldTools pattern)."""
    finished_ok = QtCore.Signal(object)
    error_occurred = QtCore.Signal(str)

    def __init__(self, func, parent=None):
        super(FuncWorker, self).__init__(parent)
        self._func = func

    def run(self):
        try:
            self.finished_ok.emit(self._func())
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# --------------------------------------------------------------------------
# Small widgets
# --------------------------------------------------------------------------

class QualitySlider(QtWidgets.QWidget):
    changed = QtCore.Signal(int)

    def __init__(self, value=7, parent=None):
        super(QualitySlider, self).__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.slider = QtWidgets.QSlider(HORIZONTAL)
        self.slider.setRange(1, 10)
        self.slider.setValue(value)
        self.label = QtWidgets.QLabel(str(value))
        self.label.setFixedWidth(18)
        lay.addWidget(self.slider)
        lay.addWidget(self.label)
        self.slider.valueChanged.connect(self._on_change)

    def _on_change(self, v):
        self.label.setText(str(v))
        self.changed.emit(v)

    def value(self):
        return self.slider.value()


class LogScaleSlider(QtWidgets.QWidget):
    """Slider mapping to a logarithmic scale factor (for comb scale etc.)."""
    changed = QtCore.Signal(float)

    def __init__(self, minimum=0.01, maximum=100.0, value=1.0, parent=None):
        super(LogScaleSlider, self).__init__(parent)
        import math
        self._lo = math.log10(minimum)
        self._hi = math.log10(maximum)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.slider = QtWidgets.QSlider(HORIZONTAL)
        self.slider.setRange(0, 1000)
        self.set_value(value)
        self.label = QtWidgets.QLabel("%.3g" % value)
        self.label.setFixedWidth(46)
        lay.addWidget(self.slider)
        lay.addWidget(self.label)
        self.slider.valueChanged.connect(self._on_change)

    def _on_change(self, _raw):
        v = self.value()
        self.label.setText("%.3g" % v)
        self.changed.emit(v)

    def value(self):
        import math
        f = self.slider.value() / 1000.0
        return 10.0 ** (self._lo + f * (self._hi - self._lo))

    def set_value(self, v):
        import math
        f = (math.log10(max(v, 1e-9)) - self._lo) / (self._hi - self._lo)
        self.slider.setValue(int(max(0.0, min(1.0, f)) * 1000))


# --------------------------------------------------------------------------
# Analysis panel base
# --------------------------------------------------------------------------

class AnalysisPanel(object):
    """Base for overlay-driven analysis task panels.

    Subclasses set TOOL_KEY and TITLE, build extra widgets in build_ui(), and
    implement rebuild() which must end with self.show_overlay(node, ...).
    Parameter widgets can call self.schedule_rebuild() for debounced refresh.
    """
    TOOL_KEY = "analysis"
    TITLE = "Analysis"

    def __init__(self):
        self.doc_name = FreeCAD.ActiveDocument.Name
        self.worker = None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.TITLE)
        self.layout = QtWidgets.QVBoxLayout(self.form)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)

        self._debounce = QtCore.QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.rebuild)

        self.build_ui()
        self.layout.addWidget(self.status)
        self.layout.addStretch(1)

    # -- subclass API ------------------------------------------------------
    def build_ui(self):
        raise NotImplementedError

    def rebuild(self):
        raise NotImplementedError

    def schedule_rebuild(self, *_args):
        self._debounce.start()

    def show_overlay(self, node, hide_objects=None):
        overlays.show(self.doc_name, self.TOOL_KEY, node, hide_objects)

    def set_status(self, text):
        self.status.setText(text)

    def run_async(self, func, on_done):
        """Run func() on a worker thread, call on_done(result) on the GUI thread."""
        if self.worker is not None and self.worker.isRunning():
            self.set_status("Busy — previous computation still running…")
            return
        self.worker = FuncWorker(func)
        self.worker.finished_ok.connect(on_done)
        self.worker.error_occurred.connect(lambda msg: self.set_status("Error: " + msg))
        self.worker.start()

    # -- FreeCAD task dialog protocol ---------------------------------------
    def getStandardButtons(self):
        return int(BTN_CLOSE)

    def reject(self):
        self.cleanup()
        Gui.Control.closeDialog()
        return True

    def accept(self):
        return self.reject()

    def cleanup(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(2000)
        overlays.clear(self.doc_name, self.TOOL_KEY)


class MeshCachePanel(AnalysisPanel):
    """Analysis panel working on a cached tessellation of the selected faces.

    Tessellation (and optional scalar augmentation) runs on a worker thread;
    node construction happens on the GUI thread. Texture/color-only parameter
    changes reuse the cached mesh and are effectively instant.

    Subclasses implement build_params_ui(), make_node(mesh) and optionally
    augment_mesh(mesh) (worker thread — no Qt/Coin calls).
    """

    def build_ui(self):
        src_group = QtWidgets.QGroupBox("Sources")
        src_lay = QtWidgets.QVBoxLayout(src_group)
        self.src_label = QtWidgets.QLabel("(nothing captured)")
        self.src_label.setWordWrap(True)
        btn = QtWidgets.QPushButton("Use current selection")
        btn.clicked.connect(self.capture_selection)
        src_lay.addWidget(self.src_label)
        src_lay.addWidget(btn)
        self.layout.addWidget(src_group)

        q_group = QtWidgets.QGroupBox("Display quality")
        q_lay = QtWidgets.QVBoxLayout(q_group)
        self.quality = QualitySlider(7)
        self.quality.changed.connect(lambda _v: self.invalidate_mesh())
        q_lay.addWidget(self.quality)
        self.layout.addWidget(q_group)

        self.build_params_ui()

        self._faces = []
        self._objs = []
        self._mesh = None
        self.capture_selection()

    # -- subclass API ------------------------------------------------------
    def build_params_ui(self):
        pass

    def augment_mesh(self, mesh):
        """Worker-thread hook: attach derived per-vertex data to the mesh."""
        return mesh

    def make_node(self, mesh):
        raise NotImplementedError

    # -- mechanics -----------------------------------------------------------
    def capture_selection(self):
        picked = selected_faces()
        if not picked:
            self.set_status("Select faces or objects, then press "
                            "'Use current selection'.")
            return
        self._faces = [f for (_o, f, _l) in picked]
        objs = []
        for (o, _f, _l) in picked:
            if o not in objs:
                objs.append(o)
        self._objs = objs
        labels = [l for (_o, _f, l) in picked]
        shown = ", ".join(labels[:6]) + (" …" if len(labels) > 6 else "")
        self.src_label.setText("%d face(s): %s" % (len(self._faces), shown))
        self.invalidate_mesh()

    def invalidate_mesh(self, *_args):
        self._mesh = None
        self.schedule_rebuild()

    def rebuild(self):
        if not self._faces:
            return
        if self._mesh is not None:
            self._refresh_node()
            return
        faces = list(self._faces)
        quality = self.quality.value()
        augment = self.augment_mesh
        self.set_status("Tessellating…")

        def work():
            mesh = overlays.tessellate(faces, quality)
            return augment(mesh)

        self.run_async(work, self._on_mesh)

    def _on_mesh(self, mesh):
        self._mesh = mesh
        if mesh.get("capped"):
            self.set_status("Vertex cap reached — quality reduced for display.")
        else:
            self.set_status("%d vertices." % len(mesh["verts"]))
        self._refresh_node()

    def _refresh_node(self):
        if self._mesh is None or not self._mesh["verts"]:
            return
        node = self.make_node(self._mesh)
        self.show_overlay(node, hide_objects=self._objs)


class DirectionWidget(QtWidgets.QWidget):
    """Axis combo + XYZ spin boxes for a direction vector."""
    _AXES = [("+X", (1, 0, 0)), ("-X", (-1, 0, 0)),
             ("+Y", (0, 1, 0)), ("-Y", (0, -1, 0)),
             ("+Z", (0, 0, 1)), ("-Z", (0, 0, -1)),
             ("View", None), ("Custom", None)]

    def __init__(self, default="+Z", parent=None):
        super(DirectionWidget, self).__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems([a for a, _v in self._AXES])
        self.combo.setCurrentIndex([a for a, _v in self._AXES].index(default))
        lay.addWidget(self.combo)
        self.spins = []
        for c in "XYZ":
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(-1000, 1000)
            sp.setDecimals(3)
            sp.setPrefix(c.lower() + " ")
            sp.setFixedWidth(72)
            sp.setVisible(False)
            self.spins.append(sp)
            lay.addWidget(sp)
        self.spins[2].setValue(1.0)
        self.combo.currentIndexChanged.connect(self._on_combo)

    def _on_combo(self, idx):
        custom = self._AXES[idx][0] == "Custom"
        for sp in self.spins:
            sp.setVisible(custom)

    def value(self):
        name, vec = self._AXES[self.combo.currentIndex()]
        if vec is not None:
            return FreeCAD.Vector(*vec)
        if name == "View":
            try:
                v = Gui.ActiveDocument.ActiveView.getViewDirection()
                return FreeCAD.Vector(v).multiply(-1.0)   # toward the viewer
            except Exception:
                return FreeCAD.Vector(0, 0, 1)
        v = FreeCAD.Vector(*[sp.value() for sp in self.spins])
        return v if v.Length > 1e-9 else FreeCAD.Vector(0, 0, 1)


class CreationPanel(object):
    """Base for OK/Cancel task panels that create document objects.

    Subclasses implement build_ui() and create() (called inside a document
    transaction; raise or return False to abort)."""
    TITLE = "Create"
    TRANSACTION = "Class-A create"

    def __init__(self):
        self.doc = FreeCAD.ActiveDocument
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.TITLE)
        self.layout = QtWidgets.QVBoxLayout(self.form)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.build_ui()
        self.layout.addWidget(self.status)
        self.layout.addStretch(1)

    def build_ui(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def set_status(self, text):
        self.status.setText(text)

    def getStandardButtons(self):
        return int(BTN_OK) | int(BTN_CANCEL)

    def accept(self):
        self.doc.openTransaction(self.TRANSACTION)
        try:
            ok = self.create()
        except Exception as exc:
            self.doc.abortTransaction()
            import traceback
            traceback.print_exc()
            self.set_status("Error: %s" % exc)
            return False
        if ok is False:
            self.doc.abortTransaction()
            return False
        self.doc.commitTransaction()
        self.doc.recompute()
        Gui.Control.closeDialog()
        return True

    def reject(self):
        Gui.Control.closeDialog()
        return True


def show_panel(panel):
    """Open a task panel, closing any already-open dialog first."""
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    Gui.Control.showDialog(panel)
