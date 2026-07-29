# SPDX-License-Identifier: LGPL-2.1-or-later
"""3D-view interaction controllers for CV editing.

DragController: screen-projection pick (nearest CV within a pixel radius) and
camera-plane drag — the Alias default editing feel. X/Y/Z keys constrain the
drag to a world axis, Shift drags the whole CV row.

ClickPlaceController: click-place points on a work plane (CV curve creation).

Both use FreeCAD's view.addEventCallback API (proven in this fork by
BNCMoldTools' hover handling) — no SoDragger complexity.
"""
import FreeCAD
import FreeCADGui as Gui

PICK_RADIUS_PX = 14


def _active_view():
    return Gui.ActiveDocument.ActiveView


class _CallbackSet(object):
    """Track event callbacks so they always get removed."""

    def __init__(self, view):
        self.view = view
        self._cbs = []

    def add(self, event_type, func):
        cb = self.view.addEventCallback(event_type, func)
        self._cbs.append((event_type, cb))

    def remove_all(self):
        for event_type, cb in self._cbs:
            try:
                self.view.removeEventCallback(event_type, cb)
            except Exception:
                pass
        self._cbs = []


class DragController(object):
    """Pick-and-drag over a set of 3D points.

    Callbacks (all optional except get_points):
      get_points()          -> list[FreeCAD.Vector], the current pole positions
      on_pick(idx)          -> called when a point is grabbed or selected
      on_drag(indices, deltas) -> live update; indices/deltas lists (row drag)
      on_release()          -> drag finished (commit)
      row_of(idx)           -> list of indices to move together on Shift-drag
    """

    def __init__(self, get_points, on_pick=None, on_drag=None,
                 on_release=None, row_of=None):
        self.get_points = get_points
        self.on_pick = on_pick or (lambda idx: None)
        self.on_drag = on_drag or (lambda idx, pos: None)
        self.on_release = on_release or (lambda: None)
        self.row_of = row_of or (lambda idx: [idx])

        self.view = _active_view()
        self._cbs = _CallbackSet(self.view)
        self.active_idx = None          # currently selected CV
        self._dragging = False
        self._drag_indices = []
        self._drag_starts = []
        self._grab_start = None
        self._axis = None               # None or FreeCAD.Vector axis constraint
        self.nudge_step = 0.5

    # -- lifecycle -----------------------------------------------------------
    def install(self):
        self._cbs.add("SoMouseButtonEvent", self._on_button)
        self._cbs.add("SoLocation2Event", self._on_move)
        self._cbs.add("SoKeyboardEvent", self._on_key)

    def uninstall(self):
        self._cbs.remove_all()

    # -- helpers -------------------------------------------------------------
    def _pick_index(self, pos):
        px, py = pos
        best, best_d2 = None, PICK_RADIUS_PX ** 2
        for i, p in enumerate(self.get_points()):
            try:
                sx, sy = self.view.getPointOnScreen(p)
            except Exception:
                continue
            d2 = (sx - px) ** 2 + (sy - py) ** 2
            if d2 < best_d2:
                best, best_d2 = i, d2
        return best

    def _plane_point(self, pos, anchor):
        """3D position of the cursor on the camera-parallel plane through
        `anchor` (or the axis-constrained equivalent)."""
        px, py = pos
        try:
            ray_pt = self.view.getPoint(px, py)
            direction = FreeCAD.Vector(self.view.getViewDirection())
        except Exception:
            return anchor
        if direction.Length < 1e-12:
            return anchor
        direction.normalize()
        new = ray_pt + direction * ((anchor - ray_pt).dot(direction))
        if self._axis is not None:
            new = anchor + self._axis * ((new - anchor).dot(self._axis))
        return new

    # -- event handlers --------------------------------------------------------
    def _on_button(self, info):
        if info.get("Button") != "BUTTON1":
            return
        pos = info.get("Position")
        if pos is None:
            return
        if info.get("State") == "DOWN":
            idx = self._pick_index(pos)
            if idx is None:
                return
            self.active_idx = idx
            shift = bool(info.get("ShiftDown"))
            self._drag_indices = self.row_of(idx) if shift else [idx]
            pts = self.get_points()
            self._drag_starts = [FreeCAD.Vector(pts[i]) for i in self._drag_indices]
            self._grab_start = FreeCAD.Vector(pts[idx])
            self._dragging = True
            self.on_pick(idx)
        elif info.get("State") == "UP" and self._dragging:
            self._dragging = False
            self.on_release()

    def _on_move(self, info):
        if not self._dragging:
            return
        pos = info.get("Position")
        if pos is None:
            return
        new = self._plane_point(pos, self._grab_start)
        delta = new - self._grab_start
        positions = [start + delta for start in self._drag_starts]
        self.on_drag(list(self._drag_indices), positions)

    def _on_key(self, info):
        if info.get("State") != "DOWN":
            return
        key = (info.get("Key") or "").lower()
        axes = {"x": FreeCAD.Vector(1, 0, 0),
                "y": FreeCAD.Vector(0, 1, 0),
                "z": FreeCAD.Vector(0, 0, 1)}
        if key in axes:
            new_axis = axes[key]
            if self._axis is not None and (self._axis - new_axis).Length < 1e-9:
                self._axis = None       # toggle off
            else:
                self._axis = new_axis
        elif key in ("up", "down", "left", "right", "pageup", "pagedown") \
                and self.active_idx is not None and not self._dragging:
            step = {"up": FreeCAD.Vector(0, 0, 1),
                    "down": FreeCAD.Vector(0, 0, -1),
                    "left": FreeCAD.Vector(-1, 0, 0),
                    "right": FreeCAD.Vector(1, 0, 0),
                    "pageup": FreeCAD.Vector(0, 1, 0),
                    "pagedown": FreeCAD.Vector(0, -1, 0)}[key]
            pts = self.get_points()
            idx = self.active_idx
            self.on_drag([idx], [FreeCAD.Vector(pts[idx]) + step * self.nudge_step])
            self.on_release()

    @property
    def axis_label(self):
        if self._axis is None:
            return "screen"
        return {(1, 0, 0): "X", (0, 1, 0): "Y", (0, 0, 1): "Z"}.get(
            (self._axis.x, self._axis.y, self._axis.z), "?")


