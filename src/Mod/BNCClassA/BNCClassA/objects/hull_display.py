# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared CV-hull display for CVCurve/CVSurface view providers.

Builds a Coin3D subgraph (dashed grey hull lines + diamond CV markers) that
the view providers attach under their RootNode and refresh on pole changes.
All display state lives in an SoSwitch so ShowCVs/ShowHull toggle cleanly.
"""

_CV_COLOR = (0.35, 0.62, 0.95)      # BNC accent blue tint
_HULL_COLOR = (0.55, 0.55, 0.58)
_HIGHLIGHT_COLOR = (1.0, 0.72, 0.1)


class HullDisplay(object):
    """Owns the hull/CV subgraph. polylines() supplies the hull rows/cols."""

    def __init__(self):
        from pivy import coin
        self.switch = coin.SoSwitch()
        self.switch.whichChild.setValue(-1)

        root = coin.SoSeparator()
        lm = coin.SoLightModel()
        lm.model.setValue(coin.SoLightModel.BASE_COLOR)
        root.addChild(lm)

        # hull lines (dashed)
        self.hull_switch = coin.SoSwitch()
        hull_sep = coin.SoSeparator()
        hc = coin.SoBaseColor()
        hc.rgb.setValue(*_HULL_COLOR)
        hull_sep.addChild(hc)
        hs = coin.SoDrawStyle()
        hs.lineWidth.setValue(1.0)
        hs.linePattern.setValue(0xF0F0)
        hull_sep.addChild(hs)
        self.hull_coords = coin.SoCoordinate3()
        hull_sep.addChild(self.hull_coords)
        self.hull_lines = coin.SoLineSet()
        hull_sep.addChild(self.hull_lines)
        self.hull_switch.addChild(hull_sep)
        self.hull_switch.whichChild.setValue(0)
        root.addChild(self.hull_switch)

        # CV markers
        self.cv_switch = coin.SoSwitch()
        cv_sep = coin.SoSeparator()
        cc = coin.SoBaseColor()
        cc.rgb.setValue(*_CV_COLOR)
        cv_sep.addChild(cc)
        self.cv_coords = coin.SoCoordinate3()
        cv_sep.addChild(self.cv_coords)
        self.markers = coin.SoMarkerSet()
        self.markers.markerIndex.setValue(coin.SoMarkerSet.DIAMOND_FILLED_9_9)
        cv_sep.addChild(self.markers)
        self.cv_switch.addChild(cv_sep)
        self.cv_switch.whichChild.setValue(0)
        root.addChild(self.cv_switch)

        # highlight (selected CV / row) — driven by the edit panels
        hl_sep = coin.SoSeparator()
        hlc = coin.SoBaseColor()
        hlc.rgb.setValue(*_HIGHLIGHT_COLOR)
        hl_sep.addChild(hlc)
        self.hl_coords = coin.SoCoordinate3()
        hl_sep.addChild(self.hl_coords)
        hl_markers = coin.SoMarkerSet()
        hl_markers.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        hl_sep.addChild(hl_markers)
        root.addChild(hl_sep)

        self.switch.addChild(root)

    # -- state ---------------------------------------------------------------
    def set_visible(self, on):
        self.switch.whichChild.setValue(0 if on else -1)

    def show_hull(self, on):
        self.hull_switch.whichChild.setValue(0 if on else -1)

    def show_cvs(self, on):
        self.cv_switch.whichChild.setValue(0 if on else -1)

    def update(self, points, polylines):
        """points: flat [(x,y,z)] for markers; polylines: list of index lists
        into points describing the hull rows/columns."""
        self.cv_coords.point.setValues(0, len(points), points)
        self.cv_coords.point.setNum(len(points))
        hull_pts, counts = [], []
        for line in polylines:
            if len(line) < 2:
                continue
            hull_pts.extend(points[i] for i in line)
            counts.append(len(line))
        self.hull_coords.point.setValues(0, len(hull_pts), hull_pts)
        self.hull_coords.point.setNum(len(hull_pts))
        self.hull_lines.numVertices.setValues(0, len(counts), counts)
        self.hull_lines.numVertices.setNum(len(counts))

    def highlight(self, points):
        """Highlight the given (x,y,z) points (selected CV or row)."""
        self.hl_coords.point.setValues(0, len(points), points)
        self.hl_coords.point.setNum(len(points))


def curve_hull_data(poles):
    """(points, polylines) for a curve pole list."""
    pts = [(p.x, p.y, p.z) if hasattr(p, "x") else tuple(p) for p in poles]
    return pts, [list(range(len(pts)))]


def surface_hull_data(poles_2d):
    """(points, polylines) for an (nu, nv, 3)-shaped nested pole structure."""
    pts, lines = [], []
    nu = len(poles_2d)
    nv = len(poles_2d[0]) if nu else 0
    for row in poles_2d:
        for p in row:
            pts.append((p.x, p.y, p.z) if hasattr(p, "x") else tuple(p))
    for i in range(nu):
        lines.append([i * nv + j for j in range(nv)])
    for j in range(nv):
        lines.append([i * nv + j for i in range(nu)])
    return pts, lines