class ClickPlaceController(object):
    """Click points onto a work plane; used by the CV curve creation tool.

    plane_fn() -> (origin, normal); on_point(Vector); on_preview(Vector or
    None) for the rubber-band; on_finish() on double-click/Enter.
    """

    def __init__(self, plane_fn, on_point, on_preview=None, on_finish=None):
        self.plane_fn = plane_fn
        self.on_point = on_point
        self.on_preview = on_preview or (lambda p: None)
        self.on_finish = on_finish or (lambda: None)
        self.view = _active_view()
        self._cbs = _CallbackSet(self.view)

    def install(self):
        self._cbs.add("SoMouseButtonEvent", self._on_button)
        self._cbs.add("SoLocation2Event", self._on_move)
        self._cbs.add("SoKeyboardEvent", self._on_key)

    def uninstall(self):
        self._cbs.remove_all()

    def _cursor_point(self, pos):
        px, py = pos
        origin, normal = self.plane_fn()
        try:
            ray_pt = self.view.getPoint(px, py)
            direction = FreeCAD.Vector(self.view.getViewDirection())
        except Exception:
            return None
        denom = direction.dot(normal)
        if abs(denom) < 1e-9:
            return None
        t = (origin - ray_pt).dot(normal) / denom
        return ray_pt + direction * t

    def _on_button(self, info):
        if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
            return
        pos = info.get("Position")
        if pos is None:
            return
        p = self._cursor_point(pos)
        if p is not None:
            self.on_point(p)

    def _on_move(self, info):
        pos = info.get("Position")
        if pos is None:
            return
        self.on_preview(self._cursor_point(pos))

    def _on_key(self, info):
        if info.get("State") != "DOWN":
            return
        key = (info.get("Key") or "").lower()
        if key in ("return", "enter"):
            self.on_finish()
